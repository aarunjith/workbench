import asyncio
import logging
import os
import getpass
from workbench import (
    Agent,
    Tool,
    AgentConfig,
    ToolConfig,
    ModelConfig,
    QueueManager,
    Message,
)
from workbench.agents import AgentConfig
from workbench.tools import ToolConfig
from workbench import MongoStateManager
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from workbench import HumanConfig, TelegramHuman

# Configure root logger to show debug messages
logging.basicConfig(level=logging.DEBUG)

# Get and configure specific loggers used in the codebase
loggers = [
    logging.getLogger("workbench"),
    logging.getLogger("workbench.agents"),
    logging.getLogger("workbench.tools"),
    logging.getLogger("workbench.listener"),
    logging.getLogger("workbench.queue_manager"),
    logging.getLogger("workbench.humans.telegram_human"),
]

for logger in loggers:
    logger.setLevel(logging.DEBUG)

# Set up API key
os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Anthropic API Key: ")

# Initialize managers
queue_manager = QueueManager()
state_manager = MongoStateManager()

# Set up agent
agent_config = AgentConfig(
    agent_name="test_agent",
    queue_manager=queue_manager,
    state_manager=state_manager,
    model_config=ModelConfig(
        model_name="claude-3-5-sonnet-20240620",
    ),
    agent_description="help the user with their questions.",
    keep_last_messages=10,
)

agent = Agent(agent_config)

# Set up human
human_config = HumanConfig(
    human_name="human123",
    queue_manager=queue_manager,
    state_manager=state_manager,
    description="A human that can help any agent if they are stuck assisting the user.",
)

human = TelegramHuman(
    human_config,
    telegram_token="7362976428:AAEp6RoArKEE2tRE5FEHbg6kqj3686BuKq8",
    chat_id="6493102810",
)


# Define email tool schemas
class EmailInput(BaseModel):
    target_address: str = Field(..., description="The target email address")
    subject: str = Field(..., description="The subject of the email")
    body: str = Field(..., description="The body of the email")


class EmailOutput(BaseModel):
    success: bool = Field(..., description="Whether the email was sent successfully")
    error: Optional[str] = Field(
        None, description="The error message if the email was not sent"
    )


# Define email tool
class EmailSenderTool(Tool):
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print(
            f"Sending email to {input_data['target_address']}"
            f" with subject {input_data['subject']} "
            f"and body {input_data['body']}"
        )
        return {"success": True}


# Set up email tool
tool_config = ToolConfig(
    tool_name="email_sender",
    description="Sends an email to the target address with the given subject and body",
    input_schema=EmailInput.model_json_schema(),
    output_schema=EmailOutput.model_json_schema(),
    queue_manager=queue_manager,
)

email_sender_tool = EmailSenderTool(tool_config)


async def main():
    # Initialize async components
    await agent.init_async()
    await human.init_async()
    await email_sender_tool.init_async()

    # Start listeners
    agent_task = asyncio.create_task(agent.start())
    human_task = asyncio.create_task(human.start())
    email_tool_task = asyncio.create_task(email_sender_tool.start())

    print("All listeners started...")

    # Send test message
    await human._send(
        Message(
            listener_id=human.listener_id,
            data=(
                "I have trouble logging in to my Steam account."
                " I have tried all the ways to get in but so far nothing has worked."
            ),
            target_listener=agent.listener_id,
            accessed=False,
            needs_response=True,
        )
    )

    try:
        # Run forever until a KeyboardInterrupt or cancellation is requested
        while True:
            await asyncio.sleep(5)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Shutting down...")
    finally:
        # Stop all listeners and clean up
        await agent.stop()
        await human.stop()
        await email_sender_tool.stop()
        await queue_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
