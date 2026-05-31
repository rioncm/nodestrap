import unittest
import tempfile
from pathlib import Path

from nodestrap.plan import build_host_plans


class PlanTests(unittest.TestCase):
    def test_builds_host_plan_with_defaults(self):
        plans = build_host_plans(
            [
                {
                    "host": "node.example.com",
                    "users": ["rion"],
                }
            ],
            {
                "connect_user": "admin",
                "ssh_port": 2222,
                "disable_password_auth": False,
            },
        )

        self.assertEqual(1, len(plans))
        self.assertEqual("node.example.com", plans[0].host)
        self.assertEqual("admin", plans[0].connect_user)
        self.assertEqual(("rion",), plans[0].users)
        self.assertEqual((), plans[0].managed_users)
        self.assertEqual(2222, plans[0].ssh_port)
        self.assertFalse(plans[0].disable_password_auth)

    def test_resolves_managed_users_and_public_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            keys_base = Path(tmp)
            (keys_base / "home.pub").write_text("ssh-ed25519 AAAA home\n", encoding="utf-8")
            plans = build_host_plans(
                [
                    {
                        "host": "node.example.com",
                        "users": ["rion"],
                    }
                ],
                config={
                    "keys": {
                        "home": {
                            "file": "home.pub",
                        },
                    },
                    "users": {
                        "rion": {
                            "username": "rion",
                            "public_keys": ["home"],
                        },
                    },
                },
                keys_base=keys_base,
            )

        self.assertEqual("rion", plans[0].managed_users[0].username)
        self.assertEqual("home", plans[0].managed_users[0].public_keys[0].name)
        self.assertEqual("ssh-ed25519 AAAA home", plans[0].managed_users[0].public_keys[0].value)


if __name__ == "__main__":
    unittest.main()
