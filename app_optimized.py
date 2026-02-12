"""Personal Assistant - Voice-controlled AI with orchestrated model routing.

Architecture:
  Voice -> Whisper (CPU) -> Orchestrator (CPU) -> Specialized Model (GPU) -> Piper TTS (CPU)

Specialized models:
  - Gemma3:    Text chat, reasoning, summarization (3.3GB GPU)
  - Moondream: Vision/image analysis (1.7GB GPU)
  - DuckDuckGo: Web search (no GPU)
  - Piper:     Text-to-speech (CPU)

GPU constraint: 4GB MX-130, only ONE model loaded at a time.
"""

import signal
import sys
import time
import traceback
import threading
import numpy as np

# Optional imports with fallbacks
try:
    import whisper

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️  Whisper not available - voice input disabled")

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("⚠️  Sounddevice not available - audio input disabled")
import argparse
import torch
import cv2
import gc
import base64
import requests
from io import BytesIO
from PIL import Image
from queue import Queue
from scipy.signal import resample_poly
from math import gcd
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_ollama import OllamaLLM

from src.logging_config import setup_logging, get_logger
from src.config_loader import load_config, validate_config
from src.connectivity import ConnectivityMonitor
from src.database import DatabaseManager
from src.vector_store import VectorStore
from src.orchestrator import Orchestrator
from src.tools import ToolExecutor
from src.web_search import WebSearch
from src.health import run_health_checks
from src.bounded_history import BoundedChatHistory
from tts import TextToSpeechService

console = Console()
log = get_logger(__name__)


