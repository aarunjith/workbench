from .base_manager import StateManager
from .state import State
from typing import Dict, Any
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorClient
import os


class MongoStateManager(StateManager):
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client["listener_db"]
        self.collection = self.db["states"]

    async def get_state(self, conversation_id: str) -> Dict[str, Any]:
        state = await self.collection.find_one(
            {"conversation_id": conversation_id}, projection={"_id": False}
        )
        if state is None:
            return {"conversation_id": conversation_id, "messages": [], "metadata": {}}
        return state

    async def update_state(self, conversation_id: str, state: State) -> Dict[str, Any]:
        updated_state = await self.collection.find_one_and_update(
            {"conversation_id": conversation_id},
            {"$set": state.to_dict()},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": False},
        )
        return updated_state
