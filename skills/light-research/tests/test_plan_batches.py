import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan_batches.py"
sys.path.insert(0, str(SCRIPT.parent))
import plan_batches as pb  # noqa: E402


class PlanBatchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, size):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)

    def test_estimate_in_quarter_bytes(self):
        self.assertEqual(pb.estimate_tokens(400), 100)
        self.assertEqual(pb.estimate_tokens(1), 1)

    def test_excludes_folders_and_binaries(self):
        self.write("src/a.py", 40)
        self.write("node_modules/lib.js", 40)
        self.write(".git/config", 40)
        self.write("img/logo.png", 40)
        files, skipped = pb.collect(str(self.root))
        self.assertEqual([p for p, _ in files], [os.path.join("src", "a.py")])
        self.assertEqual(skipped, 1)

    def test_batches_respect_budget(self):
        for i in range(5):
            self.write("f%d.txt" % i, 400)  # 100 tokens each
        result = pb.plan(str(self.root), 250)
        self.assertEqual(result["total_files"], 5)
        self.assertEqual([b["tokens"] for b in result["batches"]], [200, 200, 100])
        self.assertTrue(all(b["tokens"] <= 250 for b in result["batches"]))
        self.assertFalse(any(b["oversize"] for b in result["batches"]))

    def test_file_larger_than_budget_is_isolated_and_flagged(self):
        self.write("small.txt", 40)
        self.write("big.txt", 4000)  # 1000 tokens, budget 300
        result = pb.plan(str(self.root), 300)
        big = [b for b in result["batches"] if b["oversize"]]
        self.assertEqual(len(big), 1)
        self.assertEqual(big[0]["files"], ["big.txt"])
        self.assertEqual(len(result["batches"]), 2)

    def test_cli_json_output_and_error(self):
        self.write("a.txt", 40)
        ok = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--budget", "5000"],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["total_files"], 1)
        ko = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "absent")],
                            capture_output=True, text=True)
        self.assertEqual(ko.returncode, 2)


if __name__ == "__main__":
    unittest.main()
