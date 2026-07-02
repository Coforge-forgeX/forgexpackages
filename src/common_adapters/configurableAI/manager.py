"""
ConfigurableAI Manager - Main interface for AI provider switching.
"""

from typing import Dict, Any, Optional, List, Union, Sequence, Literal
import logging
import os
import json
import asyncio
import re
import uuid
import ast
from langchain_core.messages import AIMessage
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from .providers import ProviderRegistry, BaseAIProvider
from .config import (
    AIProviderConfig, 
    AzureOpenAIConfig,
    QuasarConfig
)

logger = logging.getLogger(__name__)


class StructuredOutputWrapper:
    """
    Runnable wrapper for structured output generation.
    
    This class implements the Runnable interface to provide structured output
    functionality compatible with LangChain patterns.
    """
    
    def __init__(
        self,
        manager: "ConfigurableAIManager",
        schema: Optional[Union[Dict, type]] = None,
        method: Literal["function_calling", "json_mode", "json_schema"] = "json_schema",
        include_raw: bool = False,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ):
        self.manager = manager
        self.schema = schema
        self.method = method
        self.include_raw = include_raw
        self.strict = strict
        self.kwargs = kwargs
        
        # Process schema to determine output format
        self._is_pydantic = self._check_pydantic_schema(schema)
        self._schema_dict = self._convert_schema_to_dict(schema)
    
    def _check_pydantic_schema(self, schema: Any) -> bool:
        """Check if schema is a Pydantic model class."""
        if schema is None:
            return False
        try:
            # Check if it's a Pydantic model class
            return (
                hasattr(schema, '__bases__') and 
                any('BaseModel' in str(base) for base in schema.__mro__)
            )
        except:
            return False
    
    def _convert_schema_to_dict(self, schema: Any) -> Optional[Dict]:
        """Convert various schema formats to dictionary format."""
        if schema is None:
            return None
            
        if isinstance(schema, dict):
            return schema
            
        if self._is_pydantic:
            try:
                # For Pydantic models, get the schema
                if hasattr(schema, 'model_json_schema'):
                    return schema.model_json_schema()
                elif hasattr(schema, 'schema'):
                    return schema.schema()
            except:
                pass
                
        # For TypedDict or other types, try to extract info
        if hasattr(schema, '__annotations__'):
            properties = {}
            required = []
            
            for field_name, field_type in schema.__annotations__.items():
                # Basic type conversion
                if field_type == str:
                    properties[field_name] = {"type": "string"}
                elif field_type == int:
                    properties[field_name] = {"type": "integer"}
                elif field_type == float:
                    properties[field_name] = {"type": "number"}
                elif field_type == bool:
                    properties[field_name] = {"type": "boolean"}
                else:
                    properties[field_name] = {"type": "string"}  # Default fallback
                    
                required.append(field_name)
            
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
        return None
    
    def _build_structured_prompt(self, original_prompt: str) -> str:
        """Build a prompt that encourages structured output."""
        if self.method == "json_mode":
            if self._schema_dict:
                schema_str = json.dumps(self._schema_dict, indent=2)
                return f"{original_prompt}\n\nPlease respond with a valid JSON object that matches this schema:\n{schema_str}"
            else:
                return f"{original_prompt}\n\nPlease respond with a valid JSON object."
        
        elif self.method == "function_calling":
            if self._schema_dict:
                # Convert schema to function format
                function_schema = {
                    "name": "structured_response",
                    "description": "Generate a structured response",
                    "parameters": self._schema_dict
                }
                schema_str = json.dumps(function_schema, indent=2)
                return f"{original_prompt}\n\nPlease call the structured_response function with the appropriate parameters:\n{schema_str}"
            else:
                return original_prompt
        
        else:  # json_schema
            if self._schema_dict:
                schema_str = json.dumps(self._schema_dict, indent=2)
                return f"{original_prompt}\n\nPlease respond with a valid JSON object that matches this schema:\n{schema_str}"
            else:
                return f"{original_prompt}\n\nPlease respond with a valid JSON object."
    
    def _parse_response(self, raw_response: str) -> tuple[Any, Optional[Exception]]:
        """Parse the raw response according to the schema."""
        try:
            # Try to extract JSON from response
            cleaned_response = raw_response.strip()
            
            # Remove code block markers if present
            if cleaned_response.startswith('```'):
                lines = cleaned_response.split('\n')
                if len(lines) > 2:
                    cleaned_response = '\n'.join(lines[1:-1])
            
            # Try to find JSON object in the response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = cleaned_response
            
            # Parse JSON
            parsed_data = json.loads(json_str)
            
            # If we have a Pydantic schema, create an instance
            if self._is_pydantic and self.schema:
                try:
                    return self.schema(**parsed_data), None
                except Exception as e:
                    # If Pydantic validation fails, return the dict
                    return parsed_data, e
            
            return parsed_data, None
            
        except Exception as e:
            return None, e
    
    def invoke(self, input_data: Union[str, List, Dict]) -> Union[Dict, Any]:
        """
        Invoke the structured output generation.
        
        Args:
            input_data: Input prompt or messages
            
        Returns:
            Structured output according to schema
        """
        # Convert input to prompt string
        if isinstance(input_data, str):
            prompt = input_data
        elif isinstance(input_data, list):
            # Handle list of messages
            prompt_parts = []
            for msg in input_data:
                if isinstance(msg, dict):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    prompt_parts.append(f"{role.upper()}: {content}")
                else:
                    prompt_parts.append(str(msg))
            prompt = '\n\n'.join(prompt_parts)
        else:
            prompt = str(input_data)
        
        # Build structured prompt
        structured_prompt = self._build_structured_prompt(prompt)
        
        # Generate response
        raw_response = self.manager.generate_text(structured_prompt, **self.kwargs)
        
        # Parse response
        parsed_response, parsing_error = self._parse_response(raw_response)
        
        if self.include_raw:
            return {
                'raw': raw_response,
                'parsed': parsed_response,
                'parsing_error': parsing_error
            }
        else:
            if parsing_error:
                raise parsing_error
            return parsed_response
    
    async def ainvoke(self, input_data: Union[str, List, Dict]) -> Union[Dict, Any]:
        """
        Async invoke the structured output generation.
        
        Args:
            input_data: Input prompt or messages
            
        Returns:
            Structured output according to schema
        """
        # Convert input to prompt string
        if isinstance(input_data, str):
            prompt = input_data
        elif isinstance(input_data, list):
            # Handle list of messages
            prompt_parts = []
            for msg in input_data:
                if isinstance(msg, dict):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    prompt_parts.append(f"{role.upper()}: {content}")
                else:
                    prompt_parts.append(str(msg))
            prompt = '\n\n'.join(prompt_parts)
        else:
            prompt = str(input_data)
        
        # Build structured prompt
        structured_prompt = self._build_structured_prompt(prompt)
        
        # Generate response
        raw_response = await self.manager.generate_text_async(structured_prompt, **self.kwargs)
        
        # Parse response
        parsed_response, parsing_error = self._parse_response(raw_response)
        
        if self.include_raw:
            return {
                'raw': raw_response,
                'parsed': parsed_response,
                'parsing_error': parsing_error
            }
        else:
            if parsing_error:
                raise parsing_error
            return parsed_response


