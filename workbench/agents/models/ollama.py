from .base_llm import BaseLLM, ModelConfig, ModelResponse

from ollama import chat


class OllamaModel(BaseLLM):
    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        assert model_config.provider == "ollama", "Ollama provider must be ollama"

    def generate_response(
        self,
        messages: List[AgentMessage],
        connected_listeners: Optional[List[ListenerMetadata]] = None,
    ) -> ModelResponse:
        pass

    def construct_tools_input(
        self, connected_listeners: List[ListenerMetadata]
    ) -> List[Dict[str, Any]]:
        pass
