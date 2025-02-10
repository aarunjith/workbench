from abc import ABC, abstractmethod
from typing import List, Literal, Dict, Any, Optional
from ..agent_messages import AgentMessage, AgentOutput
from ...listener import ListenerMetadata
from dataclasses import dataclass


@dataclass
class ModelResponse:
    response_text: str
    target_listener: Optional[str] = None
    tool_use: bool = False
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    output_tokens: Optional[int] = None
    input_tokens: Optional[int] = None



@dataclass
class ModelConfig:
    model_name: str
    temperature: float = 0.5
    max_tokens: int = 4096
    hosting_provider: Literal["native", "bedrock", "azure", "local"] = "native"
    response_format: Optional[str] = None
    system_prompt: str = "You are a helpful assistant."
    stream: bool = False

    @property
    def provider(self) -> Literal["anthropic", "openai", "ollama"]:
        if self.model_name.startswith("claude"):
            return "anthropic"
        elif self.model_name.startswith("gpt", "o3"):
            return "openai"
        elif self.model_name.startswith("ollama"):
            return "ollama"
        else:
            raise ValueError(
                f"Could not infer provider from model name: {self.model_name}"
            )


class BaseLLM(ABC):
    def __init__(self, model_config: ModelConfig):
        self.model_name = model_config.model_name
        self.max_tokens = model_config.max_tokens
        self.temperature = model_config.temperature
        self.system_prompt = model_config.system_prompt
        self.stream = model_config.stream
    @abstractmethod
    def generate_response(self, messages: List[AgentMessage],
                          connected_listeners: Optional[List[ListenerMetadata]] = None) -> ModelResponse:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    def construct_tools_input(
        self, connected_listeners: List[ListenerMetadata]
    ) -> List[Dict[str, Any]]:
        """Construct the tools input for different models as they require different formats"""
        pass

    @abstractmethod
    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        """Parse the LLM response and return the data"""
        pass
