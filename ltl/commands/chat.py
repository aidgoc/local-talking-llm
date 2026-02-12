"""Chat command - Chat with the assistant."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run(args):
    """Run the chat command."""
    if args.message:
        # Single message mode
        print(f"🎙️  You: {args.message}")
        print("\n🤖 Assistant: (This would connect to your LTL assistant)")
        print("   To use the full assistant, run: python app_optimized.py")
    else:
        # Interactive mode
        print("🎙️  LTL Chat Mode")
        print("   Type 'exit' or 'quit' to stop\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    print("\n👋 Goodbye!")
                    break

                print("🤖 Assistant: (This would connect to your LTL assistant)")
                print("   To use the full assistant, run: python app_optimized.py")
                print()

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
