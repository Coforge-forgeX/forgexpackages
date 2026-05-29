
import logging
from typing import List, Dict 

logger = logging.getLogger(__name__)


class SlidingWindowStrategy:
    def __init__(self, keep_last: int = 12):
        logger.debug(f"Initializing SlidingWindowStrategy with keep_last={keep_last}")
        self.keep_last = keep_last

    async def compact(self, messages: List[Dict[str, str]], llm=None) -> List[Dict[str, str]]:
        logger.debug(f"SlidingWindowStrategy.compact called with {len(messages)} messages.")
        try:
            if len(messages) <= self.keep_last:
                logger.info(f"No sliding window compaction needed (messages <= keep_last={self.keep_last}).")
                logger.debug("Exiting SlidingWindowStrategy.compact (no compaction performed).")
                return messages
            logger.info(f"Sliding window compaction: keeping last {self.keep_last} messages out of {len(messages)}.")
            compacted = messages[-self.keep_last:]
            logger.debug(f"Exiting SlidingWindowStrategy.compact (compaction performed, {len(compacted)} messages returned).")
            return compacted
        except Exception as e:
            logger.exception(f"Error in SlidingWindowStrategy.compact: {e}")
            raise


class SummarizeOldMessagesStrategy:
    def __init__(self, keep_last: int = 10, summary_label: str = "conversation_summary"):
        logger.debug(f"Initializing SummarizeOldMessagesStrategy with keep_last={keep_last}, summary_label={summary_label}")
        self.keep_last = keep_last
        self.summary_label = summary_label

    async def compact(self, messages: List[Dict[str, str]], llm=None) -> List[Dict[str, str]]:
        logger.debug(f"SummarizeOldMessagesStrategy.compact called with {len(messages)} messages.")
        try:
            if len(messages) <= self.keep_last:
                logger.info(f"No summarization needed (messages <= keep_last={self.keep_last}).")
                logger.debug("Exiting SummarizeOldMessagesStrategy.compact (no compaction performed).")
                return messages
            old_msgs = messages[:-self.keep_last]
            recent_msgs = messages[-self.keep_last:]
            logger.info(f"Summarization triggered: summarizing {len(old_msgs)} old messages, keeping last {self.keep_last}.")
            if llm is None:
                logger.warning("No LLM provided for summarization; returning only recent messages.")
                logger.debug("Exiting SummarizeOldMessagesStrategy.compact (no LLM, no summary performed).")
                return recent_msgs
            summary_input = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in old_msgs
            )
            logger.debug(f"Invoking LLM for summarization with input length {len(summary_input)} characters.")
            summary = llm.invoke(
                sys_prompt=(
                    "You are a context compression assistant.\n\n"
                    "Your task is to reduce the conversation into a compact memory while preserving all important information.\n\n"
                    "RULES:\n"
                    "- Keep all important details (requirements, decisions, constraints, issues)\n"
                    "- Do NOT remove critical technical or business information\n"
                    "- Remove repetition, filler text, and unnecessary conversation parts\n"
                    "- Keep it concise and easy to read (avoid too much expansion)\n\n"
                    "OUTPUT FORMAT:\n"
                    "- Requirements:\n"
                    "- Decisions:\n"
                    "- Issues / Constraints:\n"
                    "- Pending Tasks / Questions:\n"
                    "- Key Entities:\n\n"
                    "Write short bullet points (2 line each). "
                    "Do NOT make it verbose. Keep it compact but complete."
                ),
                input=summary_input
            )
            logger.info("Summarization complete. Returning summary and recent messages.")
            logger.debug("Exiting SummarizeOldMessagesStrategy.compact (summary performed).")
            return [
                {
                    "role": "system",
                    "content": f"[{self.summary_label}] {summary}"
                },
                *recent_msgs
            ]
        except Exception as e:
            logger.exception(f"Error in SummarizeOldMessagesStrategy.compact: {e}")
            raise