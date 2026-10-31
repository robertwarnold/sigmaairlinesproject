from pathlib import Path
import tempfile
import unittest

from scripts.pilot_four_datasets import CONFIG, prepare, package_amendment
from scripts.pilot_workflow import CONFIG as ORIGINAL_CONFIG, package
from sigma_fmea.integrity import load_json
from sigma_fmea.research import run_experiment


class FourDatasetAmendmentTests(unittest.TestCase):
    def test_adopted_smoke_is_byte_preserved_and_seven_new_jobs_fill_four_pairs(self):
        with tempfile.TemporaryDirectory() as temp:
            smoke = Path(temp) / "smoke"
            output = Path(temp) / "amended"
            run_experiment(ORIGINAL_CONFIG, smoke, "smoke", provider="mock")
            package(smoke, plots=False)
            before = {p.relative_to(smoke): p.read_bytes() for p in smoke.rglob("*") if p.is_file()}
            plan = prepare(smoke, output, provider="mock")
            self.assertEqual(plan["total_generations"], 8)
            self.assertEqual(len(plan["systems"]), 4)
            self.assertEqual(plan["repetitions"], 1)
            for name, content in before.items():
                self.assertEqual((output / "original-smoke" / name).read_bytes(), content)
            job = plan["jobs"][0]["job_id"]
            copied = (output / "runs" / job / "state.json").read_bytes()
            self.assertEqual(copied, before[Path("runs") / job / "state.json"])
            progress = run_experiment(CONFIG, output, "batch", provider="mock")
            self.assertEqual(progress["successful"], 8)
            self.assertEqual((output / "runs" / job / "state.json").read_bytes(), copied)
            states = [load_json(p) for p in (output / "runs").glob("*/state.json")]
            self.assertEqual(len({(s["system_id"], s["condition"]) for s in states}), 8)
            package_amendment(output, plots=False)
            self.assertTrue((output / "AMENDMENT.md").exists())
            self.assertIn("Amended design", (output / "README.md").read_text())

    def test_tampered_smoke_is_rejected_before_any_new_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            smoke, output = Path(temp) / "smoke", Path(temp) / "amended"
            run_experiment(ORIGINAL_CONFIG, smoke, "smoke", provider="mock")
            package(smoke, plots=False)
            (smoke / "progress.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "checksum"):
                prepare(smoke, output, provider="mock")
            self.assertFalse(output.exists())
