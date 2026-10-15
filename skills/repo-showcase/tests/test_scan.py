import io
import json
import os
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import gitfixtures as fx

scan = fx.scan

_env = None


def setUpModule():
    global _env
    _env = fx.isolate()


def tearDownModule():
    _env.stop_and_clean()


def scanner(terms=(), allowed=(), allow=()):
    """Scanner over a fake repo path, with personal terms [(label, words, boundary)]."""
    return scan.Scanner(Path("."), scan.Terms(list(terms), list(allowed)), set(allow))


def hits_of(text, path="notes.txt", **kwargs):
    return scanner(**kwargs).text_hits(text, path, "working-tree")


def categories(text, path="notes.txt", **kwargs):
    return {h["category"] for h in hits_of(text, path, **kwargs)}


def exif_tiff(make=b"Acme", gps=True):
    """Little-endian TIFF stream with a Make tag and, optionally, a GPS IFD with latitude and longitude."""
    count = 1 + (1 if gps else 0)
    make_offset = 8 + 2 + 12 * count + 4
    gps_offset = make_offset + len(make) + 2
    ifd = struct.pack("<H", count) + struct.pack("<HHII", 0x010F, 2, len(make) + 1, make_offset)
    if gps:
        ifd += struct.pack("<HHII", 0x8825, 4, 1, gps_offset)
    ifd += struct.pack("<I", 0)
    data = b"II*\0" + struct.pack("<I", 8) + ifd + make + b"\0\0"
    if gps:
        data += struct.pack("<H", 2) + struct.pack("<HHII", 2, 5, 3, 0) + struct.pack("<HHII", 4, 5, 3, 0)
        data += struct.pack("<I", 0)
    return data


def screenshot_tiff():
    """TIFF stream like the one of a macOS screenshot: no Make, no Model, only dimensions and a UserComment."""
    comment = b"ASCII\0\0\0Screenshot"
    sub_offset = 8 + 2 + 12 + 4
    sub = struct.pack("<H", 3) + struct.pack("<HHII", 0xA002, 4, 1, 1440) + struct.pack("<HHII", 0xA003, 4, 1, 900)
    sub += struct.pack("<HHII", 0x9286, 7, len(comment), sub_offset + 2 + 36 + 4) + struct.pack("<I", 0) + comment
    ifd = struct.pack("<H", 1) + struct.pack("<HHII", 0x8769, 4, 1, sub_offset) + struct.pack("<I", 0)
    return b"II*\0" + struct.pack("<I", 8) + ifd + sub


def make_png(*chunks):
    """PNG signature, the given (type, body) chunks, then IEND (CRCs are not checked by the scanner)."""
    out = b"\x89PNG\r\n\x1a\n"
    for kind, body in chunks + ((b"IEND", b""),):
        out += struct.pack(">I4s", len(body), kind) + body + b"\0\0\0\0"
    return out


def xmp_chunk(properties):
    """PNG iTXt chunk holding an XMP packet with the given {name: value} properties as attributes."""
    attributes = " ".join('%s="%s"' % item for item in properties.items())
    packet = '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description %s/></rdf:RDF></x:xmpmeta>' % attributes
    return b"iTXt", b"XML:com.adobe.xmp\0\0\0\0\0" + packet.encode("utf-8")


def make_jpeg(exif=None):
    body = b""
    if exif:
        body = b"\xff\xe1" + struct.pack(">H", 2 + 6 + len(exif)) + b"Exif\0\0" + exif
    return b"\xff\xd8" + body + b"\xff\xdb\x00\x04\x00\x00\xff\xd9"


