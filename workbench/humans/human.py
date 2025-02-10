from abc import abstractmethod
from typing import Dict, Any
from ..listener import Listener, Message
from ..queue_manager import QueueManager, ListenerMetadata
from dataclasses import dataclass
from ..agents.agent_messages import AgentInput
from ..agents.state_managers import StateManager
from pydantic import BaseModel, Field

class HumanProtocol(BaseModel):
    query: str = Field(..., description="The query to be answered by the human")


@dataclass
class HumanConfig:
    human_name: str
    description: str
    queue_manager: QueueManager
    state_manager: StateManager
    input_schema: Dict[str, Any] = HumanProtocol.model_json_schema() # Define how to interact with this human
    output_schema: Dict[str, Any] = AgentInput.model_json_schema() # Define what this human can provide

class Human(Listener):
    def __init__(self, config: HumanConfig):
        metadata = ListenerMetadata(
            listener_id=self._generate_listener_id("human"),
            listener_type="human",
            listener_name=config.human_name,
            description=config.description,
            input_schema=config.input_schema,
            output_schema=config.output_schema,
        )
        super().__init__(config.queue_manager, metadata)
        self.state_manager = config.state_manager

    @abstractmethod
    def _listen(self, message: Message) -> Dict[str, Any]:
        """
        Abstract method that should be implemented by concrete human interface classes.
        Should handle receiving and processing messages from the human user.

        Args:
            message (Message): The incoming message to be processed

        Returns:
            Dict[str, Any]: The processed response data from the human
        """
        pass
