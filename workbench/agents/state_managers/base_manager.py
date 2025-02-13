from abc import ABC, abstractmethod
from .state import State
from ...cache import from_cache, cache
from typing import Dict, Any, Optional


class StateManager(ABC):
    @from_cache(prefix="states", kwarg_name="conversation_id")
    @abstractmethod
    async def get_state(
        self, conversation_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously get the latest state from cache, or from the source if not in cache.
        """
        pass

    @cache(prefix="states", kwarg_name="conversation_id")
    @abstractmethod
    async def update_state(self, conversation_id: str, state: State) -> Dict[str, Any]:
        """
        Asynchronously update and return the state so it can be cached.
        """
        pass
