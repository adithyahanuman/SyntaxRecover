"""
commit.py — Committer and Resume Controller for SyntaxRecover.

Applies winning candidate edits to the live token sequence and steps the live
parser forward without resetting the parser loop:
- Applies insertions, deletions, replacements, or synchronizations
- Flags inserted tokens as synthetic
- Ensures termination guarantee (advances token index)
"""

from __future__ import annotations
from typing import List, Tuple
from syntaxrecover.tokens import Token
from syntaxrecover.parser_adapter import ParserState
from syntaxrecover.candidates import Candidate


def commit_repair(
    candidate: Candidate,
    state: ParserState,
    tokens: List[Token]
) -> Tuple[ParserState, List[Token], int]:
    """Commit the chosen repair candidate.

    Returns:
        (new_state, new_tokens, next_resume_index)
    """
    candidate.decision = "accepted"

    # Produce the repaired token stream
    new_tokens = candidate.apply_to_tokens(tokens)

    # Determine index where edits started
    first_edit_idx = min(e.at_index for e in candidate.edits) if candidate.edits else 0

    # Advance the live parser state over the new/repaired tokens
    resume_idx = first_edit_idx
    for idx in range(first_edit_idx, len(new_tokens)):
        tok = new_tokens[idx]
        if state.feed(tok):
            resume_idx = idx + 1
        else:
            resume_idx = idx
            break

    # Termination guarantee: must never loop indefinitely at the exact same index
    if resume_idx <= first_edit_idx and len(new_tokens) > first_edit_idx:
        resume_idx = first_edit_idx + 1

    return state, new_tokens, resume_idx
