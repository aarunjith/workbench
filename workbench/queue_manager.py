from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo import MongoClient, ReturnDocument
from multiprocessing import Queue
from logging import getLogger
from .cache import cache, from_cache, REDIS

logger = getLogger(__name__)


@dataclass
class ListenerMetadata:
    listener_id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    status: str = "active"
    usage: int = 0
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "listener_id": self.listener_id,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status,
            "usage": self.usage,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


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
        # Message queue for communication between listeners
        self.message_queue = Queue()
        # Dictionary to track active listeners
        self.active_listeners = {}  # listener_id -> timestamp
        # MongoDB connection for persistent storage
        self.mongo_client = MongoClient("mongodb://localhost:27017/")
        self.db = self.mongo_client["listener_db"]
        self.listeners_collection = self.db["listeners"]

        logger.info("QueueManager initialized")

    def _cache_key(self, listener_id: str) -> str:
        return f"listener_{listener_id}"

    @cache(prefix="listener", kwarg_name="listener_id", ex=3600)
    def attach_listener(
        self, listener_id: str, metadata: ListenerMetadata, stop_event: Any
    ):
        """
        Register a new listener with the queue manager
        """
        # Store in MongoDB
        metadata_dict = asdict(metadata)
        self.listeners_collection.find_one_and_update(
            {"listener_id": listener_id},
            {"$set": metadata_dict},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        # Add to active listeners dictionary with stop event
        self.active_listeners[listener_id] = ActiveListenerData(
            timestamp=datetime.now(),
            stop_event=stop_event,
            metadata=metadata,
        )
        logger.info(f"Listener {listener_id} attached")
        return {"listener_id": listener_id, "metadata": metadata.to_dict()}

    def detach_listener(self, listener_id: str):
        """
        Remove a listener from the queue manager and stop its thread
        """
        # Remove from active listeners dictionary and trigger stop event
        if listener_id in self.active_listeners:
            listener_data = self.active_listeners[listener_id]
            if listener_data.stop_event:
                listener_data.stop_event.set()
            del self.active_listeners[listener_id]
        else:
            logger.warning(f"Attempted to detach non-existent listener {listener_id}")

        # Remove from Redis cache
        REDIS.delete(self._cache_key(listener_id))

        # Update status in metadata
        self.listeners_collection.update_one(
            {"listener_id": listener_id}, {"$set": {"status": "inactive"}}
        )

        logger.info(f"Listener {listener_id} detached")

    @from_cache(prefix="listener", kwarg_name="listener_id", ex=3600)
    def get_listener_metadata(self, listener_id: str) -> Optional[ListenerMetadata]:
        """
        Fetch listener metadata from cache first, then DB
        """
        metadata = self.listeners_collection.find_one(
            {"listener_id": listener_id}, projection={"_id": False}
        )
        if metadata:
            # Convert datetime strings back to datetime objects
            if "created_at" in metadata:
                metadata["created_at"] = str(metadata["created_at"])
            if "last_active" in metadata:
                metadata["last_active"] = str(metadata["last_active"])
            return metadata
        return None

    @from_cache(prefix="listeners", kwarg_name="status", ex=3600)
    def get_all_listeners(self, status: str = "active") -> List[dict]:
        """
        Fetch all listeners with the given status
        """
        listeners = list(
            self.listeners_collection.find(
                {"status": status}, projection={"_id": False}
            )
        )
        for listener in listeners:
            if "created_at" in listener:
                listener["created_at"] = str(listener["created_at"])
            if "last_active" in listener:
                listener["last_active"] = str(listener["last_active"])
        return listeners

    @cache(prefix="listener", kwarg_name="listener_id", ex=3600)
    def update_listener_activity(self, listener_id: str) -> Optional[dict]:
        """
        Update last active timestamp for a listener and increment usage count
        """
        now = datetime.now()
        # Update DB
        metadata = self.listeners_collection.find_one_and_update(
            {"listener_id": listener_id},
            {"$set": {"last_active": now}, "$inc": {"usage": 1}},
            projection={"_id": False},
            return_document=ReturnDocument.AFTER,
        )
        if metadata:
            metadata["last_active"] = str(metadata["last_active"])
            metadata["created_at"] = str(metadata["created_at"])
            return metadata
        return None

    def close(self):
        """
        Clean up connections
        """
        self.mongo_client.close()
