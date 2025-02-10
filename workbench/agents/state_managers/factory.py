from .base_manager import StateManager
import importlib
from typing import Literal

class StateManagerFactory:
    @staticmethod
    def create_state_manager(manager_type: Literal["dict", "mongo"]) -> StateManager:
        module = importlib.import_module(f".{manager_type}_manager")
        cls_ = getattr(module, f"{manager_type.capitalize()}StateManager")
        return cls_()
