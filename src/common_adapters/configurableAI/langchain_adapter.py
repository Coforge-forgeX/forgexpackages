"""
LangChain-compatible adapter for ConfigurableAIManager.

This module provides a wrapper that makes ConfigurableAIManager fully compatible
with LangChain and LangGraph, allowing it to be used as a drop-in replacement
for LangChain chat models like AzureChatOpenAI, ChatOpenAI, etc.
"""

from typing import Any, Dict, List, Optional, Sequence, Union, Iterator, AsyncIterator, Literal
import logging
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
from langchain_core.runnables import RunnableConfig
from .manager import ConfigurableAIManager, ToolBoundConfigurableAIAdapter

logger = logging.getLogger(__name__)


class ConfigurableAIChatModel(BaseChatModel):
    """
    LangChain-compatible chat model wrapper for ConfigurableAIManager.

    This adapter allows ConfigurableAIManager to be used as a drop-in replacement
    for any LangChain chat model (like AzureChatOpenAI, ChatOpenAI, etc.) in
    LangChain chains, agents, and LangGraph applications.

    Example usage:
        ```python
        from common_adapters.configurableAI import ConfigurableAIManager
        from common_adapters.configurableAI.langchain_adapter import ConfigurableAIChatModel

        # Create manager and configure providers
        manager = ConfigurableAIManager()
        manager.configure_from_env("azure")

        # Wrap in LangChain-compatible adapter
        llm = ConfigurableAIChatModel(manager=manager)

        # Use in LangGraph or LangChain
        from langgraph.prebuilt import create_react_agent
        agent = create_react_agent(llm, tools)
        ```
    """

    manager: ConfigurableAIManager
    """The underlying ConfigurableAIManager instance."""

    provider: Optional[str] = None
    """Specific provider to use (if None, uses manager's current provider)."""

    temperature: Optional[float] = None
    """Sampling temperature."""

    max_tokens: Optional[int] = None
    """Maximum tokens to generate."""

    streaming: bool = False
    """Whether to stream responses (not yet implemented)."""

    model_kwargs: Dict[str, Any] = {}
    """Additional kwargs to pass to the provider."""

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def __init__(
        self,
        manager: ConfigurableAIManager,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        **kwargs: Any
    ):
        """
        Initialize the LangChain-compatible chat model.

        Args:
            manager: ConfigurableAIManager instance
            provider: Specific provider to use (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            streaming: Whether to stream responses
            **kwargs: Additional model parameters
        """
        super().__init__(
            manager=manager,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            model_kwargs=kwargs
        )

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "configurable-ai-chat"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "provider": self.provider or self.manager.get_current_provider(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.model_kwargs
        }

    def _convert_messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        """
        Convert LangChain messages to a prompt string.

        This method converts various LangChain message types into a format
        that the underlying ConfigurableAIManager can process.
        """
        prompt_parts = []

        for message in messages:
            if isinstance(message, SystemMessage):
                prompt_parts.append(f"SYSTEM: {message.content}")
            elif isinstance(message, HumanMessage):
                prompt_parts.append(f"USER: {message.content}")
            elif isinstance(message, AIMessage):
                # Include tool calls if present
                content = message.content
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_calls_str = "\n".join([
                        f"Tool Call: {tc.get('name', 'unknown')}({tc.get('args', {})})"
                        for tc in message.tool_calls
                    ])
                    content = f"{content}\n{tool_calls_str}" if content else tool_calls_str
                prompt_parts.append(f"ASSISTANT: {content}")
            elif isinstance(message, ToolMessage):
                tool_name = getattr(message, 'name', 'unknown')
                prompt_parts.append(f"TOOL RESULT ({tool_name}): {message.content}")
            elif isinstance(message, ChatMessage):
                role = message.role.upper()
                prompt_parts.append(f"{role}: {message.content}")
            else:
                # Fallback for any other message type
                prompt_parts.append(f"USER: {message.content}")

        return "\n\n".join(prompt_parts)

    def _prepare_kwargs(self) -> Dict[str, Any]:
        """Prepare kwargs for the underlying manager."""
        kwargs = self.model_kwargs.copy()

        if self.temperature is not None:
            kwargs['temperature'] = self.temperature

        if self.max_tokens is not None:
            kwargs['max_tokens'] = self.max_tokens

        return kwargs

    def _normalize_prompt_input(self, prompt_or_messages: Any) -> str:
        """Normalize plain text or message lists to a prompt string."""
        if isinstance(prompt_or_messages, str):
            return prompt_or_messages

        if isinstance(prompt_or_messages, list):
            # Accept LangChain message objects or dict-based role/content messages.
            if prompt_or_messages and isinstance(prompt_or_messages[0], BaseMessage):
                return self._convert_messages_to_prompt(prompt_or_messages)

            normalized_messages: List[BaseMessage] = []
            for item in prompt_or_messages:
                if isinstance(item, BaseMessage):
                    normalized_messages.append(item)
                    continue

                if isinstance(item, dict):
                    role = str(item.get("role", "user")).lower()
                    content = str(item.get("content", ""))
                    if role == "system":
                        normalized_messages.append(SystemMessage(content=content))
                    elif role in {"assistant", "ai"}:
                        normalized_messages.append(AIMessage(content=content))
                    else:
                        normalized_messages.append(HumanMessage(content=content))
                    continue

                normalized_messages.append(HumanMessage(content=str(item)))

            return self._convert_messages_to_prompt(normalized_messages)

        return str(prompt_or_messages)

    def generate_text(
        self,
        prompt_or_messages: Any,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Compatibility method for callers expecting manager-style sync API."""
        final_kwargs = self._prepare_kwargs()
        final_kwargs.update(kwargs)
        prompt = self._normalize_prompt_input(prompt_or_messages)

        return self.manager.generate_text(
            prompt,
            provider=provider or self.provider,
            **final_kwargs,
        )

    async def generate_text_async(
        self,
        prompt_or_messages: Any,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Compatibility method for callers expecting manager-style async API."""
        final_kwargs = self._prepare_kwargs()
        final_kwargs.update(kwargs)
        prompt = self._normalize_prompt_input(prompt_or_messages)

        return await self.manager.generate_text_async(
            prompt,
            provider=provider or self.provider,
            **final_kwargs,
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate response from messages (synchronous).

        This is the core method that LangChain calls for synchronous generation.
        """
        # Merge kwargs
        final_kwargs = self._prepare_kwargs()
        final_kwargs.update(kwargs)

        if stop:
            final_kwargs['stop'] = stop

        # Convert messages to prompt
        prompt = self._convert_messages_to_prompt(messages)

        # Generate using manager
        response_text = self.manager.generate_text(
            prompt,
            provider=self.provider,
            **final_kwargs
        )

        # Convert to AIMessage
        ai_message = AIMessage(content=response_text)

        # Create chat generation
        generation = ChatGeneration(message=ai_message)

        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate response from messages (asynchronous).

        This is the core method that LangChain calls for asynchronous generation.
        """
        # Merge kwargs
        final_kwargs = self._prepare_kwargs()
        final_kwargs.update(kwargs)

        if stop:
            final_kwargs['stop'] = stop

        # Convert messages to prompt
        prompt = self._convert_messages_to_prompt(messages)

        # Generate using manager
        response_text = await self.manager.generate_text_async(
            prompt,
            provider=self.provider,
            **final_kwargs
        )

        # Convert to AIMessage
        ai_message = AIMessage(content=response_text)

        # Create chat generation
        generation = ChatGeneration(message=ai_message)

        return ChatResult(generations=[generation])

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, Any]],
        *,
        tool_choice: Optional[Union[dict, str, bool]] = None,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ) -> "ConfigurableAIToolBoundChatModel":
        """
        Bind tools to this chat model.

        Returns a new instance that will use tools in generation.
        This is required for LangGraph agents and tool-calling scenarios.
        """
        return ConfigurableAIToolBoundChatModel(
            manager=self.manager,
            tools=list(tools),
            provider=self.provider,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tool_choice=tool_choice,
            strict=strict,
            base_kwargs=self.model_kwargs,
            **kwargs
        )

    def with_structured_output(
        self,
        schema: Optional[Union[Dict, type]] = None,
        *,
        method: Literal["function_calling", "json_mode", "json_schema"] = "json_schema",
        include_raw: bool = False,
        **kwargs: Any,
    ):
        """
        Return a model that outputs structured data.

        This delegates to the manager's with_structured_output method.
        """
        return self.manager.with_structured_output(
            schema=schema,
            method=method,
            include_raw=include_raw,
            **kwargs
        )


