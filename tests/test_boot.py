"""The app must boot with no .env and no secrets, as on a fresh Railway service."""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_app_imports_with_empty_environment(tmp_path: Path) -> None:
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(REPO_ROOT)}

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=tmp_path,  # no .env here for pydantic-settings to pick up
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
