"""Offline generator evidence fixtures for V4.3."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from analysis.engineering.judge_links import attach_judge_links
from analysis.engineering.store import EngineeringStore
from analysis.research.github_sync import archive_generated_members, import_engineering_run
from analysis.research.registry import Registry, encoded
from standalone_v4 import audit, candidate_diagnostics
from test_engineering_workspace import fixture


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        workspace = self.enterContext(tempfile.TemporaryDirectory(dir='results'))
        self.root = Path(workspace)
        self.registry = Registry(self.root / 'registry.sqlite')
        self.engineering = EngineeringStore(self.root / 'engineering.sqlite')
        self.addCleanup(self.registry.close)
        self.addCleanup(self.engineering.close)

    def test_receipt_bound_artifact_and_engineering_import(self):
        response, inventory, receipt_path = fixture(self.root)
        payload = response.read_bytes()
        receipt = json.loads(receipt_path.read_text())
        receipt['artifacts'] = {'run_raw.txt': {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}}
        receipt_path.write_text(encoded(receipt), encoding='utf-8')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('folder/run_raw.txt', payload)
            archive.writestr('folder/input_inventory.json', inventory.read_bytes())
            archive.writestr('unrelated.csv', b'ignored')
        with zipfile.ZipFile(stream) as archive:
            members = archive_generated_members(self.registry, archive, 'folder/run_execution.json', receipt, 'synthetic')
            self.assertEqual([entry['member'] for entry in members], ['folder/run_raw.txt'])
            first = import_engineering_run(self.registry, self.engineering, archive, receipt_path, receipt, members)
            second = import_engineering_run(self.registry, self.engineering, archive, receipt_path, receipt, members)
            self.assertEqual(first, second)
            self.assertEqual(len(self.engineering.records()), 1)
            receipt['artifacts']['run_raw.txt']['sha256'] = 'bad'
            with self.assertRaisesRegex(ValueError, 'differs'):
                archive_generated_members(self.registry, archive, 'folder/run_execution.json', receipt, 'synthetic')

    def test_one_row_many_items_and_trials_preserves_disposition(self):
        response, inventory, receipt = fixture(self.root)
        body = json.loads(receipt.read_text())
        body['row_count'] = 1
        receipt.write_text(encoded(body))
        self.engineering.ingest(response, inventory, receipt, 'synthetic')
        gid = self.registry.receipt(receipt)
        for trial in ('first','second'):
            items = [{'item_id': item, 'found': True, 'matched_row_id': 'r1'} for item in ('opaque-a','opaque-b')]
            self.registry.db.execute('INSERT INTO evaluations VALUES (?,?,?,?,?)',
                (trial,gid,encoded({'items':items,'judge_skill_version':'v1.2'}),'synthetic','2026-01-01'))
        self.registry.db.execute('UPDATE generations SET selected_evaluation=? WHERE id=?',('second',gid))
        original = self.engineering.records()[0]
        self.engineering.review(original['record_id'], original['revision'], 'NEEDS_REVIEW', 'test reviewer',
                                'Synthetic interpretation pending', {'judge_disposition':'unresolved'})
        record = attach_judge_links(self.engineering.snapshot(),self.registry.path)['records'][0]
        self.assertEqual(len(record['judge_matches']),4)
        self.assertEqual(sum(match['selected'] for match in record['judge_matches']),2)
        self.assertEqual(record['current']['judge_disposition'],'unresolved')
        self.assertNotIn('judge_disposition',record['original'])

    def test_candidate_review_keeps_active_audit_and_row_identity(self):
        response, inventory, _ = fixture(self.root)
        raw, inv = (json.loads(path.read_text()) for path in (response,inventory))
        report = audit(raw,inv)
        diagnostics = candidate_diagnostics(raw,inv,report)
        self.assertEqual(report['structural_status'],'PASS')
        self.assertEqual(diagnostics['high_severity_review'][0]['row_id'],'r1')
        self.assertNotIn('candidate_review',report)
