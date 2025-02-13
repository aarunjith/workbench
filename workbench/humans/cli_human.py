from .human import Human, HumanConfig
from typing import Dict, Any, Optional
from ..listener import Message
from logging import getLogger
import sys
import threading
from prompt_toolkit import prompt

logger = getLogger(__name__)


class CLIHuman(Human):
    def __init__(self, config: HumanConfig):
        super().__init__(config)
        # Create a lock for synchronizing console I/O
        self._console_lock = threading.Lock()

    def _safe_print(self, message: str):
        """Thread-safe printing to console"""
        with self._console_lock:
            print(message, flush=True)

    def _safe_input(self, prefix: str = "") -> str:
        """Thread-safe input from console"""
        with self._console_lock:
            if prefix:
                print(prefix, end="", flush=True)
            return prompt()

    def _listen(
        self, message: Message, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # This logic would handle the human listening in for any messages.
        # Only agents can invoke humans and the response will be sent back to the agent only
        # Direct tool calls are not supported at this time
        # One can still technically call a tool directly using queue manager but not sure if this will be useful
        listener_id = message.listener_id
        conversation_id = message.conversation_id
        current_state = self.state_manager.get_state(conversation_id=conversation_id)
        messages = current_state["messages"]
        # Print conversation history
        self._safe_print("\n=== Conversation History ===")
        if messages:
            for msg in messages:
                prefix = "User:" if msg["role"] == "user" else "Assistant:"
                self._safe_print(f"{prefix} {msg['content']}\n")

        # Print new message
        self._safe_print(f"\nNew message from {listener_id}:")
        if isinstance(message.data, dict):
            if "content" in message.data:
                self._safe_print(message.data["content"])
            else:
                self._safe_print(str(message.data))
        else:
            self._safe_print(str(message.data))

        self._safe_print("\nWaiting for user input (press Enter twice to finish)...")

        # Get user input
        user_input = []
        while True:
            try:
                line = self._safe_input()
                if line == "":
                    break
                user_input.append(line)
            except EOFError:
                logger.error("Input stream closed unexpectedly")
                break

        user_response = "\n".join(user_input)
        self._safe_print(f"\nReceived user input: {user_response}")

        return {"role": "user", "content": user_response}
