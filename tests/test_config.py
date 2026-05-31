from pathlib import Path
import tempfile
import unittest

from nodestrap.config import (
    add_key,
    add_host,
    add_user,
    empty_config,
    hosts_by_status,
    load_config,
    selected_hosts,
    set_defaults,
    validate_config,
    write_config,
)


class ConfigValidationTests(unittest.TestCase):
    def test_valid_config_has_no_issues(self):
        data = {
            "keys": {
                "home": {
                    "file": "home.pub",
                    "label": "Home",
                },
            },
            "users": {
                "rion": {
                    "username": "rion",
                    "public_keys": ["home"],
                },
            },
            "hosts": [
                {
                    "host": "node.example.com",
                    "status": "new",
                    "connect_user": "rion",
                    "users": ["rion"],
                    "completed_at": None,
                    "last_error": None,
                },
            ],
        }

        issues = validate_config(data)

        self.assertEqual([], issues)

    def test_reports_unknown_references_and_duplicate_hosts(self):
        data = {
            "defaults": {
                "connect_user": "bad user",
                "ssh_port": 70000,
                "disable_password_auth": "yes",
            },
            "keys": {},
            "users": {
                "rion": {
                    "username": "Rion",
                    "public_keys": ["missing_key"],
                },
            },
            "hosts": [
                {
                    "host": "node.example.com",
                    "status": "mystery",
                    "users": ["missing_user"],
                    "ssh_port": 0,
                    "disable_password_auth": "false",
                },
                {"host": "node.example.com", "status": "new", "users": ["rion"]},
            ],
        }

        messages = [issue.message for issue in validate_config(data)]

        self.assertIn("defaults.connect_user is not a valid account name: bad user", messages)
        self.assertIn("defaults.ssh_port must be an integer between 1 and 65535.", messages)
        self.assertIn("defaults.disable_password_auth must be a boolean.", messages)
        self.assertNotIn("defaults.public_key references unknown key: missing", messages)
        self.assertIn("users.rion.username is not a valid account name: Rion", messages)
        self.assertIn("users.rion references unknown key: missing_key", messages)
        self.assertIn("hosts[0].status is invalid: mystery", messages)
        self.assertIn("hosts[0].ssh_port must be an integer between 1 and 65535.", messages)
        self.assertIn("hosts[0].disable_password_auth must be a boolean.", messages)
        self.assertIn("hosts[0] references unknown user: missing_user", messages)
        self.assertIn("duplicate host entry: node.example.com", messages)

    def test_can_require_key_files_under_config_keys_dir(self):
        data = {
            "keys": {"home": {"file": "home.pub"}},
            "users": {},
            "hosts": [],
        }

        messages = [issue.message for issue in validate_config(data, keys_base=Path("/missing"))]

        self.assertIn("keys.home.file does not exist: home.pub", messages)


class ConfigMutationTests(unittest.TestCase):
    def test_set_defaults_and_add_key(self):
        data = empty_config()

        set_defaults(
            data,
            connect_user="admin",
            managed_user="rion",
            public_key="home",
            ssh_port=2222,
            disable_password_auth=False,
        )
        add_key(data, "home", file="home.pub", label="Home")

        self.assertEqual("admin", data["defaults"]["connect_user"])
        self.assertEqual("rion", data["defaults"]["managed_user"])
        self.assertEqual("home", data["defaults"]["public_key"])
        self.assertEqual(2222, data["defaults"]["ssh_port"])
        self.assertFalse(data["defaults"]["disable_password_auth"])
        self.assertEqual("Home", data["keys"]["home"]["label"])

    def test_default_public_key_must_reference_known_key(self):
        data = empty_config()
        data["defaults"]["public_key"] = "missing"

        messages = [issue.message for issue in validate_config(data)]

        self.assertIn("defaults.public_key references unknown key: missing", messages)

    def test_add_user_and_host_from_defaults(self):
        data = empty_config()
        data["defaults"]["connect_user"] = "admin"
        data["defaults"]["managed_user"] = "rion"

        add_user(data, "rion", public_keys=["prompt"])
        add_host(data, "node.example.com")

        self.assertEqual("admin", data["hosts"][0]["connect_user"])
        self.assertEqual(["rion"], data["hosts"][0]["users"])
        self.assertEqual([], validate_config(data))

    def test_groups_and_selects_hosts(self):
        data = {
            "hosts": [
                {"host": "a.example.com", "status": "new"},
                {"host": "b.example.com", "status": "retry"},
            ]
        }

        grouped = hosts_by_status(data)
        retry_hosts = selected_hosts(data, status="retry")

        self.assertEqual(["a.example.com"], grouped["new"])
        self.assertEqual(["b.example.com"], [host["host"] for host in retry_hosts])

    def test_write_and_load_generated_config_without_pyyaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nodestrap.yaml"
            data = empty_config()
            data["defaults"]["connect_user"] = "admin"

            write_config(path, data)
            loaded = load_config(path)

        self.assertEqual("admin", loaded["defaults"]["connect_user"])


if __name__ == "__main__":
    unittest.main()
