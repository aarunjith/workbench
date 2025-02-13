from abc import ABC, abstractmethod
import json
import asyncio
from dataclasses import dataclass, asdict
from typing import TypeVar, Dict, Any, List, Optional
from logging import getLogger, basicConfig, INFO
from datetime import datetime
from .queue_manager import QueueManager, ListenerMetadata
from uuid import uuid4

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
    conversation_id: Optional[str] = None
    needs_response: bool = False

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
        self.listener_task = None
        logger.info(f"Listener initialized with id: {self.listener_id}")

    async def init_async(self):
        """Async initialization separate from __init__"""
        await self._register()
        logger.info(f"Listener {self.listener_id} fully initialized")
        return self

    async def _register(self):
        """Register this listener with the queue manager"""
        metadata = self.metadata
        metadata.created_at = datetime.now()
        metadata.last_active = datetime.now()
        await self.queue_manager.attach_listener(
            listener_id=self.listener_id, metadata=metadata
        )

    def _generate_conversation_id(self) -> str:
        return f"conv-{uuid4().hex[:6]}"

    @abstractmethod
    async def _listen(self, message: Message) -> Dict[str, Any]:
        """
        Abstract method to be implemented by specific listeners.
        Must be implemented as a coroutine.
        """
        logger.warning(
            f"Not implemented listener {self.listener_id} received message: {message}"
        )
        return message.data

    async def start(self):
        """Start the async listener"""
        self.listener_task = asyncio.create_task(self._listen_loop())
        return self.listener_task

    async def _listen_loop(self):
        """Main asynchronous listening loop"""
        while True:
            try:
                # Get message with timeout
                json_message = await self.queue_manager.async_get_message(
                    listener_id=self.listener_id, timeout=1
                )
                message = Message.from_json(json_message)

                if message.conversation_id is None:
                    message.conversation_id = self._generate_conversation_id()
                    logger.debug(
                        f"Generated conversation id: {message.conversation_id}"
                    )

                if not message.accessed and message.target_listener == self.listener_id:
                    logger.debug(f"Received message by {self.listener_id}: {message}")

                    # Process message using the subclass implementation
                    output_data = await self._listen(message)
                    if (
                        isinstance(output_data, dict)
                        and output_data.get("status") == "tool_call"
                    ):
                        # The agent is waiting for a response from the tool
                        continue

                    # Update activity
                    await self.queue_manager.async_update_listener_activity(
                        self.listener_id
                    )

                    # Handle response if needed
                    if message.needs_response or self.metadata.listener_type == "human":
                        needs_response = self.metadata.listener_type == "human"
                        output_message = Message(
                            listener_id=self.listener_id,
                            data=output_data,
                            target_listener=message.listener_id,
                            accessed=False,
                            conversation_id=message.conversation_id,
                            needs_response=needs_response,
                        )
                        await self._send(output_message)

            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                logger.info(f"Listener {self.listener_id} task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error while processing message: {str(e)}")
                await asyncio.sleep(0.1)  # Prevent tight loop on repeated errors

    async def _send(self, data: Message):
        """Asynchronous message sending"""
        json_data = data.to_json()
        logger.debug(f"Sending data: {json_data}")
        await self.queue_manager.async_put_message(json_data)

    async def stop(self):
        """Stop the listener"""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        await self.queue_manager.async_detach_listener(self.listener_id)
        logger.info(f"Listener {self.listener_id} stopped")

    async def get_connected_listeners(
        self, others: bool = True, avoid_listeners: Optional[List[str]] = None
    ) -> List[ListenerMetadata]:
        """Get all connected listeners"""
        listeners = await self.queue_manager.async_get_all_listeners(status="active")
        avoid_listeners = avoid_listeners or []
        if others:
            avoid_listeners.append(self.listener_id)
        return [
            ListenerMetadata(**listener)
            for listener in listeners
            if listener["listener_id"] not in avoid_listeners
        ]

    def _generate_listener_id(self, prefix: str = "listener") -> str:
        return f"{prefix}-{uuid4().hex[:6]}"
