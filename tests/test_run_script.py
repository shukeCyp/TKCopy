from pathlib import Path
import os
import subprocess
import tempfile
import textwrap
import unittest


class RunScriptTests(unittest.TestCase):
    def test_run_script_builds_static_frontend_without_dev_server(self):
        script = Path("run.sh").read_text(encoding="utf-8")

        self.assertIn("npm run build", script)
        self.assertIn("uv run python tkcopy/main.py", script)
        self.assertNotIn("npm run dev", script)
        self.assertNotIn("TKCOPY_FRONTEND_URL", script)
        self.assertNotIn("wait_for_frontend", script)
        self.assertNotIn("FRONTEND_PID", script)

    def test_run_script_builds_before_starting_pywebview(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            log_file = tmp_path / "commands.log"

            (bin_dir / "npm").write_text(
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    set -e
                    if [ "$1" = "install" ]; then
                        echo npm install >> "$TKCOPY_COMMAND_LOG"
                        exit 0
                    fi
                    if [ "$1" = "run" ] && [ "$2" = "build" ]; then
                        echo npm run build >> "$TKCOPY_COMMAND_LOG"
                        exit 0
                    fi
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            (bin_dir / "uv").write_text(
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    set -e
                    if [ "$1" = "sync" ]; then
                        echo uv sync >> "$TKCOPY_COMMAND_LOG"
                        exit 0
                    fi
                    if [ "$1" = "run" ]; then
                        echo uv run "$2" "$3" >> "$TKCOPY_COMMAND_LOG"
                        exit 0
                    fi
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(bin_dir / "npm", 0o755)
            os.chmod(bin_dir / "uv", 0o755)

            env = {
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "TKCOPY_COMMAND_LOG": str(log_file),
            }
            subprocess.run(["bash", "run.sh"], check=True, env=env)

            self.assertEqual(
                log_file.read_text(encoding="utf-8").splitlines(),
                ["uv sync", "npm install", "npm run build", "uv run python tkcopy/main.py"],
            )


if __name__ == "__main__":
    unittest.main()
