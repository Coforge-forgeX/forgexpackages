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
        return [ 
            { 

                "role": "system", 
                "content": f"[{self.summary_label}] {summary}" 
            }, 
            *recent_msgs 
        ]