class ResourceManager:
    """Manages GPU memory - only ONE model in 4GB VRAM at a time.

    Strategy:
      - Gemma3 (3.3GB) on GPU for chat/search (default)
      - Moondream (1.7GB) on GPU for vision (swapped in when needed)
      - Ollama keep_alive=0 to properly free VRAM on swap
      - Orchestrator runs on CPU via num_gpu=0 (no swap needed)
      - "auto" backend: use OpenRouter when online, Ollama when offline
    """

    def __init__(self, config: dict, connectivity: ConnectivityMonitor | None = None):
        self.config = config
        self.backend = config.get("backend", "ollama")
        self.connectivity = connectivity
        self.current_gpu_model = None
        self.text_llm = None

        ollama_cfg = config.get("ollama", {})
        self.base_url = ollama_cfg.get("base_url", "http://localhost:11434")
        self.text_model = ollama_cfg.get("text_model", "gemma3")
        self.vision_model = ollama_cfg.get("vision_model", "moondream")
        self.text_temp = ollama_cfg.get("text_temperature", 0.7)

        self._openrouter = None
        self._or_text_model = ""
        self._or_vision_model = ""
        if self.backend in ("openrouter", "auto"):
            or_cfg = config.get("openrouter", {})
            api_key = or_cfg.get("api_key", "")
            if api_key:
                from src.openrouter import OpenRouterClient

                self._openrouter = OpenRouterClient(
                    api_key=api_key,
                    base_url=or_cfg.get("base_url", "https://openrouter.ai/api/v1"),
                )
                self._or_text_model = or_cfg.get("text_model", "meta-llama/llama-3.3-70b-instruct:free")
                self._or_vision_model = or_cfg.get("vision_model", "nvidia/nemotron-nano-12b-v2-vl:free")

    def _active_backend(self) -> str:
        """Resolve the active backend based on connectivity."""
        if self.backend == "auto" and self.connectivity:
            auto_cfg = self.config.get("auto_backend", {})
            if self.connectivity.is_online and self._openrouter:
                return auto_cfg.get("prefer_online", "openrouter")
            return auto_cfg.get("fallback_offline", "ollama")
        return self.backend

    def _ollama_unload(self, model_name: str):
        """Tell Ollama to fully unload a model from VRAM."""
        try:
            requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
                timeout=10,
            )
        except Exception:
            pass
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def _swap_to(self, target_model: str):
        """Swap GPU to target model: unload current, load target."""
        if self.current_gpu_model == target_model:
            return
        if self.current_gpu_model:
            console.print(f"[dim]Freeing GPU: unloading {self.current_gpu_model}...[/dim]")
            self._ollama_unload(self.current_gpu_model)
        self.current_gpu_model = target_model

    def load_text_model(self):
        """Ensure text model is on GPU."""
        self._swap_to(self.text_model)

        if self.text_llm is None:
            console.print(f"[yellow]Loading {self.text_model} onto GPU...[/yellow]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(f"Loading {self.text_model}...", total=None)
                self.text_llm = OllamaLLM(
                    model=self.text_model,
                    base_url=self.base_url,
                    temperature=self.text_temp,
                )
            console.print(f"[green]{self.text_model} ready (GPU)[/green]")

    def unload_all(self):
        """Cleanup on exit."""
        if self.current_gpu_model:
            self._ollama_unload(self.current_gpu_model)
            self.current_gpu_model = None

    @staticmethod
    def _history_to_dicts(history: InMemoryChatMessageHistory) -> list[dict]:
        """Convert LangChain chat history to plain dicts for OpenRouter."""
        result = []
        for msg in history.messages:
            role = "assistant" if msg.type == "ai" else "user"
            result.append({"role": role, "content": msg.content})
        return result

    def get_text_response(self, text: str, history: InMemoryChatMessageHistory) -> str:
        """Get text response from LLM (GPU for Ollama, cloud for OpenRouter)."""
        backend = self._active_backend()
        if backend == "openrouter" and self._openrouter:
            hist_dicts = self._history_to_dicts(history)
            return self._openrouter.get_text_response(text, self._or_text_model, history=hist_dicts)

        self.load_text_model()

        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful personal assistant. Be concise and helpful.",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )

        chain = prompt_template | self.text_llm
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda sid: history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return chain_with_history.invoke({"input": text}, config={"session_id": "voice_assistant"}).strip()

    def get_vision_response(self, text: str, image_b64: str) -> str:
        """Get vision response (local Moondream on GPU, or cloud via OpenRouter)."""
        backend = self._active_backend()
        # OpenRouter: send image to cloud vision model
        if backend == "openrouter" and self._openrouter:
            console.print(f"[yellow]Sending image to {self._or_vision_model} (cloud)...[/yellow]")
            return self._openrouter.get_vision_response(text, image_b64, self._or_vision_model)

        # Ollama: swap Moondream onto GPU
        self._swap_to(self.vision_model)
        self.text_llm = None  # Invalidate since Gemma3 was unloaded
        console.print(f"[yellow]Loading {self.vision_model} onto GPU...[/yellow]")

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.vision_model,
                "messages": [{"role": "user", "content": text, "images": [image_b64]}],
                "stream": False,
            },
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()["message"]["content"].strip()
        else:
            result = f"Vision model error (status {response.status_code})"

        # Swap back: unload Moondream -> Gemma3 reloads on next text request
        console.print(f"[dim]Freeing GPU for {self.text_model}...[/dim]")
        self._ollama_unload(self.vision_model)
        self.current_gpu_model = None

        return result


# ---------------------------------------------------------------------------
# Audio & Camera
# ---------------------------------------------------------------------------


