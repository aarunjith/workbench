from pydantic import BaseModel, Field
from typing import Literal, TypeVar
import json

T = TypeVar("T", bound="AgentMessage")


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(
        description="The role of the message sender - can be user or assistant"
    )
    content: str = Field(description="The actual content/text of the message")

    def to_json(self):
        return json.dumps(self.model_dump())

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        return cls.model_validate_json(json_str)


class AgentInput(AgentMessage):
    """Input message from a user to an agent"""

    role: Literal["user"] = Field(
        default="user",
        description="The role of the message sender, always 'user' for input messages",
    )
    content: str = Field(description="The actual message content from the user")


class AgentOutput(AgentMessage):
    """Output message from an agent to a user"""

    role: Literal["assistant"] = Field(
        default="assistant",
        description="The role of the message sender, always 'assistant' for output messages",
    )
    content: str = Field(description="The actual message content from the agent")
