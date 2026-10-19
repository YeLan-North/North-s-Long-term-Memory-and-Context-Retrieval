"""Synthetic regressions for configurable and explicit time-window exports."""
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from zoneinfo import ZoneInfo
import test_capture_reliability as reliability
from test_chatgpt_sync import conversation, message

SCRIPT = Path(__file__).resolve().parents[1] / 'bin' / 'chatgpt-window'
CORE = SCRIPT.with_name('chatgpt-sync')


class WindowTests(unittest.TestCase):
    def setUp(self):
        reliability.ReliabilityTests.setUp(self)
        loader = importlib.machinery.SourceFileLoader('window_tests', str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.window = importlib.util.module_from_spec(spec)
        os.environ['CHATGPT_SYNC_CONFIG'] = self.cs.CONFIG_PATH
        try:
            loader.exec_module(self.window)
        finally:
            del os.environ['CHATGPT_SYNC_CONFIG']
        self.window.cs = self.cs
        self.root = Path(self.tmp.name)

    def tree(self, times, active=None):
        conv = conversation()
        conv['mapping'] = {}
        for i, stamp in enumerate(times):
            msg = message('user' if i % 2 == 0 else 'assistant', 'Synthetic text ' + str(i), self.cs.to_epoch(stamp))
            msg['id'] = 'message-' + str(i)
            conv['mapping'][str(i)] = {'message': msg, 'parent': str(i - 1) if i else None}
        conv['current_node'] = active if active is not None else str(len(times) - 1)
        return conv

    def store(self, conv, at='2027-01-01T00:00:00Z'):
        index = {}
        self.cs.store(conv, None, index, force=True)
        self.cs.save_index(index)
        self.cs.write_atomic(self.cs.LAST_SYNC, json.dumps({'status': 'complete', 'project_ids': ['g-p-test'], 'at': at}))

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                              env={**os.environ, 'CHATGPT_SYNC_CONFIG': self.cs.CONFIG_PATH})

    def test_midnight_and_exact_six_boundaries_same_chat_alternative(self):
        conv = self.tree(['2026-10-18T05:59:59-07:00', '2026-10-18T06:00:00-07:00',
                          '2026-10-18T23:59:59-07:00', '2026-10-19T00:00:00-07:00',
                          '2026-10-19T05:59:59-07:00', '2026-10-19T06:00:00-07:00'], active='3')
        self.store(conv)
        rows, manifest = self.window.scan(*self.window.bounds('2026-10-18', '06:00'))
        self.assertEqual([r['message_id'] for r in rows], ['message-1', 'message-2', 'message-3', 'message-4'])
        self.assertEqual(rows[-1]['branch'], 'alternative')
        self.assertEqual(manifest['conversations'], 1)
        self.assertEqual(manifest['missing_ids'], [])

    def test_arbitrary_minutes_and_multiple_dates(self):
        start, end = self.window.normalize('2026-10-17T09:17:30Z', '2026-10-20T11:42:00Z')
        self.assertEqual([str(d) for d in self.window.calendar_dates(start, end)],
                         ['2026-10-17', '2026-10-18', '2026-10-19', '2026-10-20'])
        self.store(self.tree(['2026-10-17T09:17:29Z', '2026-10-17T09:17:30Z', '2026-10-19T03:00:00Z', '2026-10-20T11:42:00Z']))
        rows, manifest = self.window.scan(start, end)
        self.assertEqual([r['message_id'] for r in rows], ['message-1', 'message-2'])
        self.assertEqual(len(manifest['calendar_dates']), 4)

    def test_offsets_are_normalized_to_config_timezone(self):
        start, end = self.window.normalize('2026-10-19T06:00:00+09:00', '2026-10-19T07:00:00+09:00')
        self.assertEqual(start.date(), dt.date(2026, 10, 18))
        self.assertEqual([str(d) for d in self.window.calendar_dates(start, end)], ['2026-10-18'])

    def test_non_vancouver_non_integer_offset_zone(self):
        self.cs.TZ = ZoneInfo('Asia/Kathmandu'); self.cs.TIMEZONE = 'Asia/Kathmandu'
        self.store(self.tree(['2026-10-18T02:29:59+05:45', '2026-10-18T02:30:00+05:45', '2026-10-19T02:30:00+05:45']))
        rows, manifest = self.window.scan(*self.window.bounds('2026-10-18', '02:30'))
        self.assertEqual([r['message_id'] for r in rows], ['message-1'])
        self.assertEqual(manifest['timezone'], 'Asia/Kathmandu')

    def test_dst_elapsed_lengths_and_repeated_hour(self):
        for date, hours in [('2025-03-08', 23), ('2025-11-01', 25)]:
            start, end = self.window.bounds(date, '06:00')
            self.assertEqual(end.timestamp() - start.timestamp(), hours * 3600)
        self.store(self.tree(['2025-11-02T01:30:00-07:00', '2025-11-02T01:30:00-08:00']))
        rows, _ = self.window.scan(*self.window.bounds('2025-11-01', '06:00'))
        self.assertEqual(len(rows), 2)
        start, end = self.window.normalize('2025-11-02T01:45:00-07:00', '2025-11-02T01:15:00-08:00')
        self.assertEqual(end.timestamp() - start.timestamp(), 1800)

    def test_dst_daily_boundary_requires_disambiguation(self):
        for date, boundary in [('2025-03-08', '02:30'), ('2025-11-01', '01:30')]:
            with self.assertRaisesRegex(ValueError, 'ambiguous/nonexistent'):
                self.window.bounds(date, boundary)

    def test_bad_or_naive_or_reversed_bounds(self):
        for start, end in [('2026-10-18T06:00', '2026-10-19T06:00Z'),
                           ('2026-10-19T06:00Z', '2026-10-18T06:00Z'),
                           ('2026-10-18T06:00Z', '2026-10-18T06:00Z')]:
            with self.assertRaises(ValueError): self.window.normalize(start, end)

    def test_duplicate_nodes_keep_all_branch_locations_and_conflicts_fail(self):
        conv = self.tree(['2026-10-18T12:00:00Z'])
        conv['mapping']['alt'] = {'message': dict(conv['mapping']['0']['message']), 'parent': '0'}
        self.store(conv)
        rows, manifest = self.window.scan(*self.window.bounds('2026-10-18'))
        self.assertEqual(len(rows), 1); self.assertEqual(len(rows[0]['occurrences']), 2)
        self.assertEqual(len(manifest['duplicate_ids']), 1)
        conv['mapping']['alt']['message']['content'] = {'content_type': 'text', 'parts': ['different']}
        self.store(conv)
        with self.assertRaisesRegex(ValueError, 'conflicting message ID'):
            self.window.scan(*self.window.bounds('2026-10-18'))

    def test_partial_next_calendar_day_does_not_block_closed_window(self):
        self.store(self.tree(['2026-10-18T23:59:59-07:00', '2026-10-19T00:00:00-07:00']),
                   at='2026-10-19T13:00:00-07:00')
        day = self.cs.export_day(dt.date(2026, 10, 19), str(self.root / 'calendar'))
        self.assertEqual(day['status'], 'partial')
        manifest = self.window.prepare(*self.window.bounds('2026-10-18', '06:00'), self.root / 'bundle')
        self.assertEqual(manifest['messages'], 2)
        self.assertEqual(manifest['export_status'], 'verified_for_observed_inventory')

    def ready_bundle(self):
        self.store(self.tree(['2026-10-18T23:59:59-07:00', '2026-10-19T00:00:00-07:00']))
        out = self.root / 'bundle'
        self.window.prepare(*self.window.bounds('2026-10-18', '06:00'), out)
        diary = self.root / 'diary.md'; diary.write_text('## Synthetic review\nSynthetic summary', encoding='utf-8')
        return out, diary

    def mark_reviewed(self, out):
        coverage = self.window.read(out / 'coverage.json')
        for row in coverage:
            row.update(status='summarized', section='## Synthetic review', note='Synthetic test mapping only')
        self.window.dump(out / 'coverage.json', coverage)
        return coverage

    def test_pending_wrong_ids_same_count_and_stale_success(self):
        out, diary = self.ready_bundle()
        self.assertFalse(self.window.verify(out, diary)['publication_ready'])
        coverage = self.mark_reviewed(out)
        self.assertTrue(self.window.verify(out, diary)['publication_ready'])
        coverage[1]['message_id'] = 'incorrect'
        self.window.dump(out / 'coverage.json', coverage)
        self.assertFalse(self.window.verify(out, diary)['publication_ready'])
        (out / 'coverage.json').write_text('invalid JSON', encoding='utf-8')
        result = self.cli(SCRIPT, 'verify', '--bundle', str(out), '--diary', str(diary))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.window.read(out / 'verification.json')['publication_ready'])

    def test_drop_second_day_duplicate_or_change_source_prevents_publication(self):
        out, diary = self.ready_bundle(); self.mark_reviewed(out)
        original = (out / 'messages.jsonl').read_text(encoding='utf-8')
        (out / 'messages.jsonl').write_text(original.splitlines()[0] + '\n', encoding='utf-8')
        self.assertFalse(self.window.verify(out, diary)['publication_ready'])
        (out / 'messages.jsonl').write_text(original + original.splitlines()[0] + '\n', encoding='utf-8')
        self.assertFalse(self.window.verify(out, diary)['publication_ready'])
        (out / 'messages.jsonl').write_text(original, encoding='utf-8')
        self.cs.write_atomic(self.cs.LAST_SYNC, Path(self.cs.LAST_SYNC).read_text() + ' ')
        self.assertFalse(self.window.verify(out, diary)['publication_ready'])
        with self.assertRaises(FileExistsError):
            self.window.prepare(*self.window.bounds('2026-10-18'), out)

    def test_missing_inventory_fails_with_manifest(self):
        out = self.root / 'broken'
        Path(self.cs.INDEX).unlink(missing_ok=True)
        with self.assertRaises(OSError):
            self.window.prepare(*self.window.bounds('2026-10-18'), out)
        self.assertEqual(self.window.read(out / 'manifest.json')['export_status'], 'incomplete')

    def test_real_cli_primary_entry_timezone_and_compatibility(self):
        self.store(self.tree(['2026-10-18T23:59:59-07:00', '2026-10-19T00:00:00-07:00']))
        result = self.cli(CORE, 'window', '--start', '2026-10-18T06:00:00-07:00',
                          '--end', '2026-10-19T06:00:00-07:00', '--output', str(self.root / 'cli'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['messages'], 2)
        result = self.cli(SCRIPT, 'prepare', '--date', '2026-10-18', '--boundary', '06:00',
                          '--timezone', 'UTC', '--output', str(self.root / 'utc'))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.window.read(self.root / 'utc' / 'manifest.json')
        self.assertEqual(manifest['timezone'], 'UTC')
        result = self.cli(SCRIPT.with_name('aster-diary'), 'prepare', '--date', '2026-10-18',
                          '--output', str(self.root / 'compat'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['messages'], 2)
        result = self.cli(SCRIPT, 'prepare', '--start', '2026-10-18T00:00', '--end',
                          '2026-10-19T00:00Z', '--output', str(self.root / 'invalid'))
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / 'invalid').exists())


if __name__ == '__main__':
    unittest.main()
