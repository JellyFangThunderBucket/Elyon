import copy
import tempfile
import unittest
from pathlib import Path

from elyon.handles import Handles
from elyon.journal import Journal, JournalFull
from elyon.protocol import ProtocolError, event, validate_event


class ProtocolTests(unittest.TestCase):
    def sample(self):
        return event('a', 'c', 'p', 'e', 1, 'RequestAttempt',
                     {'method': 'GET', 'url': 'http://example.test/'},
                     target={'id': 'document', 'generation': '1'})

    def test_uint64_is_decimal_string_without_precision_loss(self):
        value = self.sample()
        for seq in ['9007199254740993', '18446744073709551615']:
            value['sequence'] = seq
            validate_event(value)
        for seq in [1, '01', '-1', '18446744073709551616', '1.0']:
            value['sequence'] = seq
            with self.subTest(seq=seq), self.assertRaises(ProtocolError):
                validate_event(value)

    def test_missing_identity_and_unsupported_truth_claim_are_rejected(self):
        for field in ['protocol', 'attachment', 'capture', 'revision', 'producer',
                      'epoch', 'sequence', 'id', 'target', 'timestamp', 'clock',
                      'kind', 'point', 'evidence', 'certainty', 'source']:
            value = self.sample()
            del value[field]
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                validate_event(value)
        value = self.sample()
        value['certainty'] = 'probably'
        with self.assertRaises(ProtocolError):
            validate_event(value)

    def test_relationship_requires_support_or_named_inference(self):
        value = self.sample()
        value['kind'] = 'Relationship'
        value['evidence'] = {'from': 'a', 'to': 'b', 'relation': 'redirect'}
        with self.assertRaises(ProtocolError):
            validate_event(value)
        value['evidence']['support'] = ['source-1']
        validate_event(value)
        value['certainty'] = 'inferred'
        value['evidence']['support'] = []
        with self.assertRaises(ProtocolError):
            validate_event(value)
        value['evidence']['rule'] = 'explicitly-named-rule/1'
        validate_event(value)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'evidence.ndjson'

    def tearDown(self):
        self.temp.cleanup()

    def test_append_is_immutable_and_survives_reopen(self):
        value = {'type': 'test', 'data': {'missing': None}}
        with Journal(self.path) as journal:
            journal.append(value)
            value['data']['missing'] = 'mutated'
            snapshot = journal.entries()
            snapshot[0]['data']['missing'] = 'also mutated'
            self.assertIsNone(journal.entries()[0]['data']['missing'])
        with Journal(self.path) as journal:
            self.assertEqual(journal.entries(), [{'type': 'test', 'data': {'missing': None}}])

    def test_bound_and_control_reserve_do_not_evict_evidence(self):
        with Journal(self.path, limit=4096, reserve=1024) as journal:
            journal.append({'evidence': 'x' * 2500})
            saved = copy.deepcopy(journal.entries())
            with self.assertRaises(JournalFull):
                journal.append({'evidence': 'x' * 1000})
            journal.append({'type': 'Gap', 'reason': 'journal_full'}, control=True)
            self.assertEqual(journal.entries()[0], saved[0])
            self.assertLessEqual(self.path.stat().st_size, 4096)

    def test_torn_tail_is_reported_and_second_writer_is_rejected(self):
        with Journal(self.path) as journal:
            journal.append({'ok': True})
            with self.assertRaises(BlockingIOError):
                Journal(self.path)
        with self.path.open('ab') as out:
            out.write(b'{"torn":')
        with self.assertRaisesRegex(ValueError, 'truncated'):
            Journal(self.path)


class HandleTests(unittest.TestCase):
    def test_bound_expiry_release_and_unsupported_fields(self):
        now = [10.0]
        handles = Handles(limit=1, ttl=2, clock=lambda: now[0])
        key = handles.put({'url': 'http://example.test/'})
        with self.assertRaises(BufferError):
            handles.put({'url': 'another'})
        self.assertEqual(handles.read(key, ['url', 'body'])['body'],
                         {'certainty': 'unavailable', 'reason': 'unsupported-field'})
        now[0] = 13
        with self.assertRaises(KeyError):
            handles.read(key, ['url'])
        key = handles.put({'status': 200})
        handles.release([key, key])
        self.assertEqual(len(handles), 0)


if __name__ == '__main__':
    unittest.main()
