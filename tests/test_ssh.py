import unittest

from nodestrap.plan import HostPlan
from nodestrap.ssh import build_key_login_test_command, build_scp_command, build_ssh_command, ssh_target


class SshCommandTests(unittest.TestCase):
    def test_builds_ssh_target_with_connect_user(self):
        plan = HostPlan(
            host="node.example.com",
            connect_user="admin",
            users=(),
            managed_users=(),
            ssh_port=2222,
            disable_password_auth=True,
        )

        self.assertEqual("admin@node.example.com", ssh_target(plan))
        self.assertEqual("rion@node.example.com", ssh_target(plan, user="rion"))

    def test_builds_ssh_and_scp_commands(self):
        plan = HostPlan(
            host="node.example.com",
            connect_user="admin",
            users=(),
            managed_users=(),
            ssh_port=2222,
            disable_password_auth=True,
        )

        ssh = build_ssh_command(plan, "bash /tmp/nodestrap.sh", batch_mode=True)
        scp = build_scp_command(plan, "payload.sh", "/tmp/nodestrap.sh")
        login_test = build_key_login_test_command(plan, "rion")

        self.assertEqual(
            ("ssh", "-p", "2222", "-o", "BatchMode=yes", "admin@node.example.com", "bash /tmp/nodestrap.sh"),
            ssh.argv,
        )
        self.assertEqual(
            ("scp", "-P", "2222", "payload.sh", "admin@node.example.com:/tmp/nodestrap.sh"),
            scp.argv,
        )
        self.assertEqual(
            ("ssh", "-p", "2222", "-o", "BatchMode=yes", "rion@node.example.com", "true"),
            login_test.argv,
        )


if __name__ == "__main__":
    unittest.main()

