import contextlib
import io
import tempfile
from pathlib import Path
import unittest

from nodestrap.cli import main


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


if __name__ == "__main__":
    unittest.main()
