import unittest

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
        self.assertEqual(2222, plans[0].ssh_port)
        self.assertFalse(plans[0].disable_password_auth)


if __name__ == "__main__":
    unittest.main()

