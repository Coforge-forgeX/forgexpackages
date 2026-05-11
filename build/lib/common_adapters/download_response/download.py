from .markdown2docx import markdown_to_docx
from typing import Literal, Optional, Union
from io import BytesIO
import asyncio

async def download_message(
    message: str, 
    format: Literal['docx', 'md'], 
    output_file: Optional[str] = None
) -> Optional[BytesIO]:
    """
    Convert message to specified format and return as BytesIO stream or save to file
    
    Args:
        message: The message content to convert
        format: Output format ('docx' or 'md')
        output_file: Optional file path to save the document. If None, returns BytesIO stream
    
    Returns:
        BytesIO stream if output_file is None, otherwise None (saves to file)
    """
    if format == 'docx':
        # Run synchronous markdown_to_docx in a separate thread to avoid blocking
        result = await asyncio.to_thread(markdown_to_docx, message, output_file)
        if output_file is None:
            result.seek(0)
            return result
        else:
            # File was saved, return None
            return None
    
    elif format == 'md':
        if output_file is None:
            # Return as BytesIO stream (no I/O, runs quickly)
            md_stream = BytesIO(message.encode('utf-8'))
            md_stream.seek(0)
            return md_stream
        else:
            # Save to file asynchronously in a thread
            await asyncio.to_thread(_save_markdown_file, message, output_file)
            return None

def _save_markdown_file(message: str, output_file: str) -> None:
    """Helper function to save markdown to file (runs in thread pool)"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(message)
    print(f"Markdown document saved as '{output_file}'")