def _get_recording_samplerate() -> int:
    """Get the default input device's native sample rate."""
    if not SOUNDDEVICE_AVAILABLE:
        return 16000  # Default fallback
    info = sd.query_devices(sd.default.device[0], "input")
    return int(info["default_samplerate"])


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio from orig_sr to target_sr."""
    if orig_sr == target_sr:
        return audio
    factor = gcd(orig_sr, target_sr)
    up = target_sr // factor
    down = orig_sr // factor
    return resample_poly(audio, up, down).astype(np.float32)


def record_audio(stop_event, data_queue, samplerate: int):
    """Record audio from microphone using sd.InputStream at native rate."""
    if not SOUNDDEVICE_AVAILABLE:
        console.print("[yellow]Audio recording disabled - sounddevice not available[/yellow]")
        return

    def callback(indata, frames, time_info, status):
        if status:
            console.print(status)
        data_queue.put(indata.copy())

    with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", callback=callback):
        while not stop_event.is_set():
            time.sleep(0.1)


def transcribe(stt_model, audio_np: np.ndarray, recording_sr: int) -> str:
    """Transcribe audio using Whisper on CPU (resamples to 16 kHz if needed)."""
    if stt_model is None:
        return "[Voice input disabled - Whisper not available]"

    audio_16k = _resample(audio_np, recording_sr, 16000)
    result = stt_model.transcribe(audio_16k, fp16=False)
    return result["text"].strip()


def capture_image(config: dict) -> str | None:
    """Capture image from camera with live preview.

    Returns base64-encoded JPEG or None if cancelled.
    """
    cam_cfg = config.get("camera", {})

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        console.print("[red]Could not open camera![/red]")
        return None

    console.print("[blue]Opening camera preview...[/blue]")
    console.print(
        "[dim]Press SPACE to capture | Press ESC to cancel | "
        f"Auto-capture in {cam_cfg.get('auto_capture_timeout', 5)}s[/dim]"
    )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg.get("preview_width", 640))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg.get("preview_height", 480))

    preview_window = "Camera Preview - Press SPACE to capture"
    cv2.namedWindow(preview_window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        preview_window,
        cam_cfg.get("preview_width", 640),
        cam_cfg.get("preview_height", 480),
    )

    captured_frame = None
    start_time = time.time()
    timeout = cam_cfg.get("auto_capture_timeout", 5)

    while True:
        ret, frame = cap.read()
        if not ret:
            console.print("[red]Failed to read from camera![/red]")
            break

        display_frame = frame.copy()
        remaining = max(0, timeout - (time.time() - start_time))

        cv2.putText(
            display_frame,
            "Press SPACE to capture",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            display_frame,
            "Press ESC to cancel",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            display_frame,
            f"Auto-capture in: {remaining:.1f}s",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )

        cv2.imshow(preview_window, display_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 32:  # SPACE
            captured_frame = frame.copy()
            console.print("[green]Image captured![/green]")
            break
        elif key == 27:  # ESC
            console.print("[yellow]Capture cancelled[/yellow]")
            break
        elif remaining <= 0:
            captured_frame = frame.copy()
            console.print("[yellow]Auto-captured after timeout[/yellow]")
            break

    cap.release()
    cv2.destroyWindow(preview_window)
    cv2.waitKey(1)

    if captured_frame is None:
        return None

    console.print("[dim]Processing image...[/dim]")
    frame_rgb = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(frame_rgb)
    pil_image = pil_image.resize((cam_cfg.get("capture_width", 512), cam_cfg.get("capture_height", 384)))

    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG", quality=cam_cfg.get("jpeg_quality", 85))
    img_str = base64.b64encode(buffered.getvalue()).decode()

    console.print(f"[dim]Image ready: {len(img_str) // 1024}KB[/dim]")
    return img_str


def _get_playback_samplerate() -> int:
    """Get the default output device's native sample rate."""
    if not SOUNDDEVICE_AVAILABLE:
        return 22050  # Default Piper sample rate
    info = sd.query_devices(sd.default.device[1], "output")
    return int(info["default_samplerate"])


def play_audio(sample_rate, audio_array, device_sr: int | None = None):
    """Play audio through speakers, resampling to device rate if needed."""
    if not SOUNDDEVICE_AVAILABLE:
        console.print("[yellow]Audio playback disabled - sounddevice not available[/yellow]")
        return

    target_sr = device_sr or _get_playback_samplerate()
    if sample_rate != target_sr:
        audio_array = _resample(audio_array, sample_rate, target_sr)
    sd.play(audio_array, target_sr)
    sd.wait()


