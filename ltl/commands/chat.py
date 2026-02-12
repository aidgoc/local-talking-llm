"""Chat command - Text-based chat with the assistant."""

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_ollama import OllamaLLM


class TextChatAssistant:
    """Text-based chat assistant using Ollama."""

    def __init__(self, config: dict):
        self.config = config
        self.chat_history = InMemoryChatMessageHistory()

        # Initialize Ollama
        ollama_config = config.get("providers", {}).get("ollama", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")
        model = ollama_config.get("text_model", "gemma3")

        self.llm = OllamaLLM(
            model=model,
            base_url=base_url,
            temperature=config.get("agents", {}).get("defaults", {}).get("temperature", 0.7),
        )

        # Create the chat chain
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

    def chat(self, message: str) -> str:
        """Send a message and get response."""
        try:
            response = self.chain.invoke({"input": message}, config={"configurable": {"session_id": "ltl-cli-chat"}})
            return str(response)
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

    # Initialize chat assistant
    try:
        assistant = TextChatAssistant(config)
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
