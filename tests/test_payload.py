import unittest

from nodestrap.payload import (
    AUTHORIZED_KEYS_BEGIN,
    AUTHORIZED_KEYS_END,
    describe_plan_steps,
    render_password_disable_payload,
    render_remote_payload,
)
from nodestrap.plan import HostPlan, ManagedUserPlan, PublicKeyPlan


class PayloadTests(unittest.TestCase):
    def test_remote_payload_manages_keys_and_validates_sudoers(self):
        plan = HostPlan(
            host="node.example.com",
            connect_user="admin",
            users=("rion",),
            managed_users=(
                ManagedUserPlan(
                    name="rion",
                    username="rion",
                    public_keys=(
                        PublicKeyPlan(
                            name="home",
                            file="home.pub",
                            value="ssh-ed25519 AAAA home",
                        ),
                    ),
                ),
            ),
            ssh_port=22,
            disable_password_auth=True,
        )

        payload = render_remote_payload(plan)

        self.assertIn("adduser --disabled-password --gecos '' rion", payload)
        self.assertIn(AUTHORIZED_KEYS_BEGIN, payload)
        self.assertIn("ssh-ed25519 AAAA home", payload)
        self.assertIn(AUTHORIZED_KEYS_END, payload)
        self.assertIn("visudo -cf \"$tmp_sudoers\"", payload)
        self.assertNotIn("PasswordAuthentication no", payload)

    def test_password_disable_payload_is_separate_post_verification_step(self):
        user = ManagedUserPlan(
            name="rion",
            username="rion",
            public_keys=(),
        )

        payload = render_password_disable_payload(user)

        self.assertIn("Match User %s", payload)
        self.assertIn("PasswordAuthentication no", payload)
        self.assertIn("sshd -t", payload)

    def test_describe_plan_steps_mentions_post_verification_disable(self):
        plan = HostPlan(
            host="node.example.com",
            connect_user="admin",
            users=("rion",),
            managed_users=(
                ManagedUserPlan(
                    name="rion",
                    username="rion",
                    public_keys=(),
                ),
            ),
            ssh_port=22,
            disable_password_auth=True,
        )

        steps = describe_plan_steps(plan)

        self.assertIn("test key-based login for rion", steps)
        self.assertIn("disable password SSH for rion after key login succeeds", steps)


if __name__ == "__main__":
    unittest.main()
