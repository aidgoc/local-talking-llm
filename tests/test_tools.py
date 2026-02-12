"""Tests for the tool system: fast-path routing + tool handlers."""

from src.tools import ToolExecutor


def test_fast_path_get_time(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._fast_path("what time is it")
    assert result is not None
    assert result["tool"] == "get_time"


def test_fast_path_get_location(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._fast_path("where am i")
    assert result is not None
    assert result["tool"] == "get_location"


def test_fast_path_list_tasks(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._fast_path("list my tasks")
    assert result is not None
    assert result["tool"] == "list_tasks"


def test_fast_path_list_memories(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._fast_path("show memories")
    assert result is not None
    assert result["tool"] == "list_memories"


def test_fast_path_no_match(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._fast_path("tell me about quantum physics")
    assert result is None


def test_handler_save_memory(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._save_memory({"key": "color", "value": "blue", "category": "preference"})
    assert "Saved" in result
    assert tmp_db.get_memory("color")["value"] == "blue"


def test_handler_recall_memory(tmp_db):
    tmp_db.save_memory("pet", "dog", "personal")
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._recall_memory({"query": "pet"})
    assert "pet" in result


def test_handler_list_memories_empty(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._list_memories({})
    assert "No memories" in result


def test_handler_delete_memory(tmp_db):
    tmp_db.save_memory("delme", "val", "general")
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._delete_memory({"key": "delme"})
    assert "Deleted" in result


def test_handler_create_task(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._create_task({"title": "Buy milk", "description": "", "priority": "high"})
    assert "Created task" in result


def test_handler_list_tasks_empty(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._list_tasks({})
    assert "No pending" in result


def test_handler_complete_task(tmp_db):
    tmp_db.create_task("Grocery", "", "normal")
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._complete_task({"title": "Grocery"})
    assert "Completed" in result


def test_handler_get_time(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    result = te._get_time({})
    assert "Current date and time" in result


def test_parse_tool_json(tmp_db):
    te = ToolExecutor(tmp_db, {"ollama": {}})
    # Direct JSON (full string is valid JSON)
    parsed = te._parse_tool_json('{"tool": "get_time", "params": {}}')
    assert parsed["tool"] == "get_time"
    # Direct JSON with params
    parsed = te._parse_tool_json('{"tool": "list_tasks", "params": {}}')
    assert parsed["tool"] == "list_tasks"
