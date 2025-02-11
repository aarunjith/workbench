import asyncio
import logging
import getpass
from workbench import Message, TelegramHuman, HumanConfig, QueueManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # Get Telegram credentials from environment
    telegram_token = getpass.getpass("Enter your Telegram bot token: ")
    if not telegram_token:
        raise ValueError("Please set TELEGRAM_BOT_TOKEN environment variable")

    chat_id = getpass.getpass("Enter your Telegram chat ID: ")
    if not chat_id:
        raise ValueError("Please set TELEGRAM_CHAT_ID environment variable")

    # Initialize human
    human = TelegramHuman(
        config=HumanConfig(
            description="A human that can help any agent if they are stuck assisting the user.",
            human_name="telegram_human",
            queue_manager=QueueManager(),
        ),
        telegram_token=telegram_token,
        chat_id=int(chat_id),
    )

    # Initialize async components
    await human.init_async()

    try:
        # Create test message
        dummy_response = Message(
            listener_id="agent",
            conversation_id="test_conversation",
            data={"content": "Agent says: Please provide further details."},
            target_listener=human.listener_id,
            accessed=False,
            needs_response=True,
        )

        # Get response asynchronously
        logger.info("Waiting for human response via Telegram...")
        response = await human._listen(dummy_response)
        logger.info(f"Response from human: {response}")

    finally:
        # Clean up
        await human.stop()


if __name__ == "__main__":
    asyncio.run(main())
