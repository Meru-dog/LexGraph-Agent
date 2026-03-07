"""chunker — 512-token chunks with 64-token overlap using tiktoken."""

import uuid
from typing import List


CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def chunk_text(text: str, doc_id: str) -> List[dict]:
    """Split text into overlapping chunks of ~512 tokens.

    Phase 0: character-based approximation (1 token ≈ 4 chars).
    Phase 3: use tiktoken for exact token counts.
    """
    # Character-based approximation
    char_size = CHUNK_SIZE * 4
    char_overlap = CHUNK_OVERLAP * 4

    chunks = []
    position = 0
    chunk_index = 0

    while position < len(text):
        end = min(position + char_size, len(text))
        chunk_text = text[position:end].strip()
        if chunk_text:
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "text": chunk_text,
                "position": position,
                "token_count_approx": len(chunk_text) // 4,
                "chunk_index": chunk_index,
            })
        position += char_size - char_overlap
        chunk_index += 1

    return chunks
