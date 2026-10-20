"""
test_sandbox.py — Unit tests for the Validation Sandbox (Phase 3.1).

Verifies:
- Sandbox clone isolation (live parser state bit-for-bit unchanged after 100 validations)
- Virtual token view isolation (original tokens list untouched)
- K_min lookahead threshold vs clean EOF acceptance
- Failure reason recording
- Slide example candidates: R1 valid with high progress, R2 invalid (stalls)
"""

import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.lexer import tokenize
from syntaxrecover.config import Config
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.diagnose import diagnose
from syntaxrecover.candidates import generate_candidates, Candidate, Edit
from syntaxrecover.sandbox import validate_candidate, validate_all


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestValidationSandbox:
    def test_live_state_isolation_after_100_validations(self, adapter):
        """Validating 100 candidates must leave the live parser state bit-for-bit unchanged."""
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        # Capture live state's internal properties before sandbox runs
        expected_before = state.expected()
        state_stack_before = list(state.ip.parser_state.state_stack)
        tokens_before = [Token(t.type, t.text, t.line, t.col, t.index) for t in tokens]

        # Generate candidates
        event = diagnose(state, tokens, err_idx, source=src)
        candidates = generate_candidates(event, state, tokens)

        # Replicate to reach 100 validations
        replicated_candidates = (candidates * (100 // len(candidates) + 1))[:100]
        assert len(replicated_candidates) == 100

        # Run 100 sandbox validations
        results = validate_all(replicated_candidates, state, tokens)
        assert len(results) == 100

        # Assert live state is bit-for-bit identical!
        assert state.expected() == expected_before
        assert list(state.ip.parser_state.state_stack) == state_stack_before

        # Assert original token stream is completely untouched!
        assert len(tokens) == len(tokens_before)
        for t_curr, t_old in zip(tokens, tokens_before):
            assert t_curr.type == t_old.type
            assert t_curr.text == t_old.text
            assert t_curr.index == t_old.index

    def test_slide_candidates_validation(self, adapter):
        """R1 (insert ';') must be valid with high progress; R2 (delete 'if') must stall and be invalid."""
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        event = diagnose(state, tokens, err_idx, source=src)
        candidates = generate_candidates(event, state, tokens)
        validate_all(candidates, state, tokens)

        # R1: insert ';' before 'if'
        r1 = next(c for c in candidates if c.description == "insert ';' before 'if'")
        assert r1.valid is True
        assert r1.progress >= 15
        assert "parser advances" in r1.reason

        # R2: delete 'if'
        r2 = next(c for c in candidates if c.description == "delete 'if'")
        assert r2.valid is False
        assert r2.progress == 0
        assert "parser stalls after 0 tokens" in r2.reason

    def test_clean_eof_acceptance_shorter_than_k_min(self, adapter):
        """A candidate that reaches clean EOF must be accepted even if progress < K_min."""
        # Program missing closing brace right at EOF: progress will be 1 (< K_min=3)
        src = "int main() {"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        event = diagnose(state, tokens, err_idx, source=src)
        cfg = Config(K_min=5)  # Require 5 tokens for normal lookahead

        cand = Candidate(
            id="R1",
            description="insert '}' before EOF",
            edits=[Edit(kind="INS", at_index=err_idx, token=Token(TT.RBRACE, "}", 1, 13, synthetic=True))]
        )

        validate_candidate(cand, state, tokens, cfg)
        assert cand.valid is True  # Reached clean EOF!
        assert cand.progress == cfg.P_max
