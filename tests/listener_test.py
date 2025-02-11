import time
import asyncio
from typing import Dict, Any
from workbench import Listener, Message, QueueManager, ListenerMetadata
from logging import getLogger

logger = getLogger(__name__)

# Create queue manager and event
# This can be passed to multiple listeners to enable them to communicate with each other
queue_manager = QueueManager()

metadata = ListenerMetadata(
    listener_id="1",
    listener_type="agent",
    listener_name="Test Listener",
    description="A test listener",
)  # Only required field


class TestListener(Listener):
    async def _listen(self, message: Message) -> Dict[str, Any]:
        logger.warning(f"TestListener received message: {message}")
        return message.data


async def main():
    queue_manager = QueueManager()
    metadata = ListenerMetadata(
        listener_id="test-listener",
        listener_type="agent",
        listener_name="Test Listener",
    )

    # Create listener and initialize async components
    test_listener = TestListener(queue_manager=queue_manager, metadata=metadata)
    await test_listener.init_async()

    # Start listening
    await test_listener.start()

    # Create and send test message
    test_message = Message(
        listener_id="2",
        data={"message": "Test data"},
        target_listener=test_listener.listener_id,
        accessed=False,
    )
    await test_listener._send(test_message)

    try:
        while True:
            try:
                await asyncio.sleep(5)
                listeners = await queue_manager.async_get_all_listeners(status="active")
                logger.debug(f"All listeners: {listeners}")
            except asyncio.CancelledError:
                break
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await test_listener.stop()
        await queue_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
