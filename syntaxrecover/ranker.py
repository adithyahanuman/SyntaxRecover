"""
ranker.py — Candidate Ranking Engine for SyntaxRecover.

Computes the composite score for validated candidates:
    score = α·C + γ·S − β·p
where p = P / P_max (normalized parser progress).
Applies deterministic tie-breaking:
    higher P -> lower C -> operation priority (INS > REP > DEL > SYNC) -> lexicographic token text
"""

from __future__ import annotations
from typing import List, Optional, Tuple
from syntaxrecover.config import Config, DEFAULT_CONFIG
from syntaxrecover.candidates import Candidate


OP_PRIORITY: dict[str, int] = {
    "INS": 1,
    "REP": 2,
    "DEL": 3,
    "SYNC": 4,
}


def compute_score(candidate: Candidate, cfg: Config) -> float:
    """Compute score = α·C + γ·S − β·p. Lower score is better."""
    p_norm = float(candidate.progress) / float(cfg.P_max)
    score = (cfg.alpha * candidate.cost) + (cfg.gamma * candidate.structure_penalty) - (cfg.beta * p_norm)
    candidate.score = round(score, 4)
    return candidate.score


def candidate_sort_key(cand: Candidate, cfg: Config) -> Tuple[float, float, float, int, str]:
    """Tuple for deterministic sorting. Lower is better."""
    score = compute_score(cand, cfg)
    p_neg = -float(cand.progress)  # higher progress preferred
    c_val = cand.cost              # lower cost preferred

    primary_op = cand.edits[0].kind if cand.edits else "SYNC"
    op_order = OP_PRIORITY.get(primary_op, 99)

    tok_text = ""
    if cand.edits and cand.edits[0].token:
        tok_text = cand.edits[0].token.text

    return (score, p_neg, c_val, op_order, tok_text)


def rank_candidates(
    candidates: List[Candidate],
    cfg: Optional[Config] = None
) -> List[Candidate]:
    """Score, sort, and rank valid candidates in ascending order (best first)."""
    if cfg is None:
        cfg = DEFAULT_CONFIG

    # Filter to valid candidates only
    valid_candidates = [c for c in candidates if c.valid]
    if not valid_candidates:
        return []

    sorted_candidates = sorted(valid_candidates, key=lambda c: candidate_sort_key(c, cfg))
    return sorted_candidates
