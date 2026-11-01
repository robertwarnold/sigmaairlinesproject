"""Generated FMEA output must never be committed: the repository is public (see AGENTS.md)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "tests" / "fixtures" / "research_results_frozen.txt"
GENERATED = re.compile(r"(^|/)(results|outputs)/|_run\d+\.csv$|_raw\.txt$"
                       r"|(^|/)all_generated_fmeas_[^/]*\.csv$|(^|/)bundle/fmea\.(csv|json)$")


def tracked_files():
    try:
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [path for path in listing.decode("utf-8").split("\0") if path]


class RepositoryHygieneTests(unittest.TestCase):
    def setUp(self):
        self.files = tracked_files()
        if self.files is None:
            self.skipTest("Not a git checkout")
        self.frozen = {line for line in FROZEN.read_text(encoding="utf-8").splitlines()
                       if line and not line.startswith("#")}

    def test_no_generated_output_committed(self):
        found = [path for path in self.files if GENERATED.search(path) and path not in self.frozen]
        self.assertEqual(found, [], "Generated FMEA output is tracked; keep it in results/ or private storage")

    def test_research_results_frozen(self):
        added = [path for path in self.files if path.startswith("research_results/") and path not in self.frozen]
        self.assertEqual(added, [], "research_results/ is frozen; existing files stay, new files are not allowed")
