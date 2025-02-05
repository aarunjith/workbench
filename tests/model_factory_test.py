from workbench import ModelFactory, ModelConfig, ModelResponse, AgentMessage
import os, getpass

os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Anthropic API Key: ")
test_config = ModelConfig(
    model_name="claude-3-5-sonnet-20241022",
    system_prompt="You are an AI agent. Your goal is to assist the user with their questions.",
)

model = ModelFactory.create(test_config)

print(model)

messages = [AgentMessage(role="user", content="What is the weather in San Francisco?")]

response = model.generate_response(messages)

print(response)
