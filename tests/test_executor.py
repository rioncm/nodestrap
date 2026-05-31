import tempfile
import unittest
from pathlib import Path

from nodestrap.executor import CommandResult, execute_host_plan
from nodestrap.plan import HostPlan, ManagedUserPlan, PublicKeyPlan


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run(self, argv, *, input_text=None):
        self.calls.append((argv, input_text))
        if not self.results:
            return CommandResult(returncode=0)
        return self.results.pop(0)


def _plan(disable_password_auth=True):
    return HostPlan(
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
        disable_password_auth=disable_password_auth,
    )


class ExecutorTests(unittest.TestCase):
    def test_success_runs_bootstrap_login_check_then_password_disable(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=0, stdout="bootstrapped"),
                CommandResult(returncode=0),
                CommandResult(returncode=0),
            ]
        )

        result = execute_host_plan(_plan(), runner=runner)

        self.assertTrue(result.succeeded)
        self.assertEqual("completed", result.status)
        self.assertEqual(3, len(runner.calls))
        self.assertEqual(("ssh", "-p", "22", "admin@node.example.com", "sudo -n sh -s"), runner.calls[0][0])
        self.assertIn("ssh-ed25519 AAAA home", runner.calls[0][1])
        self.assertEqual(("ssh", "-p", "22", "-o", "BatchMode=yes", "rion@node.example.com", "true"), runner.calls[1][0])
        self.assertIn("PasswordAuthentication no", runner.calls[2][1])

    def test_does_not_disable_password_auth_when_key_login_fails(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=0),
                CommandResult(returncode=255, stderr="permission denied"),
            ]
        )

        result = execute_host_plan(_plan(), runner=runner)

        self.assertFalse(result.succeeded)
        self.assertEqual("retry", result.status)
        self.assertIn("key login failed for rion", result.message)
        self.assertEqual(2, len(runner.calls))

    def test_sudo_password_is_passed_over_stdin(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=0),
                CommandResult(returncode=0),
            ]
        )

        result = execute_host_plan(_plan(disable_password_auth=False), runner=runner, sudo_password="secret")

        self.assertTrue(result.succeeded)
        self.assertEqual(("ssh", "-p", "22", "admin@node.example.com", "sudo -S -p '' sh -s"), runner.calls[0][0])
        self.assertTrue(runner.calls[0][1].startswith("secret\n#!/bin/sh"))

    def test_writes_redacted_log(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=1, stderr="Password was wrong\nplain detail"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)

            result = execute_host_plan(_plan(), runner=runner, log_dir=log_dir)
            logs = list(log_dir.glob("*.log"))
            content = logs[0].read_text(encoding="utf-8")

        self.assertFalse(result.succeeded)
        self.assertEqual(1, len(logs))
        self.assertIn("[redacted]", content)
        self.assertIn("plain detail", content)
        self.assertNotIn("Password was wrong", content)


if __name__ == "__main__":
    unittest.main()
