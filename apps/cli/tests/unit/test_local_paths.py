from pathlib import Path

from local_paths import local_data_dir


def test_local_data_dir_uses_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKEDIN_DATA_DIR", str(tmp_path / "Knocklet"))

    assert local_data_dir() == Path(tmp_path / "Knocklet")
