"""
explain.py — Explainable Diagnostic Logger for SyntaxRecover.

Produces structured RecoveryEvent instances with complete candidate ranking matrices,
decision rationale, and human-readable formatting.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from syntaxrecover.diagnose import ErrorEvent
from syntaxrecover.candidates import Candidate
from syntaxrecover.explain_templates import get_explanation


@dataclass
class RecoveryEvent:
    """Complete diagnostic record for one error recovery event."""
    id: int
    line: int
    col: int
    unexpected: str
    expected: List[str]
    candidates: List[Dict[str, Any]]
    chosen: str
    explanation: str
    possibly_secondary: bool = False
    source_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict matching the JSON schema."""
        return {
            "id": self.id,
            "line": self.line,
            "col": self.col,
            "unexpected": self.unexpected,
            "expected": self.expected,
            "possibly_secondary": self.possibly_secondary,
            "candidates": self.candidates,
            "chosen": self.chosen,
            "explanation": self.explanation,
        }

    def format_text(self) -> str:
        """Render a terminal diagnostic log block with candidate matrix."""
        lines = []
        prefix = "error[syntax]"
        if self.possibly_secondary:
            prefix = "error[syntax, secondary]"

        exp_str = ", ".join(f"'{e}'" for e in self.expected[:6])
        if len(self.expected) > 6:
            exp_str += f", ... (+{len(self.expected) - 6} more)"

        lines.append(f"{prefix}: line {self.line}:{self.col}: unexpected '{self.unexpected}', expected one of: {exp_str}")

        if self.source_snippet:
            lines.append(self.source_snippet)

        lines.append("  Candidates evaluated:")
        for c in self.candidates:
            cid = c["id"]
            desc = c["edit"]
            if c["valid"]:
                badge = "<- ACCEPTED" if cid == self.chosen else "rejected"
                cost_str = f"cost={c['cost']:.1f}"
                prog_str = f"progress={c['progress']}"
                score_str = f"score={c['score']:.2f}"
                lines.append(f"  {cid:3s} {desc:<24s} valid   {cost_str:<10s} {prog_str:<12s} {score_str:<12s} {badge}")
            else:
                reason = c.get("reason", "invalid")
                lines.append(f"  {cid:3s} {desc:<24s} invalid ({reason}){' ':>10s} rejected")

        lines.append(f"  why: {self.explanation}")
        return "\n".join(lines)


def build_recovery_event(
    event_id: int,
    error: ErrorEvent,
    all_candidates: List[Candidate],
    chosen: Candidate,
    possibly_secondary: bool = False
) -> RecoveryEvent:
    """Build a RecoveryEvent from diagnosis and candidate evaluations."""
    candidate_records = []
    for c in all_candidates:
        primary_op = c.edits[0].kind.lower() if c.edits else "sync"
        rec = {
            "id": c.id,
            "op": primary_op,
            "edit": c.description,
            "valid": c.valid,
            "decision": "accepted" if c.id == chosen.id else "rejected",
        }
        if c.valid:
            rec["cost"] = c.cost
            rec["structure_penalty"] = c.structure_penalty
            rec["progress"] = c.progress
            rec["score"] = c.score
        else:
            rec["reason"] = c.reason
        candidate_records.append(rec)

    op_kind = chosen.edits[0].kind if chosen.edits else "SYNC"
    tok_text = chosen.edits[0].token.text if (chosen.edits and chosen.edits[0].token) else chosen.description
    explanation = get_explanation(op_kind, tok_text, error.context)

    snippet = ""
    if error.source_line:
        snippet = f"{error.line:4d} | {error.source_line}\n{error.caret_line}"

    return RecoveryEvent(
        id=event_id,
        line=error.line,
        col=error.col,
        unexpected=error.token.text,
        expected=error.expected,
        candidates=candidate_records,
        chosen=chosen.id,
        explanation=explanation,
        possibly_secondary=possibly_secondary,
        source_snippet=snippet,
    )
