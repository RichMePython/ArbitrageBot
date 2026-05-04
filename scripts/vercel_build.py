from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
BROWSER_DIR = ROOT / "app" / "playwright-browsers"


def main() -> int:
    npm = resolve_executable("npm")
    run([npm, "install"], cwd=FRONTEND_DIR)
    run([npm, "run", "build"], cwd=FRONTEND_DIR)

    if should_install_browsers():
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSER_DIR)
        env.setdefault("PLAYWRIGHT_SKIP_BROWSER_GC", "1")
        run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT, env=env)
        run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=ROOT, env=env)

    return 0


def should_install_browsers() -> bool:
    value = os.getenv("INSTALL_PLAYWRIGHT_BROWSERS", "")
    return value.lower() in {"1", "true", "yes"}


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def resolve_executable(name: str) -> str:
    executable = shutil.which(name) or shutil.which(f"{name}.cmd")
    if not executable:
        raise RuntimeError(f"Could not find required executable: {name}")
    return executable


if __name__ == "__main__":
    raise SystemExit(main())
