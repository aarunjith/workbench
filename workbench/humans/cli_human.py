from .human import Human, HumanConfig
from typing import Dict, Any
from ..listener import Message
from logging import getLogger

logger = getLogger(__name__)


class CLIHuman(Human):
    def __init__(self, config: HumanConfig):
        super().__init__(config)

    def _listen(self, message: Message) -> Dict[str, Any]:
        # This logic would handle the human listening in for any messages.
        # Only agents can invoke humans and the response will be sent back to the agent only
        # Direct tool calls are not supported at this time
        # One can still technically call a tool directly using queue manager but not sure if this will be useful
        user_input = []
        listener_id = message.listener_id
        conversation_id = message.conversation_id
        current_state = self.state_manager.get_state(conversation_id=conversation_id)
        messages = current_state["messages"]
        # Since this runs in a separate thread, we need to be careful about console output
        # Log the conversation history and new message
        logger.info("\n=== Conversation History ===")
        if messages:
            for msg in messages:
                prefix = "User:" if msg["role"] == "user" else "Assistant:"
                logger.info(f"{prefix} {msg['content']}\n")

        logger.info(f"\nNew message from {listener_id}:")
        if isinstance(message.data, dict):
            if "content" in message.data:
                logger.info(message.data["content"])
            else:
                logger.info(message.data)
        else:
            logger.info(message.data)
            
        logger.info("\nWaiting for user input (press Enter twice to finish)...")

        # Get user input - this will block the thread until input is received
        # This is okay since this thread's purpose is to handle human interaction
        user_input = []
        while True:
            try:
                line = input()
                if line == "":
                    break
                user_input.append(line)
            except EOFError:
                # Handle case where input stream is closed
                logger.error("Input stream closed unexpectedly")
                break

        user_response = "\n".join(user_input)
        logger.info(f"Received user input: {user_response}")
        
        return {"role": "user", "content": user_response}






