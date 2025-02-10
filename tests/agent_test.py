import time
from workbench import (Agent,
                       Tool,
                       AgentConfig,
                       ToolConfig,
                       ModelConfig,
                       QueueManager,
                       ListenerMetadata,
                       Listener,
                       Message)
from workbench.agents import AgentConfig
from workbench.tools import ToolConfig
from workbench import MongoStateManager
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from workbench import HumanConfig, CLIHuman
import getpass
import os

import logging

# Configure root logger to show debug messages
logging.basicConfig(level=logging.DEBUG)

# Get and configure specific loggers used in the codebase
loggers = [
    logging.getLogger('workbench'),
    logging.getLogger('workbench.agents'),
    logging.getLogger('workbench.tools'),
    logging.getLogger('workbench.listener'),
    logging.getLogger('workbench.queue_manager'),
    logging.getLogger('workbench.humans')
]

for logger in loggers:
    logger.setLevel(logging.DEBUG)


os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Anthropic API Key: ")

queue_manager = QueueManager()
state_manager = MongoStateManager()

agent_config = AgentConfig(
    agent_name="test_agent",
    queue_manager=queue_manager,
    state_manager=state_manager,
    model_config=ModelConfig(
        model_name="claude-3-5-sonnet-20241022",
    ),
    agent_description="help the user with their questions.",
    keep_last_messages=10,
)

agent = Agent(agent_config)
agent_thread = agent.listen()
print("Agent is listening.....")

human_config = HumanConfig(
    human_name="human123",
    queue_manager=queue_manager,
    state_manager=state_manager,
    description="A human that can help any agent if they are stuck assisting the user.",
)

human = CLIHuman(human_config)
human_thread = human.listen()
print("Human is listening.....")



class EmailInput(BaseModel):
    target_address: str = Field(..., description="The target email address")
    subject: str = Field(..., description="The subject of the email")
    body: str = Field(..., description="The body of the email")

class EmailOutput(BaseModel):
    success: bool = Field(..., description="Whether the email was sent successfully")
    error: Optional[str] = Field(None, description="The error message if the email was not sent")


class EmailSenderTool(Tool):
    def __init__(self, config: ToolConfig):
        super().__init__(config)

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Sending email to {input_data['target_address']}"
              f" with subject {input_data['subject']} "
              f"and body {input_data['body']}")
        return {"success": True}


tool_config = ToolConfig(
    tool_name="email_sender",
    description="Sends an email to the target address with the given subject and body",
    input_schema=EmailInput.model_json_schema(),
    output_schema=EmailOutput.model_json_schema(),
    queue_manager=queue_manager,
)

email_sender_tool = EmailSenderTool(tool_config)
email_sender_tool_thread = email_sender_tool.listen()
print("Email sender tool is listening.....")

# Sending a test message to the agent
human._send(Message(
    listener_id=human.listener_id,
    data=("I have trouble logging in to my Steam account."
      " I have tried all the ways to get in but so far nothing has worked."
      " Please help me. The steam customer service email is: support@steampowered.com"),
    target_listener=agent.listener_id,
    accessed=False,
    needs_response=True,
))

try:
    while True:
        time.sleep(5)
        
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    agent.stop()
    email_sender_tool.stop()
    # Clean up
    agent_thread.join(timeout=2)
    email_sender_tool_thread.join(timeout=2)
    queue_manager.detach_listener(agent.listener_id)
    queue_manager.detach_listener(email_sender_tool.listener_id)
    queue_manager.close()



