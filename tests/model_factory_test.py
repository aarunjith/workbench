from workbench import ModelFactory, ModelConfig, ModelResponse, AgentMessage
import os, getpass
import asyncio


async def main():
    # os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Anthropic API Key: ")
    test_config = ModelConfig(
        # model_name="claude-3-5-sonnet-20241022",
        model_name="ollama/olmo2",
        system_prompt="You are an AI agent. Your goal is to assist the user with their questions.",
    )

    model = ModelFactory.create(test_config)

    print(model)

    messages = [
        AgentMessage(role="user", content="What is the weather in San Francisco?")
    ]

    response = await model.generate_response(messages)

    print(response)


if __name__ == "__main__":
    asyncio.run(main())
