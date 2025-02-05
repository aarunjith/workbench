from .base_llm import BaseLLM, ModelConfig, ModelResponse
from anthropic import Anthropic, AnthropicBedrock
from typing import List, Dict, Any, Optional
from ..agent_messages import AgentMessage
from ...listener import ListenerMetadata
import os
from logging import getLogger

logger = getLogger(__name__)


class AnthropicModel(BaseLLM):
    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        assert model_config.provider == "anthropic", "Claude provider must be anthropic"
        # If requesting for JSON then we need to update the system prompt
        if model_config.response_format:
            assert isinstance(
                model_config.response_format, str
            ), "Response format must be a string"
            self.system_prompt = f"{self.system_prompt}\n\n{f'Respond in the following format only: \n{model_config.response_format}'}"
        if model_config.hosting_provider == "bedrock":
            self.client = AnthropicBedrock()
        else:
            assert "ANTHROPIC_API_KEY" in os.environ, "Anthropic API key not found"
            self.client = Anthropic()

    def construct_tools_input(
        self, connected_listeners: List[ListenerMetadata]
    ) -> List[Dict[str, Any]]:
        if not connected_listeners:
            return []
        tools_input = [
            {
                "name": f"{listener.listener_name}||{listener.listener_id}",
                "description": listener.description,
                "input_schema": listener.input_schema,
            }
            for listener in connected_listeners
        ]
        logger.debug(f"Tools input: {tools_input}")
        return tools_input

    def generate_response(
        self,
        messages: List[AgentMessage],
        connected_listeners: Optional[List[ListenerMetadata]] = None,
    ) -> ModelResponse:
        logger.debug(f"Messages: {messages}")
        messages = [message.model_dump() for message in messages]
        tools_input = self.construct_tools_input(connected_listeners)
        response = self.client.messages.create(
            messages=messages,
            system=self.system_prompt,
            model=self.model_name,
            tools=tools_input,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        logger.debug(f"Response: {response}")
        parsed_response = self.parse_response(response)
        logger.debug(f"Parsed response: {parsed_response}")
        return parsed_response

    def parse_response(self, response) -> ModelResponse:
        logger.debug(f"Response to parse: {response}")
        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "text":
                    response_text = block.text
                elif block.type == "tool_use":
                    tool_args = block.input
                    tool_name, target_listener = block.name.split("||")
            return ModelResponse(
                response_text=response_text,
                tool_use=True,
                tool_name=tool_name,
                target_listener=target_listener,
                tool_args=tool_args,
                output_tokens=response.usage.output_tokens,
                input_tokens=response.usage.input_tokens,
            )
        elif response.stop_reason == "end_turn":
            return ModelResponse(
                response_text=response.content[0].text,
                tool_use=False,
                output_tokens=response.usage.output_tokens,
                input_tokens=response.usage.input_tokens,
            )
        else:
            raise ValueError(f"Unknown stop reason: {response.stop_reason}")
