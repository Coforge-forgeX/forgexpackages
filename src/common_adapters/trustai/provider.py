"""
TrustAI Provider Implementation

Handles LLM calls to TrustAI /chat/completions endpoint.
"""

import logging
from typing import Dict, Any, Optional, List
import httpx

from .database import TrustAIDatabaseManager
from .endpoints import TrustAIEndpoints

logger = logging.getLogger(__name__)


class TrustAIProvider:
    """
    TrustAI provider for LLM operations.

    Features:
    - Chat completions with guardrails
    - Auto-resolves provider models based on hierarchy
    - Sends proper TrustAI headers
    - Compatible with LangChain integration
    """

    def __init__(
        self,
        db_manager: TrustAIDatabaseManager,
        workspace_id: str,
        agent_id: int,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None
    ):
        """
        Initialize TrustAI provider.

        Args:
            db_manager: TrustAIDatabaseManager instance
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            user_id: User ID (optional)
            user_email: User email (optional, for tracking)
        """
        self.db = db_manager
        self.workspace_id = workspace_id
        self.agent_id = agent_id
        self.user_id = user_id
        self.user_email = user_email
        self.endpoints = TrustAIEndpoints

        # Load workspace config
        self.workspace_config = self.db.get_workspace_config(workspace_id)
        if not self.workspace_config:
            raise ValueError(
                f"No TrustAI configuration found for workspace {workspace_id}. "
                "Please register the workspace first."
            )

        # Resolve provider model
        self.provider_model = self.db.resolve_provider_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id
        )
        if not self.provider_model:
            raise ValueError(
                f"No provider model found for workspace={workspace_id}, "
                f"agent={agent_id}, user={user_id}. "
                "Please configure a provider model first."
            )

        logger.info(
            f"[TRUSTAI-PROVIDER] Initialized | workspace={workspace_id} | "
            f"agent={agent_id} | user={user_id} | "
            f"provider={self.provider_model.provider_name} | "
            f"model={self.provider_model.deployment_name}"
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers for TrustAI API."""
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.workspace_config.x_api_key,
            "X-App-Id": self.workspace_config.x_app_id,
            "X-Agent-Id": str(self.agent_id)
        }

        # Add user identification if available
        if self.user_email:
            headers["X-User-Id"] = self.user_email
        elif self.user_id:
            headers["X-User-Id"] = str(self.user_id)

        return headers

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 0.9,
        **kwargs
    ) -> str:
        """
        Generate text using TrustAI API.

        Args:
            prompt: User prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            **kwargs
        )

    async def generate_text_with_context(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 0.9,
        **kwargs
    ) -> str:
        """
        Generate text with system prompt and conversation history.

        Args:
            system_prompt: System prompt
            user_prompt: Current user prompt
            conversation_history: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            **kwargs
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 0.9,
        **kwargs
    ) -> str:
        """
        Call TrustAI /chat/completions endpoint.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            **kwargs: Additional parameters (tools, tool_choice, etc.)

        Returns:
            Generated text response

        Raises:
            httpx.HTTPError: If API call fails
        """
        headers = self._build_headers()

        payload = {
            "messages": messages,
            "model": self.provider_model.trustai_model_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p
        }

        # Add any additional kwargs (for tool calling, etc.)
        payload.update(kwargs)

        logger.debug(
            f"[TRUSTAI-PROVIDER] Calling chat/completions | "
            f"model={self.provider_model.trustai_model_key} | "
            f"messages={len(messages)}"
        )

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.endpoints.CHAT_COMPLETIONS,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                # Extract content from response
                if 'choices' not in data or not data['choices']:
                    raise ValueError(f"Invalid response structure: {data}")

                choice = data['choices'][0]
                content = choice.get('message', {}).get('content', '')

                # Check finish reason
                finish_reason = choice.get('finish_reason')
                if finish_reason == 'length':
                    logger.warning(
                        f"Response truncated due to max_tokens={max_tokens}. "
                        f"Consider increasing max_tokens."
                    )

                logger.debug(
                    f"[TRUSTAI-PROVIDER] Response received | "
                    f"length={len(content)} chars | finish_reason={finish_reason}"
                )

                return content

        except httpx.HTTPError as e:
            logger.error(f"[TRUSTAI-PROVIDER] API call failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[TRUSTAI-PROVIDER] Unexpected error: {e}")
            raise

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call TrustAI /chat/completions with tool calling support.

        Args:
            messages: List of message dicts
            tools: List of tool definitions
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Full response dict including tool calls if any
        """
        headers = self._build_headers()

        payload = {
            "messages": messages,
            "model": self.provider_model.trustai_model_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": tool_choice
        }
        payload.update(kwargs)

        logger.debug(
            f"[TRUSTAI-PROVIDER] Calling chat/completions with tools | "
            f"model={self.provider_model.trustai_model_key} | "
            f"messages={len(messages)} | tools={len(tools)}"
        )

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.endpoints.CHAT_COMPLETIONS,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                logger.debug(
                    f"[TRUSTAI-PROVIDER] Tool response received | "
                    f"choices={len(data.get('choices', []))}"
                )

                return data

        except httpx.HTTPError as e:
            logger.error(f"[TRUSTAI-PROVIDER] Tool call failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[TRUSTAI-PROVIDER] Unexpected error in tool call: {e}")
            raise

    def get_current_model_info(self) -> Dict[str, str]:
        """
        Get information about the currently configured model.

        Returns:
            Dict with provider, model, and key information
        """
        return {
            'provider_name': self.provider_model.provider_name,
            'deployment_name': self.provider_model.deployment_name,
            'trustai_model_key': self.provider_model.trustai_model_key,
            'workspace_id': self.workspace_id,
            'agent_id': str(self.agent_id)
        }
