"""Tests for the database layer."""

import os
import shutil
import tempfile


def test_save_and_get_memory(tmp_db):
    mid = tmp_db.save_memory("test_key", "test_value", "personal")
    assert mid > 0
    mem = tmp_db.get_memory("test_key")
    assert mem is not None
    assert mem["value"] == "test_value"
    assert mem["category"] == "personal"


def test_upsert_memory(tmp_db):
    mid1 = tmp_db.save_memory("test_key", "val1", "personal")
    mid2 = tmp_db.save_memory("test_key", "val2", "personal")
    assert mid2 == mid1
    assert tmp_db.get_memory("test_key")["value"] == "val2"


def test_search_memories(tmp_db):
    tmp_db.save_memory("color", "blue", "preference")
    results = tmp_db.search_memories("color")
    assert len(results) >= 1


def test_semantic_search_fallback(tmp_db):
    tmp_db.save_memory("color", "blue", "preference")
    results = tmp_db.semantic_search_memories("color")
    assert len(results) >= 1


def test_list_memories(tmp_db):
    tmp_db.save_memory("k1", "v1", "personal")
    tmp_db.save_memory("k2", "v2", "fact")
    assert len(tmp_db.list_memories()) >= 2
    assert len(tmp_db.list_memories(category="fact")) == 1


def test_delete_memory(tmp_db):
    tmp_db.save_memory("delme", "val", "general")
    assert tmp_db.delete_memory("delme")
    assert tmp_db.get_memory("delme") is None
    assert not tmp_db.delete_memory("nonexistent")


def test_create_and_list_tasks(tmp_db):
    tid = tmp_db.create_task("Buy milk", "At the store", "high")
    assert tid > 0
    tasks = tmp_db.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Buy milk"


def test_find_task_by_title(tmp_db):
    tmp_db.create_task("Buy milk", "", "normal")
    found = tmp_db.find_task_by_title("milk")
    assert found is not None
    assert found["title"] == "Buy milk"


def test_complete_task(tmp_db):
    tid = tmp_db.create_task("Task1", "", "normal")
    assert tmp_db.complete_task(tid)
    assert len(tmp_db.list_tasks("completed")) == 1
    assert len(tmp_db.list_tasks("pending")) == 0


def test_save_and_search_images(tmp_db):
    iid = tmp_db.save_image_meta("A desk", ["desk", "work"], "moondream")
    assert iid > 0
    imgs = tmp_db.list_images()
    assert len(imgs) == 1
    assert imgs[0]["tags"] == ["desk", "work"]
    assert len(tmp_db.search_images("desk")) == 1


def test_log_interaction(tmp_db):
    lid = tmp_db.log_interaction("hello", "chat", "Hi!", "ollama", "gemma3", 1.5)
    assert lid > 0


def test_sync_queue(tmp_db):
    tmp_db.queue_sync("memories", 1, "create", {"key": "test", "value": "val"})
    pending = tmp_db.get_pending_sync()
    assert len(pending) == 1
    tmp_db.mark_synced(pending[0]["id"])
    assert len(tmp_db.get_pending_sync()) == 0


def test_vector_store_integration():
    """Test semantic search with a real VectorStore attached."""
    try:
        from src.vector_store import VectorStore
    except ImportError:
        import pytest
        pytest.skip("zvec or sentence-transformers not installed")

    from src.database import DatabaseManager

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    vec_dir = tempfile.mkdtemp(prefix="zvec_test_")

    try:
        vs = VectorStore(path=vec_dir, model_name="all-MiniLM-L6-v2", device="cpu")
        if not vs.available:
            import pytest
            pytest.skip("zvec or sentence-transformers not available")

        db = DatabaseManager(db_path)
        db.init_db()
        db.set_vector_store(vs)

        db.save_memory("user_birthday", "March 15", "personal")
        db.save_memory("favorite_color", "blue", "preference")
        db.save_memory("boss_name", "Sarah Johnson", "personal")

        results = db.semantic_search_memories("when was I born", limit=3)
        assert len(results) >= 1
        keys = [r["key"] for r in results]
        assert "user_birthday" in keys

        results = db.semantic_search_memories("what color do I like", limit=3)
        keys = [r["key"] for r in results]
        assert "favorite_color" in keys

        db.delete_memory("user_birthday")
        assert db.get_memory("user_birthday") is None
        results = db.semantic_search_memories("when was I born", limit=3)
        keys = [r["key"] for r in results]
        assert "user_birthday" not in keys

    finally:
        os.remove(db_path)
        shutil.rmtree(vec_dir, ignore_errors=True)
