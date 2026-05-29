
import logging
from typing import List, Dict 
from .token_counter import estimate_tokens 
from .strategies import SlidingWindowStrategy, SummarizeOldMessagesStrategy 

logger = logging.getLogger(__name__)


class ContextCompactor:
    def __init__(
        self,
        max_tokens: int = 12000,
        strategy: str = "summarize",
        keep_last: int = 10,
        llm=None,
    ):
        logger.debug(f"Initializing ContextCompactor with max_tokens={max_tokens}, strategy={strategy}, keep_last={keep_last}, llm={'provided' if llm else 'not provided'}")
        self.max_tokens = max_tokens
        self.llm = llm
        if strategy == "sliding":
            logger.info("Using SlidingWindowStrategy for context compaction.")
            self.strategy = SlidingWindowStrategy(keep_last=keep_last)
        else:
            logger.info("Using SummarizeOldMessagesStrategy for context compaction.")
            self.strategy = SummarizeOldMessagesStrategy(keep_last=keep_last)

    async def compact(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        logger.debug(f"Entering ContextCompactor.compact with {len(messages)} messages.")
        try:
            token_count = estimate_tokens(messages)
            logger.info(f"Estimated token count: {token_count} (max allowed: {self.max_tokens})")
            if token_count <= self.max_tokens:
                logger.info("No compaction needed; returning original messages.")
                return messages
            logger.info("Compaction triggered: token count exceeds threshold.")
            compacted = await self.strategy.compact(messages, llm=self.llm)
            logger.info(f"Compaction complete. Reduced messages from {len(messages)} to {len(compacted)}.")
            return compacted
        except Exception as e:
            logger.exception(f"Error during context compaction: {e}")
            raise