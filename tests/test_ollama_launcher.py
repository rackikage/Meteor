"""Tests for Ollama launcher helpers."""

from __future__ import annotations

from unittest.mock import patch

from app.runtime import ollama_launcher as launcher


def test_is_ollama_running_true_on_200() -> None:
    class FakeResp:
        status = 200

    class FakeConn:
        def request(self, *_args, **_kwargs) -> None:
            return None

        def getresponse(self) -> FakeResp:
            return FakeResp()

        def close(self) -> None:
            return None

    with patch("app.runtime.ollama_launcher.http.client.HTTPConnection", return_value=FakeConn()):
        assert launcher.is_ollama_running() is True


def test_ensure_ollama_skips_when_already_running() -> None:
    launcher._we_started = False
    launcher._started_proc = None
    with patch("app.runtime.ollama_launcher.is_ollama_running", return_value=True):
        assert launcher.ensure_ollama_running() is True
    assert launcher._we_started is False
