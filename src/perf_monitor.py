"""
Performance Monitoring for Talking LLM Assistant

Tracks timing and resource usage for each component in the pipeline.
Helps identify bottlenecks and optimize performance.

For AI Assistants:
- This module provides detailed timing metrics for debugging
- Tracks GPU memory usage across model loads/unloads
- Logs performance data for optimization analysis
"""

import time
from typing import Dict, List, Optional
import threading
from rich.console import Console
from rich.table import Table

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class PerformanceMonitor:
    """
    Tracks performance metrics for the assistant.

    Collects timing data for each component:
    - Audio recording duration
    - Transcription time (Whisper)
    - LLM processing time (Gemma3/Moondream)
    - TTS generation time (Piper)
    - GPU memory usage

    Example:
        >>> monitor = PerformanceMonitor()
        >>> monitor.start_timing("transcription")
        >>> # ... transcribe audio ...
        >>> monitor.stop_timing("transcription")
        >>> monitor.print_report()
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize performance monitor.

        Args:
            console: Rich console for output (optional)
        """
        self.console = console or Console()
        self.timings: Dict[str, List[float]] = {}
        self.active_timers: Dict[str, float] = {}
        self.gpu_usage: List[float] = []
        self._lock = threading.Lock()

    def start_timing(self, component: str):
        """
        Start timing a component.

        Args:
            component: Name of component (e.g., "transcription", "llm", "tts")
        """
        with self._lock:
            self.active_timers[component] = time.time()

    def stop_timing(self, component: str) -> float:
        """
        Stop timing a component and return duration.

        Args:
            component: Name of component

        Returns:
            Duration in seconds
        """
        with self._lock:
            if component not in self.active_timers:
                return 0.0

            duration = time.time() - self.active_timers[component]

            # Store timing
            if component not in self.timings:
                self.timings[component] = []
            self.timings[component].append(duration)

            # Clear active timer
            del self.active_timers[component]

            return duration

    def record_gpu_usage(self):
        """Record current GPU memory usage."""
        if TORCH_AVAILABLE and torch.cuda.is_available():
            with self._lock:
                gpu_mem = torch.cuda.memory_allocated() / 1e9  # GB
                self.gpu_usage.append(gpu_mem)

    def get_component_stats(self, component: str) -> Dict[str, float]:
        """
        Get statistics for a component.

        Args:
            component: Name of component

        Returns:
            Dictionary with min, max, avg, count
        """
        with self._lock:
            if component not in self.timings or not self.timings[component]:
                return {"min": 0, "max": 0, "avg": 0, "count": 0}

            times = self.timings[component]
            return {
                "min": min(times),
                "max": max(times),
                "avg": sum(times) / len(times),
                "count": len(times),
            }

    def get_gpu_stats(self) -> Dict[str, float]:
        """
        Get GPU usage statistics.

        Returns:
            Dictionary with min, max, avg, count (in GB)
        """
        with self._lock:
            if not self.gpu_usage:
                return {"min": 0, "max": 0, "avg": 0, "count": 0}

            return {
                "min": min(self.gpu_usage),
                "max": max(self.gpu_usage),
                "avg": sum(self.gpu_usage) / len(self.gpu_usage),
                "count": len(self.gpu_usage),
            }

    def print_report(self, title: str = "Performance Report"):
        """
        Print a formatted performance report.

        Args:
            title: Report title
        """
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Avg Time (s)", justify="right")
        table.add_column("Min Time (s)", justify="right")
        table.add_column("Max Time (s)", justify="right")

        # Add timing data
        for component in sorted(self.timings.keys()):
            stats = self.get_component_stats(component)
            if stats["count"] > 0:
                table.add_row(
                    component.capitalize(),
                    str(stats["count"]),
                    f"{stats['avg']:.3f}",
                    f"{stats['min']:.3f}",
                    f"{stats['max']:.3f}",
                )

        # Add GPU data
        if self.gpu_usage:
            gpu_stats = self.get_gpu_stats()
            table.add_row(
                "GPU Memory (GB)",
                str(gpu_stats["count"]),
                f"{gpu_stats['avg']:.2f}",
                f"{gpu_stats['min']:.2f}",
                f"{gpu_stats['max']:.2f}",
            )

        # Calculate total time
        total_time = 0
        total_count = 0
        for component, times in self.timings.items():
            total_time += sum(times)
            total_count += len(times)

        if total_count > 0:
            table.add_row(
                "TOTAL",
                str(total_count),
                f"{total_time / total_count:.3f}",
                "-",
                "-",
                style="bold",
            )

        self.console.print(table)

    def reset(self):
        """Reset all collected metrics."""
        with self._lock:
            self.timings = {}
            self.active_timers = {}
            self.gpu_usage = []

    def get_last_timing(self, component: str) -> float:
        """
        Get the most recent timing for a component.

        Args:
            component: Name of component

        Returns:
            Last recorded timing in seconds, or 0 if none
        """
        with self._lock:
            if component not in self.timings or not self.timings[component]:
                return 0.0
            return self.timings[component][-1]


# Global instance for easy access
_perf_monitor: Optional[PerformanceMonitor] = None


def get_perf_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor instance."""
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor


def reset_perf_monitor():
    """Reset global performance monitor."""
    global _perf_monitor
    _perf_monitor = None


# Convenience decorator for timing functions
def timed(component: str):
    """
    Decorator to time function execution.

    Example:
        >>> @timed("transcription")
        >>> def transcribe_audio(audio):
        >>>     # ... transcribe ...
        >>>     return text
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_perf_monitor()
            monitor.start_timing(component)
            try:
                result = func(*args, **kwargs)
                duration = monitor.stop_timing(component)
                if monitor.console:
                    monitor.console.print(
                        f"[dim]⏱️  {component.capitalize()}: {duration:.2f}s[/dim]"
                    )
                return result
            except Exception as e:
                monitor.stop_timing(component)
                raise e

        return wrapper

    return decorator


# Test function
if __name__ == "__main__":
    import time

    # Create monitor
    monitor = PerformanceMonitor()

    # Simulate some timings
    print("Testing performance monitor...")

    # Time component 1
    monitor.start_timing("transcription")
    time.sleep(0.1)
    monitor.stop_timing("transcription")

    # Time component 2
    monitor.start_timing("llm_processing")
    time.sleep(0.2)
    monitor.stop_timing("llm_processing")

    # Time component 3
    monitor.start_timing("tts_generation")
    time.sleep(0.15)
    monitor.stop_timing("tts_generation")

    # Simulate GPU usage (if available)
    if TORCH_AVAILABLE:
        monitor.record_gpu_usage()

    # Print report
    print("\nPerformance Report:")
    monitor.print_report()
