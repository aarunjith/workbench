import logging
from workbench.humans.human import Human, HumanConfig
from workbench.listener import Message
import aiohttp
import asyncio
from ..agents.state_managers import State

logger = logging.getLogger(__name__)


class TelegramHuman(Human):
    def __init__(self, config: HumanConfig, telegram_token: str, chat_id: int):
        """
        Initialize a TelegramHuman that uses a Telegram bot to communicate with a human user.

        :param config: HumanConfig instance.
        :param telegram_token: Bot token provided by BotFather.
        :param chat_id: The Telegram chat ID for the human user.
        """
        super().__init__(config)
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{telegram_token}"
        self.updates_url = f"{self.base_url}/getUpdates"
        self.send_url = f"{self.base_url}/sendMessage"

    async def _listen(self, message: Message):
        """
        When a message is addressed to this human, forward it to the Telegram user.
        """
        original_conversation_id = message.conversation_id
        logger.debug(f"Original conversation id: {original_conversation_id}")
        conversation_state = State.from_dict(
            await self.state_manager.get_state(conversation_id=original_conversation_id)
        )
        logger.debug(f"Conversation state: {conversation_state}")

        conv_history = conversation_state.messages
        conv_history_str = "\n".join(
            [f"**{msg.role}:**\n{msg.content}" for msg in conv_history]
        )
        text = f"**Conversation History**\n\n{conv_history_str}\n\n"
        logger.debug(f"Sending message to Telegram: {text}")
        response = await self._wait_for_response(text)
        return {"role": "user", "content": response}

    async def _wait_for_response(self, message: str):
        """
        Wait for a response from the Telegram user.
        """
        current_length = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(self.updates_url) as response:
                updates = await response.json()
                if updates["ok"] and updates["result"]:
                    current_length = len(updates["result"])
                    logger.debug(
                        f"Current length of the telegram chat: {current_length}"
                    )

            send_params = {"chat_id": self.chat_id, "text": message}
            async with session.post(self.send_url, params=send_params) as response:
                send_response = await response.json()

            if send_response["ok"]:
                # Wait for response
                last_message = None
                while True:
                    async with session.get(self.updates_url) as response:
                        response_json = await response.json()
                        if response_json["ok"] and response_json["result"]:
                            if len(response_json["result"]) > current_length:
                                # Get the most recent message
                                last_message = response_json["result"][-1]["message"]
                                if "text" in last_message:
                                    logger.debug(
                                        f"Received response from Telegram: {last_message['text']}"
                                    )
                                    return last_message["text"]

                    await asyncio.sleep(1)  # Wait 1 second before checking again
