---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''

---

## 🐛 Bug Description
<!-- A clear and concise description of what the bug is -->

## 🔍 Steps to Reproduce
<!-- Steps to reproduce the behavior -->
1. 
2. 
3. 
4. 

## ✅ Expected Behavior
<!-- What you expected to happen -->

## ❌ Actual Behavior
<!-- What actually happened -->

## 📋 System Information

<!-- Run these commands and paste the output -->

**Operating System:**
```bash
uname -a
```

**Python Version:**
```bash
python3 --version
```

**Ollama Status:**
```bash
curl http://localhost:11434/api/tags
```

**GPU Information (if applicable):**
```bash
nvidia-smi  # For NVIDIA
# or
system_profiler SPDisplaysDataType  # For macOS
```

**Installed Models:**
```bash
ollama list
```

## 📁 Configuration

**Your config file** (located at `~/.config/talking-llm/config.yaml`):
```yaml
# Paste your config here
```

## 📜 Error Logs

<!-- Paste any error messages or logs -->
```
[Paste error messages here]
```

## 🎯 AI Assistant Quick Check

<!-- For AI assistants helping debug: -->
- [ ] Ollama is running on port 11434
- [ ] Models are downloaded (gemma3, moondream)
- [ ] GPU has available memory (if using GPU)
- [ ] Python environment is activated
- [ ] Camera/microphone permissions granted (macOS)

## 🛠️ What I've Tried

<!-- List any troubleshooting steps you've already taken -->
- [ ] Restarted Ollama
- [ ] Checked GPU memory
- [ ] Verified camera permissions
- [ ] Reinstalled application
- [ ] Checked logs

## 📎 Additional Context

<!-- Add any other context about the problem here -->
- Does it happen consistently or intermittently?
- Does it happen with specific commands/phrases?
- Any recent changes to your system?

## 💡 Suggested Fix (Optional)

<!-- If you have an idea of how to fix this, describe it here -->

---

**For AI Assistants:**
This bug report uses structured sections to make it easy to parse. Key information:
- System info in code blocks
- Checkboxes for quick verification
- Clear sections for different data types
