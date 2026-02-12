"""Tests for bounded chat history pruning behavior."""

from langchain_core.messages import AIMessage, HumanMessage

from src.bounded_history import BoundedChatHistory


def test_under_limit_no_prune():
    h = BoundedChatHistory(max_messages=10)
    h.add_message(HumanMessage(content="hi"))
    h.add_message(AIMessage(content="hello"))
    assert len(h.messages) == 2


def test_prune_at_limit():
    h = BoundedChatHistory(max_messages=4)
    h.add_message(HumanMessage(content="msg1"))
    h.add_message(AIMessage(content="resp1"))
    h.add_message(HumanMessage(content="msg2"))
    h.add_message(AIMessage(content="resp2"))
    # At limit -- no prune yet
    assert len(h.messages) == 4

    # Adding one more triggers prune
    h.add_message(HumanMessage(content="msg3"))
    assert len(h.messages) <= 4
    # Newest preserved
    assert h.messages[-1].content == "msg3"


def test_prune_removes_pairs():
    h = BoundedChatHistory(max_messages=4)
    for i in range(6):
        h.add_message(HumanMessage(content=f"user-{i}"))
        h.add_message(AIMessage(content=f"ai-{i}"))
    # Should have at most 4 messages
    assert len(h.messages) <= 4
    # Most recent messages should be preserved
    contents = [m.content for m in h.messages]
    assert "ai-5" in contents


def test_empty_history():
    h = BoundedChatHistory(max_messages=50)
    assert len(h.messages) == 0


def test_single_message():
    h = BoundedChatHistory(max_messages=2)
    h.add_message(HumanMessage(content="just one"))
    assert len(h.messages) == 1
