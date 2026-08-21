import re


# Basic user-input validation used to block empty / symbol-only prompts.
# Goal: avoid wasting LLM calls and provide a clear client-facing message.
_HAS_ALNUM_RE = re.compile(r"[A-Za-z0-9]")


def is_valid_user_prompt(text: str | None) -> bool:
    """Return True if prompt has meaningful content.

    Rules:
    - Must not be None
    - After trimming whitespace, must not be empty
    - Must contain at least one alphanumeric character (blocks only-special-char input)
    """
    if text is None:
        return False
    t = text.strip()
    if not t:
        return False
    return _HAS_ALNUM_RE.search(t) is not None
