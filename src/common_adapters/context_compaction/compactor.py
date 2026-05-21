from typing import List, Dict 
from .token_counter import estimate_tokens 
from .strategies import SlidingWindowStrategy, SummarizeOldMessagesStrategy 

class ContextCompactor: 
    def __init__( 
        self, 
        max_tokens: int = 12000, 
        strategy: str = "summarize", 
        keep_last: int = 10, 
        llm=None, 
    ): 
        self.max_tokens = max_tokens 
        self.llm = llm 
        if strategy == "sliding": 
            self.strategy = SlidingWindowStrategy(keep_last=keep_last) 
        else: 
            self.strategy = SummarizeOldMessagesStrategy(keep_last=keep_last) 

    async def compact(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]: 
        token_count = estimate_tokens(messages) 
        if token_count <= self.max_tokens: 
            return messages 
        return await self.strategy.compact(messages, llm=self.llm)