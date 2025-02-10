from ..listener import ListenerMetadata, Listener, Message
from ..queue_manager import QueueManager
from typing import Dict, Any
from dataclasses import dataclass
from uuid import uuid4
from jsonschema import validate, ValidationError
from abc import ABC, abstractmethod

@dataclass
class ToolConfig:
    tool_name: str
    description: str
    queue_manager: QueueManager
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]

class Tool(Listener, ABC):
    def __init__(self, config: ToolConfig):
        self.tool_id = self._generate_listener_id(prefix="tool")
        tool_metadata = ListenerMetadata(
            listener_type="tool",
            listener_id=self.tool_id,
            listener_name=config.tool_name,
            description=config.description,
            input_schema=config.input_schema,
            output_schema=config.output_schema,
        )
        self.input_schema = config.input_schema
        self.output_schema = config.output_schema

        super().__init__(config.queue_manager, tool_metadata)
    
    def _validate_input(self, message: Message) -> None:
        try:
            validate(message.data, self.input_schema)
        except ValidationError as e:
            raise ValueError(f"Invalid input: {e}")

    def _listen(self, message: Message) -> Dict[str, Any]:
        self._validate_input(message)
        return self.execute(message.data)
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
