import contextlib
import io
import tempfile
from pathlib import Path
import unittest

from nodestrap.cli import main
from nodestrap.cli import _run
from nodestrap.config import load_config, write_config
from nodestrap.executor import CommandResult


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run(self, argv, *, input_text=None):
        self.calls.append((argv, input_text))
        if not self.results:
            return CommandResult(returncode=0)
        return self.results.pop(0)


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--version"])

        self.assertEqual(0, raised.exception.code)

    def test_run_requires_dry_run_until_executor_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "nodestrap.yaml"

            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--config", str(config), "run"])

        self.assertEqual(2, code)

    def test_dry_run_prints_resolved_plan_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "nodestrap.yaml"
            keys = root / "keys"
            keys.mkdir()
            (keys / "home.pub").write_text("ssh-ed25519 AAAA home\n", encoding="utf-8")
            write_config(
                config,
                {
                    "defaults": {
                        "connect_user": "admin",
                        "ssh_port": 22,
                        "disable_password_auth": True,
                    },
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
                    "hosts": [
                        {
                            "host": "node.example.com",
                            "status": "new",
                            "users": ["rion"],
                        },
                    ],
                },
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--config", str(config), "run", "--dry-run"])

        self.assertEqual(0, code)
        output = stdout.getvalue()
        self.assertIn("dry run: 1 host(s) selected", output)
        self.assertIn("connect_user=admin", output)
        self.assertIn("install 1 public key(s) for rion", output)
        self.assertIn("disable password SSH for rion after key login succeeds", output)

    def test_execute_updates_host_state_with_injected_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "nodestrap.yaml"
            keys = root / "keys"
            logs = root / "logs"
            keys.mkdir()
            (keys / "home.pub").write_text("ssh-ed25519 AAAA home\n", encoding="utf-8")
            write_config(
                config,
                {
                    "defaults": {
                        "connect_user": "admin",
                        "ssh_port": 22,
                        "disable_password_auth": False,
                    },
                    "keys": {"home": {"file": "home.pub"}},
                    "users": {"rion": {"username": "rion", "public_keys": ["home"]}},
                    "hosts": [{"host": "node.example.com", "status": "new", "users": ["rion"]}],
                },
            )
            runner = FakeRunner(
                [
                    CommandResult(returncode=0),
                    CommandResult(returncode=0),
                ]
            )

            with contextlib.redirect_stdout(io.StringIO()):
                code = _run(
                    config,
                    host=None,
                    status="new",
                    dry_run=False,
                    execute=True,
                    runner=runner,
                    log_dir=logs,
                )

            updated = load_config(config)

        self.assertEqual(0, code)
        self.assertEqual(2, len(runner.calls))
        self.assertEqual("completed", updated["hosts"][0]["status"])
        self.assertIsNone(updated["hosts"][0]["last_error"])


if __name__ == "__main__":
    unittest.main()
