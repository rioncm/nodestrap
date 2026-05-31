from pathlib import Path
import tempfile
import unittest

from nodestrap.config import ConfigError
from nodestrap.keys import discover_public_keys, key_name_from_path, read_public_key


class KeyTests(unittest.TestCase):
    def test_reads_supported_public_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "id_ed25519.pub"
            key.write_text("ssh-ed25519 AAAATEST user@example\n", encoding="utf-8")

            value = read_public_key(key)

        self.assertEqual("ssh-ed25519 AAAATEST user@example", value)

    def test_rejects_invalid_public_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "bad.pub"
            key.write_text("not-a-key\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                read_public_key(key)

    def test_discovers_public_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh_dir = Path(tmp)
            (ssh_dir / "id_ed25519.pub").write_text("ssh-ed25519 AAAA\n", encoding="utf-8")
            (ssh_dir / "id_ed25519").write_text("secret", encoding="utf-8")

            discovered = discover_public_keys(ssh_dir)

        self.assertEqual(["id_ed25519.pub"], [path.name for path in discovered])

    def test_key_name_from_path_is_config_friendly(self):
        self.assertEqual("id_ed25519_work", key_name_from_path(Path("id_ed25519-work.pub")))


if __name__ == "__main__":
    unittest.main()

