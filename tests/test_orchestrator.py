"""Tests for the keyword-based intent classifier (pure logic, no mocking)."""

from src.orchestrator import Orchestrator


def _classify(text: str) -> str:
    """Helper: classify text and return intent string."""
    orch = Orchestrator({})
    return orch.classify_intent(text)["intent"]


# -- Vision --

def test_vision_take_photo():
    assert _classify("take a photo of this") == "vision"


def test_vision_camera_keyword():
    assert _classify("open camera") == "vision"


def test_vision_what_do_you_see():
    assert _classify("what do you see") == "vision"


def test_vision_describe_this():
    assert _classify("describe this") == "vision"


# -- Search --

def test_search_search_for():
    assert _classify("search for python tutorials") == "search"


def test_search_weather():
    assert _classify("weather in London") == "search"


def test_search_latest_news():
    assert _classify("latest news about AI") == "search"


def test_search_price():
    assert _classify("current price of bitcoin") == "search"


# -- Tool --

def test_tool_remember():
    assert _classify("remember that my birthday is March 15") == "tool"


def test_tool_list_tasks():
    assert _classify("list my tasks") == "tool"


def test_tool_what_time():
    assert _classify("what time is it") == "tool"


def test_tool_where_am_i():
    assert _classify("where am i") == "tool"


def test_tool_create_task():
    assert _classify("create a task to buy groceries") == "tool"


def test_tool_mark_done():
    assert _classify("mark done buy milk") == "tool"


# -- System --

def test_system_exit():
    assert _classify("exit") == "system"


def test_system_quit():
    assert _classify("quit") == "system"


def test_system_shutdown():
    assert _classify("shut down") == "system"


def test_system_goodbye():
    assert _classify("goodbye") == "system"


# -- Chat (default) --

def test_chat_greeting():
    assert _classify("hello how are you") == "chat"


def test_chat_general_question():
    assert _classify("explain quantum computing") == "chat"


def test_chat_default():
    assert _classify("tell me a joke") == "chat"
