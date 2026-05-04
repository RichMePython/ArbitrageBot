from pathlib import Path

from app.config import resolve_data_dir


def test_data_dir_uses_local_data_folder_by_default():
    assert resolve_data_dir(Path("/home/app/project"), {}) == Path("/home/app/project/data")


def test_data_dir_uses_tmp_for_lambda_bundle_path():
    assert resolve_data_dir(Path("/var/task"), {}) == Path("/tmp/arbitragebot/data")


def test_data_dir_uses_env_override():
    assert resolve_data_dir(Path("/var/task"), {"DATA_DIR": "/custom/data"}) == Path("/custom/data")

