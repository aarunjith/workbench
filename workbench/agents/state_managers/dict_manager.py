from .base_manager import StateManager
from .state import State
from typing import Dict, Any, Optional


class DictStateManager(StateManager):
    def __init__(self):
        # In-memory dictionary to store state per conversation_id
        self.state_dict: Dict[str, Dict[str, Any]] = {}

    async def get_state(
        self, conversation_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if metadata is None:
            metadata = {}
        # Return saved state; if none exists, return a default state
        return self.state_dict.get(
            conversation_id,
            {
                "conversation_id": conversation_id,
                "messages": [],
                "metadata": metadata,
            },
        )

    async def update_state(self, conversation_id: str, state: State) -> Dict[str, Any]:
        # Update the state and return it as a dictionary
        self.state_dict[conversation_id] = state.to_dict()
        return self.state_dict[conversation_id]
