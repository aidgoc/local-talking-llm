"""Workspace management for LTL."""

import os


LTL_DIR = os.path.expanduser("~/.ltl")
WORKSPACE_DIR = os.path.join(LTL_DIR, "workspace")


def get_workspace_path():
    """Get the workspace path."""
    return WORKSPACE_DIR


def get_config_path():
    """Get the config path."""
    return os.path.join(LTL_DIR, "config.json")


def create_workspace():
    """Create the workspace directory structure."""
    # Create main directories
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "memory"), exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "skills"), exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "cron"), exist_ok=True)

    # Create template files
    create_template_files()

    return WORKSPACE_DIR


def create_template_files():
    """Create template markdown files in workspace."""

    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
- Be proactive and helpful
- Learn from user feedback

## Capabilities

- Voice interaction (speech-to-text and text-to-speech)
- Vision analysis (camera/image understanding)
- Web search for current information
- Task management and reminders
- Memory storage and recall
- Tool execution (time, location, etc.)
""",
        "SOUL.md": """# Soul

I am LTL (Local Talking LLM), a privacy-first AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn
- Honest and transparent
- Privacy-conscious

## Values

- User privacy and data security
- Transparency in actions
- Accuracy over speed
- Continuous improvement
- Local-first operation

## Mission

To provide intelligent AI assistance while keeping all data local and private.
""",
        "USER.md": """# User

Information about user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
- Voice: (enabled/disabled)
- Vision: (enabled/disabled)

## Personal Information

- Name: (optional)
- Location: (optional)
- Occupation: (optional)

## Learning Goals

- What the user wants to learn from AI
- Preferred interaction style
- Areas of interest

## Important Notes

- (Any important preferences or facts to remember)
""",
        "IDENTITY.md": """# Identity

## Name
LTL (Local Talking LLM) 🎙️

## Description
Privacy-first personal AI assistant with voice interaction, vision capabilities, and local data storage.

## Version
2.1.0

## Purpose
- Provide intelligent AI assistance with complete privacy
- Support voice interaction for hands-free operation
- Enable vision analysis for image understanding
- Maintain local-only data storage (no cloud)
- Run efficiently on consumer hardware (4GB VRAM)

## Capabilities

### Core
- Voice recognition (Whisper)
- Natural language understanding (Gemma3)
- Text-to-speech (Piper)
- Vision analysis (Moondream)

### Tools
- Web search (DuckDuckGo)
- Memory storage and retrieval
- Task management
- Time and location
- File operations

### Integrations
- Ollama (local LLM)
- OpenRouter (cloud fallback)
- Multiple chat channels (planned)

## Philosophy

- Privacy over convenience
- Local over cloud
- Open source and transparent
- User control and ownership
- Community-driven development

## Goals

- Provide fast, private AI assistance
- Enable offline operation
- Support multi-modal interaction
- Maintain high quality responses
- Run on consumer hardware

## License
MIT License - Free and open source

## Repository
https://github.com/aidgoc/LTL

## Contact
Issues: https://github.com/aidgoc/LTL/issues
""",
        "TOOLS.md": """# Available Tools

## Core Tools

### Memory
- `save_memory(key, content)` - Store information
- `get_memory(key)` - Retrieve information
- `search_memories(query)` - Search stored memories
- `list_memories()` - List all memories

### Tasks
- `create_task(title, description)` - Create a new task
- `list_tasks()` - List all tasks
- `complete_task(task_id)` - Mark task as complete

### Time & Location
- `get_time()` - Get current time
- `get_location()` - Get current location

### Web
- `web_search(query)` - Search the web
- `fetch_url(url)` - Fetch content from URL

### System
- `execute_command(cmd)` - Execute shell command
- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to file

## Usage

Tools are automatically invoked based on user intent.
The orchestrator determines which tools to use for each request.
""",
    }

    for filename, content in templates.items():
        filepath = os.path.join(WORKSPACE_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(content)

    # Create memory file
    memory_path = os.path.join(WORKSPACE_DIR, "memory", "MEMORY.md")
    if not os.path.exists(memory_path):
        with open(memory_path, "w") as f:
            f.write("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)

## Configuration

- Model preferences
- Channel settings
- Tools enabled
""")
