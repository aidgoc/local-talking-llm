# 📚 LTL User Guide - Complete Documentation

> **Local Talking LLM** - Your Privacy-First AI Assistant

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [CLI Commands](#cli-commands)
4. [Tool System](#tool-system)
5. [Configuration](#configuration)
6. [Channel Integration](#channel-integration)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

## 🚀 Quick Start

### Prerequisites
- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, or Windows (WSL)
- **RAM**: 4GB minimum (8GB recommended)
- **Microphone**: For voice interaction (optional)

### 1-Minute Setup

```bash
# Clone and enter directory
git clone https://github.com/aidgoc/LTL.git
cd LTL

# Run installer
chmod +x install.sh
./install.sh

# Initialize LTL
python3 -m ltl init

# Check status
python3 -m ltl status

# Test a tool
python3 -m ltl tool web_search query="hello world"
```

---

## 📦 Installation

### Automated Installation (Recommended)

```bash
# Make installer executable
chmod +x install.sh

# Run installer
./install.sh
```

This will:
- ✅ Check Python version
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Create data directories
- ✅ Download Piper voice model
- ✅ Pull Ollama models (if Ollama is installed)

### Manual Installation

```bash
# Create virtual environment
python3.11 -m venv .venv311
source .venv311/bin/activate

# Install package
pip install -e ".[dev]"

# Install optional channel dependencies
pip install python-telegram-bot discord.py

# Initialize LTL
python3 -m ltl init
```

### Verify Installation

```bash
# Check CLI works
python3 -m ltl --help

# Check status
python3 -m ltl status

# Should show:
# ✓ Config: ~/.ltl/config.json
# ✓ Workspace: ~/.ltl/workspace
# ✓ All template files present
```

---

## 🎮 CLI Commands

### Core Commands

#### `ltl init` - Initialize Workspace
```bash
# First time setup
python3 -m ltl init

# Force re-initialization (will overwrite)
python3 -m ltl init --force
```

Creates:
- `~/.ltl/config.json` - Configuration file
- `~/.ltl/workspace/` - Working directory with templates
- `~/.ltl/workspace/memory/` - Long-term memory storage
- `~/.ltl/workspace/skills/` - Custom skills directory

#### `ltl status` - System Status
```bash
python3 -m ltl status
```

Shows:
- Configuration status
- Workspace file status
- API provider status
- Channel status

#### `ltl config` - Configuration Management
```bash
# View current config
python3 -m ltl config show

# Edit config in default editor
python3 -m ltl config edit
```

### Tool Commands

#### `ltl tool` - Execute Tools
```bash
# List all available tools
python3 -m ltl tool list

# Get help for specific tool
python3 -m ltl tool help web_search

# Execute a tool
python3 -m ltl tool web_search query="python tutorial"

# Execute with multiple parameters
python3 -m ltl tool execute_command command="ls -la" timeout=30
```

### Channel Commands

#### `ltl gateway` - Start Message Gateway
```bash
# Start gateway (runs in foreground)
python3 -m ltl gateway

# Stop with Ctrl+C
```

This starts the message routing system for:
- Telegram bot
- Discord bot
- Future channels

### Setup Commands

#### `ltl setup` - Configure Services
```bash
# Show available setup options
python3 -m ltl setup

# Setup LocalAI for enhanced LLM
python3 -m ltl setup localai

# Setup Whisper for voice transcription
python3 -m ltl setup whisper
```

### Task Management

#### `ltl cron` - Scheduled Tasks
```bash
# List scheduled tasks
python3 -m ltl cron list

# Add a reminder
python3 -m ltl cron add -n "lunch" -m "Time for lunch!" -e 3600

# Remove a task
python3 -m ltl cron remove <task_id>
```

### Chat Interface

#### `ltl chat` - Interactive Chat
```bash
# Start interactive chat mode
python3 -m ltl chat

# Send single message
python3 -m ltl chat -m "What time is it?"

# Specify backend
python3 -m ltl chat --backend openrouter
```

---

## 🔧 Tool System

LTL includes 7 built-in tools for automation and data retrieval.

### Available Tools

#### 1. Web Search (`web_search`)
Search the web using DuckDuckGo (free, no API key).

```bash
# Basic search
python3 -m ltl tool web_search query="python best practices"

# Limit results
python3 -m ltl tool web_search query="AI news" max_results=3
```

**Parameters:**
- `query` (required): Search query string
- `max_results` (optional): Number of results (1-10, default: 5)

#### 2. Web Fetch (`web_fetch`)
Fetch and extract text content from a URL.

```bash
# Fetch article
python3 -m ltl tool web_fetch url="https://example.com/article"

# Limit content length
python3 -m ltl tool web_fetch url="https://example.com/docs" max_chars=2000
```

**Parameters:**
- `url` (required): URL to fetch
- `max_chars` (optional): Maximum characters to return (default: 5000)

#### 3. File Operations

**Read File (`read_file`):**
```bash
python3 -m ltl tool read_file path="~/document.txt"
```

**Write File (`write_file`):**
```bash
# Write new file
python3 -m ltl tool write_file path="~/notes.txt" content="My notes here"

# Append to file
python3 -m ltl tool write_file path="~/notes.txt" content="More notes" append=true
```

**List Directory (`list_dir`):**
```bash
# List current directory
python3 -m ltl tool list_dir path="."

# List recursively
python3 -m ltl tool list_dir path="/home" recursive=true
```

#### 4. Execute Command (`execute_command`)
Execute shell commands safely.

```bash
# Simple command
python3 -m ltl tool execute_command command="echo Hello"

# With timeout
python3 -m ltl tool execute_command command="sleep 5" timeout=10
```

**Security:** Dangerous commands (rm -rf, mkfs, etc.) are blocked.

#### 5. Get Time (`get_time`)
Get current time and date.

```bash
# Default format
python3 -m ltl tool get_time

# Custom format
python3 -m ltl tool get_time format="%Y-%m-%d"
```

### Using Tools Programmatically

```python
from ltl.core.tools import get_registry
from ltl.tools import register_builtin_tools

# Initialize
registry = get_registry()
register_builtin_tools(registry)

# Execute tool
result = registry.execute("web_search", query="python", max_results=3)

if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")
```

---

## ⚙️ Configuration

### Configuration File Location
```
~/.ltl/config.json
```

### Default Configuration

```json
{
  "version": "2.1.0",
  "agents": {
    "defaults": {
      "workspace": "~/.ltl/workspace",
      "model": "gemma3",
      "max_tokens": 8192,
      "temperature": 0.7,
      "max_tool_iterations": 20
    }
  },
  "backend": "ollama",
  "channels": {
    "telegram": {
      "enabled": false,
      "token": "",
      "allow_from": []
    },
    "discord": {
      "enabled": false,
      "token": "",
      "allow_from": []
    }
  },
  "providers": {
    "ollama": {
      "base_url": "http://localhost:11434",
      "text_model": "gemma3",
      "vision_model": "moondream"
    },
    "localai": {
      "enabled": false,
      "base_url": "http://localhost:8080"
    },
    "openrouter": {
      "api_key": "",
      "api_base": "https://openrouter.ai/api/v1"
    }
  },
  "tools": {
    "web": {
      "search": {
        "enabled": true,
        "max_results": 5
      }
    },
    "voice": {
      "enabled": true,
      "whisper_model": "base.en"
    }
  }
}
```

### Configuration Sections

#### Backend Settings
- `backend`: Primary backend (`ollama`, `openrouter`, or `auto`)
- `providers`: API configurations for each provider

#### Channel Settings
- `telegram`: Telegram bot configuration
- `discord`: Discord bot configuration

#### Tool Settings
- `web.search`: Web search configuration
- `voice`: Voice transcription settings

### Environment Variables

You can override config values using environment variables:

```bash
# Override OpenRouter API key
export TALKING_LLM_PROVIDERS_OPENROUTER_API_KEY="sk-or-v1-xxx"

# Override backend
export TALKING_LLM_BACKEND="openrouter"
```

---

## 📱 Channel Integration

### Telegram Bot Setup

1. **Create Bot with BotFather:**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Your User ID:**
   - Search for `@userinfobot`
   - It will show your user ID

3. **Configure LTL:**
   ```bash
   python3 -m ltl config edit
   ```
   
   Add to `channels.telegram`:
   ```json
   {
     "enabled": true,
     "token": "YOUR_BOT_TOKEN_HERE",
     "allow_from": ["YOUR_USER_ID"]
   }
   ```

4. **Start Gateway:**
   ```bash
   python3 -m ltl gateway
   ```

5. **Test:**
   - Open Telegram
   - Find your bot
   - Send a message!

### Discord Bot Setup

1. **Create Discord Application:**
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Name it "LTL Assistant"

2. **Create Bot:**
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the token

3. **Enable Intents:**
   - Enable "MESSAGE CONTENT INTENT"
   - Save changes

4. **Invite Bot:**
   - Go to "OAuth2" → "URL Generator"
   - Select scopes: `bot`
   - Bot permissions: `Send Messages`, `Read Message History`
   - Open the generated URL and add to your server

5. **Configure LTL:**
   ```json
   {
     "enabled": true,
     "token": "YOUR_BOT_TOKEN_HERE",
     "allow_from": ["YOUR_DISCORD_USER_ID"]
   }
   ```

6. **Start Gateway:**
   ```bash
   python3 -m ltl gateway
   ```

---

## 🚀 Advanced Features

### LocalAI Integration

LocalAI provides faster, more capable local LLM inference than Ollama.

**Setup:**
```bash
python3 -m ltl setup localai
```

Or manually with Docker:
```bash
docker run -p 8080:8080 -v $HOME/.localai:/models localai/localai:latest
```

**Enable in config:**
```json
{
  "providers": {
    "localai": {
      "enabled": true,
      "base_url": "http://localhost:8080"
    }
  }
}
```

### Voice Transcription

Uses openai-whisper for local speech-to-text.

**Setup:**
```bash
python3 -m ltl setup whisper
```

**Models:**
- `tiny` - Fastest, less accurate (39 MB)
- `base` - Balanced (74 MB)
- `small` - Better accuracy (244 MB)
- `medium` - Best accuracy (769 MB)

**Configure:**
```json
{
  "tools": {
    "voice": {
      "transcription": "whisper",
      "whisper_model": "base"
    }
  }
}
```

### Custom Tools

Create custom tools by extending the Tool base class:

```python
from ltl.core.tools import Tool, ToolParameter, ToolResult

class MyTool(Tool):
    def name(self):
        return "my_tool"
    
    def description(self):
        return "Does something useful"
    
    def parameters(self):
        return [
            ToolParameter("input", "string", "Input data", required=True)
        ]
    
    def execute(self, input):
        # Your logic here
        return ToolResult(success=True, data=f"Processed: {input}")

# Register
from ltl.core.tools import register_tool
register_tool(MyTool())
```

---

## 🔧 Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'ltl'"
```bash
# Make sure you're in the project directory
cd /path/to/LTL

# Activate virtual environment
source .venv311/bin/activate

# Install package
pip install -e .
```

#### "Ollama connection failed"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start Ollama
ollama serve

# Pull required models
ollama pull gemma3
ollama pull moondream
```

#### "Permission denied" on install
```bash
# Make scripts executable
chmod +x install.sh
chmod +x run_optimized.sh

# Or run with bash
bash install.sh
```

#### Telegram bot not responding
```bash
# Check if gateway is running
python3 -m ltl gateway

# Verify token in config
python3 -m ltl config show

# Check BotFather for token
# Ensure "allow_from" includes your user ID
```

#### Web search not working
- Check internet connection
- DuckDuckGo is rate-limited for heavy use
- Consider using Brave Search API for production

### Debug Mode

Enable debug logging:
```bash
# Set environment variable
export TALKING_LLM_LOG_LEVEL=DEBUG

# Run command
python3 -m ltl status
```

### Getting Help

```bash
# Show help for any command
python3 -m ltl --help
python3 -m ltl tool --help
python3 -m ltl cron --help

# Check logs
ls ~/.local/share/talking-llm/logs/
```

---

## ❓ FAQ

**Q: Is LTL completely free?**
A: Yes! LTL is 100% free and open source (MIT License). All core features use free, local, open-source software.

**Q: Does it require internet?**
A: No! With Ollama backend, everything runs locally. Internet is only needed for web search and optional cloud LLMs.

**Q: Can I use it without a GPU?**
A: Yes! LTL works on CPU-only systems. Models will be slower but fully functional.

**Q: Is my data private?**
A: Absolutely! All conversations, memories, and data stay on your machine. No cloud storage, no data sharing.

**Q: How do I add custom tools?**
A: See "Custom Tools" section above. You can extend the Tool class and register your own tools.

**Q: Can I use it with ChatGPT/Claude?**
A: Yes! Configure OpenRouter in `config.json` with your API key to access cloud models.

**Q: What's the difference between Ollama and LocalAI?**
A: Ollama is simpler and easier to set up. LocalAI is faster and more powerful for complex tasks but requires Docker.

**Q: How do I backup my data?**
A: Your data is in `~/.ltl/`. Simply copy this directory to backup:
```bash
cp -r ~/.ltl ~/ltl_backup
```

---

## 📖 Additional Resources

- **Main Application**: See `app_optimized.py` for voice-enabled assistant
- **Architecture**: See `AI_INSTRUCTIONS.md` for technical details
- **Contributing**: See `CONTRIBUTING.md` for development guide
- **Changelog**: See `CHANGELOG.md` for version history

---

## 🤝 Support

- **Issues**: https://github.com/aidgoc/LTL/issues
- **Discussions**: https://github.com/aidgoc/LTL/discussions
- **Email**: Open an issue for contact

---

**Made with ❤️ for privacy-conscious users**

*Local Talking LLM - Your data, your control, your AI.*
