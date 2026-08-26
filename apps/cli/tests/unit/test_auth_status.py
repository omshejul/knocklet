import json

from auth import has_saved_session


def test_has_saved_session_accepts_li_at_cookie(tmp_path):
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text(json.dumps([{"name": "li_at", "value": "saved"}]))

    assert has_saved_session(cookies_file) is True


def test_has_saved_session_rejects_missing_or_invalid_file(tmp_path):
    cookies_file = tmp_path / "cookies.json"

    assert has_saved_session(cookies_file) is False

    cookies_file.write_text("not-json")
    assert has_saved_session(cookies_file) is False
