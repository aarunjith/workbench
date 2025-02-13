from .base_llm import BaseLLM, ModelConfig, ModelResponse
from anthropic import AsyncAnthropic, AsyncAnthropicBedrock
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
            self.client = AsyncAnthropicBedrock()
        else:
            assert "ANTHROPIC_API_KEY" in os.environ, "Anthropic API key not found"
            self.client = AsyncAnthropic()

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
        messages = [message.model_dump() for message in messages]
        tools_input = self.construct_tools_input(connected_listeners)

        response = await self.client.messages.create(
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
        response_text = ""
        tool_use = False
        tool_name = None
        target_listener = None
        tool_args = None
        for block in response.content:
            if block.type == "text":
                response_text = block.text
            elif block.type == "tool_use":
                tool_args = block.input
                tool_name, target_listener = block.name.split("__")
                # Add tool call details to response text
                tool_details = f"\n\nTool Call Details:\nTool: {tool_name}\nListener: {target_listener}\nArguments: {tool_args}"
                response_text = response_text + tool_details if response_text else tool_details
        if response.stop_reason == "tool_use":
            tool_use = True
        else:
            tool_use = False
        return ModelResponse(
            response_text=response_text,
            tool_use=tool_use,
            tool_name=tool_name,
            target_listener=target_listener,
            tool_args=tool_args,
            output_tokens=response.usage.output_tokens,
            input_tokens=response.usage.input_tokens,
        )
