import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cua_doctor as cd  # noqa: E402


class DoctorTest(unittest.TestCase):
    def test_permissions(self):
        self.assertEqual(cd.parse_permissions('{"accessibility": true, "screen_recording": false}'), (True, False))
        self.assertIsNone(cd.parse_permissions("pas du json"))
        self.assertIsNone(cd.parse_permissions(None))

    def test_status(self):
        text = "Cua Driver daemon is running\n  pid: 1\n  permission mode: standard (built_in_default)\n"
        self.assertEqual(cd.parse_status(text), {"running": True, "mode": "standard"})
        self.assertEqual(cd.parse_status(None), {"running": False, "mode": None})

    def test_mcp_declare(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"mcpServers": {"cua-driver": {}}}), encoding="utf-8")
            self.assertTrue(cd.mcp_declared(str(path)))
            path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            self.assertFalse(cd.mcp_declared(str(path)))
            self.assertFalse(cd.mcp_declared(str(Path(tmp) / "absent.json")))

    def test_diagnose_sans_binaire(self):
        original = cd.shutil.which
        cd.shutil.which = lambda name: None
        try:
            report = cd.diagnose("/nulle/part.json")
        finally:
            cd.shutil.which = original
        self.assertFalse(report["binary"])
        self.assertTrue(report["todo"])


if __name__ == "__main__":
    unittest.main()
