from dataclasses import dataclass
from ..agent_messages import AgentMessage
from typing import List, Dict, Any, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound="State")

@dataclass
class State:
    conversation_id: str
    messages: List[AgentMessage]
    metadata: Dict[str, Any]

    # IMPROVE: This is a temporary solution to limit the number of messages in the state
    def truncate_messages(self, keep_last: int = 10) -> None:
        self.messages = self.messages[-keep_last:]
    
    def add_message(self, message: AgentMessage) -> None:
        self.messages.append(message)

    @classmethod
    def from_dict(cls: type[T], data: Dict[str, Any]) -> T:
        return cls(conversation_id=data['conversation_id'],
                   messages=[AgentMessage(**message) for message in data['messages']],
                   metadata=data['metadata'])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conversation_id': self.conversation_id,
            'messages': [message.model_dump() for message in self.messages],
            'metadata': self.metadata
        }

