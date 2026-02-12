#!/usr/bin/env python3
"""
Performance benchmark suite for Local Talking LLM

Run with: python examples/benchmark.py
"""

import time
import statistics
from typing import Callable
from contextlib import contextmanager


class Benchmark:
    """Simple benchmark utility."""

    def __init__(self, name: str):
        self.name = name
        self.times = []

    @contextmanager
    def measure(self):
        """Context manager to measure execution time."""
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            self.times.append(end - start)

    def stats(self) -> dict:
        """Calculate statistics."""
        if not self.times:
            return {}

        return {
            "count": len(self.times),
            "min": min(self.times),
            "max": max(self.times),
            "mean": statistics.mean(self.times),
            "median": statistics.median(self.times),
            "stdev": statistics.stdev(self.times) if len(self.times) > 1 else 0,
        }

    def report(self):
        """Print benchmark report."""
        stats = self.stats()
        if not stats:
            print(f"{self.name}: No data")
            return

        print(f"\n{self.name}:")
        print(f"  Runs: {stats['count']}")
        print(f"  Min: {stats['min'] * 1000:.2f}ms")
        print(f"  Max: {stats['max'] * 1000:.2f}ms")
        print(f"  Mean: {stats['mean'] * 1000:.2f}ms")
        print(f"  Median: {stats['median'] * 1000:.2f}ms")
        print(f"  StdDev: {stats['stdev'] * 1000:.2f}ms")


def benchmark_database():
    """Benchmark database operations."""
    import tempfile
    import os
    from src.database import AssistantDatabase

    print("📊 Benchmarking Database Operations...")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = AssistantDatabase(db_path)

        # Benchmark memory writes
        write_bm = Benchmark("Memory Write")
        for i in range(100):
            with write_bm.measure():
                db.save_memory(f"memory_{i}", f"content_{i}")

        write_bm.report()

        # Benchmark memory reads
        read_bm = Benchmark("Memory Read")
        for i in range(100):
            with read_bm.measure():
                db.get_memory(f"memory_{i}")

        read_bm.report()

        # Benchmark memory search
        search_bm = Benchmark("Memory Search")
        for i in range(50):
            with search_bm.measure():
                db.search_memories(f"content_{i}", limit=10)

        search_bm.report()

    finally:
        os.unlink(db_path)


def benchmark_vector_store():
    """Benchmark vector store operations."""
    import tempfile
    import shutil
    from src.vector_store import VectorStore

    print("\n📊 Benchmarking Vector Store Operations...")

    vector_dir = tempfile.mkdtemp()

    try:
        vs = VectorStore(persist_directory=vector_dir)

        # Benchmark embedding
        texts = [f"This is test text number {i}" for i in range(100)]

        embed_bm = Benchmark("Text Embedding (100 texts)")
        with embed_bm.measure():
            embeddings = vs.embedder.encode(texts, show_progress_bar=False)

        embed_bm.report()

        # Benchmark similarity search
        vs.add_memories([{"key": f"mem_{i}", "content": texts[i]} for i in range(100)])

        search_bm = Benchmark("Similarity Search")
        for i in range(20):
            with search_bm.measure():
                vs.search(f"test text number {i}", top_k=5)

        search_bm.report()

    finally:
        shutil.rmtree(vector_dir)


def benchmark_tool_execution():
    """Benchmark tool execution."""
    from src.tools import ToolRegistry

    print("\n📊 Benchmarking Tool Execution...")

    registry = ToolRegistry()

    # Test fast path tools
    fast_tools = ["get_time", "get_location"]

    for tool in fast_tools:
        bm = Benchmark(f"Tool: {tool}")
        for _ in range(100):
            with bm.measure():
                registry.execute(tool, {})
        bm.report()


def benchmark_whisper():
    """Benchmark Whisper transcription."""
    print("\n📊 Benchmarking Whisper STT...")
    print("  (Requires actual audio file - skipped in basic benchmark)")
    print("  Run with: python examples/benchmark_whisper.py")


def main():
    """Run all benchmarks."""
    print("=" * 60)
    print("🚀 Local Talking LLM - Performance Benchmarks")
    print("=" * 60)

    try:
        benchmark_database()
    except Exception as e:
        print(f"  ⚠️  Database benchmark failed: {e}")

    try:
        benchmark_vector_store()
    except Exception as e:
        print(f"  ⚠️  Vector store benchmark failed: {e}")

    try:
        benchmark_tool_execution()
    except Exception as e:
        print(f"  ⚠️  Tool execution benchmark failed: {e}")

    try:
        benchmark_whisper()
    except Exception as e:
        print(f"  ⚠️  Whisper benchmark failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Benchmarks complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
