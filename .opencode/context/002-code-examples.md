# Code Examples for Talking LLM Assistant

## ResourceManager Pattern

### Loading Text Model
```python
# Load text model for chat
resource_mgr.load_text_model("gemma3")
response = resource_mgr.get_text_response("Hello!", chat_history)
```

### Loading Vision Model
```python
# MUST unload first due to 4GB VRAM limit
resource_mgr.unload_current_model()  # Critical!
resource_mgr.load_vision_model("moondream")
response = resource_mgr.get_vision_response("What do you see?", image_b64)
```

### Complete Vision Flow
```python
# 1. User asks vision question
if is_vision_request:
    # 2. Capture image
    image_b64 = capture_image()
    
    # 3. Load vision model (unloads text first automatically)
    response = resource_mgr.get_vision_response(text, image_b64)
    
    # 4. Free VRAM for next text chat
    if not args.keep_vision_loaded:
        resource_mgr.unload_current_model()
```

## Audio Processing

### Recording Audio
```python
def record_audio(stop_event, data_queue):
    def callback(indata, frames, time_info, status):
        data_queue.put(bytes(indata))
    
    with sd.RawInputStream(
        samplerate=16000, 
        dtype="int16", 
        channels=1, 
        callback=callback
    ):
        while not stop_event.is_set():
            time.sleep(0.1)
```

### Transcribing
```python
result = stt.transcribe(audio_np, fp16=False)  # CPU doesn't support fp16 well
text = result["text"].strip()
```

## Camera Capture

### Opening Preview
```python
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

cv2.namedWindow("Camera Preview", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Camera Preview", 640, 480)
```

### Capture with Timeout
```python
start_time = time.time()
auto_capture_timeout = 5

while True:
    ret, frame = cap.read()
    elapsed = time.time() - start_time
    remaining = max(0, auto_capture_timeout - elapsed)
    
    # Add overlay text
    cv2.putText(frame, f"Auto-capture in: {remaining:.1f}s", 
                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
    cv2.imshow("Camera Preview", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == 32:  # SPACE
        captured_frame = frame.copy()
        break
    elif key == 27:  # ESC
        break
    elif remaining <= 0:  # Timeout
        captured_frame = frame.copy()
        break
```

### Processing Image
```python
# Convert and resize
frame_rgb = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)
pil_image = Image.fromarray(frame_rgb)
pil_image = pil_image.resize((512, 384))  # Optimized for MX130

# Convert to base64
buffered = BytesIO()
pil_image.save(buffered, format="JPEG", quality=85)
img_str = base64.b64encode(buffered.getvalue()).decode()
```

## Text-to-Speech

### Basic Synthesis
```python
sample_rate, audio_array = tts.synthesize("Hello, world!")
sd.play(audio_array, sample_rate)
sd.wait()
```

### Long-form Synthesis
```python
sample_rate, audio_array = tts.long_form_synthesize(long_text)
play_audio(sample_rate, audio_array)
```

## Error Handling

### Camera Error
```python
if not cap.isOpened():
    console.print("[red]❌ Could not open camera!")
    console.print("[yellow]Hint: Check camera permissions in System Settings")
    return None
```

### GPU Memory Check
```python
def show_resource_usage():
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.memory_allocated() / 1e9
        gpu_total = torch.cuda.get_device_properties(0).total_memory / 1e9
        console.print(f"[dim]GPU: {gpu_mem:.1f}GB / {gpu_total:.1f}GB[/dim]")
```

### Ollama Connection Check
```python
import requests

try:
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={...},
        timeout=30
    )
    if response.status_code == 200:
        result = response.json()["message"]["content"]
    else:
        result = f"Error: Status {response.status_code}"
except requests.exceptions.ConnectionError:
    result = "Error: Cannot connect to Ollama. Is it running?"
```

## Configuration

### Loading Config
```python
import yaml

def load_config():
    default_config = {
        "text_model": "gemma3",
        "vision_model": "moondream",
        "whisper_model": "base.en",
    }
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            user_config = yaml.safe_load(f)
            # Merge with defaults
            return {**default_config, **user_config}
    
    return default_config
```

## Vision Keywords Detection

```python
VISION_KEYWORDS = ["see", "look", "camera", "what is this", "describe"]

is_vision_request = use_vision and any(
    keyword in text.lower()
    for keyword in VISION_KEYWORDS
)
```

## UI Elements with Rich

### Status Spinner
```python
with console.status("[yellow]🎤 Transcribing...", spinner="dots"):
    text = transcribe(audio_np)
```

### Panel
```python
console.print(Panel.fit(
    "[bold cyan]🤖 Voice Assistant[/bold cyan]\n\n"
    "Ready to help!",
    title="🚀 Ready",
    border_style="cyan",
))
```

### Colored Text
```python
console.print(f"[bold yellow]You:[/bold yellow] {text}")
console.print(f"[bold cyan]Assistant:[/bold cyan] {response}")
console.print("[green]✓ Success![/green]")
console.print("[red]❌ Error![/red]")
console.print("[yellow]⚠️ Warning[/yellow]")
```

## LangChain Integration

### Chat with History
```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant. Be concise."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt_template | text_llm
chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda sid: history,
    input_messages_key="input",
    history_messages_key="history",
)

response = chain_with_history.invoke(
    {"input": text}, 
    config={"session_id": "voice_assistant"}
).strip()
```

## Argument Parsing

```python
parser = argparse.ArgumentParser(description="Voice Assistant")
parser.add_argument("--model", type=str, default="gemma3", help="Text model")
parser.add_argument("--vision-model", type=str, default="moondream")
parser.add_argument("--whisper-model", type=str, default="base.en",
                   choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en"])
parser.add_argument("--vision", action="store_true", help="Enable vision mode")
parser.add_argument("--keep-vision-loaded", action="store_true")
args = parser.parse_args()
```
