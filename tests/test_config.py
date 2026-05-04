from pathlib import Path

from app.config import resolve_data_dir, resolve_playwright_browsers_path


def test_data_dir_uses_local_data_folder_by_default():
    assert resolve_data_dir(Path("/home/app/project"), {}) == Path("/home/app/project/data")


def test_data_dir_uses_tmp_for_lambda_bundle_path():
    assert resolve_data_dir(Path("/var/task"), {}) == Path("/tmp/arbitragebot/data")


def test_data_dir_uses_env_override():
    assert resolve_data_dir(Path("/var/task"), {"DATA_DIR": "/custom/data"}) == Path("/custom/data")


def test_playwright_browser_path_uses_project_folder_in_serverless():
    assert resolve_playwright_browsers_path(Path("/var/task"), {}) == Path("/var/task/app/playwright-browsers")


def test_playwright_browser_path_uses_env_override():
    assert resolve_playwright_browsers_path(
        Path("/var/task"),
        {"PLAYWRIGHT_BROWSERS_PATH": "/custom/browsers"},
    ) == Path("/custom/browsers")


def test_playwright_browser_path_is_default_cache_locally():
    assert resolve_playwright_browsers_path(Path("/home/app/project"), {}) is None
