"""Chat command - Text-based chat with the assistant."""

import os
import re
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Try to import langchain, fallback to simple implementation
try:
    from langchain_core.chat_history import InMemoryChatMessageHistory
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables.history import RunnableWithMessageHistory
    from langchain_ollama import OllamaLLM

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

try:
    from src.web_search import WebSearch
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

# Phrases that signal a web-search intent
_SEARCH_RE = re.compile(
    r"^(search( for)?|look up|find( out)?|google|what is|who is|"
    r"when (is|was|did)|where is|how (do|does|can|to)|latest|news about)\b",
    re.IGNORECASE,
)


class TextChatAssistant:
    """Text-based chat assistant using Ollama."""

    def __init__(self, config: dict, search_engine=None):
        self.config = config
        self.search_engine = search_engine
        self.chat_history = []  # Simple list for history

        # Initialize Ollama config
        ollama_config = config.get("providers", {}).get("ollama", {})
        self.base_url = ollama_config.get("base_url", "http://localhost:11434")
        self.model = ollama_config.get("text_model", "gemma3")
        self.temperature = config.get("agents", {}).get("defaults", {}).get("temperature", 0.7)

        if LANGCHAIN_AVAILABLE:
            # Use langchain if available
            self.chat_history = InMemoryChatMessageHistory()
            self.llm = OllamaLLM(model=self.model, base_url=self.base_url, temperature=self.temperature)

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are LTL, a helpful AI assistant. Be concise, accurate, and friendly. You can help with tasks, answer questions, and provide information.",
                    ),
                    MessagesPlaceholder(variable_name="history"),
                    ("human", "{input}"),
                ]
            )

            self.chain = RunnableWithMessageHistory(
                prompt | self.llm,
                lambda session_id: self.chat_history,
                input_messages_key="input",
                history_messages_key="history",
            )
        else:
            # Fallback to direct Ollama API calls
            self.use_direct_api = True

    def _maybe_inject_search(self, message: str) -> str:
        """If message looks like a search query, prepend web results and return enriched prompt."""
        if not self.search_engine or not _SEARCH_RE.match(message):
            return message
        print("🔍 Searching...", flush=True)
        results = self.search_engine.search_and_format(message, max_results=4)
        if not results or results == "No search results found.":
            return message
        return (
            f"{message}\n\n"
            f"[Web search results for context:]\n{results}"
        )

    def chat(self, message: str) -> str:
        """Send a message and get response."""
        enriched = self._maybe_inject_search(message)
        if LANGCHAIN_AVAILABLE:
            try:
                response = self.chain.invoke(
                    {"input": enriched}, config={"configurable": {"session_id": "ltl-cli-chat"}}
                )
                return str(response)
            except Exception as e:
                return f"Sorry, I encountered an error: {e}"
        else:
            # Direct API fallback
            return self._chat_direct(enriched)

    def _chat_direct(self, message: str) -> str:
        """Direct Ollama API chat without langchain."""
        try:
            import requests

            # Build conversation history
            messages = [
                {
                    "role": "system",
                    "content": "You are LTL, a helpful AI assistant. Be concise, accurate, and friendly.",
                }
            ]

            # Add recent history (last 4 messages to keep context manageable)
            for msg in self.chat_history[-4:]:
                if msg.startswith("You: "):
                    messages.append({"role": "user", "content": msg[5:]})
                elif msg.startswith("LTL: "):
                    messages.append({"role": "assistant", "content": msg[5:]})

            # Add current message
            messages.append({"role": "user", "content": message})

            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": 512},
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result["message"]["content"]
                return ai_response
            else:
                return f"API error: {response.status_code}"

        except Exception as e:
            return f"Sorry, I encountered an error: {e}"


def run(args):
    """Run the chat command."""
    # Load config
    try:
        from ltl.core.config import load_config

        config = load_config()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        print("Run 'ltl init' first to set up LTL.")
        return

    # Check if Ollama is available
    try:
        import requests

        ollama_config = config.get("providers", {}).get("ollama", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")

        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code != 200:
            raise Exception("Ollama not responding")
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        print("Or start it with: systemctl start ollama")
        return

    # Web search (optional)
    search_engine = None
    no_search = getattr(args, "no_search", False)
    if SEARCH_AVAILABLE and not no_search:
        try:
            search_engine = WebSearch(config.get("search", {}))
            print("🔍 DuckDuckGo search enabled")
        except Exception as e:
            print(f"⚠️  Search unavailable: {e}")

    # Initialize chat assistant
    try:
        assistant = TextChatAssistant(config, search_engine=search_engine)
    except Exception as e:
        print(f"❌ Failed to initialize chat assistant: {e}")
        return

    if args.message:
        # Single message mode
        print(f"🎙️  You: {args.message}")
        print("🤖 Assistant: ", end="", flush=True)
        response = assistant.chat(args.message)
        print(response)
    else:
        # Interactive mode
        print("🎙️  LTL Text Chat Mode")
        print("   Type 'exit', 'quit', or 'bye' to stop")
        print("   Type 'clear' to clear chat history")
        if search_engine:
            print("   Search: start with 'search for', 'what is', 'look up', etc.")
        print()

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("\n👋 Goodbye!")
                    break

                if user_input.lower() == "clear":
                    assistant.chat_history.clear()
                    print("🧹 Chat history cleared\n")
                    continue

                print("🤖 Assistant: ", end="", flush=True)
                response = assistant.chat(user_input)
                print(response)
                print()

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break
