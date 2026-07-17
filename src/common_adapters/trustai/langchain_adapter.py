"""
LangChain-compatible adapter for TrustAI Provider.

This module provides a wrapper that makes TrustAIProvider fully compatible
with LangChain and LangGraph, allowing it to be used as a drop-in replacement
for LangChain chat models like AzureChatOpenAI, ChatOpenAI, etc.
"""

from typing import Any, Dict, List, Optional, Iterator, AsyncIterator
import logging
import asyncio
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    ChatMessage,
    AIMessageChunk,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun

from .provider import TrustAIProvider

logger = logging.getLogger(__name__)


class TrustAIChatModel(BaseChatModel):
    """
    LangChain-compatible chat model wrapper for TrustAIProvider.

    This adapter allows TrustAIProvider to be used as a drop-in replacement
    for any LangChain chat model (like AzureChatOpenAI, ChatOpenAI, etc.) in
    LangChain chains, agents, and LangGraph applications.

    This version is decoupled from the database - it receives a configuration
    dict instead of a database manager.

    Example usage:
        ```python
        from common_adapters.trustai import get_llm_helper

        # Get LLM helper
        helper = get_llm_helper(database_url)

        # Get LangChain-compatible chat model
        llm = helper.get_router_llm(
            workspace_id="ws_123",
            agent_id=1,
            user_id=42
        )

        # Use in LangGraph or LangChain
        from langgraph.prebuilt import create_react_agent
        agent = create_react_agent(llm, tools)
        ```
    """

    config: Dict[str, Any]
    """Provider configuration dict."""

    workspace_id: str
    """Workspace UUID string."""

    agent_id: int
    """Agent ID."""

    user_id: Optional[int] = None
    """User ID (optional)."""

    user_email: Optional[str] = None
    """User email (optional)."""

    temperature: Optional[float] = 0.7
    """Sampling temperature."""

    max_tokens: Optional[int] = 1000
    """Maximum tokens to generate."""

    top_p: Optional[float] = 0.9
    """Nucleus sampling parameter."""

    streaming: bool = False
    """Whether to stream responses (not yet implemented)."""

    model_kwargs: Dict[str, Any] = {}
    """Additional kwargs to pass to the provider."""

    _provider: Optional[TrustAIProvider] = None
    """Cached provider instance."""

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def __init__(
        self,
        config: Dict[str, Any],
        user_email: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 1000,
        top_p: Optional[float] = 0.9,
        streaming: bool = False,
        **kwargs: Any
    ):
        """
        Initialize the LangChain-compatible chat model.

        Args:
            config: Configuration dict from get_provider_configuration()
            user_email: User email (optional, overrides config user_id)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            streaming: Whether to stream responses
            **kwargs: Additional model parameters
        """
        super().__init__(
            config=config,
            workspace_id=config['workspace_id'],
            agent_id=config['agent_id'],
            user_id=config.get('user_id'),
            user_email=user_email,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            streaming=streaming,
            model_kwargs=kwargs
        )

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "trustai"

    def _get_provider(self) -> TrustAIProvider:
        """Get or create the TrustAI provider instance."""
        if self._provider is None:
            self._provider = TrustAIProvider.from_configuration(
                config=self.config,
                user_email=self.user_email
            )
        return self._provider

    def _convert_messages_to_dicts(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to TrustAI format."""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                # Handle tool calls if present
                if msg.tool_calls or msg.additional_kwargs.get('tool_calls'):
                    converted.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": msg.tool_calls or msg.additional_kwargs.get('tool_calls', [])
                    })
                else:
                    converted.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                converted.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                })
            elif isinstance(msg, ChatMessage):
                converted.append({"role": msg.role, "content": msg.content})
            else:
                # Fallback for unknown message types
                converted.append({"role": "user", "content": str(msg.content)})

        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Generate chat completion (synchronous).

        Args:
            messages: List of LangChain messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional parameters

        Returns:
            ChatResult with generated message
        """
        # Run async method in sync context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in an event loop, create a new one
            import nest_asyncio
            nest_asyncio.apply()

        return loop.run_until_complete(
            self._agenerate(messages, stop, run_manager, **kwargs)
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Generate chat completion (asynchronous).

        Args:
            messages: List of LangChain messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional parameters

        Returns:
            ChatResult with generated message
        """
        provider = self._get_provider()
        message_dicts = self._convert_messages_to_dicts(messages)

        # Merge model parameters
        params = {
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'top_p': self.top_p,
            **self.model_kwargs,
            **kwargs
        }

        # Check if tools are provided
        tools = params.pop('tools', None)
        tool_choice = params.pop('tool_choice', 'auto')

        try:
            if tools:
                # Tool calling mode
                response_data = await provider.chat_completion_with_tools(
                    messages=message_dicts,
                    tools=tools,
                    tool_choice=tool_choice,
                    **params
                )

                # Parse response
                choice = response_data['choices'][0]
                message_data = choice['message']
                content = message_data.get('content', '')
                tool_calls = message_data.get('tool_calls', [])

                # Create AIMessage with tool calls
                ai_message = AIMessage(
                    content=content,
                    additional_kwargs={'tool_calls': tool_calls} if tool_calls else {}
                )

                # Set tool_calls attribute if present
                if tool_calls:
                    ai_message.tool_calls = tool_calls

            else:
                # Regular completion mode
                content = await provider.chat_completion(
                    messages=message_dicts,
                    **params
                )
                ai_message = AIMessage(content=content)

            generation = ChatGeneration(message=ai_message)
            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"Error in TrustAI chat completion: {e}")
            raise

    def bind_tools(
        self,
        tools: List[Any],
        **kwargs: Any
    ) -> "TrustAIChatModel":
        """
        Bind tools to this model.

        Args:
            tools: List of tool definitions
            **kwargs: Additional parameters

        Returns:
            New instance with tools bound
        """
        # Convert tools to OpenAI format if needed
        from langchain_core.utils.function_calling import convert_to_openai_tool

        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]

        # Create new instance with tools in model_kwargs
        return self.__class__(
            config=self.config,
            user_email=self.user_email,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            streaming=self.streaming,
            tools=formatted_tools,
            **{**self.model_kwargs, **kwargs}
        )

    def with_structured_output(
        self,
        schema: Any,
        **kwargs: Any
    ) -> Any:
        """
        Get a version of the model that outputs structured data.

        Args:
            schema: Pydantic model or JSON schema
            **kwargs: Additional parameters

        Returns:
            Model that outputs structured data
        """
        from langchain_core.utils.function_calling import convert_to_openai_function

        # Convert schema to function
        function = convert_to_openai_function(schema)

        # Bind the function as a tool
        return self.bind_tools(
            tools=[function],
            tool_choice={"type": "function", "function": {"name": function["name"]}},
            **kwargs
        )

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters."""
        return {
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p
        }


def get_trustai_chat_model(
    config: Dict[str, Any],
    user_email: Optional[str] = None,
    **kwargs
) -> TrustAIChatModel:
    """
    Factory function to create TrustAI chat model.

    DEPRECATED: Use TrustAILLMHelper.get_router_llm() instead.

    Args:
        config: Configuration dict from get_provider_configuration()
        user_email: User email (optional)
        **kwargs: Additional model parameters

    Returns:
        TrustAIChatModel instance

    Example:
        ```python
        from common_adapters.trustai import get_llm_helper

        helper = get_llm_helper(database_url)
        llm = helper.get_router_llm(workspace_id, agent_id, user_id)
        ```
    """
    return TrustAIChatModel(
        config=config,
        user_email=user_email,
        **kwargs
    )
