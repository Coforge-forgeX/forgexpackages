"""
LLM Helper for TrustAI Integration

Provides convenience methods for LLM operations using TrustAI.
Similar to ProductOwner's llm_manager.py but adapted for TrustAI.

Usage:
    ```python
    from common_adapters.trustai import get_llm_helper

    # Initialize helper
    helper = get_llm_helper(database_url)

    # Simple text generation
    response = helper.get_llm_response(
        workspace_id="ws_123",
        agent_id=1,
        prompt="Your prompt here"
    )

    # With context and history
    response = helper.get_llm_response_with_context(
        workspace_id="ws_123",
        agent_id=1,
        sys_prompt="You are a helpful assistant",
        user_input="What is AI?",
        history=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello! How can I help?"}
        ]
    )

    # Get LangChain-compatible router
    llm = helper.get_router_llm(workspace_id="ws_123", agent_id=1)
    response = llm.invoke("Your prompt")
    ```
"""

import logging
import asyncio
from typing import Optional, Union, List, Dict, Any

from .database import TrustAIDatabaseManager
from .provider import TrustAIProvider
from .langchain_adapter import TrustAIChatModel

logger = logging.getLogger(__name__)

# Type alias for agent_id (can be int or str)
AgentId = Union[int, str]


class TrustAILLMHelper:
    """
    Helper class for LLM operations using TrustAI.

    Provides simple methods for:
    - Text generation
    - Context-aware conversations
    - LangChain-compatible models
    """

    def __init__(self, database_url: str):
        """
        Initialize LLM helper.

        Args:
            database_url: PostgreSQL connection string
        """
        self.db_manager = TrustAIDatabaseManager(database_url)
        self.db_manager.initialize_tables()
        logger.info("TrustAI LLM Helper initialized")

    def _normalize_agent_id(self, agent_id: AgentId) -> int:
        """Normalize agent_id to integer."""
        if isinstance(agent_id, str):
            try:
                return int(agent_id)
            except ValueError:
                raise ValueError(f"Invalid agent_id: {agent_id}")
        return agent_id

    def get_llm_response(
        self,
        workspace_id: str,
        agent_id: AgentId,
        prompt: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Get LLM response for a simple prompt.

        Args:
            workspace_id: Workspace UUID string
            agent_id: Agent ID (int or str)
            prompt: The prompt to send to the LLM
            user_id: User ID (optional)
            user_email: User email (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            LLM response text
        """
        agent_id = self._normalize_agent_id(agent_id)

        try:
            provider = TrustAIProvider(
                db_manager=self.db_manager,
                workspace_id=workspace_id,
                agent_id=agent_id,
                user_id=user_id,
                user_email=user_email
            )

            logger.info(
                f"[TRUSTAI-HELPER] get_llm_response | workspace={workspace_id} | "
                f"agent={agent_id} | user={user_id}"
            )

            # Run async method in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an event loop, create a new task
                future = asyncio.ensure_future(
                    provider.generate_text(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                )
                return loop.run_until_complete(future)
            else:
                return loop.run_until_complete(
                    provider.generate_text(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                )

        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            raise

    def get_llm_response_with_context(
        self,
        workspace_id: str,
        agent_id: AgentId,
        sys_prompt: str,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Get LLM response with system prompt and conversation history.

        Args:
            workspace_id: Workspace UUID string
            agent_id: Agent ID (int or str)
            sys_prompt: System prompt defining LLM behavior
            user_input: Current user message
            history: Conversation history (list of dicts with 'role' and 'content')
            user_id: User ID (optional)
            user_email: User email (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            LLM response text
        """
        agent_id = self._normalize_agent_id(agent_id)

        if history is None:
            history = []

        try:
            provider = TrustAIProvider(
                db_manager=self.db_manager,
                workspace_id=workspace_id,
                agent_id=agent_id,
                user_id=user_id,
                user_email=user_email
            )

            logger.info(
                f"[TRUSTAI-HELPER] get_llm_response_with_context | "
                f"workspace={workspace_id} | agent={agent_id} | user={user_id} | "
                f"history_length={len(history)}"
            )

            # Run async method in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(
                    provider.generate_text_with_context(
                        system_prompt=sys_prompt,
                        user_prompt=user_input,
                        conversation_history=history,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                )
                return loop.run_until_complete(future)
            else:
                return loop.run_until_complete(
                    provider.generate_text_with_context(
                        system_prompt=sys_prompt,
                        user_prompt=user_input,
                        conversation_history=history,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                )

        except Exception as e:
            logger.error(f"Error getting LLM response with context: {e}")
            raise

    def get_router_llm(
        self,
        workspace_id: str,
        agent_id: AgentId,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        **kwargs
    ) -> TrustAIChatModel:
        """
        Return LangChain-compatible chat model for this workspace/agent.

        Returns TrustAIChatModel which extends BaseChatModel, making it fully
        compatible with LangChain chains, LangGraph agents, and tool-calling scenarios.

        Args:
            workspace_id: Workspace UUID string
            agent_id: Agent ID (int or str)
            user_id: User ID (optional)
            user_email: User email (optional)
            **kwargs: Additional model parameters

        Returns:
            TrustAIChatModel instance
        """
        agent_id = self._normalize_agent_id(agent_id)

        logger.info(
            f"[TRUSTAI-HELPER] get_router_llm | workspace={workspace_id} | "
            f"agent={agent_id} | user={user_id}"
        )

        # Create and return LangChain-compatible chat model
        return TrustAIChatModel(
            db_manager=self.db_manager,
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id,
            user_email=user_email,
            **kwargs
        )

    def get_provider(
        self,
        workspace_id: str,
        agent_id: AgentId,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None
    ) -> TrustAIProvider:
        """
        Get TrustAI provider instance.

        Args:
            workspace_id: Workspace UUID string
            agent_id: Agent ID (int or str)
            user_id: User ID (optional)
            user_email: User email (optional)

        Returns:
            TrustAIProvider instance
        """
        agent_id = self._normalize_agent_id(agent_id)

        return TrustAIProvider(
            db_manager=self.db_manager,
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id,
            user_email=user_email
        )

    def get_current_model_info(
        self,
        workspace_id: str,
        agent_id: AgentId,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get current model information for workspace/agent/user.

        Args:
            workspace_id: Workspace UUID string
            agent_id: Agent ID (int or str)
            user_id: User ID (optional)

        Returns:
            Dict with provider, model, and configuration info
        """
        agent_id = self._normalize_agent_id(agent_id)

        provider_model = self.db_manager.resolve_provider_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id
        )

        if not provider_model:
            return {
                'error': 'No provider model configured',
                'workspace_id': workspace_id,
                'agent_id': agent_id,
                'user_id': user_id
            }

        return {
            'provider_name': provider_model.provider_name,
            'deployment_name': provider_model.deployment_name,
            'trustai_model_key': provider_model.trustai_model_key,
            'is_system_default': provider_model.is_system_default,
            'workspace_id': workspace_id,
            'agent_id': agent_id,
            'user_id': user_id
        }


# Global helper instance cache
_helper_instances: Dict[str, TrustAILLMHelper] = {}


def get_llm_helper(database_url: str) -> TrustAILLMHelper:
    """
    Get or create a TrustAI LLM helper instance.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        TrustAILLMHelper instance
    """
    if database_url not in _helper_instances:
        _helper_instances[database_url] = TrustAILLMHelper(database_url)
    return _helper_instances[database_url]


# Convenience functions (similar to ProductOwner's llm_manager)

def get_llm_response(
    workspace_id: str,
    agent_id: AgentId,
    prompt: str,
    database_url: str,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function to get LLM response.

    Args:
        workspace_id: Workspace UUID string
        agent_id: Agent ID
        prompt: The prompt
        database_url: Database connection string
        user_id: User ID (optional)
        user_email: User email (optional)
        **kwargs: Additional parameters

    Returns:
        LLM response text
    """
    helper = get_llm_helper(database_url)
    return helper.get_llm_response(
        workspace_id=workspace_id,
        agent_id=agent_id,
        prompt=prompt,
        user_id=user_id,
        user_email=user_email,
        **kwargs
    )


def get_router_llm(
    workspace_id: str,
    agent_id: AgentId,
    database_url: str,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    **kwargs
) -> TrustAIChatModel:
    """
    Convenience function to get LangChain-compatible router LLM.

    Args:
        workspace_id: Workspace UUID string
        agent_id: Agent ID
        database_url: Database connection string
        user_id: User ID (optional)
        user_email: User email (optional)
        **kwargs: Additional model parameters

    Returns:
        TrustAIChatModel instance
    """
    helper = get_llm_helper(database_url)
    return helper.get_router_llm(
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        user_email=user_email,
        **kwargs
    )
