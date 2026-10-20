"""
candidates.py — Candidate Repair Engine for SyntaxRecover.

Generates structured repair candidates:
- Insert from expected set (with placeholders for IDENT/literals)
- Delete offending token(s)
- Replace offending token with expected terminals
- Synchronize to safe landing tokens
- Multi-edit composition up to max_edits with beam search
- Deduplication and deterministic naming (R1, R2, ...)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple
from syntaxrecover.tokens import TT, Token, make_placeholder, KEYWORDS
from syntaxrecover.config import Config, DEFAULT_CONFIG
from syntaxrecover.diagnose import ErrorEvent
from syntaxrecover.parser_adapter import ParserState


STRUCTURAL_DELIMITERS: frozenset[str] = frozenset({"{", "}", "(", ")"})


@dataclass(frozen=True)
class Edit:
    """An atomic edit action."""
    kind: str                      # "INS" | "DEL" | "REP" | "SYNC"
    at_index: int                  # token index in original stream
    token: Optional[Token] = None  # inserted or replacement token
    count: int = 1                 # deleted or skipped count


@dataclass
class Candidate:
    """A proposed repair composed of one or more atomic edits."""
    id: str
    description: str
    edits: List[Edit]
    cost: float = 0.0
    structure_penalty: float = 0.0
    valid: bool = False
    progress: int = 0
    score: float = 0.0
    reason: str = ""
    decision: str = "pending"  # "accepted" | "rejected" | "pending"

    def apply_to_tokens(self, tokens: List[Token]) -> List[Token]:
        """Produce a new virtual token list with candidate edits applied."""
        result: List[Token] = []
        skip_until = -1

        # Map edits by index
        ins_map: dict[int, list[Token]] = {}
        del_map: dict[int, int] = {}
        rep_map: dict[int, Token] = {}
        sync_map: dict[int, int] = {}

        for edit in self.edits:
            if edit.kind == "INS" and edit.token is not None:
                ins_map.setdefault(edit.at_index, []).append(edit.token)
            elif edit.kind == "DEL":
                del_map[edit.at_index] = edit.count
            elif edit.kind == "REP" and edit.token is not None:
                rep_map[edit.at_index] = edit.token
            elif edit.kind == "SYNC":
                sync_map[edit.at_index] = edit.count

        for i, tok in enumerate(tokens):
            if i < skip_until:
                continue

            # Check for insertions before this token
            if i in ins_map:
                for ins_tok in ins_map[i]:
                    result.append(ins_tok)

            # Check for deletions
            if i in del_map:
                span = del_map[i]
                skip_until = i + span
                continue

            # Check for synchronize skip
            if i in sync_map:
                span = sync_map[i]
                skip_until = i + span
                continue

            # Check for replace
            if i in rep_map:
                result.append(rep_map[i])
                continue

            result.append(tok)

        # Insertions at the very end (at index == len(tokens))
        if len(tokens) in ins_map:
            for ins_tok in ins_map[len(tokens)]:
                result.append(ins_tok)

        # Produce fresh virtual token copies with updated indices (never mutate original tokens)
        virtual_tokens: List[Token] = []
        for idx, t in enumerate(result):
            virtual_tokens.append(Token(
                type=t.type,
                text=t.text,
                line=t.line,
                col=t.col,
                index=idx,
                synthetic=t.synthetic,
            ))

        return virtual_tokens


def _terminal_to_token(term: str, at_line: int, at_col: int) -> Token:
    """Convert an expected terminal string into a Token instance."""
    if term == "IDENT":
        return make_placeholder(TT.IDENT, at_line, at_col)
    if term == "INT_LIT":
        return make_placeholder(TT.INT_LIT, at_line, at_col)
    if term == "FLOAT_LIT":
        return make_placeholder(TT.FLOAT_LIT, at_line, at_col)
    if term == "CHAR_LIT":
        return make_placeholder(TT.CHAR_LIT, at_line, at_col)
    if term == "STRING_LIT":
        return make_placeholder(TT.STRING_LIT, at_line, at_col)

    # Keyword or punctuation
    tt = KEYWORDS.get(term)
    if tt is not None:
        return Token(type=tt, text=term, line=at_line, col=at_col, synthetic=True)

    # Punctuation/operators
    for candidate_tt in TT:
        if candidate_tt.value == term:
            return Token(type=candidate_tt, text=term, line=at_line, col=at_col, synthetic=True)

    # Fallback identifier
    return Token(type=TT.IDENT, text=term, line=at_line, col=at_col, synthetic=True)


def calculate_edit_cost(edit: Edit, cfg: Config) -> float:
    """Calculate Edit Cost C for an atomic edit."""
    if edit.kind == "INS":
        if edit.token and edit.token.text in ("__id__", "0", "0.0", "'a'", '""'):
            return 1.0 + cfg.placeholder_penalty
        return 1.0
    if edit.kind == "DEL":
        return 1.0 * edit.count
    if edit.kind == "REP":
        if edit.token and edit.token.text in ("__id__", "0", "0.0", "'a'", '""'):
            return 1.0 + cfg.placeholder_penalty
        return 1.0
    if edit.kind == "SYNC":
        return 1.0 + float(edit.count)
    return 1.0


def calculate_structure_penalty(
    edit: Edit,
    tokens: List[Token],
    cfg: Config
) -> float:
    """Calculate Source Structure Preservation Penalty S for an edit."""
    removed_or_skipped = 0
    structural_changed = 0

    if edit.kind == "INS":
        if edit.token and edit.token.text in STRUCTURAL_DELIMITERS:
            structural_changed += 1

    elif edit.kind == "DEL":
        removed_or_skipped += edit.count
        start = edit.at_index
        for tok in tokens[start : start + edit.count]:
            if tok.text in STRUCTURAL_DELIMITERS:
                structural_changed += 1

    elif edit.kind == "REP":
        orig_tok = tokens[edit.at_index] if edit.at_index < len(tokens) else None
        if orig_tok and orig_tok.text in STRUCTURAL_DELIMITERS:
            structural_changed += 1
        if edit.token and edit.token.text in STRUCTURAL_DELIMITERS:
            structural_changed += 1

    elif edit.kind == "SYNC":
        removed_or_skipped += edit.count
        start = edit.at_index
        for tok in tokens[start : start + edit.count]:
            if tok.text in STRUCTURAL_DELIMITERS:
                structural_changed += 1

    return float(removed_or_skipped) + (cfg.lambda_ * float(structural_changed))


def generate_single_edits(
    event: ErrorEvent,
    tokens: List[Token],
    cfg: Config
) -> List[Candidate]:
    """Generate all single-edit repair candidates."""
    candidates: List[Candidate] = []
    t = event.token
    i = event.index

    # 1. INSERT candidates
    for term in event.expected:
        if term == "EOF":
            continue
        ins_tok = _terminal_to_token(term, t.line, t.col)
        edit = Edit(kind="INS", at_index=i, token=ins_tok)
        cost = calculate_edit_cost(edit, cfg)
        s_pen = calculate_structure_penalty(edit, tokens, cfg)
        desc = f"insert '{ins_tok.text}' before '{t.text}'"
        candidates.append(Candidate(
            id="",
            description=desc,
            edits=[edit],
            cost=cost,
            structure_penalty=s_pen,
        ))

        # Backtrack window: also try insert before previous token
        if cfg.backtrack_window >= 1 and event.prev_token is not None and i > 0:
            b_edit = Edit(kind="INS", at_index=i - 1, token=ins_tok)
            b_cost = calculate_edit_cost(b_edit, cfg)
            b_pen = calculate_structure_penalty(b_edit, tokens, cfg)
            b_desc = f"insert '{ins_tok.text}' before '{event.prev_token.text}'"
            candidates.append(Candidate(
                id="",
                description=b_desc,
                edits=[b_edit],
                cost=b_cost,
                structure_penalty=b_pen,
            ))

    # 2. DELETE candidate
    if t.type != TT.EOF:
        for span in range(1, cfg.delete_span + 1):
            if i + span <= len(tokens):
                del_edit = Edit(kind="DEL", at_index=i, count=span)
                del_cost = calculate_edit_cost(del_edit, cfg)
                del_pen = calculate_structure_penalty(del_edit, tokens, cfg)
                del_desc = f"delete '{t.text}'" if span == 1 else f"delete {span} tokens starting at '{t.text}'"
                candidates.append(Candidate(
                    id="",
                    description=del_desc,
                    edits=[del_edit],
                    cost=del_cost,
                    structure_penalty=del_pen,
                ))

    # 3. REPLACE candidates
    if t.type != TT.EOF:
        for term in event.expected:
            if term == "EOF":
                continue
            rep_tok = _terminal_to_token(term, t.line, t.col)
            if rep_tok.text == t.text:
                continue
            rep_edit = Edit(kind="REP", at_index=i, token=rep_tok)
            rep_cost = calculate_edit_cost(rep_edit, cfg)
            rep_pen = calculate_structure_penalty(rep_edit, tokens, cfg)
            rep_desc = f"replace '{t.text}' with '{rep_tok.text}'"
            candidates.append(Candidate(
                id="",
                description=rep_desc,
                edits=[rep_edit],
                cost=rep_cost,
                structure_penalty=rep_pen,
            ))

    # 4. SYNCHRONIZE candidate (unless disabled by ablation)
    if not cfg.no_sync:
        sync_target_idx = None
        for j in range(i + 1, len(tokens)):
            tok_j = tokens[j]
            if tok_j.text in cfg.sync_tokens or tok_j.type == TT.EOF:
                sync_target_idx = j
                break

        if sync_target_idx is not None:
            skipped_count = sync_target_idx - i
            sync_tok_text = tokens[sync_target_idx].text or "EOF"
            sync_edit = Edit(kind="SYNC", at_index=i, count=skipped_count)
            sync_cost = calculate_edit_cost(sync_edit, cfg)
            sync_pen = calculate_structure_penalty(sync_edit, tokens, cfg)
            sync_desc = f"sync to '{sync_tok_text}'"
            candidates.append(Candidate(
                id="",
                description=sync_desc,
                edits=[sync_edit],
                cost=sync_cost,
                structure_penalty=sync_pen,
            ))

    return candidates


def generate_candidates(
    event: ErrorEvent,
    state: ParserState,
    tokens: List[Token],
    cfg: Optional[Config] = None
) -> List[Candidate]:
    """Generate, deduplicate, and label repair candidates for the error event."""
    if cfg is None:
        cfg = DEFAULT_CONFIG

    raw_candidates = generate_single_edits(event, tokens, cfg)

    # Deduplicate: if two candidates produce the same token stream view, keep cheaper
    unique_candidates: dict[str, Candidate] = {}
    for cand in raw_candidates:
        view_key = cand.description
        if view_key not in unique_candidates or cand.cost < unique_candidates[view_key].cost:
            unique_candidates[view_key] = cand

    result = list(unique_candidates.values())

    # Assign IDs: R1, R2, R3...
    for idx, cand in enumerate(result, start=1):
        cand.id = f"R{idx}"

    return result