class ConfigurableAIToolBoundChatModel(BaseChatModel):
    """
    LangChain-compatible chat model with tools bound.

    This class is returned when bind_tools() is called on ConfigurableAIChatModel.
    It provides tool-calling capabilities compatible with LangChain and LangGraph.
    """

    manager: ConfigurableAIManager
    """The underlying ConfigurableAIManager instance."""

    tools: List[Any]
    """List of bound tools."""

    provider: Optional[str] = None
    """Specific provider to use."""

    temperature: Optional[float] = None
    """Sampling temperature."""

    max_tokens: Optional[int] = None
    """Maximum tokens to generate."""

    tool_choice: Optional[Union[dict, str, bool]] = None
    """Tool choice specification."""

    strict: Optional[bool] = None
    """Whether to use strict mode."""

    base_kwargs: Dict[str, Any] = {}
    """Base kwargs from parent model."""

    model_kwargs: Dict[str, Any] = {}
    """Additional model kwargs."""

    _tool_adapter: Optional[ToolBoundConfigurableAIAdapter] = None
    """Internal tool adapter instance."""

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def __init__(
        self,
        manager: ConfigurableAIManager,
        tools: List[Any],
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tool_choice: Optional[Union[dict, str, bool]] = None,
        strict: Optional[bool] = None,
        base_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ):
        """Initialize tool-bound chat model."""
        super().__init__(
            manager=manager,
            tools=tools,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            strict=strict,
            base_kwargs=base_kwargs or {},
            model_kwargs=kwargs
        )

        # Create the underlying tool adapter
        self._tool_adapter = self.manager.bind_tools(
            tools=self.tools,
            tool_choice=self.tool_choice,
            strict=self.strict,
            **kwargs
        )

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "configurable-ai-chat-tools"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "provider": self.provider or self.manager.get_current_provider(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "num_tools": len(self.tools),
            "tool_choice": self.tool_choice,
            **self.base_kwargs,
            **self.model_kwargs
        }

    def _convert_messages_to_langchain(self, messages: List[BaseMessage]) -> List[Any]:
        """Convert LangChain messages to format expected by ToolBoundConfigurableAIAdapter."""
        converted = []
        for message in messages:
            if isinstance(message, SystemMessage):
                converted.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                converted.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                content = message.content
                converted.append({"role": "assistant", "content": content})
            elif isinstance(message, ToolMessage):
                tool_name = getattr(message, 'name', 'tool')
                converted.append({
                    "role": "user",
                    "content": f"[Tool result from {tool_name}] {message.content}"
                })
            elif isinstance(message, ChatMessage):
                converted.append({"role": message.role, "content": message.content})
            else:
                converted.append({"role": "user", "content": str(message.content)})

        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate response with tool support (synchronous).
        """
        # Note: Tool execution needs async, but we can work around it
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, need to use run_in_executor
            import concurrent.futures

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self._agenerate(messages, stop, None, **kwargs)
                    )
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        except RuntimeError:
            # No event loop, safe to use asyncio.run
            return asyncio.run(self._agenerate(messages, stop, None, **kwargs))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate response with tool support (asynchronous).
        """
        # Convert messages to format expected by tool adapter
        converted_messages = self._convert_messages_to_langchain(messages)

        # Call the tool adapter's ainvoke method
        ai_message = await self._tool_adapter.ainvoke(converted_messages)

        # Create chat generation
        generation = ChatGeneration(message=ai_message)

        return ChatResult(generations=[generation])

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, Any]],
        *,
        tool_choice: Optional[Union[dict, str, bool]] = None,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ) -> "ConfigurableAIToolBoundChatModel":
        """
        Bind additional tools to this chat model.

        Returns a new instance with merged tools.
        """
        merged_tools = list(self.tools) + list(tools)
        merged_kwargs = {**self.base_kwargs, **self.model_kwargs, **kwargs}

        return ConfigurableAIToolBoundChatModel(
            manager=self.manager,
            tools=merged_tools,
            provider=self.provider,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tool_choice=tool_choice if tool_choice is not None else self.tool_choice,
            strict=strict if strict is not None else self.strict,
            base_kwargs=self.base_kwargs,
            **merged_kwargs
        )


def create_langchain_chat_model(
    manager: Optional[ConfigurableAIManager] = None,
    provider_name: str = "azure",
    auto_configure: bool = True,
    **kwargs: Any
) -> ConfigurableAIChatModel:
    """
    Convenience function to create a LangChain-compatible chat model.

    Args:
        manager: Existing ConfigurableAIManager (if None, creates new one)
        provider_name: Provider to configure (if creating new manager)
        auto_configure: Whether to auto-configure from environment
        **kwargs: Additional parameters for the chat model

    Returns:
        ConfigurableAIChatModel instance ready to use with LangChain/LangGraph

    Example:
        ```python
        # Simple usage
        llm = create_langchain_chat_model(provider_name="azure")

        # Use in LangGraph
        from langgraph.prebuilt import create_react_agent
        agent = create_react_agent(llm, tools)
        ```
    """
    if manager is None:
        from .manager import get_ai_manager
        manager = get_ai_manager(
            provider_name=provider_name,
            auto_configure=auto_configure
        )

    return ConfigurableAIChatModel(manager=manager, **kwargs)
