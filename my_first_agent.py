from strands import Agent
from strands_tools import calculator, http_request

# Create an agent with community tools (uses Bedrock Claude 4 Sonnet by default)
agent = Agent(
    tools=[calculator, http_request],
    system_prompt="You are a helpful assistant that can perform calculations and make HTTP requests."
)

# Test the agent with a simple question
response = agent("What is 25 * 47?")
print(response)

# The agent maintains conversation context
agent("My favorite color is blue")
response = agent("What's my favorite color?")
print(response)
