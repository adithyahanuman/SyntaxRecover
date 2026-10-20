"""
test_candidates.py — Unit tests for Candidate Repair Engine.

Verifies candidate generation (Insert, Delete, Replace, Sync), placeholder handling,
backtrack window, costs, structure penalties, and bounds on candidate count.
"""

import pytest
from syntaxrecover.tokens import TT
from syntaxrecover.lexer import tokenize
from syntaxrecover.config import Config
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.diagnose import diagnose
from syntaxrecover.candidates import generate_candidates, Candidate, Edit


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestCandidateGeneration:
    def test_slide_example_candidates(self, adapter):
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        assert err_idx is not None
        event = diagnose(state, tokens, err_idx, source=src)
        candidates = generate_candidates(event, state, tokens)

        # Must generate a non-empty, bounded list of candidates
        assert 3 <= len(candidates) <= 60

        # Check candidate IDs are sequential R1, R2...
        assert candidates[0].id == "R1"
        assert candidates[1].id == "R2"

        descriptions = [c.description for c in candidates]

        # Must include insert ';' before 'if'
        assert any("insert ';'" in d for d in descriptions)

        # Must include delete 'if'
        assert any("delete 'if'" in d for d in descriptions)

        # Must include a replace candidate
        assert any("replace 'if'" in d for d in descriptions)

        # Must include sync candidate
        assert any("sync to" in d for d in descriptions)

    def test_candidate_costs_and_penalties(self, adapter):
        src = "int main() { int x = (3 + 4; return 0; }"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        assert err_idx is not None
        event = diagnose(state, tokens, err_idx, source=src)
        candidates = generate_candidates(event, state, tokens)

        # Find insert ')'
        ins_paren = next((c for c in candidates if "insert ')'" in c.description), None)
        assert ins_paren is not None
        assert ins_paren.cost == 1.0
        # Structural delimiter ')' inserted => structure penalty > 0
        assert ins_paren.structure_penalty == 2.0  # lambda_ = 2.0 * 1

    def test_no_sync_ablation(self, adapter):
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        event = diagnose(state, tokens, err_idx, source=src)
        cfg = Config(no_sync=True)
        candidates = generate_candidates(event, state, tokens, cfg=cfg)

        # No sync candidate should be present
        assert not any("sync to" in c.description for c in candidates)
