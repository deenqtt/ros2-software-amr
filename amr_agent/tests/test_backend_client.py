"""Tests for backend_client.py's credentials handling. No network."""

import io
import logging
import sys
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend_client  # noqa: E402
from backend_client import BackendClient, BackendError  # noqa: E402

TOKEN = "s3cret-token-value"


class FakeResponse:
    headers = {}

    def __init__(self, body=b"{}"):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_client(monkeypatch, token):
    if token is None:
        monkeypatch.delenv("AMR_AGENT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("AMR_AGENT_TOKEN", token)
    return BackendClient("http://backend.test", "r1")


def test_header_present_when_token_set(monkeypatch):
    client = make_client(monkeypatch, TOKEN)
    with mock.patch.object(
        backend_client.urllib.request, "urlopen", return_value=FakeResponse()
    ) as urlopen:
        client.get_robot()
    request = urlopen.call_args.args[0]
    assert request.get_header("Authorization") == f"Bearer {TOKEN}"


def test_header_absent_when_token_unset(monkeypatch):
    client = make_client(monkeypatch, None)
    with mock.patch.object(
        backend_client.urllib.request, "urlopen", return_value=FakeResponse()
    ) as urlopen:
        client.get_robot()
    assert urlopen.call_args.args[0].get_header("Authorization") is None


def test_header_on_every_request_kind(monkeypatch):
    client = make_client(monkeypatch, TOKEN)
    with mock.patch.object(
        backend_client.urllib.request, "urlopen", return_value=FakeResponse()
    ) as urlopen:
        client.get_robot()
        client.report_run("run1", {"a": 1})
        client.download_map_file("m1", "yaml")
    assert urlopen.call_count == 3
    for call in urlopen.call_args_list:
        assert call.args[0].get_header("Authorization") == f"Bearer {TOKEN}"


def _http_error(code):
    return urllib.error.HTTPError("http://x", code, "no", {}, io.BytesIO(b"denied"))


def test_401_logs_once_without_token(monkeypatch, caplog):
    client = make_client(monkeypatch, TOKEN)
    with caplog.at_level(logging.DEBUG, logger="backend_client"):
        with mock.patch.object(
            backend_client.urllib.request, "urlopen", side_effect=_http_error(401)
        ):
            for _ in range(3):
                try:
                    client.get_robot()
                except BackendError as error:
                    assert error.status == 401
                    assert TOKEN not in str(error)
    refusals = [r for r in caplog.records if "refused agent credentials" in r.getMessage()]
    assert len(refusals) == 1
    assert "AMR_AGENT_TOKEN" in refusals[0].getMessage()
    assert TOKEN not in caplog.text


def test_403_logs_again_after_recovery(monkeypatch, caplog):
    client = make_client(monkeypatch, TOKEN)
    with caplog.at_level(logging.DEBUG, logger="backend_client"):
        with mock.patch.object(
            backend_client.urllib.request, "urlopen", side_effect=_http_error(403)
        ):
            try:
                client.get_robot()
            except BackendError:
                pass
        with mock.patch.object(
            backend_client.urllib.request, "urlopen", return_value=FakeResponse()
        ):
            client.get_robot()
        with mock.patch.object(
            backend_client.urllib.request, "urlopen", side_effect=_http_error(403)
        ):
            try:
                client.get_robot()
            except BackendError:
                pass
    refusals = [r for r in caplog.records if "refused agent credentials" in r.getMessage()]
    assert len(refusals) == 2
    assert TOKEN not in caplog.text
