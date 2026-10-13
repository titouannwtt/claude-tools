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

    def test_estimation_en_quart_d_octet(self):
        self.assertEqual(pb.estimate_tokens(400), 100)
        self.assertEqual(pb.estimate_tokens(1), 1)

    def test_exclusions_dossiers_et_binaires(self):
        self.write("src/a.py", 40)
        self.write("node_modules/lib.js", 40)
        self.write(".git/config", 40)
        self.write("img/logo.png", 40)
        files, skipped = pb.collect(str(self.root))
        self.assertEqual([p for p, _ in files], [os.path.join("src", "a.py")])
        self.assertEqual(skipped, 1)

    def test_lots_respectent_le_budget(self):
        for i in range(5):
            self.write("f%d.txt" % i, 400)  # 100 tokens chacun
        result = pb.plan(str(self.root), 250)
        self.assertEqual(result["total_files"], 5)
        self.assertEqual([b["tokens"] for b in result["batches"]], [200, 200, 100])
        self.assertTrue(all(b["tokens"] <= 250 for b in result["batches"]))
        self.assertFalse(any(b["oversize"] for b in result["batches"]))

    def test_fichier_plus_grand_que_le_budget_est_isole_et_marque(self):
        self.write("petit.txt", 40)
        self.write("gros.txt", 4000)  # 1000 tokens, budget 300
        result = pb.plan(str(self.root), 300)
        big = [b for b in result["batches"] if b["oversize"]]
        self.assertEqual(len(big), 1)
        self.assertEqual(big[0]["files"], ["gros.txt"])
        self.assertEqual(len(result["batches"]), 2)

    def test_cli_sortie_json_et_erreur(self):
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
