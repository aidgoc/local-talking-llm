"""Tests for src/rlm_client.py — all external RLM calls are mocked."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.rlm_client import RLMClient, _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rlm_mock(response_text="hello"):
    """Return a mock RLM instance whose .completion() returns response_text."""
    mock = MagicMock()
    mock.completion.return_value = SimpleNamespace(response=response_text)
    return mock


# ---------------------------------------------------------------------------
# _build_prompt (static, no mocking needed)
# ---------------------------------------------------------------------------

def test_build_prompt_no_history():
    assert RLMClient._build_prompt("hi", None) == "hi"


def test_build_prompt_empty_history():
    assert RLMClient._build_prompt("hi", []) == "hi"


def test_build_prompt_with_history():
    history = [
        HumanMessage(content="what's the weather?"),
        AIMessage(content="It's sunny."),
    ]
    result = RLMClient._build_prompt("thanks", history)
    assert "[Previous conversation]" in result
    assert "User: what's the weather?" in result
    assert "Assistant: It's sunny." in result
    assert result.endswith("User: thanks")


def test_build_prompt_caps_at_ten_messages():
    history = [HumanMessage(content=f"msg{i}") for i in range(20)]
    result = RLMClient._build_prompt("new", history)
    # Only last 10 should appear
    assert "msg10" in result
    assert "msg0" not in result


# ---------------------------------------------------------------------------
# __init__ — ollama backend
# ---------------------------------------------------------------------------

@patch("src.rlm_client.RLM")
def test_init_ollama_backend(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "text_model": "gemma3"},
    }
    client = RLMClient(config)

    MockRLM.assert_called_once()
    call_kwargs = MockRLM.call_args.kwargs
    assert call_kwargs["backend"] == "openai"
    assert call_kwargs["backend_kwargs"]["base_url"] == "http://localhost:11434/v1"
    assert call_kwargs["backend_kwargs"]["model_name"] == "gemma3"
    assert call_kwargs["max_depth"] == 1
    assert call_kwargs["custom_system_prompt"] == _SYSTEM_PROMPT


@patch("src.rlm_client.RLM")
def test_init_ollama_strips_trailing_slash(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "ollama",
        "ollama": {"base_url": "http://localhost:11434/", "text_model": "gemma3"},
    }
    RLMClient(config)
    url = MockRLM.call_args.kwargs["backend_kwargs"]["base_url"]
    assert not url.endswith("//")
    assert url == "http://localhost:11434/v1"


@patch("src.rlm_client.RLM")
def test_init_auto_backend_uses_ollama_path(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "auto",
        "ollama": {"base_url": "http://localhost:11434", "text_model": "gemma3"},
    }
    RLMClient(config)
    assert MockRLM.call_args.kwargs["backend"] == "openai"


@patch("src.rlm_client.RLM")
def test_init_custom_max_depth(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "ollama",
        "ollama": {},
        "rlm": {"max_depth": 3},
    }
    RLMClient(config)
    assert MockRLM.call_args.kwargs["max_depth"] == 3


@patch("src.rlm_client.RLM")
def test_init_custom_system_prompt(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "ollama",
        "ollama": {},
        "rlm": {"system_prompt": "You are a pirate."},
    }
    RLMClient(config)
    assert MockRLM.call_args.kwargs["custom_system_prompt"] == "You are a pirate."


# ---------------------------------------------------------------------------
# __init__ — openrouter backend
# ---------------------------------------------------------------------------

@patch("src.rlm_client.RLM")
def test_init_openrouter_backend(MockRLM):
    MockRLM.return_value = _make_rlm_mock()
    config = {
        "backend": "openrouter",
        "openrouter": {
            "api_key": "sk-test",
            "text_model": "meta-llama/llama-3.3-70b-instruct:free",
        },
    }
    RLMClient(config)
    call_kwargs = MockRLM.call_args.kwargs
    assert call_kwargs["backend"] == "openrouter"
    assert call_kwargs["backend_kwargs"]["api_key"] == "sk-test"
    assert call_kwargs["backend_kwargs"]["model_name"] == "meta-llama/llama-3.3-70b-instruct:free"


@patch("src.rlm_client.RLM")
def test_init_openrouter_api_key_from_env(MockRLM, monkeypatch):
    MockRLM.return_value = _make_rlm_mock()
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key-123")
    config = {"backend": "openrouter", "openrouter": {}}
    RLMClient(config)
    assert MockRLM.call_args.kwargs["backend_kwargs"]["api_key"] == "env-key-123"


# ---------------------------------------------------------------------------
# get_response
# ---------------------------------------------------------------------------

@patch("src.rlm_client.RLM")
def test_get_response_no_history(MockRLM):
    mock_rlm = _make_rlm_mock("  hello world  ")
    MockRLM.return_value = mock_rlm
    client = RLMClient({"backend": "ollama", "ollama": {}})

    result = client.get_response("ping")
    assert result == "hello world"
    mock_rlm.completion.assert_called_once_with("ping")


@patch("src.rlm_client.RLM")
def test_get_response_with_history(MockRLM):
    mock_rlm = _make_rlm_mock("fine thanks")
    MockRLM.return_value = mock_rlm
    client = RLMClient({"backend": "ollama", "ollama": {}})

    history = [HumanMessage(content="how are you?"), AIMessage(content="great")]
    result = client.get_response("and you?", history)
    assert result == "fine thanks"
    prompt_used = mock_rlm.completion.call_args.args[0]
    assert "[Previous conversation]" in prompt_used
    assert "User: how are you?" in prompt_used


@patch("src.rlm_client.RLM")
def test_get_response_strips_whitespace(MockRLM):
    MockRLM.return_value = _make_rlm_mock("\n  trimmed \n")
    client = RLMClient({"backend": "ollama", "ollama": {}})
    assert client.get_response("x") == "trimmed"
