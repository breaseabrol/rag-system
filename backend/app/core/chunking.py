import tiktoken
import re
from abc import ABC, abstractmethod

_encoding = tiktoken.get_encoding('cl100k_base')

def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))

class Chunker(ABC):
    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        ...


class FixedSizeChunker(Chunker):
    def __init__(self, chunk_size: int = 400, overlap: int = 70):
        self.chunk_size = chunk_size
        self.overlap =  overlap

    def chunk(self, text: str) -> list[str]:
        tokens = _encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = start+self.chunk_size
            chunk_tokens = tokens[start:end]
            chunks.append(_encoding.decode(chunk_tokens))
            if end >= len(tokens):
                break
            start = end - self.overlap
        return chunks

def split_into_segments(text: str) -> list[dict]:
    """
    Walk the document text and break it into typed segments in order:
    - "code": content of a [CODE]...[/CODE] block, treated as atomic
    - "table_row": one row from inside a [TABLE]...[/TABLE] block
    - "prose": a paragraph of plain text (split on blank lines)
    """
    segments = []
 
    # matches [CODE]...[/CODE] or [TABLE]...[/TABLE], keeping the tag so we know which
    pattern = re.compile(r"\[(CODE|TABLE)\]\n(.*?)\n\[/\1\]", re.DOTALL)
 
    pos = 0
    for match in pattern.finditer(text):
        # anything before this match is prose — split into paragraphs
        prose_before = text[pos:match.start()].strip()
        if prose_before:
            for para in prose_before.split("\n\n"):
                para = para.strip()
                if para:
                    segments.append({"type": "prose", "content": para})
 
        tag, inner = match.group(1), match.group(2)
        if tag == "CODE":
            segments.append({"type": "code", "content": inner.strip()})
        else:  # TABLE
            for row in split_table_into_rows(inner):
                segments.append({"type": "table_row", "content": row})
 
        pos = match.end()
 
    # trailing prose after the last match
    remaining = text[pos:].strip()
    if remaining:
        for para in remaining.split("\n\n"):
            para = para.strip()
            if para:
                segments.append({"type": "prose", "content": para})
 
    return segments
 

def split_table_into_rows(table_text: str) -> list[str]:
    rows = table_text.split("\n\n")
    return [r.strip() for r in rows if r.strip()]

def pack_segments(segments: list[dict], chunk_size: int, overlap: int) -> list[str]:
    """
    Greedily pack segments into chunks under chunk_size tokens.
    "code" segments are never split, even if they alone exceed chunk_size —
    a split SQL example is close to useless, so we let those chunks run long.
    Overlap is carried forward as whole segments (not raw token slicing),
    so every chunk's content stays semantically clean at its edges.
    """
    chunks = []
    current_segments: list[dict] = []
    current_tokens = 0
 
    def flush():
        nonlocal current_segments, current_tokens
        if current_segments:
            chunks.append("\n\n".join(s["content"] for s in current_segments))
        current_segments = []
        current_tokens = 0
 
    for seg in segments:
        seg_tokens = count_tokens(seg["content"])
 
        # code blocks are atomic: if one alone is bigger than chunk_size,
        # it still gets its own chunk rather than being split
        if seg["type"] == "code" and seg_tokens > chunk_size:
            flush()
            chunks.append(seg["content"])
            continue
 
        if current_tokens + seg_tokens > chunk_size and current_segments:
            flush_boundary = current_segments.copy()
            flush()
 
            # carry back whole segments from the end of the previous chunk,
            # up to the overlap budget, as the start of the next one
            carry: list[dict] = []
            carry_tokens = 0
            for prev_seg in reversed(flush_boundary):
                t = count_tokens(prev_seg["content"])
                if carry_tokens + t > overlap:
                    break
                carry.insert(0, prev_seg)
                carry_tokens += t
 
            current_segments = carry
            current_tokens = carry_tokens
 
        current_segments.append(seg)
        current_tokens += seg_tokens
 
    flush()
    return chunks

class RecursiveChunker(Chunker):
    def __init__(self, chunk_size: int = 400, overlap: int = 70):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        # calls split_into_segments(), then pack_segments()
        segments = split_into_segments(text)
        return pack_segments(segments, self.chunk_size, self.overlap)
