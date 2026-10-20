"""
explain_templates.py — Template lookup table for human-readable error recovery explanations.

Keyed by (operation, token_text, context) with sensible hierarchical fallbacks.
"""

from __future__ import annotations
from typing import Optional


# Explanations keyed by (operation, token_text)
SPECIFIC_EXPLANATIONS: dict[tuple[str, str], str] = {
    ("INS", ";"): "Inserted ';' because the statement grammar requires a statement terminator.",
    ("INS", ")"): "Inserted ')' to match and close the opening parenthesis in expression.",
    ("INS", "}"): "Inserted '}' to complete the enclosing block.",
    ("INS", "{"): "Inserted '{' to open statement body block.",
    ("INS", "("): "Inserted '(' required around conditional expression.",
    ("INS", ","): "Inserted ',' separator between declaration or argument items.",
    ("DEL", "}"): "Deleted extraneous closing brace to restore valid program termination.",
    ("DEL", ";"): "Deleted unexpected semicolon.",
    ("DEL", ")"): "Deleted unmatched closing parenthesis.",
    ("REP", ";"): "Replaced unexpected token with semicolon to terminate preceding statement.",
    ("REP", "="): "Replaced operator with assignment operator.",
    ("SYNC", ";"): "Resynchronized parser to the next statement delimiter ';'.",
    ("SYNC", "}"): "Resynchronized parser to the end of the enclosing block '}'.",
}

# Fallbacks keyed by operation
OP_FALLBACKS: dict[str, str] = {
    "INS": "Inserted expected token '{tok}' to satisfy grammar requirement.",
    "DEL": "Deleted invalid token '{tok}' to allow parsing to continue.",
    "REP": "Replaced token with '{tok}' to restore valid grammatical transition.",
    "SYNC": "Resynchronized parser state to recover forward progress.",
}


def get_explanation(op: str, tok_text: str, context: Optional[str] = None) -> str:
    """Retrieve or generate human-readable explanation for a repair decision."""
    key = (op, tok_text)
    if key in SPECIFIC_EXPLANATIONS:
        return SPECIFIC_EXPLANATIONS[key]

    template = OP_FALLBACKS.get(op, "Applied repair '{tok}'.")
    return template.format(tok=tok_text)
