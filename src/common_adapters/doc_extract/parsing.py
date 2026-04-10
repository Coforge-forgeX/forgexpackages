# doc_extract/parsing.py
from collections import defaultdict
from typing import Dict, List, Tuple

def parse_textract_blocks(blocks: List[Dict]) -> Tuple[str, List[str]]:
    page_lines: Dict[int, List[str]] = defaultdict(list)
    for b in blocks:
        if b.get("BlockType") == "LINE" and "Text" in b:
            page = int(b.get("Page") or 1)
            page_lines[page].append(b["Text"])
    ordered_pages = [page_lines[p] for p in sorted(page_lines.keys())]
    pages_text = ["\n".join(lines) for lines in ordered_pages]
    full_text = "\n\n".join(pages_text)
    return full_text, pages_text