"""Independent broker. All content interaction happens outside this process."""

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from .graph import graph
from .handles import Handles
from .journal import JOURNAL_LIMIT, Journal, JournalFull
from .protocol import (
    MAX_BATCH, MAX_MESSAGE, PROTOCOL, ProtocolError, clone, encode, target, text, uint64,
    validate_event,
)

# No real Gecko actor has been validated. Keep those capabilities explicitly false.
UNAVAILABLE = ['native-gecko', 'native-channel', 'cache-origin', 'service-worker-origin',
               'policy-enforcement', 'page-visible-response', 'native-causal-message-identity']


class Broker:
    def __init__(self, path: Path, *, limit: int = JOURNAL_LIMIT, reserve: int = 65536):
        self.journal = Journal(path, limit, reserve)
        self.lock = threading.RLock()
        self.handles = Handles()
        self.attachment: dict[str, Any] | None = None
        self.captures: dict[str, dict[str, Any]] = {}
        self.targets: dict[str, dict[str, Any]] = {}
        self.sequences: dict[tuple[str, str], int] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.gaps: list[dict[str, Any]] = []
        self.full = False
        self.connected = False
        try:
            for row in self.journal.entries():
                self._apply(row)
        except BaseException:
            self.journal.close()
            raise

    def _apply(self, row: dict[str, Any]) -> None:
        kind = row['type']
        if kind == 'attach':
            self.attachment = clone(row)
            self.targets.clear()
            self.sequences.clear()
        elif kind == 'detach':
            self.attachment = None
            self.targets.clear()
            self.sequences.clear()
            self.handles.clear()
            for capture in self.captures.values():
                if capture['state'] != 'stopped':
                    capture['incomplete'] = True
                    capture['state'] = 'detached'
        elif kind == 'start':
            self.captures[row['capture']] = {**clone(row), 'state': 'requested',
                                             'activated': False, 'incomplete': False}
        elif kind == 'activation':
            self.captures[row['capture']].update(state='active', activated=True,
                                                target=clone(row['target']))
        elif kind in {'stop', 'stopped'}:
            self.captures[row['capture']]['state'] = 'stop-requested' if kind == 'stop' else 'stopped'
        elif kind.startswith('target.'):
            identity = row['target']['id']
            self.targets[identity] = {**clone(row), 'ended': kind == 'target.end'}
            for capture in self.captures.values():
                if capture['target']['id'] == identity and (
                    capture['target'] != row['target'] or kind == 'target.end'
                ):
                    capture.update(activated=False, incomplete=True)
        elif kind == 'events':
            for e in row['batch']:
                self.events[e['id']] = clone(e)
                self.sequences[(e['producer'], e['epoch'])] = int(e['sequence'])
            self.gaps.extend(clone(row['gaps']))
        elif kind == 'gap':
            self.gaps.append(clone(row))
            self.full = self.full or row['reason'] == 'journal-full'
        elif kind == 'health':
            if self.attachment:
                self.attachment['healthy'] = row['healthy']
            if not row['healthy']:
                self.gaps.append({**clone(row), 'reason': 'collector-unhealthy'})
        else:
            raise ProtocolError(f'unknown journal entry {kind}')

    def _save(self, row: dict[str, Any], *, control: bool = True) -> None:
        self.journal.append(row, control=control)
        self._apply(row)

    def _attached(self, m: dict[str, Any]) -> dict[str, Any]:
        if not self.attachment or m.get('attachment') != self.attachment['attachment']:
            raise ProtocolError('stale or absent attachment')
        return self.attachment

    def _capture(self, m: dict[str, Any]) -> dict[str, Any]:
        self._attached(m)
        capture = self.captures.get(m.get('capture'))
        if not capture or capture['attachment'] != m['attachment']:
            raise ProtocolError('unknown capture')
        return capture

    def dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if not isinstance(message, dict) or len(encode(message)) > MAX_MESSAGE:
                raise ProtocolError('message exceeds bound')
            m = clone(message)
            if m.get('protocol') != PROTOCOL:
                raise ProtocolError('unsupported protocol')
            kind = text(m.get('type'), 'type')
            if kind == 'hello':
                return {'protocol': PROTOCOL, 'type': 'capabilities', 'credit': MAX_BATCH,
                        'unavailable': UNAVAILABLE, 'maxMessageBytes': MAX_MESSAGE,
                        'journalLimit': self.journal.limit}
            if kind == 'snapshot':
                return self.snapshot()
            if kind == 'export':
                return self.export(redacted=m.get('redacted', True))
            if kind == 'attach':
                if self.attachment:
                    raise ProtocolError('detach existing attachment first')
                if m.get('source') not in {'synthetic', 'desktop-chromium-playwright'}:
                    raise ProtocolError('native-gecko adapter not validated')
                if not isinstance(m.get('scope'), dict):
                    raise ProtocolError('scope required')
                caps = m.get('capabilities')
                if not isinstance(caps, dict) or not 1 <= len(caps) <= 32:
                    raise ProtocolError('capabilities required')
                for name, states in caps.items():
                    text(name, 'capability')
                    if (not isinstance(states, dict) or set(states) != {
                        'supported', 'permitted', 'enabled', 'healthy'
                    } or any(not isinstance(v, bool) for v in states.values())):
                        raise ProtocolError('separate boolean capability states required')
                    if (states['enabled'] and not (states['supported'] and states['permitted'])):
                        raise ProtocolError('enabled unsupported or forbidden capability')
                m['attachment'] = f'attachment-{len(self.journal.entries()) + 1}'
                m['healthy'] = True
                self._save(m)
                self.connected = True
                return {'attachment': m['attachment'], 'credit': MAX_BATCH}
            self._attached(m)
            if kind == 'detach':
                self._save(m)
                self.connected = False
                return {'type': 'detached'}
            if kind in {'target.upsert', 'target.end'}:
                target(m.get('target'))
                if m.get('target') is None:
                    raise ProtocolError('concrete target required')
                old = self.targets.get(m['target']['id'])
                if old and uint64(m['target']['generation']) < uint64(old['target']['generation']):
                    raise ProtocolError('target generation regressed')
                if kind == 'target.upsert':
                    text(m.get('targetKind'), 'targetKind')
                    target(m.get('parent'))
                    if len(self.targets) >= 256 and not old:
                        raise ProtocolError('target limit')
                else:
                    if not old or old['target'] != m['target']:
                        raise ProtocolError('unknown target generation')
                    text(m.get('reason'), 'reason')
                self._save(m)
                return {'type': kind}
            if kind == 'start':
                text(m.get('capture'), 'capture')
                text(m.get('revision'), 'revision')
                if m['capture'] in self.captures or len(self.captures) >= 256:
                    raise ProtocolError('capture exists or capture limit reached')
                if any(c['state'] in {'requested', 'active', 'stop-requested'}
                       for c in self.captures.values()):
                    raise ProtocolError('stop previous capture first')
                if not isinstance(m.get('plan'), dict):
                    raise ProtocolError('plan required')
                self._current_target(m.get('target'))
                self._save(m)
                return {'state': 'requested', 'ready': False}
            if kind in {'activation', 'stop', 'stopped'}:
                capture = self._capture(m)
                if kind == 'activation':
                    if capture['state'] not in {'requested', 'active'}:
                        raise ProtocolError('capture cannot activate')
                    if m.get('revision') != capture['revision']:
                        raise ProtocolError('configuration revision mismatch')
                    self._current_target(m.get('target'))
                elif kind == 'stop' and capture['state'] not in {'requested', 'active'}:
                    raise ProtocolError('capture cannot stop')
                elif kind == 'stopped' and capture['state'] != 'stop-requested':
                    raise ProtocolError('stop was not requested')
                self._save(m)
                return {'state': self.captures[m['capture']]['state']}
            if kind == 'events':
                return self._ingest(m)
            if kind in {'gap', 'health'}:
                text(m.get('reason'), 'reason')
                if kind == 'health' and not isinstance(m.get('healthy'), bool):
                    raise ProtocolError('healthy boolean required')
                self._save(m)
                return {'type': kind}
            if kind == 'handle':
                value = self.events.get(m.get('id'))
                if not value:
                    raise ProtocolError('unknown evidence id')
                return {'handle': self.handles.put(value['evidence'])}
            if kind == 'read':
                fields = m.get('fields')
                if not isinstance(fields, list) or len(fields) > 64:
                    raise ProtocolError('bounded fields required')
                for field in fields:
                    text(field, 'field')
                return {'fields': self.handles.read(text(m.get('handle'), 'handle'), fields)}
            if kind == 'release':
                keys = m.get('handles')
                if not isinstance(keys, list) or len(keys) > 128:
                    raise ProtocolError('bounded handles required')
                for key in keys:
                    text(key, 'handle')
                self.handles.release(keys)
                return {'released': True}
            raise ProtocolError('unknown message type')

    def _current_target(self, identity: Any) -> None:
        target(identity)
        if identity is None:
            raise ProtocolError('target identity required')
        known = self.targets.get(identity['id'])
        if not known or known['ended'] or known['target'] != identity:
            raise ProtocolError('unknown or stale target generation')

    def _ingest(self, m: dict[str, Any]) -> dict[str, Any]:
        batch = m.get('batch')
        if not isinstance(batch, list) or not 1 <= len(batch) <= MAX_BATCH:
            raise ProtocolError('batch must contain 1..64 events')
        if self.full:
            return {'ack': [], 'duplicates': [], 'credit': 0, 'reason': 'journal-full'}
        sequences = self.sequences.copy()
        accepted: dict[str, dict[str, Any]] = {}
        duplicates: list[str] = []
        gaps: list[dict[str, Any]] = []
        for e in batch:
            validate_event(e)
            if e['attachment'] != m['attachment']:
                raise ProtocolError('event attachment mismatch')
            capture = self._capture(e)
            if not self.connected or not capture['activated'] or capture['state'] not in {
                'active', 'stop-requested'
            } or not self.attachment or not self.attachment['healthy']:
                raise ProtocolError('collector not activated or not healthy')
            if e['revision'] != capture['revision'] or e['source'] != self.attachment['source']:
                raise ProtocolError('configuration or source mismatch')
            if e['target'] is not None:
                self._current_target(e['target'])
            previous = accepted.get(e['id'], self.events.get(e['id']))
            if previous:
                if previous != e:
                    raise ProtocolError('event ID reused with different content')
                duplicates.append(e['id'])
                continue
            if e['kind'] == 'Relationship':
                refs = [e['evidence']['from'], e['evidence']['to'],
                        *e['evidence'].get('support', [])]
                if any(ref not in self.events and ref not in accepted for ref in refs):
                    raise ProtocolError('relationship references unknown evidence')
            key = (e['producer'], e['epoch'])
            seq = int(e['sequence'])
            last = sequences.get(key, 0)
            if seq <= last:
                raise ProtocolError('out-of-order or conflicting sequence')
            if seq > last + 1:
                gaps.append({'type': 'gap', 'reason': 'sequence-gap', 'capture': e['capture'],
                             'attachment': e['attachment'], 'producer': e['producer'],
                             'epoch': e['epoch'], 'missing': [str(last + 1), str(seq - 1)]})
            if key not in sequences and len(sequences) >= 128:
                raise ProtocolError('producer/epoch limit')
            sequences[key] = seq
            accepted[e['id']] = e
        if accepted:
            try:
                self._save({**m, 'batch': list(accepted.values()), 'gaps': gaps}, control=False)
            except JournalFull:
                self._save({'type': 'gap', 'reason': 'journal-full', 'attachment': m['attachment'],
                            'missing': None})
                return {'ack': [], 'duplicates': duplicates, 'credit': 0, 'reason': 'journal-full'}
        return {'type': 'ack', 'ack': list(accepted), 'duplicates': duplicates, 'credit': MAX_BATCH}

    def snapshot(self) -> dict[str, Any]:
        active = [c for c in self.captures.values() if c['state'] in {
            'requested', 'active', 'stop-requested'
        }]
        ready = bool(self.connected and self.attachment and self.attachment.get('healthy')
                     and active and all(c['activated'] for c in active) and not self.full)
        return clone({'protocol': PROTOCOL, 'ready': ready, 'incomplete': bool(self.gaps) or any(
            c['incomplete'] or c['state'] != 'stopped' for c in self.captures.values()),
            'attachment': self.attachment, 'captures': self.captures, 'targets': self.targets,
            'graph': graph(list(self.events.values())), 'gaps': self.gaps,
            'unavailable': UNAVAILABLE, 'retainedHandles': len(self.handles),
            'journalBytes': self.journal.size, 'journalLimit': self.journal.limit})

    def export(self, *, redacted: bool = True) -> dict[str, Any]:
        entries = self.journal.entries()
        if redacted:
            entries = _redact_entries(entries)
        return {'manifest': {'protocol': PROTOCOL, 'archiveVersion': 1, 'redacted': redacted,
                             'journalLimit': self.journal.limit, 'reserve': self.journal.reserve,
                             'sha256': hashlib.sha256(encode(entries)).hexdigest(),
                             'unavailable': UNAVAILABLE, 'artifacts': []}, 'entries': entries}

    def close(self) -> None:
        self.handles.clear()
        self.journal.close()


