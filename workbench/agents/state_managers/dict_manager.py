from .base_manager import StateManager
from .state import State
from typing import Dict, Any

class DictStateManager(StateManager):
    def __init__(self):
        self.state_dict = {} # type: Dict[str, Dict[str, Any]]

    def get_state(self, conversation_id: str) -> Dict[str, Any]:
        return self.state_dict.get(conversation_id,
                                   {"conversation_id": conversation_id,
                                    "messages": [],
                                    "metadata": {}})

    def update_state(self, conversation_id: str, state: State) -> Dict[str, Any]:
        self.state_dict[conversation_id] = state.to_dict()
        return self.state_dict[conversation_id]

