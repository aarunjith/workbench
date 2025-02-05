from ..listener import Listener
from ..queue_manager import QueueManager, ListenerMetadata
from uuid import uuid4
from .agent_messages import AgentMessage, AgentInput, AgentOutput
from typing import List, Literal
from pydantic import BaseModel
from dataclasses import dataclass
from .models import ModelConfig, ModelResponse


class AgentState(BaseModel):
    messages: List[AgentMessage]


@dataclass
class AgentConfig:
    agent_description: str
    queue_manager: QueueManager
    model: ModelConfig


class Agent(Listener):
    def __init__(
        self,
        queue_manager: QueueManager,
        model: ModelConfig,
        agent_description: str = "An AI Agent",
    ):
        self.agent_id = self._get_agent_id()
        self.agent_description = agent_description
        self.model = model
        self.model.system_prompt = (
            f"You are an AI agent. Your goal is to {self.agent_description}."
        )
        agent_metadata = ListenerMetadata(
            listener_id=self.agent_id,
            description=self.agent_description,
            input_schema=AgentInput.model_json_schema(),
            output_schema=AgentOutput.model_json_schema(),
        )
        super().__init__(queue_manager, agent_metadata)

    def _get_agent_id(self) -> str:
        agent_id = uuid4().hex[:6]
        return f"agent-{agent_id}"
