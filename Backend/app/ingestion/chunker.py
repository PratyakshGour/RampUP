def split_transcript(text: str, max_chars: int) -> list[tuple[str, str]]:
    """Split on paragraph boundaries and retain stable section references."""
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_size = 0
    section = 1

    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            if current:
                chunks.append((f"Section {section}", "\n".join(current)))
                section += 1
                current, current_size = [], 0
            chunks.append((f"Section {section}", paragraph[:max_chars]))
            section += 1
            paragraph = paragraph[max_chars:]
        if current and current_size + len(paragraph) + 1 > max_chars:
            chunks.append((f"Section {section}", "\n".join(current)))
            section += 1
            current, current_size = [], 0
        current.append(paragraph)
        current_size += len(paragraph) + 1

    if current:
        chunks.append((f"Section {section}", "\n".join(current)))
    return chunks
