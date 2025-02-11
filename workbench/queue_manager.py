from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from asyncio import Queue
from logging import getLogger
from .cache import REDIS
import asyncio
import json
from pymongo import ReturnDocument

logger = getLogger(__name__)


@dataclass
class ListenerMetadata:
    listener_id: str
    listener_type: Literal["agent", "tool", "human"]
    listener_name: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    status: Literal["active", "inactive"] = "active"
    usage: int = 0
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "listener_id": self.listener_id,
            "listener_type": self.listener_type,
            "listener_name": self.listener_name,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status,
            "usage": self.usage,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    def to_json(self) -> str:
        """Serialize metadata to JSON string with datetime handling"""
        return json.dumps(
            {
                **asdict(self),
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "last_active": (
                    self.last_active.isoformat() if self.last_active else None
                ),
            }
        )


@dataclass
class ActiveListenerData:
    timestamp: datetime
    stop_event: Any
    metadata: ListenerMetadata

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "metadata": asdict(self.metadata),
        }


class QueueManager:
    def __init__(self):
        # Async message queue for communication between listeners
        self.message_queue = Queue()
        # Dictionary to track active listeners
        self.active_listeners = {}
        # MongoDB async connection for persistent storage
        self.mongo_client = AsyncIOMotorClient("mongodb://localhost:27017/")
        self.db = self.mongo_client["listener_db"]
        self.listeners_collection = self.db["listeners"]

        logger.info("QueueManager initialized")

    def _cache_key(self, listener_id: str) -> str:
        return f"listener_{listener_id}"

    async def attach_listener(
        self, listener_id: str, metadata: ListenerMetadata
    ) -> Dict[str, Any]:
        """
        Register a new listener with the queue manager
        """
        # Store in MongoDB
        metadata_dict = asdict(metadata)
        result = await self.listeners_collection.find_one_and_update(
            {"listener_id": listener_id},
            {"$set": metadata_dict},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        # Add to active listeners dictionary
        self.active_listeners[listener_id] = metadata

        # Cache the result
        await REDIS.set(self._cache_key(listener_id), metadata.to_json(), ex=3600)

        logger.info(f"Listener {listener_id} attached")
        return {"listener_id": listener_id, "metadata": metadata_dict}

    async def async_detach_listener(self, listener_id: str):
        """
        Remove a listener from the queue manager
        """
        # Remove from active listeners dictionary
        if listener_id in self.active_listeners:
            del self.active_listeners[listener_id]

        # Remove from Redis cache
        await REDIS.delete(self._cache_key(listener_id))

        # Update status in metadata
        await self.listeners_collection.update_one(
            {"listener_id": listener_id}, {"$set": {"status": "inactive"}}
        )

        logger.info(f"Listener {listener_id} detached")

    async def async_put_message(self, message_json: str):
        """
        Put a message into the queue
        """
        await self.message_queue.put(message_json)

    async def async_get_message(self, listener_id: str, timeout: float = 1) -> str:
        """
        Only return a message if it is for the intended listener.
        """
        while True:
            try:
                message_json = await asyncio.wait_for(
                    self.message_queue.get(), timeout=timeout
                )
                message = json.loads(message_json)
                if message["target_listener"] == listener_id:
                    return message_json
                else:
                    logger.debug(
                        f"Skipping message {message} because it was not addressed to {listener_id}"
                    )
                    await self.async_put_message(message_json)
                    await asyncio.sleep(0.1)  # Yield control before trying again
            except asyncio.TimeoutError:
                raise

    async def async_get_listener_metadata(
        self, listener_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch listener metadata from cache first, then DB
        """
        # Try cache first
        cached_data = await REDIS.get(self._cache_key(listener_id))
        if cached_data:
            return json.loads(cached_data)

        # If not in cache, get from DB
        metadata = await self.listeners_collection.find_one(
            {"listener_id": listener_id}, projection={"_id": False}
        )

        if metadata:
            # Convert datetime objects to strings
            if "created_at" in metadata:
                metadata["created_at"] = str(metadata["created_at"])
            if "last_active" in metadata:
                metadata["last_active"] = str(metadata["last_active"])

            # Cache the result
            await REDIS.set(self._cache_key(listener_id), json.dumps(metadata), ex=3600)
            return metadata
        return None

    async def async_get_all_listeners(
        self, status: str = "active"
    ) -> List[Dict[str, Any]]:
        """
        Fetch all listeners with the given status
        """
        cursor = self.listeners_collection.find(
            {"status": status}, projection={"_id": False}
        )

        listeners = []
        async for listener in cursor:
            if "created_at" in listener:
                listener["created_at"] = str(listener["created_at"])
            if "last_active" in listener:
                listener["last_active"] = str(listener["last_active"])
            listeners.append(listener)

        return listeners

    async def async_update_listener_activity(self, listener_id: str) -> Optional[dict]:
        """
        Update last active timestamp for a listener and increment usage count
        """
        now = datetime.now()
        # Update DB
        metadata = await self.listeners_collection.find_one_and_update(
            {"listener_id": listener_id},
            {"$set": {"last_active": now}, "$inc": {"usage": 1}},
            projection={"_id": False},
            return_document=ReturnDocument.AFTER,
        )

        if metadata:
            # Fix datetime serialization for cache
            metadata["last_active"] = metadata["last_active"].isoformat()
            metadata["created_at"] = metadata["created_at"].isoformat()
            await REDIS.set(self._cache_key(listener_id), json.dumps(metadata), ex=3600)
            return metadata
        return None

    async def close(self):
        """
        Clean up connections
        """
        self.mongo_client.close()
