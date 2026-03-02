"""Common utilities."""


def truncate(text: str, max_len: int = 200) -> str:
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len] + "..."
