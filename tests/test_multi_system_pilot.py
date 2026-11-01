"""Synthetic campaign safety and progress tests; never dispatch a real provider call."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from scripts import multi_system_pilot as pilot
from scripts import evaluate_multi_system as evaluate


class CampaignTests(unittest.TestCase):
    """Exercise the four-request boundary, atomic progress and existing engine reuse."""
    def setUp(self):
        # All mutable campaign evidence is synthetic and isolated from the real pilot.
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.folder = self.root / "synthetic-campaign"

    def test_atomic_progress_and_collision_refusal(self):
        progress = pilot.initialize(self.folder, "synthetic-campaign")
        progress.update(phase="synthetic generation", active_system="system_B", latest_event="synthetic")
        state = json.loads((self.folder / "status.json").read_text())
        self.assertEqual(state["completed_request_count"], 0)
        self.assertEqual(state["successful_request_count"], 0)
        self.assertIn("system_B", (self.folder / "STATUS.md").read_text())
        with self.assertRaises(FileExistsError):
            pilot.initialize(self.folder, "synthetic-campaign")

    def test_preflight_no_generation_and_sdk_retries_disabled(self):
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=65536, supported_actions=["generateContent"])
        with patch.object(pilot, "specification", return_value={"campaign_id": "synthetic"}), \
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test-key"}), \
                patch.object(pilot.engine, "load_local_env"), \
                patch("google.genai.Client", return_value=client) as factory:
            pilot.remote_preflight("synthetic", self.root / "plan.json")
        client.models.generate_content.assert_not_called()
        self.assertEqual(factory.call_args.kwargs["http_options"].retry_options.attempts, 1)

    def test_four_system_order_no_retry_and_durable_confirmed_counts(self):
        pilot.initialize(self.folder, "synthetic-campaign")
        (self.folder / "preflight").mkdir()
        (self.folder / "preflight/plan.json").write_text(json.dumps({"campaign_id": "synthetic-campaign", "model": pilot.MODEL, "maximum_new_requests": 4}))
        progress = pilot.Progress(self.folder)
        progress.update(preflight_run_id="synthetic-preflight")
        dispatched = []
        def github(wrapper, *args):
            if args[:2] == ("workflow", "run"):
                selected = next(a.split("=", 1)[1] for a in args if a.startswith("system="))
                dispatched.append(selected)
                return f"https://github.com/synthetic/project/actions/runs/{100+len(dispatched)}"
            if args[:2] == ("run", "view"):
                return json.dumps({"status": "completed", "conclusion": "success", "jobs": []})
            return ""
        # Precreated result directories keep the test focused on dispatch accounting.
        for system in pilot.SYSTEMS:
            (self.folder / system).mkdir()
        def receipt(folder, system, plan):
            return {"status": "failed" if system == "system_C" else "success", "duration_seconds": 2,
                    "row_count": None if system == "system_C" else 1, "cost_usd": None if system == "system_C" else .01,
                    "billing_uncertain": True}
        with patch.object(pilot, "github", side_effect=github), patch.object(pilot, "verify_download", side_effect=receipt):
            pilot.worker(self.folder, "synthetic-branch", "synthetic-gh", 4)
        self.assertEqual(dispatched, list(pilot.SYSTEMS))
        state = json.loads((self.folder / "status.json").read_text())
        self.assertEqual(state["reserved_request_count"], 4)
        self.assertEqual(state["completed_request_count"], 4)
        self.assertEqual(state["successful_request_count"], 3)
        self.assertEqual(state["failed_request_count"], 1)
        with self.assertRaises(FileExistsError):
            pilot.worker(self.folder, "synthetic-branch", "synthetic-gh", 4)

    def test_uncertain_dispatch_blocks_automatic_redispatch(self):
        progress = pilot.initialize(self.folder, "synthetic-campaign")
        (self.folder / "preflight").mkdir()
        (self.folder / "preflight/plan.json").write_text(json.dumps({"campaign_id": "synthetic-campaign", "model": pilot.MODEL, "maximum_new_requests": 4}))
        progress.state["systems"]["system_B"]["dispatch_reserved"] = True
        progress.update(preflight_run_id="synthetic", reserved_request_count=1)
        with patch.object(pilot, "github") as github:
            with self.assertRaisesRegex(RuntimeError, "Uncertain"):
                pilot.worker(self.folder, "synthetic", "synthetic", 4)
            github.assert_not_called()

    def test_remote_gate_and_preflight_config_match(self):
        # No malformed authorization can reach the existing engine boundary.
        with patch.object(pilot.engine, "generate_fmea") as generate:
            for system, count in (("system_A", 1), ("system_B", 4), ("system_B", 0)):
                with self.assertRaises(ValueError):
                    pilot.remote_single(self.root / "unused-plan.json", system, count)
            generate.assert_not_called()

    def test_structural_validation_synthetic_csv_and_rpn(self):
        row = {f: (2 if f in pilot.engine.RATINGS else "synthetic") for f in pilot.engine.FIELDS}
        row["RPN"] = 8
        path = self.root / "synthetic.csv"
        import csv
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[*pilot.engine.FIELDS, "RPN"])
            writer.writeheader()
            writer.writerow(row)
        with patch.object(evaluate, "inventory", return_value=[]):
            result = evaluate.structure(path, "synthetic-system")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["missing_required_fields"], 0)

    def test_workflow_contains_manual_campaign_gates_and_no_other_system(self):
        # Source declarations provide an additional guard against accidental UI-level expansion.
        text = (pilot.ROOT / ".github/workflows/generate-fmea.yml").read_text()
        self.assertIn("multi_system_preflight", text)
        self.assertIn("multi_system_single", text)
        self.assertIn("System/campaign already dispatched; never retry", text)
        self.assertEqual(pilot.SYSTEMS, ("system_B", "system_C", "system_D", "system_E"))
