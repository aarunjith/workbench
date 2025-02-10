from abc import ABC, abstractmethod
from .state import State
from ...cache import from_cache, cache
from typing import Dict, Any

class StateManager(ABC):
    @from_cache(prefix='states', kwarg_name='conversation_id')
    @abstractmethod
    def get_state(self, conversation_id: str) -> Dict[str, Any]:
        # Get the latest state from cache, or from the source if not in cache
        pass

    @cache(prefix='states', kwarg_name='conversation_id')
    @abstractmethod
    def update_state(self, conversation_id: str, state: State) -> Dict[str, Any]:
        # Needs to return the updated state to cache
        pass
