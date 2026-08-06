"""
TrustAI Guardrail Exceptions.
"""

from typing import List, Optional, Dict, Any


class GuardrailBlockedException(Exception):
    """
    Raised when TrustAI guardrails block a request or response.
    
    Attributes:
        blocked_by: List of guardrail names that blocked (e.g., ['TOXIC', 'PII'])
        details: List of guardrail check details
        block_message: The message returned by TrustAI when blocked
    """
    
    def __init__(
        self,
        blocked_by: List[str],
        details: Optional[List[Dict[str, Any]]] = None,
        block_message: str = "Content blocked by guardrails"
    ):
        self.blocked_by = blocked_by
        self.details = details or []
        self.block_message = block_message
        super().__init__(
            f"Request blocked by guardrails: {', '.join(blocked_by)}. "
            f"Message: {block_message}"
        )
    
    def get_user_message(self) -> str:
        """Get a user-friendly message about the blocking."""
        if self.blocked_by:
            return f"Your request was blocked by content safety filters ({', '.join(self.blocked_by)}). Please rephrase your message."
        return self.block_message


def check_trustai_guardrail_response(data: Dict[str, Any]) -> None:
    """
    Check TrustAI response for guardrail blocks and raise exception if blocked.
    
    Args:
        data: Full response dict from TrustAI API
        
    Raises:
        GuardrailBlockedException: If the response was blocked by guardrails
    """
    checks = data.get("checks", {})
    blocked_by = checks.get("blocked_by", [])
    
    # Also check content for the standard blocked message
    content = ""
    choices = data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    
    is_blocked = bool(blocked_by) or content == "Content blocked by guardrails"
    
    if is_blocked:
        # Collect details from input/output guardrails
        details = []
        for g in checks.get("input_guardrails", []):
            if g.get("detail", {}).get("outcome") == "Fail":
                details.append({
                    "guardrail": g.get("guardrail"),
                    "type": "input",
                    "outcome": g.get("detail", {}).get("outcome"),
                    "message": g.get("detail", {}).get("message", "")
                })
        for g in checks.get("output_guardrails", []):
            if g.get("detail", {}).get("outcome") == "Fail":
                details.append({
                    "guardrail": g.get("guardrail"),
                    "type": "output", 
                    "outcome": g.get("detail", {}).get("outcome"),
                    "message": g.get("detail", {}).get("message", "")
                })
        
        raise GuardrailBlockedException(
            blocked_by=blocked_by,
            details=details,
            block_message=content if content else "Content blocked by guardrails"
        )