def make_docx(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document><w:p><w:t>%s</w:t></w:p></w:document>" % text)
    return buffer.getvalue()


class SecretTests(unittest.TestCase):
    def test_provider_tokens_are_found(self):
        for value in (fx.ANTHROPIC, fx.OPENAI, fx.GITHUB, fx.AWS, fx.GOOGLE, fx.SLACK, fx.STRIPE, fx.SENDGRID,
                      fx.TELEGRAM, fx.JWT, "github_pat_" + "a1" * 25):
            with self.subTest(prefix=value[:6]):
                found = hits_of("value: %s\n" % value)
                self.assertIn("secret", {h["category"] for h in found})
                self.assertEqual({h["severity"] for h in found if h["category"] == "secret"}, {"high"})

    def test_aws_secret_assignment_and_private_key(self):
        text = 'aws_secret_access_key = "%s"\n' % ("Zq8/Lm2+Ab" * 4)
        self.assertIn("secret", categories(text))
        self.assertIn("secret", categories(fx.PRIVATE_KEY))

    def test_private_key_marker_without_body_is_ignored(self):
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        self.assertNotIn("secret", categories('pattern = "%s"\n' % marker))

    def test_crypto_key_and_seed_phrase(self):
        key = "0x" + "ab" * 32
        self.assertIn("secret", categories('private_key = "%s"\n' % key))
        self.assertNotIn("secret", categories('tx_hash = "%s"\n' % key))
        words = " ".join(["abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd",
                          "abuse", "access", "accident"])
        self.assertIn("secret", categories('mnemonic = "%s"\n' % words))
        self.assertNotIn("secret", categories('title = "%s"\n' % words))

    def test_placeholders_are_not_secrets(self):
        for text in ("sk-ant-" + "x" * 30, "AKIA" + "IOSFODNN7EXAMPLE", "sk-ant-" + "your-key-here-" + "0" * 12):
            self.assertNotIn("secret", categories(text), text[:12])

    def test_generic_assignment_positive_and_negative(self):
        positives = ['password = "hunter2hunter"\n', "db_password: hunter2hunter\n", 'API_KEY="abc123def456ghi"\n',
                     '{"client_secret": "Zx81Pq93mm"}\n']
        for text in positives:
            with self.subTest(text=text[:15]):
                self.assertIn("secret", categories(text, "settings.py" if text.startswith("pass") else "conf.yaml"))
        negatives = ['password = ""\n', 'password = "changeme"\n', 'password = "${DB_PASSWORD}"\n',
                     'password = os.environ["DB_PASSWORD"]\n', 'password = "<your password>"\n',
                     'token = "example-token-value"\n', 'password = "test1234"\n', 'author = "Jane Doe"\n',
                     "password = args.password_value\n", 'token = "{{ secrets.TOKEN }}"\n',
                     'secret_key_path = "/etc/keys/value-file"\n', 'password = "short"\n', 'auth = "oauth2"\n',
                     'tokenizer = "gpt2-large-model"\n', 'proxy_auth_hdr = "Proxy-Authorization"\n', 'password_prompt = "Enter the password: "\n']
        for text in negatives:
            with self.subTest(text=text[:25]):
                self.assertNotIn("secret", categories(text, "settings.py"))

    def test_generic_assignment_in_env_file_and_code_needs_quotes(self):
        self.assertIn("secret", categories("TOKEN=abc123def456\n", ".env"))
        self.assertNotIn("secret", categories("token = abc123def456\n", "settings.py"))
        self.assertNotIn("secret", categories("password = hunter2hunter\n", "README.md"))

    def test_credentials_url(self):
        url = "postgres://admin:" + "S3cretPw99" + "@db.corp.io/app"
        self.assertIn("credentials-url", categories("DATABASE_URL=%s\n" % url))
        for safe in ("postgres://user:password@localhost/db", "https://user:" + "S3cretPw99" + "@example.com/x",
                     "https://user:<password>@db.corp.io/x", "https://user:${PASSWORD}@db.corp.io/x"):  # check-repo: ignore
            self.assertNotIn("credentials-url", categories(safe + "\n"), safe)

    def test_ignore_marker_and_allowlist(self):
        line = 'KEY = "%s"' % fx.ANTHROPIC
        self.assertEqual(hits_of(line + "  # showcase: ignore\n"), [])
        found = hits_of(line + "\n")
        self.assertEqual(len(found), 1)
        self.assertEqual(hits_of(line + "\n", allow={found[0]["fingerprint"]}), [])


class PersonalDataTests(unittest.TestCase):
    def test_email(self):
        self.assertIn("email", categories("contact: %s\n" % fx.REAL_EMAIL))
        for safe in ("1+tester@users.noreply.github.com", "a@example.com", "x@sub.example", "git@github.com:org/r",  # check-repo: ignore
                     "you@your-domain.org", "name@domain.tld", "foo@bar.com", "logo@2x.png", "bot@localhost",  # check-repo: ignore
                     "noreply@corp.io", "react@18.2.0"):
            self.assertNotIn("email", categories(safe + "\n"), safe)

    def test_ip(self):
        public = ".".join(["8"] * 4)
        private = ".".join(["10", "0", "0", "5"])
        found = {h["severity"] for h in hits_of("host %s\n" % public) if h["category"] == "ip"}
        self.assertEqual(found, {"medium"})
        found = {h["severity"] for h in hits_of("host %s\n" % private) if h["category"] == "ip"}
        self.assertEqual(found, {"low"})
        for ignored in ("127.0.0.1", "0.0.0.0", "192.0.2.10", "198.51.100.7", "255.255.255.0", "version 1.2.3.4",  # check-repo: ignore
                        "v1.2.3.4", "numpy>=1.2.3.4"):  # check-repo: ignore
            self.assertNotIn("ip", categories(ignored + "\n"), ignored)

    def test_ipv6(self):
        self.assertIn("ip", categories("addr 2606:4700:4700::1111\n"))
        self.assertNotIn("ip", categories("addr ::1 and 2001:db8::1 and std::string\n"))

    def test_port(self):
        self.assertEqual({h["severity"] for h in hits_of("redis db.corp.io:6379\n") if h["category"] == "port"},
                         {"low"})
        for ignored in ("localhost:3000", "http://127.0.0.1:8080", "see app.py:120", "example.com:8080"):
            self.assertNotIn("port", categories(ignored + "\n"), ignored)

    def test_username_from_home_path(self):
        home = "/" + "Users" + "/zorglub/project"
        self.assertEqual({h["severity"] for h in hits_of("cd %s\n" % home) if h["category"] == "username"},
                         {"medium"})
        self.assertIn("username", categories("C:\\\\" + "Users" + "\\\\zorglub\\\\x\n"))
        for ignored in ("/Users/name/x", "/home/user/x", "/Users/<user>/x", "/home/runner/work", "/home/login"):  # check-repo: ignore
            self.assertNotIn("username", categories(ignored + "\n"), ignored)

    def test_phone_address_iban_card(self):
        self.assertIn("phone", categories("tel +33 " + "6 12 34 56 78\n"))
        self.assertIn("phone", categories("tel 06 12 34 56 78\n"))
        self.assertIn("phone", categories("call (212) 555-" + "0147 now, 212-654-" + "0147\n"))
        self.assertNotIn("phone", categories("on 2024-01-15 at 12:30\n"))
        self.assertIn("postal-address", categories("habite 12 rue de la Paix\n"))
        self.assertIn("postal-address", categories("lives at 123 Main Street\n"))
        self.assertNotIn("postal-address", categories("we have 2 place holders here\n"))
        iban = "GB82" + "WEST" + "12345698765432"
        self.assertIn("iban", categories("IBAN %s\n" % iban))
        self.assertNotIn("iban", categories("IBAN %s\n" % (iban[:-1] + "3")))
        self.assertIn("card-number", categories("card " + " ".join(["4111"] + ["1111"] * 3) + "\n"))
        self.assertIn("card-number", categories("card " + "4111" + "1111" * 3 + "\n"))
        self.assertNotIn("card-number", categories("card " + "4111" + "1111" * 2 + "1112\n"))
        self.assertNotIn("card-number", categories("ts 1700000000000\n"))

    def test_card_and_port_noise(self):
        # Luhn-valid digits as decimals or bare data are not cards; code identifiers are not hosts.
        self.assertNotIn("card-number", categories("size=3." + "4111" + "1111" * 3 + "\n"))
        self.assertNotIn("card-number", categories("[" + "4111" + "1111" * 3 + "]\n"))
        self.assertIn("card-number", categories("pay " + "-".join(["4111"] + ["1111"] * 3) + "\n"))
        self.assertNotIn("port", categories("see Props.Catacombs:34 and Workspace.Map:120\n"))

    def test_personal_terms_and_allowed_strings(self):
        terms = [("--terms", ["zorglub"], False)]
        found = hits_of("written by Zorglub\n", terms=terms)
        self.assertEqual([h["category"] for h in found], ["personal-name"])
        self.assertEqual(found[0]["severity"], "high")
        self.assertEqual(hits_of("see github.com/zorglub-org/tool\n", terms=terms, allowed=["zorglub-org"]), [])
        self.assertEqual(len(hits_of("zorglub and github.com/zorglub-org\n", terms=terms, allowed=["zorglub-org"])), 1)
        self.assertEqual(categories("mail zorglub" + "@" + "corp.io\n", terms=terms), {"email"})

    def test_auto_terms_use_word_boundaries(self):
        terms = [("os full name", ["mark"], True)]
        self.assertEqual(hits_of("a markdown file\n", terms=terms), [])
        self.assertEqual(len(hits_of("by Mark Twain\n", terms=terms)), 1)

    def test_previews_never_show_the_value(self):
        for text in ('KEY = "%s"\n' % fx.ANTHROPIC, "mail %s\n" % fx.REAL_EMAIL):
            for hit in hits_of(text):
                self.assertNotIn(fx.ANTHROPIC, json.dumps(scan.public(hit)))
                self.assertNotIn(fx.REAL_EMAIL, json.dumps(scan.public(hit)))
                self.assertLessEqual(len(hit["preview"]), 14)


class FileTests(unittest.TestCase):
    def file_categories(self, path, data=None, size=None, **kwargs):
        return {h["category"]: h for h in scanner(**kwargs).file_hits(path, data, "working-tree", size)}

    def test_env_files(self):
        self.assertIn("env-file", self.file_categories(".env", b"A=1\n"))
        self.assertIn("env-file", self.file_categories("config/.env.production", b"A=1\n"))
        for safe in (".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults"):
            self.assertNotIn("env-file", self.file_categories(safe, b"A=1\n"), safe)

    def test_credential_files(self):
        for name in ("server.pem", "tls/server.key", "id_rsa", "id_ed25519", "ks.jks", "ks.keystore", "a.p12",
                     "a.pfx", "credentials.json", "service-account-prod.json", ".pypirc", ".netrc", ".htpasswd",
                     "vault.kdbx", "office.ovpn", "kubeconfig"):
            with self.subTest(name=name):
                self.assertEqual(self.file_categories(name, b"x\n").get("credential-file", {}).get("severity"),
                                 "high")
        self.assertNotIn("credential-file", self.file_categories("id_rsa.pub", b"ssh-rsa AAA\n"))

    def test_symlink_to_a_key_is_not_a_key(self):
        self.assertNotIn("credential-file", self.file_categories("certs/server.pem", b"../shared/server.pem"))

    def test_npmrc_needs_a_literal_token(self):
        literal = b"//registry.npmjs.org/:_authToken=" + b"npm_" + b"a1" * 15 + b"\n"
        self.assertIn("credential-file", self.file_categories(".npmrc", literal))
        self.assertNotIn("credential-file", self.file_categories(".npmrc", b"//r.org/:_authToken=${NPM_TOKEN}\n"))

    def test_certificate_only_pem_is_low(self):
        data = b"-----BEGIN " + b"CERTIFICATE-----\nMIIB\n-----END " + b"CERTIFICATE-----\n"
        self.assertEqual(self.file_categories("ca.pem", data)["credential-file"]["severity"], "low")

    def test_personal_files(self):
        for name in ("contrat_bail.pdf", "docs/Facture-2024.pdf", "cv.pdf", "my resume.docx", "passport.jpg",
                     "RIB.png", "fiche de paie.pdf", "bulletin_de_salaire.pdf", "avis-d-imposition.pdf"):
            with self.subTest(name=name):
                self.assertIn("personal-file", self.file_categories(name, None))
        for name in ("cv2.png", "readme.pdf", "contract.py", "invoices.md", "screenshot.png"):
            with self.subTest(name=name):
                self.assertNotIn("personal-file", self.file_categories(name, None))

    def test_office_text_is_extracted_and_raises_severity(self):
        plain = self.file_categories("resume.docx", make_docx("Skills: python and git"))
        self.assertEqual(plain["personal-file"]["severity"], "medium")
        pii = self.file_categories("resume.docx", make_docx("Contact %s or +33 6 12 34 56 78" % fx.REAL_EMAIL))
        self.assertEqual(pii["personal-file"]["severity"], "high")
        self.assertIn("email", pii)
        contract = self.file_categories("lease.docx", make_docx("Contrat de location"))
        self.assertNotIn("personal-file", contract)
        self.assertEqual(self.file_categories("contrat.docx", make_docx("Contrat de location"))["personal-file"][
            "severity"], "high")

    def test_large_blob(self):
        found = self.file_categories("data.bin", None, size=6 * 1048576)
        self.assertEqual(found["large-blob"]["severity"], "low")
        self.assertNotIn("large-blob", self.file_categories("data.bin", None, size=1048576))

    def test_personal_term_in_a_file_name(self):
        terms = [("--terms", ["zorglub"], False)]
        found = self.file_categories("notes/zorglub-todo.txt", b"nothing\n", terms=terms)
        self.assertIn("personal-name", found)


class PhotoTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(scan, "count_faces", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def photo(self, path, data):
        return {h["category"]: h for h in scanner().file_hits(path, data, "working-tree", len(data))}

    def test_gps_makes_a_high_photo_location(self):
        found = self.photo("trip/img.jpg", make_jpeg(exif_tiff(gps=True)))
        self.assertEqual(found["photo-location"]["severity"], "high")
        self.assertNotIn("photo", found)

    def test_camera_metadata_is_medium(self):
        found = self.photo("a.jpeg", make_jpeg(exif_tiff(gps=False)))
        self.assertEqual(found["photo"]["severity"], "medium")
        self.assertIn("face detection unavailable", found["photo"]["detail"])

    def test_jpeg_without_exif_is_low(self):
        self.assertEqual(self.photo("hero.jpg", make_jpeg())["photo"]["severity"], "low")

    def test_tiff_and_heic(self):
        self.assertEqual(self.photo("scan.tif", exif_tiff(gps=True))["photo-location"]["severity"], "high")
        self.assertEqual(self.photo("IMG_0001.HEIC", b"\0\0\0\x18ftypheic")["photo"]["severity"], "medium")

    def test_png_only_with_exif(self):
        plain = b"\x89PNG\r\n\x1a\n" + struct.pack(">I4s", 0, b"IEND") + b"\0\0\0\0"
        self.assertEqual(self.photo("logo.png", plain), {})
        tiff = exif_tiff(gps=True)
        with_exif = b"\x89PNG\r\n\x1a\n" + struct.pack(">I4s", len(tiff), b"eXIf") + tiff + b"\0\0\0\0"
        self.assertEqual(self.photo("shot.png", with_exif)["photo-location"]["severity"], "high")

    def test_screenshot_metadata_is_low_not_medium(self):
        shot = make_png((b"eXIf", screenshot_tiff()))
        found = self.photo("Screenshot 2026-10-15.png", shot)
        self.assertEqual(found["photo"]["severity"], "low")
        self.assertIn("without camera make or model", found["photo"]["detail"])
        self.assertEqual(self.photo("shot.jpg", make_jpeg(screenshot_tiff()))["photo"]["severity"], "low")
        xmp = make_png(xmp_chunk({"exif:PixelXDimension": "1440", "exif:PixelYDimension": "900",
                                  "exif:UserComment": "Screenshot"}))
        self.assertEqual(self.photo("shot2.png", xmp)["photo"]["severity"], "low")

    def test_camera_make_or_model_in_xmp_is_medium_and_gps_stays_high(self):
        camera = make_png(xmp_chunk({"tiff:Make": "Acme", "tiff:Model": "Z1"}))
        self.assertEqual(self.photo("cam.png", camera)["photo"]["severity"], "medium")
        located = make_png(xmp_chunk({"tiff:Make": "Acme", "exif:GPSLatitude": "48,51.4N",
                                      "exif:GPSLongitude": "2,17.6E"}))
        found = self.photo("trip.png", located)
        self.assertEqual(found["photo-location"]["severity"], "high")
        self.assertNotIn("photo", found)

    def test_faces_make_a_high_photo_person(self):
        with mock.patch.object(scan, "count_faces", return_value=2):
            found = self.photo("team.jpg", make_jpeg())
        self.assertEqual(found["photo-person"]["severity"], "high")
        self.assertIn("2 face(s)", found["photo-person"]["detail"])

    def test_pillow_is_used_when_importable(self):
        class FakeExif(dict):
            def get_ifd(self, tag):
                return {1: 2}

        class FakeImage:
            def getexif(self):
                return FakeExif({0x010F: "Acme"})

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        image_module = mock.Mock(open=mock.Mock(return_value=FakeImage()))
        pil = mock.Mock(Image=image_module)
        with mock.patch.dict(sys.modules, {"PIL": pil, "PIL.Image": image_module}):
            info = scan.exif_info(b"not a real image", ".jpg")
        self.assertEqual(info, {"make": "Acme", "model": None, "gps": True})

    def test_image_cap(self):
        instance = scanner()
        instance.counts["images"] = scan.IMAGE_CAP
        found = instance.file_hits("x.jpg", make_jpeg(), "working-tree", 10)
        self.assertEqual(found[0]["severity"], "low")
        self.assertIn("cap", found[0]["detail"])


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        fx.patch_identity(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = fx.make_repo(self.tmp.name)

    def security(self, *extra):
        return fx.run_cli(scan, ["security", str(self.repo.path), "--no-remote"] + list(extra))

    def test_secret_deleted_from_head_is_found_in_history(self):
        self.repo.commit("add config", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        self.repo.commit("remove it", {"app.py": "KEY = None\n"})
        code, data, text = self.security()
        self.assertEqual(code, 4)
        secrets = [f for f in data["findings"] if f["category"] == "secret"]
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["where"], "history")
        self.assertEqual(secrets[0]["path"], "app.py")
        self.assertEqual(secrets[0]["line"], 1)
        self.assertTrue(secrets[0]["commit"])
        self.assertIn("rewrite-history", secrets[0]["remedy"])
        code, data, _ = self.security("--no-history")
        self.assertEqual(code, 0)
        self.assertEqual(data["findings"], [])

    def test_secret_in_the_working_tree(self):
        self.repo.commit("add", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        _, data, _ = self.security()
        self.assertEqual({f["where"] for f in data["findings"] if f["category"] == "secret"}, {"working-tree"})
        self.assertEqual(len([f for f in data["findings"] if f["category"] == "secret"]), 1)

    def test_raw_values_never_reach_stdout_or_report(self):
        value = fx.ANTHROPIC
        self.repo.commit("add", {"app.py": 'KEY = "%s"\nmail = "%s"\n' % (value, fx.REAL_EMAIL),
                                 ".env": "TOKEN=" + "abc123def456\n"},
                         author="Dev <%s>" % fx.REAL_EMAIL)
        self.repo.commit("msg with %s" % fx.GITHUB)
        code, data, text = self.security()
        self.assertEqual(code, 4)
        report = Path(data["report"])
        self.assertTrue(report.exists())
        self.assertEqual(stat.S_IMODE(report.stat().st_mode), 0o600)
        for raw in (value, fx.REAL_EMAIL, fx.GITHUB, "abc123def456"):
            self.assertNotIn(raw, text)
            self.assertNotIn(raw, report.read_text())
        self.assertGreaterEqual(data["summary"]["high"], 3)
        self.assertIn("secret", data["summary"]["by_category"])

    def test_occurrences_are_capped_and_limit_applies(self):
        files = {"f%d.txt" % i: "key: %s\n" % fx.ANTHROPIC for i in range(8)}
        files["other.txt"] = "mail %s\n" % fx.REAL_EMAIL
        self.repo.commit("many", files)
        _, data, _ = self.security()
        secret = [f for f in data["findings"] if f["category"] == "secret"][0]
        self.assertEqual(secret["occurrences_total"], 8)
        self.assertEqual(len(secret["occurrences"]), 5)
        _, data, _ = self.security("--limit", "1")
        self.assertEqual(len(data["findings"]), 1)
        self.assertEqual(data["truncated"], 1)
        report = json.loads(Path(data["report"]).read_text())
        self.assertEqual(len(report["findings"]), 2)

    def test_identities_terms_and_messages(self):
        self.repo.commit("work by zorglub", {"a.txt": "hello\n"}, author="Zorglub Q <9+z@users.noreply.github.com>")
        self.repo.commit("second", {"b.txt": "hi\n"}, author="Dev <%s>" % fx.REAL_EMAIL)
        _, data, text = self.security("--terms", "zorglub")
        found = {(f["category"], o["where"]) for f in data["findings"] for o in f["occurrences"]}
        self.assertIn(("personal-name", "identity"), found)
        self.assertIn(("personal-name", "commit-message"), found)
        self.assertIn(("email", "identity"), found)
        self.assertEqual(data["summary"]["term_sources"], {"--terms": 1})
        self.assertNotIn("zorglub", text.lower().replace("personal-name", ""))
        email = [f for f in data["findings"] if f["category"] == "email"][0]
        self.assertIn("mailmap", email["remedy"])
        self.assertNotIn("redact-head", email["remedy"])

    def test_allowlist_command_suppresses_and_restores(self):
        self.repo.commit("add", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        _, data, _ = self.security()
        fingerprint = data["findings"][0]["fingerprint"]
        code, out, _ = fx.run_cli(scan, ["allow", str(self.repo.path), fingerprint])
        self.assertEqual((code, out["allowed"]), (0, 1))
        code, data, _ = self.security()
        self.assertEqual((code, data["findings"]), (0, []))
        fx.run_cli(scan, ["allow", str(self.repo.path), fingerprint, "--remove"])
        code, data, _ = self.security()
        self.assertEqual(code, 4)

    def test_photo_with_gps_deleted_from_head_is_found_in_history(self):
        with mock.patch.object(scan, "count_faces", return_value=None):
            self.repo.commit("add photo", {"img/trip.jpg": make_jpeg(exif_tiff(gps=True)), "k.txt": "x\n"})
            self.repo.commit("remove photo", remove=["img/trip.jpg"])
            _, data, _ = self.security()
        found = [f for f in data["findings"] if f["category"] == "photo-location"]
        self.assertEqual([(f["severity"], f["where"], f["path"]) for f in found],
                         [("high", "history", "img/trip.jpg")])
        self.assertNotIn("untrack", found[0]["remedy"])

    def test_office_document_in_history(self):
        self.repo.commit("add", {"docs/cv.docx": make_docx("Contact %s" % fx.REAL_EMAIL)})
        self.repo.commit("remove", remove=["docs/cv.docx"])
        _, data, text = self.security()
        by_category = {f["category"]: f for f in data["findings"]}
        self.assertEqual(by_category["personal-file"]["severity"], "high")
        self.assertEqual(by_category["personal-file"]["where"], "history")
        self.assertEqual(by_category["email"]["path"], "docs/cv.docx")
        self.assertNotIn(fx.REAL_EMAIL, text)

    def test_tagger_identity_and_tag_message(self):
        self.repo.commit("work", {"a.txt": "x\n"})
        self.repo.git("tag", "-a", "v1", "-m", "release\n\n" + fx.AI_TRAILER,
                      env={"GIT_COMMITTER_NAME": "Tagger", "GIT_COMMITTER_EMAIL": fx.REAL_EMAIL})
        _, data, text = self.security()
        emails = [f for f in data["findings"] if f["category"] == "email"]
        self.assertEqual([(f["where"], "tagger" in f["detail"]) for f in emails], [("identity", True)])
        self.assertNotIn(fx.REAL_EMAIL, text)
        _, data, _ = self.attribution()
        self.assertEqual([f["category"] for f in data["findings"]], ["ai-coauthor"])

    def attribution(self):
        return fx.run_cli(scan, ["attribution", str(self.repo.path), "--no-remote"])

    def test_ignore_marker_in_a_file(self):
        self.repo.commit("add", {"app.py": 'KEY = "%s"  # showcase: ignore\n' % fx.ANTHROPIC})
        code, data, _ = self.security()
        self.assertEqual((code, data["findings"]), (0, []))

    def test_tracked_credential_file_and_untracked_is_ignored(self):
        self.repo.commit("add", {"deploy/id_rsa": "x\n", ".env.example": "A=1\n"})
        self.repo.write(".env", "TOKEN=" + "abc123def456\n")
        _, data, _ = self.security()
        self.assertEqual({f["category"] for f in data["findings"]}, {"credential-file"})

    def test_bare_clone_is_scanned(self):
        self.repo.commit("add", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        bare = Path(self.tmp.name) / "bare.git"
        self.repo.git("clone", "-q", "--bare", str(self.repo.path), str(bare))
        result = scan.scan_repo(bare, history=True)
        self.assertTrue(any(f["category"] == "secret" for f in result["findings"]))

    def test_scan_repo_api_shape(self):
        self.repo.commit("add", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        result = scan.scan_repo(self.repo.path, history=True, terms=None, include_remote=False)
        self.assertEqual(set(result), {"findings", "summary"})
        for key in ("high", "medium", "low", "info", "by_category"):
            self.assertIn(key, result["summary"])
        self.assertNotIn("_value", result["findings"][0])
        raw = scan.scan_repo(self.repo.path, raw=True)
        self.assertEqual(raw["findings"][0]["_value"], fx.ANTHROPIC)

    def test_empty_repository(self):
        code, data, _ = self.security()
        self.assertEqual((code, data["findings"]), (0, []))

    def test_not_a_repository(self):
        code, data, _ = fx.run_cli(scan, ["security", self.tmp.name])
        self.assertEqual(code, 3)

    def test_gitleaks_results_are_merged_when_installed(self):
        secret = "Zz9" * 8
        self.repo.commit("add", {"x.txt": "token is %s\n" % secret})
        fake = Path(self.tmp.name) / "bin"
        fake.mkdir()
        script = fake / "gitleaks"
        script.write_text("#!/usr/bin/env python3\nimport json, sys\npath = sys.argv[sys.argv.index('--report-path') "
                          "+ 1]\njson.dump([{'RuleID': 'fake-rule', 'File': 'x.txt', 'StartLine': 1, 'Commit': '', "
                          "'Secret': %r}], open(path, 'w'))\n" % secret)
        script.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(fake) + os.pathsep + os.environ["PATH"]}):
            code, data, text = self.security()
        self.assertEqual(code, 4)
        self.assertTrue(any("fake-rule" in (f.get("detail") or "") for f in data["findings"]))
        self.assertNotIn(secret, text)
        self.assertFalse(list((self.repo.path / ".git" / "repo-showcase").glob("gitleaks-*")))


class AttributionTests(unittest.TestCase):
    def setUp(self):
        fx.patch_identity(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = fx.make_repo(self.tmp.name)

    def attribution(self, *extra):
        return fx.run_cli(scan, ["attribution", str(self.repo.path)] + list(extra))

    def test_trailer_in_a_commit_message(self):
        self.repo.commit("feature\n\n" + fx.AI_TRAILER, {"a.txt": "x\n"})
        code, data, _ = self.attribution("--no-remote")
        self.assertEqual(code, 4)
        found = data["findings"][0]
        self.assertEqual((found["category"], found["severity"], found["where"]), ("ai-coauthor", "high",
                                                                                  "commit-message"))
        self.assertEqual(found["remedy"], ["strip-messages", "rewrite-history"])
        self.assertTrue(found["commit"])

    def test_generated_lines_in_messages_and_files(self):
        self.repo.commit("fix\n\n" + fx.AI_GENERATED, {"NOTES.md": "intro\n" + fx.AI_GENERATED + "\n"})
        _, data, _ = self.attribution("--no-remote")
        places = {f["where"] for f in data["findings"] if f["category"] == "ai-coauthor"}
        self.assertEqual(places, {"commit-message", "working-tree"})
        tree = [f for f in data["findings"] if f["where"] == "working-tree"][0]
        self.assertEqual((tree["path"], tree["line"], tree["remedy"]), ("NOTES.md", 2, ["redact-head"]))

    def test_other_phrasings(self):
        message = "x\n\nGenerated-" + "by: some tool\nAssisted-" + "by: another\n\U0001F916 Generated with a tool\n"
        self.repo.commit(message, {"a.txt": "x\n"})
        self.repo.commit("aider: add parser", {"b.txt": "y\n"})
        self.repo.commit("w\n\nCo-authored-by: Copilot <1+Copilot@users.noreply.github.com>", {"c.txt": "z\n"})
        _, data, _ = self.attribution("--no-remote")
        labels = {f["preview"] for f in data["findings"] if f["category"] == "ai-coauthor"}
        self.assertIn("Generated-by or Assisted-by trailer", labels)
        self.assertIn("robot Generated line", labels)
        self.assertIn("aider: subject prefix", labels)
        self.assertIn("Co-authored-by trailer", labels)

    def test_product_mentions_and_human_coauthors_are_not_flagged(self):
        self.repo.commit("Add a skill for Claude Code hooks\n\nSupports Copilot and Cursor users.\n\n"
                         "Co-authored-by: Claude Dupont <claude@dupont.example>\n"
                         "Co-authored-by: Jane Roe <jane@example.com>",
                         {"README.md": "A skill for Claude Code. Works with GitHub Copilot and Cursor.\n"
                                       "Generated documents live in docs/.\n"})
        code, data, _ = self.attribution("--no-remote")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_ai_bot_identities(self):
        self.repo.commit("bot change", {"a.txt": "x\n"}, author="Copilot <1+Copilot@users.noreply.github.com>")
        self.repo.commit("human", {"b.txt": "y\n"}, author="Claude Dupont <claude.dupont@free.example>")
        _, data, _ = self.attribution("--no-remote")
        authors = [f for f in data["findings"] if f["category"] == "ai-author"]
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0]["severity"], "medium")
        self.assertIn("mailmap", authors[0]["remedy"])
        self.assertEqual(scan.ai_identity("dependabot[bot]", "1+dependabot[bot]@users.noreply.github.com"), None)
        self.assertEqual(scan.ai_identity("Claude", "noreply@" + "anthropic.com"), "claude")

    def test_ai_config_files_are_info_only(self):
        self.repo.commit("cfg", {"CLAUDE.md": "rules\n", ".claude/settings.json": "{}\n", ".cursor/rules/a.mdc": "r\n"})
        code, data, _ = self.attribution("--no-remote")
        self.assertEqual(code, 0)
        self.assertEqual({f["category"] for f in data["findings"]}, {"ai-config-file"})
        self.assertEqual({f["severity"] for f in data["findings"]}, {"info"})
        self.assertEqual(len(data["findings"]), 3)

    def test_pull_requests_and_releases_are_scanned_through_gh(self):
        self.repo.commit("init", {"a.txt": "x\n"})
        self.repo.git("remote", "add", "origin", "https://github.com/acme/widgets.git")
        prs = [{"number": 7, "title": "Add parser", "body": "Details\n\n" + fx.AI_GENERATED, "url": "u7"},
               {"number": 8, "title": "Plain", "body": "nothing special", "url": "u8"}]
        releases = [{"id": 5, "tag_name": "v1", "body": fx.AI_TRAILER, "html_url": "r5"}]
        with mock.patch.object(scan, "fetch_pull_requests", return_value=prs) as fetch_prs, \
                mock.patch.object(scan, "fetch_releases", return_value=releases):
            code, data, _ = self.attribution()
            self.assertEqual(code, 4)
            self.assertEqual(data["summary"]["remote"], "ok")
            wheres = {f["where"]: f for f in data["findings"]}
            self.assertEqual(wheres["pull-request"]["remedy"], ["edit-pr"])
            self.assertIn("PR #7", wheres["pull-request"]["detail"])
            self.assertEqual(wheres["release"]["remedy"], ["edit-pr"])
            fetch_prs.reset_mock()
            code, data, _ = self.attribution("--no-remote")
            fetch_prs.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(data["summary"]["remote"], "disabled")

    def test_remote_failure_is_reported_not_fatal(self):
        self.repo.commit("init", {"a.txt": "x\n"})
        self.repo.git("remote", "add", "origin", "https://github.com/acme/widgets.git")
        with mock.patch.object(scan, "fetch_pull_requests", side_effect=scan.Failure(5, "gh missing")):
            code, data, _ = self.attribution()
        self.assertEqual(code, 0)
        self.assertTrue(data["summary"]["remote"].startswith("skipped"))

    def test_allow_applies_to_attribution(self):
        self.repo.commit("x\n\n" + fx.AI_TRAILER, {"a.txt": "x\n"})
        _, data, _ = self.attribution("--no-remote")
        fx.run_cli(scan, ["allow", str(self.repo.path), data["findings"][0]["fingerprint"]])
        code, data, _ = self.attribution("--no-remote")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_strip_ai_text(self):
        cleaned, removed = scan.strip_ai_text("Fix bug\n\nDetails\n\n" + fx.AI_TRAILER + "\n" + fx.AI_GENERATED + "\n")
        self.assertEqual(cleaned, "Fix bug\n\nDetails\n")
        self.assertEqual(len(removed), 2)
        self.assertEqual(scan.strip_ai_text("Nothing here\n"), ("Nothing here\n", []))


if __name__ == "__main__":
    unittest.main()
