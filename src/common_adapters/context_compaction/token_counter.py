from typing import List, Dict 

def estimate_tokens(messages: List[Dict[str, str]]) -> int: 
    total_chars = 0 
    for msg in messages: 
        total_chars += len(msg.get("content", "")) 
        
    return max(1, total_chars // 4) 