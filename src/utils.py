# src/utils.py
import re


def reply_text(response) -> str:
    """Turn a model reply into clean plain text."""
    content = response.content if hasattr(response, "content") else response

    # Some models return a list of blocks instead of a string
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        content = "".join(parts)

    # Remove any visible "thinking" text
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    return content.strip()