"""
Usage Examples for TrustAI Integration Package

This file contains comprehensive examples of how to use the TrustAI package.
"""

import asyncio
import os
from typing import Optional


# Example 1: Basic Setup and Workspace Registration
async def example_workspace_registration():
    """
    Example: Register a workspace with TrustAI.
    """
    from common_adapters.trustai import (
        TrustAIDatabaseManager,
        TrustAIWorkspaceIntegration
    )

    # Set environment variables (do this before importing)
    os.environ["TRUSTAI_MASTER_API_KEY"] = "your-master-key-here"

    # Initialize database manager
    database_url = "postgresql://user:password@host:5432/dbname"
    db_manager = TrustAIDatabaseManager(database_url)

    # Initialize tables (creates them if they don't exist)
    db_manager.initialize_tables()
    print("✓ Database tables initialized")

    # Create workspace integration
    integration = TrustAIWorkspaceIntegration(db_manager)

    # Define TrustAI configuration
    trustai_config = {
        "application": {
            "name": "My Workspace",
            "description": "Production workspace for AI agents",
            "line_of_business": "technology",
            "technical_architect": "tech@example.com",
            "business_sponsor": "business@example.com"
        },
        "guardrails": [
            "BSI_DETECTION",
            "TOXIC",
            "COMPETITOR_CHECK",
            "PII",
            "TOKEN_QUOTA",
            "PROMPT_INJECTION",
            "BIAS_DETECTION",
            "FACTUAL_ACCURACY"
        ],
        "system_config": {
            "guardrail_model": "llama-4-scout",
            "admin_emails": ["admin@example.com"],
            "is_guardrail_notification_enabled": True,
            "input_guardrail_execution_mode": "sync",
            "output_guardrail_execution_mode": "sync",
            "warning_message": "Your input may violate our policies",
            "block_message": "Your input has been blocked"
        }
    }

    # Register workspace
    try:
        app_id, api_key = await integration.register_workspace(
            workspace_id="ws_12345678-1234-1234-1234-123456789abc",
            trustai_config=trustai_config
        )
        print(f"✓ Workspace registered successfully")
        print(f"  App ID: {app_id}")
        print(f"  API Key: {api_key[:20]}...")
        return app_id, api_key
    except Exception as e:
        print(f"✗ Failed to register workspace: {e}")
        raise


# Example 2: Configure Provider Models
def example_configure_provider_models():
    """
    Example: Set up provider models in the database.
    """
    from common_adapters.trustai import TrustAIDatabaseManager

    database_url = "postgresql://user:password@host:5432/dbname"
    db_manager = TrustAIDatabaseManager(database_url)

    # Add system default model
    model = db_manager.create_provider_model(
        provider_name="azure",
        deployment_name="gpt-4-1",
        trustai_model_key="gpt-4-1",
        is_system_default=True
    )
    print(f"✓ Created system default model: {model}")

    # Add additional models
    model2 = db_manager.create_provider_model(
        provider_name="azure",
        deployment_name="gpt-4-turbo",
        trustai_model_key="gpt-4-turbo",
        is_system_default=False
    )
    print(f"✓ Created additional model: {model2}")


# Example 3: Simple LLM Usage with Helper
def example_simple_llm_usage():
    """
    Example: Use LLM helper for simple text generation.
    """
    from common_adapters.trustai import get_llm_helper

    database_url = "postgresql://user:password@host:5432/dbname"
    helper = get_llm_helper(database_url)

    # Simple text generation
    response = helper.get_llm_response(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        prompt="What is artificial intelligence?",
        user_id=42,
        user_email="user@example.com",
        temperature=0.7,
        max_tokens=500
    )
    print(f"✓ LLM Response: {response[:100]}...")

    # With conversation history
    response2 = helper.get_llm_response_with_context(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        sys_prompt="You are a helpful AI assistant.",
        user_input="Tell me more about machine learning",
        history=[
            {"role": "user", "content": "Hi!"},
            {"role": "assistant", "content": "Hello! How can I help you today?"}
        ],
        user_id=42
    )
    print(f"✓ Contextual Response: {response2[:100]}...")


# Example 4: LangChain Integration
def example_langchain_integration():
    """
    Example: Use TrustAI with LangChain and LangGraph.
    """
    from common_adapters.trustai import get_llm_helper
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    database_url = "postgresql://user:password@host:5432/dbname"
    helper = get_llm_helper(database_url)

    # Get LangChain-compatible LLM
    llm = helper.get_router_llm(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=42,
        temperature=0.7
    )

    # Create a simple chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that explains concepts clearly."),
        ("user", "{topic}")
    ])

    chain = prompt | llm | StrOutputParser()

    # Invoke the chain
    result = chain.invoke({"topic": "quantum computing"})
    print(f"✓ Chain result: {result[:100]}...")


# Example 5: Tool Calling with LangGraph
async def example_tool_calling():
    """
    Example: Use TrustAI with tool calling in LangGraph.
    """
    from common_adapters.trustai import get_llm_helper
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    @tool
    def get_weather(location: str) -> str:
        """Get the current weather for a location."""
        # Mock implementation
        return f"Weather in {location}: Sunny, 72°F"

    @tool
    def search_web(query: str) -> str:
        """Search the web for information."""
        # Mock implementation
        return f"Search results for: {query}"

    database_url = "postgresql://user:password@host:5432/dbname"
    helper = get_llm_helper(database_url)

    llm = helper.get_router_llm(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=42
    )

    # Create agent with tools
    tools = [get_weather, search_web]
    agent_executor = create_react_agent(llm, tools)

    # Run agent
    result = await agent_executor.ainvoke({
        "messages": [("user", "What's the weather in San Francisco?")]
    })

    print(f"✓ Agent result: {result}")


