"""Deterministic keyword retrieval for source chunks."""
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
import math
import re

from ..ingestion.chunker import Chunk
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+")
_CAMEL_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _tokens(text: str) -> list[str]:
    """Tokenize text while retaining whole identifiers and their subwords."""
    tokens = []
    for identifier in _IDENTIFIER.findall(text):
        normalized = identifier.lower()
        tokens.append(normalized)
        for part in identifier.split("_"):
            # Split camel case while keeping the full identifier as a token too.
            tokens.extend(piece.lower() for piece in _CAMEL_PART.findall(part))
    return tokens


def keyword_search(
    chunks: Sequence[Mapping[str, object] | Chunk],
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Rank chunks using BM25 text relevance plus a metadata match boost.

    Returns copies of matching chunks with a numeric ``score`` field. Function
    names and file paths receive a boost because code questions often mention
    exact identifiers. Empty queries return no results; ``top_k`` must be
    positive.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    query_terms = list(dict.fromkeys(_tokens(query)))
    if not query_terms or not chunks:
        return []

    chunk_dicts = [
        asdict(chunk) if isinstance(chunk, Chunk) else dict(chunk)
        for chunk in chunks
    ]
    content_tokens = [_tokens(chunk.get("text", "")) for chunk in chunk_dicts]
    metadata_tokens = [
        _tokens(" ".join(
            str(chunk.get(field, ""))
            for field in ("file", "name", "qualified_name")
        ))
        for chunk in chunk_dicts
    ]
    content_counts = [Counter(tokens) for tokens in content_tokens]
    metadata_sets = [set(tokens) for tokens in metadata_tokens]
    doc_freq = {
        term: sum(
            term in counts or term in metadata
            for counts, metadata in zip(content_counts, metadata_sets)
        )
        for term in query_terms
    }

    doc_count = len(chunks)
    avg_length = sum(map(len, content_tokens)) / doc_count
    k1, b = 1.5, 0.75
    ranked = []

    for index, chunk in enumerate(chunk_dicts):
        length = len(content_tokens[index])
        score = 0.0
        for term in query_terms:
            frequency = content_counts[index][term]
            if frequency:
                inverse_frequency = math.log1p(
                    (doc_count - doc_freq[term] + 0.5)
                    / (doc_freq[term] + 0.5)
                )
                denominator = frequency + k1 * (
                    1 - b + b * length / avg_length
                ) if avg_length else frequency + k1
                score += inverse_frequency * (
                    frequency * (k1 + 1) / denominator
                )
            if term in metadata_sets[index]:
                inverse_frequency = math.log1p(
                    (doc_count - doc_freq[term] + 0.5)
                    / (doc_freq[term] + 0.5)
                )
                score += 2.0 * inverse_frequency

        if score > 0:
            ranked.append((score, index, chunk))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [{**chunk, "score": score} for score, _, chunk in ranked[:top_k]]
