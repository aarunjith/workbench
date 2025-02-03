from abc import ABC, abstractmethod
from queue import Empty
import json
import uuid
from dataclasses import dataclass, asdict
from typing import TypeVar, Dict, Any
from logging import getLogger, basicConfig, INFO
from threading import Event
from datetime import datetime
from .queue_manager import QueueManager, ListenerMetadata

# Configure logging
basicConfig(level=INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = getLogger(__name__)

T = TypeVar("T", bound="Message")


@dataclass
class Message:
    listener_id: str
    data: Dict[str, Any]
    target_listener: str
    accessed: bool

    def to_json(self):
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        return cls(**json.loads(json_str))


class Listener(ABC):
    def __init__(self, queue_manager: QueueManager, metadata: ListenerMetadata):
        self.queue_manager = queue_manager
        self.listener_id = metadata.listener_id
        self.metadata = metadata
        self.stop_event = Event()
        self._register()
        logger.info(f"Listener initialized with id: {self.listener_id}")

    def _register(self):
        """
        Register this listener with the queue manager
        """
        metadata = self.metadata
        metadata.created_at = datetime.now()
        metadata.last_active = datetime.now()
        self.queue_manager.attach_listener(
            listener_id=self.listener_id,
            metadata=metadata,
            stop_event=self.stop_event,
        )

    @abstractmethod
    def _listen(self, message: Message) -> Dict[str, Any]:
        logger.warning(
            f"Not implemented listener {self.listener_id} received message: {message}"
        )
        # This method should return a dictionary of data to be sent to the next listener
        # Ideally you should do some processing here
        return message.data

    def listen(self):
        while not self.stop_event.is_set():
            try:
                message = self.queue_manager.message_queue.get(timeout=1)
                message = Message.from_json(message)
                logger.debug(f"Received message: {message}")
                if not message.accessed and message.target_listener == self.listener_id:
                    output_data = self._listen(message)
                    self.queue_manager.update_listener_activity(
                        listener_id=self.listener_id
                    )
                    output_message = Message(
                        listener_id=self.listener_id,
                        data=output_data,
                        target_listener=message.listener_id,
                        accessed=False,
                    )
                    self._send(output_message)
                    message.accessed = True
                    self._send(message)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error while processing message: {str(e)}")
                continue
        logger.info(f"Listener {self.listener_id} stopped")

    def _send(self, data: Message):
        data = data.to_json()
        logger.debug(f"Sending data: {data}")
        self.queue_manager.message_queue.put(data)

    def stop(self):
        # Queue manager will stop the listener thread
        self.queue_manager.detach_listener(self.listener_id)