# Example 6: Structured Output
def example_structured_output():
    """
    Example: Get structured output from the LLM.
    """
    from common_adapters.trustai import get_llm_helper
    from pydantic import BaseModel, Field

    class PersonInfo(BaseModel):
        """Information about a person."""
        name: str = Field(description="Person's full name")
        age: int = Field(description="Person's age in years")
        occupation: str = Field(description="Person's occupation or job title")
        location: str = Field(description="Person's location or city")

    database_url = "postgresql://user:password@host:5432/dbname"
    helper = get_llm_helper(database_url)

    llm = helper.get_router_llm(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=42
    )

    # Get structured output
    structured_llm = llm.with_structured_output(PersonInfo)
    result = structured_llm.invoke(
        "Tell me about Sarah Chen, a 28 year old software engineer living in Seattle"
    )

    print(f"✓ Structured output:")
    print(f"  Name: {result.name}")
    print(f"  Age: {result.age}")
    print(f"  Occupation: {result.occupation}")
    print(f"  Location: {result.location}")


# Example 7: Configure User-Specific Preferences
def example_user_preferences():
    """
    Example: Configure user-specific model preferences.
    """
    from common_adapters.trustai import (
        TrustAIDatabaseManager,
        TrustAIWorkspaceIntegration
    )

    database_url = "postgresql://user:password@host:5432/dbname"
    db_manager = TrustAIDatabaseManager(database_url)
    integration = TrustAIWorkspaceIntegration(db_manager)

    # Configure workspace-agent default
    config = integration.configure_agent_provider_model(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        provider_name="azure",
        deployment_name="gpt-4-1",
        created_by=100
    )
    print(f"✓ Workspace-agent config: {config}")

    # Configure user-specific preference
    user_config = integration.configure_user_specific_agent_provider_model(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        user_id=42,
        agent_id=1,
        provider_name="azure",
        deployment_name="gpt-4-turbo"
    )
    print(f"✓ User-specific config: {user_config}")

    # Fetch resolved model (will use user preference)
    resolved = integration.fetch_workspace_agent_provider_model(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=42
    )
    print(f"✓ Resolved model for user 42: {resolved}")

    # Fetch resolved model (will use workspace default)
    resolved2 = integration.fetch_workspace_agent_provider_model(
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=None
    )
    print(f"✓ Resolved model (no user): {resolved2}")


# Example 8: Direct Provider Usage
async def example_direct_provider():
    """
    Example: Use TrustAIProvider directly for more control.
    """
    from common_adapters.trustai import (
        TrustAIDatabaseManager,
        TrustAIProvider
    )

    database_url = "postgresql://user:password@host:5432/dbname"
    db_manager = TrustAIDatabaseManager(database_url)

    # Create provider
    provider = TrustAIProvider(
        db_manager=db_manager,
        workspace_id="ws_12345678-1234-1234-1234-123456789abc",
        agent_id=1,
        user_id=42,
        user_email="user@example.com"
    )

    # Get model info
    info = provider.get_current_model_info()
    print(f"✓ Current model: {info}")

    # Generate text
    response = await provider.generate_text(
        prompt="Explain quantum computing in simple terms",
        temperature=0.7,
        max_tokens=500
    )
    print(f"✓ Response: {response[:100]}...")

    # Generate with context
    response2 = await provider.generate_text_with_context(
        system_prompt="You are a science educator.",
        user_prompt="How does photosynthesis work?",
        conversation_history=[],
        temperature=0.7,
        max_tokens=500
    )
    print(f"✓ Contextual response: {response2[:100]}...")


# Main execution
if __name__ == "__main__":
    print("TrustAI Integration Package - Examples\n")

    # Run examples
    print("=" * 60)
    print("Example 1: Workspace Registration")
    print("=" * 60)
    # Uncomment to run:
    # asyncio.run(example_workspace_registration())

    print("\n" + "=" * 60)
    print("Example 2: Configure Provider Models")
    print("=" * 60)
    # Uncomment to run:
    # example_configure_provider_models()

    print("\n" + "=" * 60)
    print("Example 3: Simple LLM Usage")
    print("=" * 60)
    # Uncomment to run:
    # example_simple_llm_usage()

    print("\n" + "=" * 60)
    print("Example 4: LangChain Integration")
    print("=" * 60)
    # Uncomment to run:
    # example_langchain_integration()

    print("\n" + "=" * 60)
    print("Example 5: Tool Calling")
    print("=" * 60)
    # Uncomment to run:
    # asyncio.run(example_tool_calling())

    print("\n" + "=" * 60)
    print("Example 6: Structured Output")
    print("=" * 60)
    # Uncomment to run:
    # example_structured_output()

    print("\n" + "=" * 60)
    print("Example 7: User Preferences")
    print("=" * 60)
    # Uncomment to run:
    # example_user_preferences()

    print("\n" + "=" * 60)
    print("Example 8: Direct Provider Usage")
    print("=" * 60)
    # Uncomment to run:
    # asyncio.run(example_direct_provider())

    print("\n" + "=" * 60)
    print("All examples listed. Uncomment to run specific examples.")
    print("=" * 60)
