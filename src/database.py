"""Persistent SQLite database for assistant memory, tasks, and interaction logs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    category = Column(String, default="general")  # personal, preference, fact, general
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="pending")  # pending, in_progress, completed
    priority = Column(String, default="normal")  # low, normal, high
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class ImageMeta(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    tags = Column(Text, default="[]")  # JSON array
    captured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    vision_model = Column(String, default="")


class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True)
    user_input = Column(Text)
    intent = Column(String)
    response = Column(Text)
    backend = Column(String)
    model_used = Column(String)
    duration = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SyncQueueItem(Base):
    __tablename__ = "sync_queue"
    id = Column(Integer, primary_key=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    operation = Column(String, nullable=False)  # create, update, delete
    payload = Column(Text, default="{}")  # JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    synced_at = Column(DateTime, nullable=True)
    sync_status = Column(String, default="pending")  # pending, success, failed


class DatabaseManager:
    """Manages all persistent storage for the assistant."""

    def __init__(self, db_path: str):
        db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self._Session = sessionmaker(bind=self.engine)
        self._vector_store = None  # set via set_vector_store()

    def set_vector_store(self, vector_store) -> None:
        """Attach a VectorStore for semantic search (optional, additive)."""
        self._vector_store = vector_store

    def init_db(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)

    def _session(self) -> Session:
        return self._Session()

    # -- Memories --

    def save_memory(self, key: str, value: str, category: str = "general") -> int:
        """Save or update a memory. Returns record id."""
        with self._session() as s:
            existing = s.query(Memory).filter_by(key=key).first()
            if existing:
                existing.value = value
                existing.category = category
                existing.updated_at = datetime.now(timezone.utc)
                s.commit()
                record_id = existing.id
            else:
                mem = Memory(key=key, value=value, category=category)
                s.add(mem)
                s.commit()
                record_id = mem.id

        # Index in vector store (key + value concatenated for richer embedding)
        if self._vector_store and self._vector_store.available:
            self._vector_store.add(
                doc_id=f"mem:{key}",
                text=f"{key}: {value}",
                metadata={"key": key, "category": category, "source": "memory"},
            )

        return record_id

    def get_memory(self, key: str) -> dict | None:
        """Get a specific memory by key."""
        with self._session() as s:
            mem = s.query(Memory).filter_by(key=key).first()
            if mem:
                return {"key": mem.key, "value": mem.value, "category": mem.category}
        return None

    def search_memories(self, query: str, limit: int = 5) -> list[dict]:
        """Search memories by key or value substring."""
        with self._session() as s:
            q = query.lower()
            results = (
                s.query(Memory)
                .filter(
                    (Memory.key.ilike(f"%{q}%")) | (Memory.value.ilike(f"%{q}%"))
                )
                .limit(limit)
                .all()
            )
            return [{"key": m.key, "value": m.value, "category": m.category} for m in results]

    def semantic_search_memories(self, query: str, limit: int = 5) -> list[dict]:
        """Search memories using semantic similarity, falling back to ILIKE."""
        if self._vector_store and self._vector_store.available:
            hits = self._vector_store.search(query, limit=limit)
            if hits:
                # Map vector results back to memory records
                results: list[dict] = []
                with self._session() as s:
                    for hit in hits:
                        key = hit.get("key", "")
                        if not key:
                            # Extract key from doc_id "mem:some_key"
                            doc_id = hit.get("id", "")
                            key = doc_id.removeprefix("mem:")
                        mem = s.query(Memory).filter_by(key=key).first()
                        if mem:
                            results.append({
                                "key": mem.key,
                                "value": mem.value,
                                "category": mem.category,
                            })
                if results:
                    return results
        # Fallback to substring search
        return self.search_memories(query, limit=limit)

    def list_memories(self, category: str | None = None, limit: int = 20) -> list[dict]:
        """List memories, optionally filtered by category."""
        with self._session() as s:
            q = s.query(Memory)
            if category:
                q = q.filter_by(category=category)
            results = q.order_by(Memory.updated_at.desc()).limit(limit).all()
            return [{"key": m.key, "value": m.value, "category": m.category} for m in results]

    def delete_memory(self, key: str) -> bool:
        """Delete a memory by key. Returns True if found and deleted."""
        with self._session() as s:
            mem = s.query(Memory).filter_by(key=key).first()
            if mem:
                s.delete(mem)
                s.commit()
                if self._vector_store and self._vector_store.available:
                    self._vector_store.delete(f"mem:{key}")
                return True
        return False

    # -- Tasks --

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        due_date: datetime | None = None,
    ) -> int:
        """Create a new task. Returns task id."""
        with self._session() as s:
            task = Task(
                title=title, description=description,
                priority=priority, due_date=due_date,
            )
            s.add(task)
            s.commit()
            return task.id

    def list_tasks(self, status: str = "pending", limit: int = 10) -> list[dict]:
        """List tasks by status."""
        with self._session() as s:
            results = (
                s.query(Task)
                .filter_by(status=status)
                .order_by(
                    Task.priority.desc(),  # high > normal > low (alphabetical desc)
                    Task.created_at.desc(),
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in results
            ]

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed. Returns True if found."""
        with self._session() as s:
            task = s.query(Task).filter_by(id=task_id).first()
            if task:
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                s.commit()
                return True
        return False

    def find_task_by_title(self, title_query: str) -> dict | None:
        """Find a task by title substring."""
        with self._session() as s:
            task = (
                s.query(Task)
                .filter(Task.title.ilike(f"%{title_query}%"))
                .filter(Task.status != "completed")
                .first()
            )
            if task:
                return {"id": task.id, "title": task.title, "status": task.status}
        return None

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by id."""
        with self._session() as s:
            task = s.query(Task).filter_by(id=task_id).first()
            if task:
                s.delete(task)
                s.commit()
                return True
        return False

    # -- Images --

    def save_image_meta(
        self, description: str, tags: list[str] | None = None, vision_model: str = ""
    ) -> int:
        """Save image metadata. Returns record id."""
        with self._session() as s:
            img = ImageMeta(
                description=description,
                tags=json.dumps(tags or []),
                vision_model=vision_model,
            )
            s.add(img)
            s.commit()
            record_id = img.id

        if self._vector_store and self._vector_store.available:
            self._vector_store.add(
                doc_id=f"img:{record_id}",
                text=description,
                metadata={"source": "image"},
            )

        return record_id

    def list_images(self, limit: int = 10) -> list[dict]:
        """List recent image captures."""
        with self._session() as s:
            results = (
                s.query(ImageMeta)
                .order_by(ImageMeta.captured_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": i.id,
                    "description": i.description,
                    "tags": json.loads(i.tags),
                    "captured_at": i.captured_at.isoformat() if i.captured_at else None,
                }
                for i in results
            ]

    def search_images(self, query: str, limit: int = 5) -> list[dict]:
        """Search images by description."""
        with self._session() as s:
            results = (
                s.query(ImageMeta)
                .filter(ImageMeta.description.ilike(f"%{query}%"))
                .limit(limit)
                .all()
            )
            return [
                {"id": i.id, "description": i.description, "tags": json.loads(i.tags)}
                for i in results
            ]

    # -- Interactions --

    def log_interaction(
        self,
        user_input: str,
        intent: str,
        response: str,
        backend: str = "",
        model_used: str = "",
        duration: float = 0.0,
    ) -> int:
        with self._session() as s:
            entry = Interaction(
                user_input=user_input, intent=intent, response=response,
                backend=backend, model_used=model_used, duration=duration,
            )
            s.add(entry)
            s.commit()
            return entry.id

    # -- Sync Queue --

    def queue_sync(self, table: str, record_id: int, operation: str, payload: dict):
        """Add an item to the sync queue."""
        with self._session() as s:
            item = SyncQueueItem(
                table_name=table, record_id=record_id,
                operation=operation, payload=json.dumps(payload),
            )
            s.add(item)
            s.commit()

    def get_pending_sync(self, limit: int = 50) -> list[dict]:
        """Get pending sync items."""
        with self._session() as s:
            results = (
                s.query(SyncQueueItem)
                .filter_by(sync_status="pending")
                .order_by(SyncQueueItem.created_at)
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": i.id,
                    "table_name": i.table_name,
                    "record_id": i.record_id,
                    "operation": i.operation,
                    "payload": json.loads(i.payload),
                }
                for i in results
            ]

    def mark_synced(self, sync_id: int):
        """Mark a sync item as successfully synced."""
        with self._session() as s:
            item = s.query(SyncQueueItem).filter_by(id=sync_id).first()
            if item:
                item.sync_status = "success"
                item.synced_at = datetime.now(timezone.utc)
                s.commit()