def _redact_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # All free-form payload fields are removed, including unknown nested fields.
    # Keep relationship IDs and structure to preserve the graph, not arbitrary labels.
    for row in entries:
        if row['type'] == 'attach':
            row['scope'] = {'redacted': True}
        if row['type'] == 'start':
            row['plan'] = {'redacted': True}
        for e in row.get('batch', []):
            if e['kind'] == 'Relationship':
                original = e['evidence']
                e['evidence'] = {k: v for k, v in original.items()
                                 if k in {'from', 'to', 'support', 'rule', 'relation'}}
            else:
                e['evidence'] = {'redaction': {'certainty': 'redacted', 'reason': 'export-policy'}}
                e['certainty'] = 'redacted'
        if row['type'] in {'health', 'gap', 'target.end'}:
            # Known machine codes are useful coverage evidence; free text is not exported.
            if row.get('reason') not in {'journal-full', 'sequence-gap', 'transport-interruption',
                                         'process-terminated', 'collector-unhealthy'}:
                row['reason'] = 'redacted'
    return entries


def import_archive(path: Path, archive: dict[str, Any]) -> Broker:
    """Validate by replaying the public command contract before creating destination."""
    import tempfile

    manifest, entries = archive.get('manifest', {}), archive.get('entries')
    if (manifest.get('protocol') != PROTOCOL or manifest.get('archiveVersion') != 1
            or not isinstance(entries, list) or len(encode(entries)) > JOURNAL_LIMIT
            or hashlib.sha256(encode(entries)).hexdigest() != manifest.get('sha256')):
        raise ProtocolError('invalid archive manifest, size or digest')
    if path.exists():
        raise FileExistsError(path)
    with tempfile.TemporaryDirectory() as scratch:
        staged = Path(scratch) / 'validated'
        broker = Broker(staged, limit=manifest['journalLimit'], reserve=manifest['reserve'])
        try:
            for row in entries:
                command = clone(row)
                if command['type'] == 'attach':
                    command.pop('attachment', None)
                    command.pop('healthy', None)
                command.pop('gaps', None)
                command['protocol'] = PROTOCOL
                broker.dispatch(command)
            if broker.journal.entries() != entries:
                raise ProtocolError('archive is not canonical or replayable')
            data = staged.read_bytes()
        finally:
            broker.close()
    # Exclusive create preserves user files and prevents partial validated imports on failure.
    with path.open('xb') as destination:
        destination.write(data)
        destination.flush()
        import os
        os.fsync(destination.fileno())
    return Broker(path, limit=manifest['journalLimit'], reserve=manifest['reserve'])