class ToolBoundConfigurableAIAdapter:
    """
    LangChain-compatible wrapper returned by ConfigurableAIManager.bind_tools().
    """

    def __init__(
        self,
        manager: "ConfigurableAIManager",
        tools: List[Any],
        *,
        system_prompt: Optional[str] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        strict: Optional[bool] = None,
        parallel_tool_calls: Optional[bool] = None,
        response_format: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        self._manager = manager
        self._tools = tools
        self._system_prompt = system_prompt
        self._tool_choice = tool_choice
        self._strict = strict
        self._parallel_tool_calls = parallel_tool_calls
        self._response_format = response_format
        
        # Store additional bound parameters from bind() method
        self._bound_params = kwargs

    @staticmethod
    def _tool_name(tool_obj: Any) -> str:
        return getattr(tool_obj, "name", None) or getattr(tool_obj, "__name__", "tool")

    @staticmethod
    def _tool_desc(tool_obj: Any) -> str:
        doc = getattr(tool_obj, "description", None) or getattr(tool_obj, "__doc__", "")
        return (doc or "").strip().split(":param")[0].strip()

    def _resolve_tool_choice_name(self) -> Optional[str]:
        tc = self._tool_choice
        if tc is None:
            return None
        if isinstance(tc, str):
            return tc
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            if isinstance(fn, dict):
                return fn.get("name")
        return None

    def _build_tool_protocol(self) -> str:
        lines: List[str] = []
        for idx, tool_obj in enumerate(self._tools, start=1):
            name = self._tool_name(tool_obj)
            desc = self._tool_desc(tool_obj)
            lines.append(f"{idx}. {name}: {desc}" if desc else f"{idx}. {name}")
        tools_desc = "\n".join(lines)

        base = self._system_prompt or "You are an AI assistant that helps developers generate structured instruction files for building software applications."

        forced = self._resolve_tool_choice_name()
        if forced:
            base += f"\n\nWhen responding to this request, please use the '{forced}' tool."
        elif self._tool_choice in ("any", "required"):
            base += "\n\nWhen responding to this request, please select and use one of the available tools."

        return (
            f"{base}\n\n"
            "You have access to the following tools:\n"
            f"{tools_desc}\n\n"
            "When using a tool, respond with the tool name and arguments in this structure:\n"
            '{"tool_call":{"name":"tool_name","arguments":{}}}\n\n'
            "When providing a direct response without using tools, use this structure:\n"
            '{"final":"your message"}\n\n'
            "Please ensure your response follows valid JSON formatting and uses the exact tool names listed above."
        )

    @staticmethod
    def _extract_json_object(text: str) -> Optional[dict]:
        if not text:
            return None
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # Parse first valid top-level JSON object instead of greedy regex capture.
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(cleaned):
            if ch != "{":
                continue
            try:
                obj, _end = decoder.raw_decode(cleaned[idx:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue

        return None

    @staticmethod
    def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
        """Extract all top-level JSON objects present in text."""
        if not text:
            return []

        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        objects: List[Dict[str, Any]] = []
        decoder = json.JSONDecoder()

        idx = 0
        total = len(cleaned)
        while idx < total:
            start = cleaned.find("{", idx)
            if start == -1:
                break
            try:
                obj, end = decoder.raw_decode(cleaned[start:])
                if isinstance(obj, dict):
                    objects.append(obj)
                # Move index forward relative to original string.
                idx = start + max(end, 1)
            except Exception:
                idx = start + 1

        return objects

    @staticmethod
    def _extract_balanced_braces_segment(text: str, start_idx: int) -> Optional[str]:
        """Return balanced {...} segment starting at start_idx, if any."""
        if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
            return None

        depth = 0
        in_string = False
        escaped = False
        quote_char = ""

        for i in range(start_idx, len(text)):
            ch = text[i]

            if in_string:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == quote_char:
                    in_string = False
                continue

            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1]

        return None

    @staticmethod
    def _extract_tool_call_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Best-effort extractor for malformed tool_call payloads in raw text."""
        if not text:
            return None

        # Fast path: locate tool_call block.
        key_idx = text.find('"tool_call"')
        if key_idx == -1:
            key_idx = text.find("'tool_call'")
        if key_idx == -1:
            return None

        # Parse from the outer object containing "tool_call".
        outer_start = text.rfind("{", 0, key_idx)
        brace_idx = outer_start if outer_start != -1 else text.find("{", key_idx)
        if brace_idx == -1:
            return None

        segment = ToolBoundConfigurableAIAdapter._extract_balanced_braces_segment(text, brace_idx)
        if not segment:
            # Recover from truncated payload by balancing braces to end.
            tail = text[brace_idx:].strip()
            open_count = tail.count("{")
            close_count = tail.count("}")
            if open_count > close_count:
                tail = tail + ("}" * (open_count - close_count))
            segment = tail

        # Try strict JSON first.
        try:
            obj = json.loads(segment)
            parsed = ToolBoundConfigurableAIAdapter._extract_tool_call_from_dict(obj) if isinstance(obj, dict) else None
            if parsed:
                return parsed
        except Exception:
            pass

        # Try Python-dict style payloads (single quotes / True False / None).
        try:
            obj = ast.literal_eval(segment)
            parsed = ToolBoundConfigurableAIAdapter._extract_tool_call_from_dict(obj) if isinstance(obj, dict) else None
            if parsed:
                return parsed
        except Exception:
            pass

        return None

    @staticmethod
    def _normalize_tool_args(raw_args: Any) -> Optional[Dict[str, Any]]:
        """Normalize tool arguments to dictionary if possible."""
        if isinstance(raw_args, dict):
            return raw_args

        if isinstance(raw_args, str):
            stripped = raw_args.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None

        return None

    @staticmethod
    def _extract_tool_call_from_dict(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize supported tool-call payload variants to {name,args}."""
        if not isinstance(data, dict):
            return None

        # Variant 0: direct payload {"name": "x", "arguments": {...}}
        direct_name = data.get("name")
        if isinstance(direct_name, str):
            direct_args = ToolBoundConfigurableAIAdapter._normalize_tool_args(
                data.get("arguments", {})
            )
            if isinstance(direct_args, dict):
                return {"name": direct_name.strip(), "args": direct_args}

        # Variant 1: {"tool_call": {"name": "x", "arguments": {...}}}
        direct = data.get("tool_call")
        if isinstance(direct, dict):
            name = direct.get("name")
            args = ToolBoundConfigurableAIAdapter._normalize_tool_args(
                direct.get("arguments", {})
            )
            if isinstance(name, str) and isinstance(args, dict):
                return {"name": name.strip(), "args": args}

        # Variant 2: OpenAI-style {"tool_calls": [{"function": {"name":..., "arguments": ...}}]}
        tool_calls = data.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            first = tool_calls[0]
            if isinstance(first, dict):
                fn = first.get("function") if isinstance(first.get("function"), dict) else first
                if isinstance(fn, dict):
                    name = fn.get("name")
                    args = ToolBoundConfigurableAIAdapter._normalize_tool_args(
                        fn.get("arguments", {})
                    )
                    if isinstance(name, str) and isinstance(args, dict):
                        return {"name": name.strip(), "args": args}

        return None

    @staticmethod
    def _to_langchain_messages(messages: List[Any]) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        for message in messages:
            if isinstance(message, dict):
                role = message.get("role", "user")
                content = message.get("content", "")
                if role not in ("system", "user", "assistant"):
                    role = "user"
                normalized.append({"role": role, "content": str(content)})
                continue

            if hasattr(message, "type") and hasattr(message, "content"):
                msg_type = message.type
                content = str(message.content)
                if msg_type == "system":
                    normalized.append({"role": "system", "content": content})
                elif msg_type in ("human", "user"):
                    normalized.append({"role": "user", "content": content})
                elif msg_type == "ai":
                    normalized.append({"role": "assistant", "content": content})
                elif msg_type == "tool":
                    tool_name = getattr(message, "name", "tool")
                    normalized.append({"role": "user", "content": f"[Tool result from {tool_name}] {content}"})
                else:
                    normalized.append({"role": "user", "content": content})
                continue

            normalized.append({"role": "user", "content": str(message)})
        return normalized

    async def ainvoke(self, messages: List[Any]) -> AIMessage:
        protocol = self._build_tool_protocol()
        normalized_messages = self._to_langchain_messages(messages)
        
        # Merge all system messages into one to avoid dual SYSTEM blocks
        system_contents = [protocol]
        non_system_messages = []
        
        for msg in normalized_messages:
            if msg.get("role") == "system":
                system_contents.append(msg.get("content", ""))
            else:
                non_system_messages.append(msg)
        
        # Create single system message with merged content
        merged_system_content = "\n\n".join(system_contents)
        request_messages = [{"role": "system", "content": merged_system_content}]
        request_messages.extend(non_system_messages)

        prompt_parts = []
        for msg in request_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.upper()}: {content}")
        prompt = "\n\n".join(prompt_parts)

        text = await self._manager.generate_text_async(prompt)
        data = self._extract_json_object(text)
        candidates = self._extract_json_objects(text)
        if isinstance(data, dict):
            candidates.insert(0, data)

        # De-duplicate candidates while preserving order.
        unique_candidates: List[Dict[str, Any]] = []
        seen_serialized = set()
        for candidate in candidates:
            try:
                marker = json.dumps(candidate, sort_keys=True, ensure_ascii=False)
            except Exception:
                marker = str(candidate)
            if marker in seen_serialized:
                continue
            seen_serialized.add(marker)
            unique_candidates.append(candidate)

        expanded_candidates: List[Dict[str, Any]] = []
        for candidate in unique_candidates:
            expanded_candidates.append(candidate)
            for key in ("response", "result", "output"):
                nested = candidate.get(key)
                if isinstance(nested, dict):
                    expanded_candidates.append(nested)

        selected_tool_call = None
        selected_final = None
        for candidate in expanded_candidates:
            tool_call_payload = self._extract_tool_call_from_dict(candidate)
            if tool_call_payload and tool_call_payload.get("name"):
                selected_tool_call = tool_call_payload
                break
            if selected_final is None and isinstance(candidate.get("final"), str):
                selected_final = candidate.get("final")

        if selected_tool_call is None:
            selected_tool_call = self._extract_tool_call_from_text(text)

        forced = self._resolve_tool_choice_name()
        if selected_tool_call:
            name = selected_tool_call.get("name", "")
            args = selected_tool_call.get("args", {})
            if forced is not None and name != forced:
                name = forced
                args = {}
            if isinstance(name, str):
                name = name.strip()
            if name and isinstance(args, dict):
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": f"call_{uuid.uuid4().hex[:16]}",
                            "name": name,
                            "args": args,
                        }
                    ],
                )

        if isinstance(selected_final, str):
            return AIMessage(content=selected_final)

        return AIMessage(content=text)

    # Returns string response for consistency with ConfigurableAIManager
    async def generate_text_async(self, messages: List[Any]) -> str:
        """
        Generate text with tools support - returns string response.
        
        Args:
            messages: List of message objects.
            
        Returns:
            Generated text string (extracted from final answer or raw text).
        """
        result = await self.ainvoke(messages)
        return result.content if hasattr(result, 'content') else str(result)

    def bind(self, **kwargs: Any) -> "ToolBoundConfigurableAIAdapter":
        """
        Bind additional parameters to create a new ToolBoundConfigurableAIAdapter.
        
        This ensures that both bind() and bind_tools() return the same type,
        providing a consistent interface for LangChain compatibility.
        
        Args:
            **kwargs: Additional parameters to bind
            
        Returns:
            A new ToolBoundConfigurableAIAdapter with merged parameters
        """
        # Merge existing bound parameters with new ones
        merged_params = self._bound_params.copy()
        merged_params.update(kwargs)
        
        return ToolBoundConfigurableAIAdapter(
            self._manager,
            self._tools,
            system_prompt=self._system_prompt,
            tool_choice=self._tool_choice,
            strict=self._strict,
            parallel_tool_calls=self._parallel_tool_calls,
            response_format=self._response_format,
            **merged_params
        )

    def bind_tools(
        self,
        tools: Sequence[Union[dict, type, Any]],
        *,
        tool_choice: Optional[Union[dict, str, bool]] = None,
        strict: Optional[bool] = None,
        parallel_tool_calls: Optional[bool] = None,
        response_format: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> "ToolBoundConfigurableAIAdapter":
        """
        Bind additional tools to this adapter.
        
        Args:
            tools: Additional tools to bind
            tool_choice: Tool choice override
            strict: Strict mode override
            parallel_tool_calls: Parallel tool calls override
            response_format: Response format override
            system_prompt: System prompt override
            **kwargs: Additional parameters
            
        Returns:
            A new ToolBoundConfigurableAIAdapter with additional tools
        """
        # Merge tools
        merged_tools = list(self._tools) + list(tools)
        
        # Merge bound parameters
        merged_params = self._bound_params.copy()
        merged_params.update(kwargs)
        
        return ToolBoundConfigurableAIAdapter(
            self._manager,
            merged_tools,
            system_prompt=system_prompt or self._system_prompt,
            tool_choice=tool_choice if tool_choice is not None else self._tool_choice,
            strict=strict if strict is not None else self._strict,
            parallel_tool_calls=parallel_tool_calls if parallel_tool_calls is not None else self._parallel_tool_calls,
            response_format=response_format or self._response_format,
            **merged_params
        )


class ConfigurableAIManager:
    """
    Main manager class for configurable AI providers.
    
    This class provides a simple interface to switch between different AI providers
    and perform common AI operations like text generation and embeddings.
    """
    
    def __init__(self, default_provider: Optional[str] = None):
        """
        Initialize the ConfigurableAI Manager.
        
        Args:
            default_provider: Default provider to use if none specified
        """
        self._providers: Dict[str, BaseAIProvider] = {}
        self._current_provider: Optional[str] = None
        self._default_provider = default_provider or os.getenv("DEFAULT_AI_PROVIDER", "openai")
        
        logger.info(f"Initialized ConfigurableAI Manager with default provider: {self._default_provider}")
    
    def configure_provider(self, provider_name: str, config: Union[AIProviderConfig, Dict[str, Any]]) -> None:
        """
        Configure an AI provider.
        
        Args:
            provider_name: Name of the provider (e.g., 'quasar','azure')
            config: Provider configuration (AIProviderConfig object or dict)
        """
        provider_name = provider_name.lower()
        
        # Convert dict to appropriate config object if needed
        if isinstance(config, dict):
            config = self._create_config_from_dict(provider_name, config)
        
        # Get provider class and create instance
        provider_class = ProviderRegistry.get_provider(provider_name)
        provider_instance = provider_class(config)
        
        # Validate configuration
        if not provider_instance.validate_config():
            raise ValueError(f"Invalid configuration for provider '{provider_name}'")
        
        self._providers[provider_name] = provider_instance
        
        # Set as current provider if it's the first one or default
        if not self._current_provider or provider_name == self._default_provider:
            self._current_provider = provider_name
        
        logger.info(f"Configured provider '{provider_name}' successfully")
    
    def configure_from_env(self, provider_name: str) -> bool:
        """
        Configure a provider using environment variables.
        
        Args:
            provider_name: Name of the provider to configure
            
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        provider_name = provider_name.lower()
        
        try:
            # Create config from environment
            if provider_name == "azure":
                config = AzureOpenAIConfig.from_env()
            elif provider_name == "quasar":
                config = QuasarConfig.from_env()
            else:
                logger.warning(f"Unknown provider type: {provider_name}, using generic config")
                config = AIProviderConfig.from_env(provider_name)
            
            logger.info(f"Created {provider_name} config: api_key={'***' if config.api_key else 'None'}, endpoint={config.endpoint}, model={config.model}")
            
            # Validate that required fields are present
            if not config.api_key:
                logger.error(f"Missing API key for {provider_name} provider")
                return False
            
            if not config.endpoint:
                logger.error(f"Missing endpoint for {provider_name} provider")
                return False
                
            if not config.model:
                logger.error(f"Missing model for {provider_name} provider")
                return False
            
            logger.info(f"All required fields present for {provider_name}, proceeding with configuration")
            self.configure_provider(provider_name, config)
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure provider {provider_name} from environment: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def configure_from_file(self, config_file: str) -> None:
        """
        Configure providers from a JSON configuration file.
        
        Args:
            config_file: Path to JSON configuration file
        """
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        providers_config = config_data.get('providers', {})
        default_provider = config_data.get('default_provider', self._default_provider)
        
        for provider_name, provider_config in providers_config.items():
            self.configure_provider(provider_name, provider_config)
        
        if default_provider in self._providers:
            self.set_current_provider(default_provider)
    
    def set_current_provider(self, provider_name: str) -> None:
        """
        Set the current active provider.
        
        Args:
            provider_name: Name of the provider to set as current
        """
        provider_name = provider_name.lower()
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured. Available: {list(self._providers.keys())}")
        
        self._current_provider = provider_name
        logger.info(f"Set current provider to: {provider_name}")
    
    def get_current_provider(self) -> Optional[str]:
        """Get the name of the current active provider."""
        return self._current_provider
    
    def list_configured_providers(self) -> List[str]:
        """List all configured providers."""
        return list(self._providers.keys())
    
    def list_available_providers(self) -> List[str]:
        """List all available provider types."""
        return ProviderRegistry.list_providers()
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """
        Get the current configuration status.
        
        Returns:
            Dictionary containing configuration status information
        """
        return {
            "current_provider": self._current_provider,
            "configured_providers": list(self._providers.keys()),
            "available_providers": self.list_available_providers(),
            "default_provider": self._default_provider,
            "total_configured": len(self._providers),
            "is_configured": len(self._providers) > 0,
            "has_current_provider": self._current_provider is not None
        }
    
    def generate_text(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using the specified or current provider (synchronous).
        
        Args:
            prompt: Text prompt for generation
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            Generated text
        """
        # Merge bound parameters with kwargs (kwargs take precedence)
        final_kwargs = {}
        if hasattr(self, '_bound_params'):
            final_kwargs.update(self._bound_params)
        final_kwargs.update(kwargs)
        
        try:
            # Try to get existing event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we need to use a different approach
            import concurrent.futures
            
            def run_in_thread():
                # Create a new event loop in a separate thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.generate_text_async(prompt, provider, **final_kwargs)
                    )
                finally:
                    new_loop.close()
            
            # Run in a separate thread to avoid event loop conflict
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.generate_text_async(prompt, provider, **final_kwargs))
    
    async def generate_text_async(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using the specified or current provider (asynchronous).
        
        Args:
            prompt: Text prompt for generation
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            Generated text
        """
        provider_name = provider or self._current_provider
        
        if not provider_name:
            raise ValueError("No provider specified and no current provider set")
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")
        
        # Merge bound parameters with kwargs (kwargs take precedence)
        final_kwargs = {}
        if hasattr(self, '_bound_params'):
            final_kwargs.update(self._bound_params)
        final_kwargs.update(kwargs)
        
        # Ensure consistent max_tokens default for all providers
        if 'max_tokens' not in final_kwargs:
            final_kwargs['max_tokens'] = 10000
            logger.debug(f"Setting default max_tokens=10000 for provider: {provider_name}")
        
        logger.info(f"Generating text using provider: {provider_name} with max_tokens={final_kwargs.get('max_tokens')}")
        return await self._providers[provider_name].generate_text(prompt, **final_kwargs)
    
    def generate_embeddings(self, texts: List[str], provider: Optional[str] = None, **kwargs) -> List[List[float]]:
        """
        Generate embeddings using the specified or current provider (synchronous).
        
        Args:
            texts: List of texts to generate embeddings for
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            List of embeddings
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we need to use a different approach
            import concurrent.futures
            
            def run_in_thread():
                # Create a new event loop in a separate thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.generate_embeddings_async(texts, provider, **kwargs)
                    )
                finally:
                    new_loop.close()
            
            # Run in a separate thread to avoid event loop conflict
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.generate_embeddings_async(texts, provider, **kwargs))
    
    async def generate_embeddings_async(self, texts: List[str], provider: Optional[str] = None, **kwargs) -> List[List[float]]:
        """
        Generate embeddings using the specified or current provider (asynchronous).
        
        Args:
            texts: List of texts to generate embeddings for
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            List of embeddings
        """
        provider_name = provider or self._current_provider
        
        if not provider_name:
            raise ValueError("No provider specified and no current provider set")
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")
        
        logger.info(f"Generating embeddings using provider: {provider_name}")
        return await self._providers[provider_name].generate_embeddings(texts, **kwargs)
    
    def _create_config_from_dict(self, provider_name: str, config_dict: Dict[str, Any]) -> AIProviderConfig:
        """Create appropriate config object from dictionary."""
        config_dict['provider_name'] = provider_name
        
        if provider_name == "azure":
            return AzureOpenAIConfig(**config_dict)
        elif provider_name == "quasar":
            return QuasarConfig(**config_dict)
        else:
            return AIProviderConfig.from_dict(config_dict)

    def bind_tools(
        self,
        tools: Sequence[Union[dict, type, Any]],
        *,
        tool_choice: Optional[Union[dict, str, bool]] = None,
        strict: Optional[bool] = None,
        parallel_tool_calls: Optional[bool] = None,
        response_format: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolBoundConfigurableAIAdapter:
        """
        Bind tool-like objects to this chat model.

        Assumes model is compatible with OpenAI tool-calling API.

        Args:
            tools: A list of tool definitions to bind to this chat model.
            tool_choice: Which tool to require the model to call. Options are:
                - `str` of the form `'<<tool_name>>'`: calls `<<tool_name>>` tool.
                - `'auto'`: automatically selects a tool (including no tool).
                - `'none'`: does not call a tool.
                - `'any'` or `'required'` or `True`: force at least one tool to be called.
                - `dict` of the form `{"type": "function", "function": {"name": <<tool_name>>}}`: calls `<<tool_name>>` tool.
                - `False` or `None`: no effect, default behavior.
            strict: If `True`, model output is guaranteed to exactly match the JSON Schema
                provided in the tool definition.
            parallel_tool_calls: Set to `False` to disable parallel tool use.
                Defaults to `None` (no specification, which allows parallel tool use).
            response_format: Optional schema to format model response.
            system_prompt: Optional system prompt override.
            **kwargs: Any additional parameters.

        Returns:
            ToolBoundConfigurableAIAdapter instance.
        """
        # Process tool_choice similar to LangChain
        processed_tool_choice = self._process_tool_choice(tool_choice, tools)
        
        # Handle parallel_tool_calls
        if parallel_tool_calls is not None:
            kwargs["parallel_tool_calls"] = parallel_tool_calls
            
        # Handle strict mode
        if strict is not None:
            kwargs["strict"] = strict
            
        # Handle response_format
        if response_format is not None:
            kwargs["response_format"] = response_format
        
        # Log unsupported kwargs
        unsupported = [k for k in kwargs if k not in ["parallel_tool_calls", "strict", "response_format"]]
        if unsupported:
            logger.debug("bind_tools ignoring unsupported kwargs: %s", unsupported)
            
        return ToolBoundConfigurableAIAdapter(
            self,
            list(tools),
            system_prompt=system_prompt,
            tool_choice=processed_tool_choice,
            strict=strict,
            parallel_tool_calls=parallel_tool_calls,
            response_format=response_format,
        )
    
    def bind(self, **kwargs: Any) -> ToolBoundConfigurableAIAdapter:
        """
        Bind arbitrary parameters and return a ToolBoundConfigurableAIAdapter.
        
        This method is required for LangChain compatibility, particularly with
        langchain.agents.create_agent. Returns the same type as bind_tools() to
        ensure consistent interface.
        
        Args:
            **kwargs: Arbitrary keyword arguments to bind to the manager
            
        Returns:
            A ToolBoundConfigurableAIAdapter instance with bound parameters
        """
        # Create a ToolBoundConfigurableAIAdapter with empty tools but bound parameters
        # This ensures consistent interface with bind_tools()
        return ToolBoundConfigurableAIAdapter(
            self,
            tools=[],  # No tools for general bind()
            **kwargs
        )

    def _process_tool_choice(self, tool_choice: Optional[Union[dict, str, bool]], tools: Sequence[Any]) -> Optional[Union[dict, str]]:
        """Process tool_choice parameter similar to LangChain implementation."""
        if not tool_choice:
            return tool_choice
            
        # Get tool names for validation
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            elif isinstance(tool, dict) and 'function' in tool:
                tool_names.append(tool['function'].get('name', ''))
            elif isinstance(tool, dict) and 'name' in tool:
                tool_names.append(tool['name'])
        
        if isinstance(tool_choice, str):
            # tool_choice is a tool/function name
            if tool_choice in tool_names:
                return {
                    "type": "function",
                    "function": {"name": tool_choice},
                }
            # 'any' is not natively supported by OpenAI API.
            # We support 'any' since other models use this instead of 'required'.
            elif tool_choice == "any":
                return "required"
            elif tool_choice in ["auto", "none", "required"]:
                return tool_choice
            else:
                # Unknown string, pass through
                return tool_choice
        elif isinstance(tool_choice, bool):
            return "required" if tool_choice else None
        elif isinstance(tool_choice, dict):
            return tool_choice
        else:
            raise ValueError(
                f"Unrecognized tool_choice type. Expected str, bool or dict. "
                f"Received: {tool_choice}"
            )

    def with_structured_output(
        self,
        schema: Optional[Union[Dict, type]] = None,
        *,
        method: Literal["function_calling", "json_mode", "json_schema"] = "json_schema",
        include_raw: bool = False,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, Union[Dict, Any]]:
        """Model wrapper that returns outputs formatted to match the given schema.

        Args:
            schema: The output schema. Can be passed in as:
                - A JSON Schema,
                - A `TypedDict` class,
                - A Pydantic class,
                - Or an OpenAI function/tool schema.

                If `schema` is a Pydantic class then the model output will be a
                Pydantic instance of that class, and the model-generated fields will be
                validated by the Pydantic class. Otherwise the model output will be a
                dict and will not be validated.

            method: The method for steering model generation, one of:
                - `'json_schema'`: Uses structured output API (default)
                - `'function_calling'`: Uses tool-calling API
                - `'json_mode'`: Uses JSON mode

            include_raw: If `False` then only the parsed structured output is returned.
                If `True` then both the raw model response and the parsed model response
                will be returned.

            strict: Whether to enable strict mode for schema validation.

            kwargs: Additional keyword args are passed through to the model.

        Returns:
            A `Runnable` that takes same inputs as ConfigurableAIManager.
            If `include_raw` is `False` and `schema` is a Pydantic class, outputs an
            instance of `schema`. Otherwise, outputs a `dict`.

            If `include_raw` is `True`, then outputs a `dict` with keys:
            - `'raw'`: Raw model response
            - `'parsed'`: Parsed response (None if parsing error)
            - `'parsing_error'`: BaseException | None

        Example:
            ```python
            from pydantic import BaseModel

            class AnswerWithJustification(BaseModel):
                answer: str
                justification: str

            manager = ConfigurableAIManager()
            structured_model = manager.with_structured_output(AnswerWithJustification)
            result = structured_model.invoke("What weighs more, a pound of bricks or feathers?")
            ```
        """
        return StructuredOutputWrapper(
            manager=self,
            schema=schema,
            method=method,
            include_raw=include_raw,
            strict=strict,
            **kwargs
        )


# Convenience function for quick setup (env-var based, no persistence)
def get_ai_manager(
    provider_name: str = "azure",
    auto_configure: bool = True,
) -> ConfigurableAIManager:
    """
    Get a ConfigurableAI Manager pre-configured from environment variables.

    For database-backed, workspace-scoped managers use the tool layer
    (_build_manager_from_db in llm_router_tool.py) instead.

    Args:
        provider_name: Name of the provider to configure.
        auto_configure: Whether to auto-configure from environment variables.

    Returns:
        Configured ConfigurableAIManager instance.
    """
    manager = ConfigurableAIManager(default_provider=provider_name)
    if auto_configure:
        manager.configure_from_env(provider_name)
    return manager


# Cache for AI manager instances per workspace/agent
_ai_managers: Dict[str, ConfigurableAIManager] = {}


def _get_manager_key(workspace_id: int, agent_id: Optional[int] = None) -> str:
    """Generate a cache key for AI manager instances."""
    return f"ws_{workspace_id}_agent_{agent_id}"


def clear_ai_manager_cache(workspace_id: Optional[int] = None, agent_id: Optional[int] = None):
    """
    Clear AI manager cache for specific workspace/agent or all cached managers.
    
    Args:
        workspace_id: ID of the workspace (None to clear all)
        agent_id: ID of the agent (None to clear workspace default)
    """
    global _ai_managers
    
    if workspace_id is not None:
        key = _get_manager_key(workspace_id, agent_id)
        if key in _ai_managers:
            del _ai_managers[key]
            logger.info(f"Cleared AI manager cache for workspace {workspace_id}, agent {agent_id}")
    else:
        _ai_managers.clear()
        logger.info("Cleared all AI manager cache")


def get_cached_manager_count() -> int:
    """Get the number of cached AI manager instances."""
    return len(_ai_managers)