# ---------------------------------------------------------------------------
# Interaction pipeline
# ---------------------------------------------------------------------------


def handle_system_command(text: str) -> str | None:
    """Handle system commands. Returns None to signal exit."""
    lower = text.lower().strip()
    if any(kw in lower for kw in ("exit", "quit", "stop", "shutdown", "shut down")):
        return None  # Signal to exit
    if "status" in lower or "help" in lower:
        return "I'm your personal assistant. I can chat, search the web, and analyze images with the camera."
    return "I didn't understand that system command."


def process_interaction(
    audio_np: np.ndarray,
    stt_model,
    orchestrator: Orchestrator,
    resource_mgr: ResourceManager,
    search_engine: WebSearch | None,
    tool_executor: ToolExecutor | None,
    db: DatabaseManager | None,
    tts_service: TextToSpeechService | None,
    chat_history: InMemoryChatMessageHistory,
    config: dict,
    recording_sr: int = 16000,
) -> bool:
    """Process one voice interaction. Returns False to signal exit."""
    if audio_np.size == 0:
        return True

    t_start = time.time()

    # Step 1: Transcribe
    with console.status("[yellow]Transcribing...", spinner="dots"):
        text = transcribe(stt_model, audio_np, recording_sr)

    if not text or len(text.strip()) < 2:
        console.print("[dim]No speech detected[/dim]")
        return True

    console.print(f"\n[bold yellow]You:[/bold yellow] {text}")
    log.info("User: %s", text)

    # Step 2: Classify intent
    with console.status("[cyan]Thinking...", spinner="dots"):
        intent_result = orchestrator.classify_intent(text)

    intent = intent_result["intent"]
    log.info("Intent: %s (confidence=%.2f)", intent, intent_result.get("confidence", 0))
    response = ""

    # Step 3: Route to appropriate handler
    if intent == "vision":
        try:
            image_b64 = capture_image(config)
            if image_b64:
                prompt = intent_result.get("vision_prompt") or text
                with console.status("[blue]Analyzing image...", spinner="dots"):
                    response = resource_mgr.get_vision_response(prompt, image_b64)
                # Auto-save image metadata to DB
                if db and response:
                    try:
                        vision_model = resource_mgr.vision_model
                        backend = resource_mgr._active_backend()
                        if backend == "openrouter":
                            vision_model = resource_mgr._or_vision_model
                        db.save_image_meta(description=response, tags=[], vision_model=vision_model)
                        console.print("[dim]Image metadata saved to memory[/dim]")
                    except Exception:
                        pass
            else:
                console.print("[yellow]Camera unavailable, using text model...[/yellow]")
                with console.status("[green]Thinking...", spinner="dots"):
                    response = resource_mgr.get_text_response(text, chat_history)
        except Exception as e:
            log.error("Vision pipeline failed: %s", e, exc_info=True)
            console.print(f"[red]Vision error: {e}. Falling back to text...[/red]")
            with console.status("[green]Thinking...", spinner="dots"):
                response = resource_mgr.get_text_response(text, chat_history)

    elif intent == "search":
        if search_engine:
            query = intent_result.get("search_query") or text
            with console.status("[cyan]Searching...", spinner="dots"):
                search_results = search_engine.search_and_format(query)

            console.print(Panel(search_results, title="Search Results", border_style="cyan"))

            summarize_prompt = (
                f"Based on these search results, answer the user's question: '{text}'\n\n"
                f"Search Results:\n{search_results}\n\n"
                f"Provide a concise, helpful answer."
            )
            with console.status("[green]Summarizing...", spinner="dots"):
                response = resource_mgr.get_text_response(summarize_prompt, chat_history)
        else:
            console.print("[yellow]Search disabled, using text model...[/yellow]")
            with console.status("[green]Thinking...", spinner="dots"):
                response = resource_mgr.get_text_response(text, chat_history)

    elif intent == "tool":
        if tool_executor:
            # Tool extraction + execution runs locally on CPU (no API cost)
            with console.status("[magenta]Executing action...", spinner="dots"):
                tool_result = tool_executor.extract_and_execute(text)
            console.print(Panel(tool_result, title="Action Result", border_style="magenta"))
            # Speak the result directly -- no extra LLM call needed
            response = tool_result
        else:
            with console.status("[green]Thinking...", spinner="dots"):
                response = resource_mgr.get_text_response(text, chat_history)

    elif intent == "system":
        response = handle_system_command(text)
        if response is None:
            return False  # Exit signal

    else:  # "chat"
        # Inject relevant memories as context
        memory_context = ""
        if db:
            memories = db.semantic_search_memories(text, limit=3)
            if memories:
                facts = "; ".join(f"{m['key']}={m['value']}" for m in memories)
                memory_context = f"\n[Known facts about the user: {facts}]\n"

        prompt = memory_context + text if memory_context else text
        with console.status("[green]Thinking...", spinner="dots"):
            response = resource_mgr.get_text_response(prompt, chat_history)

    # Step 4: Output
    console.print(f"\n[bold cyan]Assistant:[/bold cyan] {response}")
    log.info("Response length: %d chars", len(response))

    # TTS (guarded - tts_service may be None)
    if tts_service:
        try:
            with console.status("[magenta]Speaking...", spinner="dots"):
                sample_rate, audio_array = tts_service.long_form_synthesize(response)
            # Play the audio directly - our enhanced TTS already handles resampling
            if SOUNDDEVICE_AVAILABLE:
                sd.play(audio_array, sample_rate)
                sd.wait()
            else:
                console.print("[yellow]Audio playback disabled - sounddevice not available[/yellow]")
        except Exception as e:
            log.error("TTS playback failed: %s", e)
            console.print(f"[yellow]Speech output failed: {e}[/yellow]")

    # Step 5: Log interaction
    if db and config.get("database", {}).get("log_interactions", True):
        duration = time.time() - t_start
        try:
            db.log_interaction(
                user_input=text,
                intent=intent,
                response=response,
                backend=resource_mgr._active_backend(),
                model_used=resource_mgr.text_model,
                duration=duration,
            )
        except Exception:
            pass

    return True


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _cleanup(
    resource_mgr: ResourceManager | None,
    db: DatabaseManager | None,
    openrouter_client=None,
):
    """Release resources on shutdown."""
    if resource_mgr:
        try:
            resource_mgr.unload_all()
        except Exception:
            pass
    if db:
        try:
            db.engine.dispose()
        except Exception:
            pass
    if openrouter_client:
        try:
            openrouter_client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Personal Assistant with Orchestrated Model Routing",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    parser.add_argument(
        "--backend",
        type=str,
        choices=["ollama", "openrouter", "auto"],
        help="LLM backend: ollama, openrouter, or auto (overrides config)",
    )
    parser.add_argument("--openrouter-key", type=str, help="OpenRouter API key")
    parser.add_argument("--model", type=str, help="Text model (overrides config)")
    parser.add_argument("--vision-model", type=str, help="Vision model (overrides config)")
    parser.add_argument(
        "--whisper-model",
        type=str,
        choices=["tiny.en", "base.en", "small.en"],
        help="Whisper model size (overrides config)",
    )
    parser.add_argument("--no-search", action="store_true", help="Disable web search")
    parser.add_argument("--no-vision", action="store_true", help="Disable vision/camera")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup logging as first action
    log_cfg = config.get("logging", {})
    setup_logging(level=log_cfg.get("level", "INFO"))
    log.info("Starting Personal Assistant")

    # Validate config
    config_errors = validate_config(config)
    if config_errors:
        for err in config_errors:
            console.print(f"[red]Config error: {err}[/red]")
            log.error("Config error: %s", err)
        sys.exit(1)

    # Apply CLI overrides
    if args.backend:
        config["backend"] = args.backend
    if args.openrouter_key:
        config.setdefault("openrouter", {})["api_key"] = args.openrouter_key
    if args.model:
        config.setdefault("ollama", {})["text_model"] = args.model
    if args.vision_model:
        config.setdefault("ollama", {})["vision_model"] = args.vision_model
    if args.no_search:
        config.setdefault("search", {})["enabled"] = False
    if args.no_vision:
        config.setdefault("camera", {})["enabled"] = False

    whisper_model = args.whisper_model or config.get("whisper", {}).get("model", "base.en")
    backend = config.get("backend", "ollama")
    ollama_cfg = config.get("ollama", {})
    or_cfg = config.get("openrouter", {})
    search_cfg = config.get("search", {})
    db_cfg = config.get("database", {})

    # -- Health checks --
    report = run_health_checks(config)
    console.print(Panel("\n".join(report.summary_lines()), title="Health Checks", border_style="cyan"))
    for check in report.checks:
        log.info("Health check %s: %s - %s", check.name, check.status, check.detail)

    if report.has_critical_failure:
        console.print("[red]Critical health check failed. Fix the issues above and retry.[/red]")
        log.error("Exiting due to critical health check failure")
        sys.exit(1)

    # -- Connectivity monitor (for auto backend) --
    connectivity = None
    if backend == "auto":
        auto_cfg = config.get("auto_backend", {})
        connectivity = ConnectivityMonitor(interval=auto_cfg.get("check_interval", 300))
        connectivity.start()
        status_str = "online" if connectivity.is_online else "offline"
        console.print(f"[green]Connectivity: {status_str}[/green]")

    # -- Startup banner --
    if backend == "openrouter":
        banner_lines = (
            f"[bold cyan]Personal Assistant[/bold cyan]\n"
            f"[dim]Backend:[/dim] OpenRouter (cloud)\n"
            f"[dim]Text LLM:[/dim] {or_cfg.get('text_model', 'N/A')} [magenta](cloud)[/magenta]\n"
            f"[dim]Vision:[/dim] {or_cfg.get('vision_model', 'N/A')} [magenta](cloud)[/magenta]\n"
            f"[dim]STT:[/dim] Whisper {whisper_model} [cyan](CPU)[/cyan]\n"
            f"[dim]TTS:[/dim] Piper [cyan](CPU)[/cyan]\n"
            f"[dim]Search:[/dim] {'DuckDuckGo' if search_cfg.get('enabled', True) else 'Disabled'}\n"
            f"[dim]Tools:[/dim] Memory, Tasks, Time, Location\n"
            f"[dim]Database:[/dim] {db_cfg.get('path', 'default')}"
        )
    elif backend == "auto":
        active = "OpenRouter" if (connectivity and connectivity.is_online) else "Ollama"
        banner_lines = (
            f"[bold cyan]Personal Assistant[/bold cyan]\n"
            f"[dim]Backend:[/dim] Auto ({active} active)\n"
            f"[dim]Online:[/dim] {or_cfg.get('text_model', 'N/A')} [magenta](cloud)[/magenta]\n"
            f"[dim]Offline:[/dim] {ollama_cfg.get('text_model', 'gemma3')} [green](local GPU)[/green]\n"
            f"[dim]STT:[/dim] Whisper {whisper_model} [cyan](CPU)[/cyan]\n"
            f"[dim]TTS:[/dim] Piper [cyan](CPU)[/cyan]\n"
            f"[dim]Search:[/dim] {'DuckDuckGo' if search_cfg.get('enabled', True) else 'Disabled'}\n"
            f"[dim]Tools:[/dim] Memory, Tasks, Time, Location\n"
            f"[dim]Database:[/dim] {db_cfg.get('path', 'default')}"
        )
    else:
        banner_lines = (
            f"[bold cyan]Personal Assistant[/bold cyan]\n"
            f"[dim]Backend:[/dim] Ollama (local)\n"
            f"[dim]Text LLM:[/dim] {ollama_cfg.get('text_model', 'gemma3')} [green](GPU, 3.3GB)[/green]\n"
            f"[dim]Vision:[/dim] {ollama_cfg.get('vision_model', 'moondream')} [green](GPU, swapped in)[/green]\n"
            f"[dim]STT:[/dim] Whisper {whisper_model} [cyan](CPU)[/cyan]\n"
            f"[dim]TTS:[/dim] Piper [cyan](CPU)[/cyan]\n"
            f"[dim]Search:[/dim] {'DuckDuckGo' if search_cfg.get('enabled', True) else 'Disabled'}\n"
            f"[dim]Tools:[/dim] Memory, Tasks, Time, Location\n"
            f"[dim]Database:[/dim] {db_cfg.get('path', 'default')}"
        )
    console.print(Panel.fit(banner_lines, title="HNG Assistant", border_style="cyan"))

    # -- Initialize components (each guarded with try/except) --

    # Database
    db = None
    try:
        db_path = db_cfg.get("path", "~/.local/share/talking-llm/assistant.db")
        db = DatabaseManager(db_path)
        db.init_db()
        console.print("[green]Database ready[/green]")
        log.info("Database initialized: %s", db_path)
    except Exception as e:
        log.error("Database init failed: %s", e)
        console.print(f"[yellow]Database unavailable: {e}[/yellow]")

    # Vector store for semantic memory search (CPU only, zero VRAM)
    vs_cfg = config.get("vector_store", {})
    if vs_cfg.get("enabled", True) and db:
        try:
            vs = VectorStore(
                path=vs_cfg.get("path", "~/.local/share/talking-llm/vectors"),
                model_name=vs_cfg.get("embedding_model", "all-MiniLM-L6-v2"),
                device=vs_cfg.get("embedding_device", "cpu"),
            )
            if vs.available:
                db.set_vector_store(vs)
                console.print("[green]Semantic vector store ready[/green]")
            else:
                console.print("[yellow]Vector store unavailable, using substring search[/yellow]")
        except Exception as e:
            log.error("Vector store init failed: %s", e)
            console.print(f"[yellow]Vector store unavailable: {e}[/yellow]")

    # Whisper STT (optional - skip if not available)
    stt_model = None
    if WHISPER_AVAILABLE:
        try:
            console.print(f"[yellow]Loading Whisper {whisper_model} (CPU)...[/yellow]")
            stt_model = whisper.load_model(whisper_model, device="cpu")
            console.print("[green]Whisper ready[/green]")
            log.info("Whisper loaded: %s", whisper_model)
        except Exception as e:
            log.error("Whisper load failed: %s", e)
            console.print(f"[yellow]Whisper unavailable: {e}[/yellow]")
            console.print("[yellow]Voice input disabled - use text mode[/yellow]")
    else:
        console.print("[yellow]Whisper not installed - voice input disabled[/yellow]")
        console.print("[yellow]Install with: pip install openai-whisper[/yellow]")

    # Piper TTS (non-critical)
    tts_service = None
    try:
        console.print("[yellow]Loading Piper TTS (CPU)...[/yellow]")
        voice_path = config.get("tts", {}).get("piper", {}).get("voice_path")
        tts_service = TextToSpeechService(voice_path=voice_path)
        console.print("[green]Piper TTS ready[/green]")
        log.info("Piper TTS loaded")
    except Exception as e:
        log.warning("Piper TTS load failed: %s", e)
        console.print(f"[yellow]TTS unavailable: {e}. Continuing without speech output.[/yellow]")

    # Orchestrator
    orchestrator = Orchestrator(config, console)
    console.print("[green]Orchestrator ready[/green]")

    # Web search
    search_engine = None
    if search_cfg.get("enabled", True):
        try:
            search_engine = WebSearch(search_cfg)
            console.print("[green]DuckDuckGo search ready[/green]")
        except Exception as e:
            log.warning("Web search init failed: %s", e)
            console.print(f"[yellow]Web search unavailable: {e}[/yellow]")

    # Tool executor
    tool_executor = None
    if db:
        try:
            tool_executor = ToolExecutor(db, config)
            console.print("[green]Tool system ready (9 tools)[/green]")
        except Exception as e:
            log.warning("Tool executor init failed: %s", e)
            console.print(f"[yellow]Tool system unavailable: {e}[/yellow]")

    # Resource manager
    resource_mgr = ResourceManager(config, connectivity)
    max_history = config.get("chat", {}).get("max_history_messages", 50)
    chat_history = BoundedChatHistory(max_messages=max_history)

    # Detect recording sample rate
    recording_sr = _get_recording_samplerate()
    console.print(f"[green]Audio input: {recording_sr} Hz[/green]")

    # Pre-load text model (Ollama only - not needed for cloud)
    if backend in ("ollama", "auto"):
        if not connectivity or not connectivity.is_online:
            try:
                resource_mgr.load_text_model()
            except Exception as e:
                log.warning("Text model pre-load failed: %s", e)
                console.print(f"[yellow]Text model pre-load failed: {e}[/yellow]")

    console.print(
        Panel(
            "[dim]Press Enter to start recording, Enter again to stop.\n"
            "Say 'exit' or 'quit' to stop. Ctrl+C to force quit.[/dim]\n"
            "[dim]Vision:[/dim]  'take a photo', 'what do you see', 'camera'\n"
            "[dim]Search:[/dim]  'search for ...', 'weather in ...', 'latest news'\n"
            "[dim]Memory:[/dim]  'remember that ...', 'what do you know about ...'\n"
            "[dim]Tasks:[/dim]   'create a task ...', 'list my tasks', 'mark done'\n"
            "[dim]Utils:[/dim]   'what time is it', 'where am I'\n"
            "[dim]Chat:[/dim]    anything else",
            title="Controls",
            border_style="dim",
        )
    )

    # -- Signal handling --
    shutdown_event = threading.Event()

    def _signal_handler(signum, frame):
        log.info("Received signal %s, shutting down...", signal.Signals(signum).name)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Main loop
    openrouter_client = resource_mgr._openrouter
    try:
        while not shutdown_event.is_set():
            try:
                console.input("\n[dim]Press Enter to start recording...[/dim]")
            except EOFError:
                break

            if shutdown_event.is_set():
                break

            data_queue = Queue()
            stop_event = threading.Event()
            recording_thread = threading.Thread(target=record_audio, args=(stop_event, data_queue, recording_sr))
            recording_thread.start()

            try:
                input("Recording... Press Enter to stop ")
            except EOFError:
                stop_event.set()
                recording_thread.join()
                break

            stop_event.set()
            recording_thread.join()

            chunks = list(data_queue.queue)
            if not chunks:
                continue
            audio_np = np.concatenate(chunks).flatten()

            try:
                should_continue = process_interaction(
                    audio_np,
                    stt_model,
                    orchestrator,
                    resource_mgr,
                    search_engine,
                    tool_executor,
                    db,
                    tts_service,
                    chat_history,
                    config,
                    recording_sr,
                )

                if not should_continue:
                    console.print("[blue]Goodbye![/blue]")
                    break
            except Exception as e:
                log.error("Interaction error: %s\n%s", e, traceback.format_exc())
                console.print(f"[red]Error during interaction: {e}[/red]")
                console.print("[dim]Recovering... ready for next input.[/dim]")
                continue

    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
    finally:
        log.info("Shutting down...")
        _cleanup(resource_mgr, db, openrouter_client)
        console.print("[blue]Session ended.[/blue]")
        log.info("Session ended")


if __name__ == "__main__":
    main()
