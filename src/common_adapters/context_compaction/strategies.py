from typing import List, Dict 

class SlidingWindowStrategy: 
    def __init__(self, keep_last: int = 12): 
        self.keep_last = keep_last 
    async def compact(self, messages: List[Dict[str, str]], llm=None) -> List[Dict[str, str]]: 
        if len(messages) <= self.keep_last: 
            return messages 
        return messages[-self.keep_last:] 

class SummarizeOldMessagesStrategy: 
    def __init__(self, keep_last: int = 10, summary_label: str = "conversation_summary"): 
        self.keep_last = keep_last 
        self.summary_label = summary_label 
    async def compact(self, messages: List[Dict[str, str]], llm=None) -> List[Dict[str, str]]:
        if len(messages) <= self.keep_last: 
            return messages 
        old_msgs = messages[:-self.keep_last] 
        recent_msgs = messages[-self.keep_last:] 
        if llm is None: 
            return recent_msgs
        summary_input = "\n".join( 
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in old_msgs 
        ) 
        summary = llm.invoke( 
            sys_prompt=( 
                "Summarize the older conversation context into a compact but complete memory. " 
                "Preserve requirements, decisions, constraints, unresolved questions, and referenced entities." 
            ), 
            input=summary_input 
        ) 
        return [ 
            { 

                "role": "system", 
                "content": f"[{self.summary_label}] {summary}" 
            }, 
            *recent_msgs 
        ]