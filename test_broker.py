import json
import tempfile
import unittest
from pathlib import Path

from elyon.broker import Broker, import_archive
from elyon.protocol import PROTOCOL, ProtocolError, event

CAPS = {'requests': {'supported': True, 'permitted': True, 'enabled': True, 'healthy': True},
        'nativeGecko': {'supported': False, 'permitted': False,
                        'enabled': False, 'healthy': False}}
TARGET = {'id': 'document', 'generation': '1'}


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'journal'
        self.broker = Broker(self.path)
        self.attach()

    def tearDown(self):
        self.broker.close()
        self.tmp.cleanup()

    def cmd(self, kind, **kwargs):
        return self.broker.dispatch({'protocol': PROTOCOL, 'type': kind, **kwargs})

    def attach(self):
        self.a = self.cmd('attach', scope={'kind': 'test'}, source='synthetic',
                          capabilities=CAPS)['attachment']
        self.cmd('target.upsert', attachment=self.a, target=TARGET, parent=None,
                 targetKind='document')

    def start(self, name='capture', activate=True):
        self.cmd('start', attachment=self.a, capture=name, revision='1',
                 plan={'mode': 'metadata'}, target=TARGET)
        if activate:
            self.cmd('activation', attachment=self.a, capture=name,
                     revision='1', target=TARGET)

    def ev(self, seq=1, kind='RequestAttempt', payload=None, capture='capture', **kwargs):
        return event(self.a, capture, 'producer', 'epoch', seq, kind,
                     payload or {'url': 'https://example.test/', 'method': 'GET'},
                     target=TARGET, **kwargs)

    def ingest(self, *events):
        return self.cmd('events', attachment=self.a, batch=list(events))

    def test_start_is_not_activation_and_navigation_invalidates_readiness(self):
        self.start(activate=False)
        with self.assertRaises(ProtocolError):
            self.ingest(self.ev())
        self.cmd('target.upsert', attachment=self.a,
                 target={'id': 'document', 'generation': '2'}, parent=None, targetKind='document')
        with self.assertRaises(ProtocolError):
            self.cmd('activation', attachment=self.a, capture='capture', revision='1', target=TARGET)
        self.assertFalse(self.cmd('snapshot')['ready'])

    def test_immutable_graph_does_not_invent_response_exposure_or_redirect(self):
        self.start()
        req = self.ev()
        response = self.ev(2, 'ResponseVersion', {'status': 302})
        self.ingest(req, response)
        req['evidence']['method'] = 'MUTATED'
        snapshot = self.cmd('snapshot')
        self.assertEqual(len(snapshot['graph']['nodes']), 2)
        self.assertEqual(snapshot['graph']['relationships'], [])
        self.assertEqual(snapshot['graph']['nodes'][0]['evidence']['method'], 'GET')
        self.assertIn('page-visible-response', snapshot['unavailable'])
        snapshot['graph']['nodes'].clear()
        self.assertEqual(len(self.cmd('snapshot')['graph']['nodes']), 2)

    def test_duplicate_missing_and_out_of_order_sequences(self):
        self.start()
        one, three = self.ev(), self.ev(3)
        self.assertEqual(self.ingest(one)['ack'], [one['id']])
        self.assertEqual(self.ingest(one)['duplicates'], [one['id']])
        self.ingest(three)
        self.assertEqual(self.cmd('snapshot')['gaps'][0]['missing'], ['2', '2'])
        with self.assertRaises(ProtocolError):
            self.ingest(self.ev(2))
        changed = self.ev()
        changed['id'] = 'conflicting-id'
        with self.assertRaises(ProtocolError):
            self.ingest(changed)

    def test_sequence_above_js_precision_and_new_epoch(self):
        self.start()
        self.ingest(self.ev(9007199254740993))
        self.assertEqual(self.cmd('snapshot')['gaps'][0]['missing'], ['1', '9007199254740992'])
        next_epoch = self.ev()
        next_epoch['epoch'] = 'next-epoch'
        next_epoch['id'] = 'unique-next-epoch'
        self.ingest(next_epoch)
        self.assertEqual(len(self.cmd('snapshot')['graph']['nodes']), 2)

    def test_batch_validation_is_atomic_and_credit_is_bounded(self):
        self.start()
        invalid = self.ev(2)
        invalid['revision'] = 'wrong'
        with self.assertRaises(ProtocolError):
            self.ingest(self.ev(), invalid)
        self.assertEqual(self.cmd('snapshot')['graph']['nodes'], [])
        with self.assertRaises(ProtocolError):
            self.ingest(*[self.ev(n) for n in range(1, 66)])
        self.assertEqual(self.ingest(self.ev())['credit'], 64)

    def test_relationship_dangling_support_rejected_then_valid_link_preserved(self):
        self.start()
        req, resp = self.ev(), self.ev(2, 'ResponseVersion', {'status': 200})
        rel = self.ev(3, 'Relationship', {'from': req['id'], 'to': resp['id'],
                                        'relation': 'response-for', 'support': [resp['id']]})
        with self.assertRaises(ProtocolError):
            self.ingest(rel)
        self.ingest(req, resp, rel)
        self.assertEqual(self.cmd('snapshot')['graph']['relationships'][0]['evidence']['to'],
                         resp['id'])

    def test_fixture_families_and_unknown_sw_origin_remain_distinct_100_runs(self):
        for run in range(100):
            self.start(str(run))
            families = ['LoadIntent', 'RequestAttempt', 'ResponseVersion', 'Redirect',
                        'CacheObservation', 'ServiceWorkerHandling', 'PolicyDecision',
                        'Exposure', 'Termination', 'Coverage', 'Gap']
            batch = [self.ev(run * 11 + i + 1, family,
                             {'fixture': family, 'origin': None}, capture=str(run))
                     for i, family in enumerate(families)]
            self.ingest(*batch)
            self.cmd('stop', attachment=self.a, capture=str(run))
            self.cmd('stopped', attachment=self.a, capture=str(run))
        nodes = self.cmd('snapshot')['graph']['nodes']
        self.assertEqual(len(nodes), 1100)
        self.assertTrue(all(n['source'] == 'synthetic' for n in nodes))
        sw = next(n for n in nodes if n['kind'] == 'ServiceWorkerHandling')
        self.assertIsNone(sw['evidence']['origin'])

    def test_detach_cleans_handles_and_invalidates_old_attachment_100_cycles(self):
        old = self.a
        for _ in range(100):
            self.cmd('detach', attachment=self.a)
            self.assertEqual(self.cmd('snapshot')['retainedHandles'], 0)
            self.attach()
        with self.assertRaises(ProtocolError):
            self.cmd('health', attachment=old, healthy=False, reason='late')

    def test_handle_read_and_detach_release(self):
        self.start()
        e = self.ev()
        self.ingest(e)
        handle = self.cmd('handle', attachment=self.a, id=e['id'])['handle']
        self.assertEqual(self.cmd('read', attachment=self.a, handle=handle,
                                  fields=['body'])['fields']['body']['certainty'], 'unavailable')
        self.cmd('release', attachment=self.a, handles=[handle])
        with self.assertRaises(KeyError):
            self.cmd('read', attachment=self.a, handle=handle, fields=['url'])

    def test_transport_failure_termination_and_restart_preserve_evidence(self):
        self.start()
        self.ingest(self.ev())
        self.cmd('gap', attachment=self.a, reason='transport-interruption', missing=None)
        self.cmd('target.end', attachment=self.a, target=TARGET, reason='process-terminated')
        self.broker.close()
        self.broker = Broker(self.path)
        snap = self.cmd('snapshot')
        self.assertEqual(len(snap['graph']['nodes']), 1)
        self.assertTrue(snap['incomplete'])
        self.assertFalse(snap['ready'])

    def test_export_import_fidelity_and_redaction(self):
        self.start()
        e = self.ev(payload={'url': '<SECRET>',
                             'headers': {'Authorization': 'SECRET'}, 'body': 'SECRET'})
        self.ingest(e)
        raw = self.cmd('export', redacted=False)
        clone = import_archive(Path(self.tmp.name) / 'imported', raw)
        try:
            self.assertEqual(clone.dispatch({'protocol': PROTOCOL, 'type': 'export',
                                             'redacted': False}), raw)
        finally:
            clone.close()
        redacted = self.cmd('export', redacted=True)
        self.assertNotIn('SECRET', json.dumps(redacted))
        self.assertNotIn('name:pass', json.dumps(redacted))
        restored = import_archive(Path(self.tmp.name) / 'redacted', redacted)
        restored.close()
        self.assertEqual(raw['manifest']['protocol'], PROTOCOL)
        self.assertTrue(redacted['manifest']['redacted'])

    def test_journal_exhaustion_records_gap_without_evicting(self):
        self.broker.close()
        self.broker = Broker(Path(self.tmp.name) / 'small', limit=8192, reserve=2048)
        self.attach()
        self.start()
        count = 0
        for n in range(1, 30):
            result = self.ingest(self.ev(n, payload={'body': 'x' * 1000}))
            if result['credit'] == 0:
                break
            count += 1
        snap = self.cmd('snapshot')
        self.assertGreater(count, 0)
        self.assertEqual(len(snap['graph']['nodes']), count)
        self.assertEqual(snap['gaps'][-1]['reason'], 'journal-full')
        self.assertLessEqual(self.broker.journal.size, 8192)


if __name__ == '__main__':
    unittest.main()
