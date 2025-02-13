from .base_llm import BaseLLM, ModelConfig, ModelResponse
from typing import List, Dict, Any, Optional
from ..agent_messages import AgentMessage
from ...listener import ListenerMetadata
from ollama import AsyncClient
from logging import getLogger

logger = getLogger(__name__)


class OllamaModel(BaseLLM):
    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        assert model_config.provider == "ollama", "Ollama provider must be ollama"
        # If requesting for JSON then we need to update the system prompt
        if model_config.response_format:
            assert isinstance(
                model_config.response_format, str
            ), "Response format must be a string"
            self.system_prompt = f"{self.system_prompt}\n\n{f'Respond in the following format only: \n{model_config.response_format}'}"
        self.model_name = self.get_ollama_name(self.model_name)
        self.client = AsyncClient()

    def get_ollama_name(self, model_name: str) -> str:
        return model_name.split("/")[1]

    def construct_tools_input(
        self, connected_listeners: List[ListenerMetadata]
    ) -> List[Dict[str, Any]]:
        if not connected_listeners:
            return []
        tools_input = [
            {
                "name": f"{listener.listener_name}__{listener.listener_id}",
                "description": listener.description,
                "input_schema": listener.input_schema,
            }
            for listener in connected_listeners
        ]
        logger.debug(f"Tools input: {tools_input}")
        return tools_input

    async def generate_response(
        self,
        messages: List[AgentMessage],
        connected_listeners: Optional[List[ListenerMetadata]] = None,
    ) -> ModelResponse:
        logger.debug(f"Messages: {messages}")
        if self.system_prompt:
            current_messages = [{"role": "system", "content": self.system_prompt}]
        else:
            current_messages = []
        messages = [*current_messages, *[message.model_dump() for message in messages]]
        tools_input = self.construct_tools_input(connected_listeners)

        response = await self.client.chat(
            messages=messages,
            model=self.model_name,
            tools=tools_input,
        )

        logger.debug(f"Response: {response}")
        parsed_response = self.parse_response(response)
        logger.debug(f"Parsed response: {parsed_response}")
        return parsed_response

    def parse_response(self, response) -> ModelResponse:
        logger.debug(f"Response to parse: {response}")
        response_text = ""
        tool_use = False
        tool_name = None
        target_listener = None
        tool_args = None

        # Ollama returns a ChatResponse object with a message attribute
        if hasattr(response, "message"):
            response_text = response.message.content or ""

            # Check for tool calls
            if hasattr(response.message, "tool_calls") and response.message.tool_calls:
                tool_use = True
                # Get the first tool call
                tool_call = response.message.tool_calls[0]
                if hasattr(tool_call, "function"):
                    # Extract tool name and target listener from the function name
                    # The name should be in format: tool_name__listener_id
                    function_name = tool_call.function.name
                    if "__" in function_name:
                        tool_name, target_listener = function_name.split("__")
                    else:
                        # If no listener ID in the name, use the whole name as tool_name
                        tool_name = function_name
                    # Get the arguments as tool args
                    tool_args = tool_call.function.arguments

        # Get token counts from the response
        input_tokens = getattr(response, "prompt_eval_count", 0)
        output_tokens = getattr(response, "eval_count", 0)

        return ModelResponse(
            response_text=response_text,
            tool_use=tool_use,
            tool_name=tool_name,
            target_listener=target_listener,
            tool_args=tool_args,
            output_tokens=output_tokens,
            input_tokens=input_tokens,
        )
