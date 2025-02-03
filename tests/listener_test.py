import time
from threading import Thread
from typing import Dict, Any
from workbench.listener import Listener, Message
from workbench.queue_manager import QueueManager, ListenerMetadata
from logging import getLogger

logger = getLogger(__name__)

# Create queue manager and event
queue_manager = QueueManager()

metadata = ListenerMetadata(listener_id="1")  # Only required field


class TestListener(Listener):
    def _listen(self, message: Message) -> Dict[str, Any]:
        logger.warning(f"TestListener received message: {message}")
        return message.data


test_listener = TestListener(queue_manager=queue_manager, metadata=metadata)

# Example of how to get metadata
logger.info(
    f"Listener metadata: {queue_manager.get_listener_metadata(test_listener.listener_id)}"
)

# Start listener in a separate thread
listener_thread = Thread(target=test_listener.listen)
listener_thread.daemon = True
listener_thread.start()

logger.info("Listener started")
time.sleep(2)

# Create and send test message
test_message = Message(
    listener_id="2",
    data={"message": "Test data"},
    target_listener=test_listener.listener_id,  # Post a message to a non-existent listener
    accessed=False,
)
test_listener._send(test_message)

try:
    while True:
        time.sleep(5)
        # Example of getting all listeners
        logger.debug(
            f"All listeners: {queue_manager.get_all_listeners(status='active')}"
        )
except KeyboardInterrupt:
    logger.info("Shutting down...")
finally:
    test_listener.stop()
    listener_thread.join(timeout=2)
    # Clean up
    queue_manager.detach_listener(test_listener.listener_id)
    queue_manager.close()
