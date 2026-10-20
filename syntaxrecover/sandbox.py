"""
sandbox.py — Validation Sandbox for SyntaxRecover.

Validates proposed candidate repairs in isolated cloned parser states:
- Feeds virtual token stream without mutating live parser state
- Measures parser progress distance P (capped at P_max)
- Evaluates lookahead validation rule (progress >= K_min or clean EOF accept)
- Discards unsafe/stalling candidates with explicit failure reasons
"""

from __future__ import annotations
from typing import List, Optional
from syntaxrecover.tokens import TT, Token
from syntaxrecover.config import Config, DEFAULT_CONFIG
from syntaxrecover.parser_adapter import ParserState
from syntaxrecover.candidates import Candidate


def validate_candidate(
    candidate: Candidate,
    state: ParserState,
    tokens: List[Token],
    cfg: Optional[Config] = None
) -> Candidate:
    """Validate a candidate repair using an isolated parser clone.

    Updates candidate.valid, candidate.progress, and candidate.reason in place.
    """
    if cfg is None:
        cfg = DEFAULT_CONFIG

    # Isolate parser state
    sandbox = state.clone()

    # Build virtual token view
    virtual_tokens = candidate.apply_to_tokens(tokens)

    # Determine start point: index of first applied edit
    first_edit_idx = min(e.at_index for e in candidate.edits) if candidate.edits else 0
    start_feed_idx = max(0, first_edit_idx)

    # Replay tokens in sandbox starting from start_feed_idx
    progress = 0
    stalled_at_tok = None

    for idx in range(start_feed_idx, len(virtual_tokens)):
        tok = virtual_tokens[idx]
        if sandbox.feed(tok):
            progress += 1
            if progress >= cfg.P_max:
                break
        else:
            stalled_at_tok = tok
            break

    candidate.progress = progress

    # Clean EOF check
    at_eof_cleanly = (
        sandbox.at_accept()
        or (progress > 0 and stalled_at_tok is not None and stalled_at_tok.type == TT.EOF and sandbox.at_accept())
    )

    if progress >= cfg.K_min or at_eof_cleanly:
        candidate.valid = True
        candidate.reason = f"parser advances {progress} tokens successfully"
    else:
        candidate.valid = False
        if stalled_at_tok:
            candidate.reason = f"parser stalls after {progress} tokens at '{stalled_at_tok.text}'"
        else:
            candidate.reason = f"parser stalls after {progress} tokens"

    return candidate


def validate_all(
    candidates: List[Candidate],
    state: ParserState,
    tokens: List[Token],
    cfg: Optional[Config] = None
) -> List[Candidate]:
    """Validate all candidates and return them."""
    if cfg is None:
        cfg = DEFAULT_CONFIG
    return [validate_candidate(c, state, tokens, cfg) for c in candidates]
