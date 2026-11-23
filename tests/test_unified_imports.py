import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import zipfile

from analysis.research.github_sync import discover_branches, synchronize
from analysis.research.historical import FIELDS, MEMBER, comparison_metrics, load_comparison
from analysis.research.judge_import import adapt
from analysis.research.registry import Registry


class UnifiedImportTests(unittest.TestCase):
    def test_branch_discovery_and_selection(self):
        client = Mock()
        client.pages.return_value = [{'name': 'feat/example', 'commit': {'sha': 'a' * 40}}]
        self.assertEqual(discover_branches('owner/repo', client),
                         [{'branch': 'feat/example', 'commit': 'a' * 40}])
        client.pages.assert_called_once_with('/repos/owner/repo/branches', None)
        client.pages.reset_mock()
        client.pages.return_value = []
        with tempfile.TemporaryDirectory(dir='results') as folder:
            store = Registry(Path(folder) / 'registry.sqlite')
            try:
                synchronize(store, 'owner/repo', client=client, branches=['feat/example', 'feat/example'])
            finally:
                store.close()
        client.pages.assert_called_once_with(
            '/repos/owner/repo/actions/workflows/generate-fmea.yml/runs?branch=feat%2Fexample',
            'workflow_runs')

    def test_comparison_archive_and_distinct_denominators(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'study.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(MEMBER, ','.join(FIELDS) +
                                 '\nv2.0,A,1,100,20,20,4,85\nv2.0,B,1,10,5,50,0,5\n')
            metrics = comparison_metrics(load_comparison(path))['v2.0']
            self.assertAlmostEqual(metrics['pooled_missed_rate'], 25 / 110)
            self.assertAlmostEqual(metrics['mean_run_missed_rate'], 0.35)
            self.assertEqual(metrics['mean_unmatched_generated_per_run'], 2)

    def test_judge_archive_allowlist(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('judge.json', '{"schema":"standalone-judge-import-1","runs":[]}')
        with tempfile.TemporaryDirectory(dir='results') as folder:
            path = Path(folder) / 'judge.zip'
            path.write_bytes(data.getvalue())
            self.assertEqual(adapt(path)['runs'], [])
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('../unexpected.json', '{}')
            with self.assertRaisesRegex(ValueError, 'ZIP must contain'):
                adapt(path)


if __name__ == '__main__':
    unittest.main()
