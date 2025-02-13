from ..listener import Listener, Message
from ..queue_manager import QueueManager, ListenerMetadata
from uuid import uuid4
from .agent_messages import AgentMessage, AgentInput, AgentOutput
from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
from dataclasses import dataclass, asdict
from .models import ModelConfig, ModelResponse, ModelFactory
from .state_managers import StateManager, DictStateManager, State
from logging import getLogger

logger = getLogger(__name__)


@dataclass
class AgentConfig:
    agent_name: str
    queue_manager: QueueManager
    model_config: ModelConfig
    state_manager: Optional[StateManager] = DictStateManager()
    agent_description: str = "An AI Agent"
    keep_last_messages: int = 10


class Agent(Listener):
    def __init__(
        self,
        config: AgentConfig,
    ):
        self.agent_id = self._generate_listener_id(prefix="agent")
        self.agent_name = config.agent_name
        self.agent_description = config.agent_description
        self.model_config = config.model_config
        self.state_manager = config.state_manager
        self.model_config.system_prompt = (
            f"You are an AI agent. Your goal is to {self.agent_description}."
        )
        self.keep_last_messages = config.keep_last_messages
        agent_metadata = ListenerMetadata(
            listener_type="agent",
            listener_id=self.agent_id,
            listener_name=self.agent_name,
            description=self.agent_description,
            input_schema=AgentInput.model_json_schema(),
            output_schema=AgentOutput.model_json_schema(),
        )
        super().__init__(config.queue_manager, agent_metadata)
        self.base_llm = ModelFactory.create(self.model_config)

    async def _process_message(self, message: Message) -> AgentMessage:
        listener_metadata = await self.queue_manager.async_get_listener_metadata(
            listener_id=message.listener_id
        )
        if isinstance(message.data, dict):
            try:
                # Try to parse the message with the input schema of the agent
                input_message = AgentMessage(**message.data)
                return input_message
            except ValidationError as e:
                # When the input schema fails, give context to the agent about the data
                logger.debug(f"Not a valid agent message: {message}")
                logger.debug(
                    f'Parsing with the output schema of the sender: {listener_metadata["output_schema"]}'
                )
                message_content = (
                    "The output from the tool/agent is as follows:\n"
                    f"{message.data}\n"
                    "The output follows the JSON schema given below:\n"
                    f"{listener_metadata['output_schema']}"
                )
                try:
                    input_message = AgentMessage(role="user", content=message_content)
                    return input_message
                except ValidationError as e:
                    raise ValueError(f"Invalid message data: {e}")
        elif isinstance(message.data, str):
            return AgentMessage(role="user", content=message.data)
        else:
            raise ValueError(
                f"Invalid message data type ({type(message.data)}): {message}"
            )

    async def _listen(self, message: Message) -> Dict[str, Any]:
        original_conversation_id = message.conversation_id
        logger.debug(f"Original conversation id: {original_conversation_id}")
        # Do not invoke the same listener again if its a human, we will send the message to the same listener anyway
        listener_metadata = await self.queue_manager.async_get_listener_metadata(
            listener_id=message.listener_id
        )
        if listener_metadata["listener_type"] == "human":
            avoid_listeners = [message.listener_id]
        else:
            avoid_listeners = None

        raw_state = await self.state_manager.get_state(
            conversation_id=original_conversation_id
        )
        conversation_state = State.from_dict(raw_state)
        logger.debug(f"Conversation state: {conversation_state}")
        # IMPROVE: Need other strategies to manage the messages
        conversation_state.truncate_messages(keep_last=self.keep_last_messages)
        logger.debug(f"Conversation state after truncation: {conversation_state}")
        input_message = await self._process_message(message)
        conversation_state.add_message(input_message)
        connected_listeners = await self.get_connected_listeners(
            avoid_listeners=avoid_listeners
        )
        response = await self.base_llm.generate_response(
            conversation_state.messages, connected_listeners
        )
        # Update the state
        conversation_state.add_message(
            AgentMessage(role="assistant", content=response.response_text)
        )
        await self.state_manager.update_state(
            conversation_id=original_conversation_id, state=conversation_state
        )
        # This response might be a tool call, so we need to handle it
        if response.tool_use:
            target_listener = response.target_listener
            tool_data = response.tool_args
            tool_message = Message(
                listener_id=self.agent_id,
                data=tool_data,  # Tool specific message that adhers to the tool schema
                target_listener=target_listener,
                accessed=False,
                conversation_id=original_conversation_id,
                needs_response=True,  # Ask for a response from the tool
            )
            # Send a message to the tool listener
            await self._send(tool_message)
        # Do not need to invoke any other listener
        return asdict(response)
