from anthropic import AsyncAnthropic
import getpass
import asyncio


async def main():
    api_key = getpass.getpass("Enter your Anthropic API key: ")

    client = AsyncAnthropic(api_key=api_key)

    response = await client.messages.create(
        messages=[{"role": "user", "content": "Hello, world!"}],
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        temperature=0.5,
    )

    print(f"No Tool: {response}")

    tool_definition = {
        "name": "get_weather",
        "description": "Get the weather for a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                }
            },
            "required": ["location"],
        },
    }
    response = await client.messages.create(
        messages=[{"role": "user", "content": "What is the weather in San Francisco?"}],
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        temperature=0.5,
        tools=[tool_definition],
    )
    print(f"Tool: {response}")


if __name__ == "__main__":
    asyncio.run(main())
