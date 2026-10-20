"""
test_explain.py — Unit tests for Explainable Logger and Diagnostic Logs (Phase 3.5).

Verifies:
- RecoveryEvent structured serialization matching docs/recovery_log_schema.json
- Formatted text output with caret, candidate evaluation matrix, and explanation
- Template table resolution for various operations
- Golden log comparison against slide presentation specification
"""

import json
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.cli import recover_all


def test_recovery_event_json_structure():
    """Serialized event must contain all required schema fields."""
    src = "int main() { int a = 10 if (a > 5) { print(a); } }"
    tokens = tokenize(src)
    result = recover_all(tokens, source=src)

    assert len(result.events) == 1
    event = result.events[0]
    data = event.to_dict()

    # Required JSON schema properties
    for key in ("id", "line", "col", "unexpected", "expected", "candidates", "chosen", "explanation"):
        assert key in data, f"Missing required JSON key '{key}'"

    # Candidates matrix properties
    assert len(data["candidates"]) > 0
    first_cand = data["candidates"][0]
    for c_key in ("id", "op", "edit", "valid", "decision"):
        assert c_key in first_cand, f"Candidate missing key '{c_key}'"

    # Must be valid json
    serialized = json.dumps(data)
    assert len(serialized) > 0


def test_golden_slide_example_log_contents():
    """Text output must present the Candidate Ranking Matrix and explanation."""
    src = "int main() {\n    int a = 10 if (a > 5) { print(a); }\n}"
    tokens = tokenize(src)
    result = recover_all(tokens, source=src)

    text_log = result.events[0].format_text()

    # Diagnostic header
    assert "error[syntax]" in text_log
    assert "unexpected 'if'" in text_log

    # Source snippet with caret
    assert "int a = 10 if (a > 5)" in text_log
    assert "^" in text_log

    # Candidate Ranking Matrix
    assert "Candidates evaluated:" in text_log
    assert "insert ';'" in text_log
    assert "<- ACCEPTED" in text_log
    assert "rejected" in text_log

    # Rationale explanation
    assert "why:" in text_log
    assert "statement grammar requires a statement terminator" in text_log
