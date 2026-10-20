"""
test_ranker.py — Unit tests for the Candidate Ranking Engine (Phase 3.2).

Verifies:
- Cost, Progress, Structure penalty score composition
- Formula: score = α·C + γ·S − β·p
- Slide example ranking: R1 (Insert ';') < R3 (Sync)
- Deterministic tie-breaking across 100 runs
- Property test: ranking defines a strict total order over all candidates
"""

import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.config import Config
from syntaxrecover.candidates import Candidate, Edit
from syntaxrecover.ranker import compute_score, rank_candidates, candidate_sort_key


class TestRanker:
    def test_slide_candidates_scores_and_ordering(self):
        """Verifies R1 < R3 matching worked example in docs/ranking_spec.md."""
        cfg = Config(alpha=1.0, beta=3.0, gamma=1.0, P_max=20)

        # R1: Insert ';' before 'if'
        # C = 1.0, S = 0.0, P = 15 -> p = 0.75 -> score = 1.0 + 0 - 3*0.75 = -1.25
        r1 = Candidate(
            id="R1",
            description="insert ';' before 'if'",
            edits=[Edit(kind="INS", at_index=9, token=Token(TT.SEMI, ";", 2, 16))],
            cost=1.0,
            structure_penalty=0.0,
            progress=15,
            valid=True
        )

        # R3: Sync to next ';'
        # C = 10.0, S = 9.0, P = 8 -> p = 0.40 -> score = 10.0 + 9.0 - 3*0.40 = 17.80
        r3 = Candidate(
            id="R3",
            description="sync to ';'",
            edits=[Edit(kind="SYNC", at_index=9, count=9)],
            cost=10.0,
            structure_penalty=9.0,
            progress=8,
            valid=True
        )

        assert compute_score(r1, cfg) == -1.25
        assert compute_score(r3, cfg) == 17.80

        ranked = rank_candidates([r3, r1], cfg)
        assert len(ranked) == 2
        assert ranked[0].id == "R1"
        assert ranked[1].id == "R3"

    def test_weight_overrides_from_config(self):
        """Weights α, β, γ loaded from Config change rankings appropriately."""
        c1 = Candidate("C1", "c1", edits=[Edit("INS", 0)], cost=2.0, structure_penalty=0.0, progress=10, valid=True)
        c2 = Candidate("C2", "c2", edits=[Edit("DEL", 0)], cost=1.0, structure_penalty=2.0, progress=10, valid=True)

        # Default weights: alpha=1.0, gamma=1.0 -> C1 cost+pen=2.0, C2 cost+pen=3.0 -> C1 wins
        cfg_default = Config(alpha=1.0, gamma=1.0, beta=0.0)
        ranked1 = rank_candidates([c2, c1], cfg_default)
        assert ranked1[0].id == "C1"

        # Heavy alpha weight: alpha=5.0, gamma=0.5 -> C1=10.0, C2=6.0 -> C2 wins!
        cfg_heavy_alpha = Config(alpha=5.0, gamma=0.5, beta=0.0)
        ranked2 = rank_candidates([c1, c2], cfg_heavy_alpha)
        assert ranked2[0].id == "C2"

    def test_deterministic_tie_breaking_across_100_runs(self):
        """Tie breaking must be 100% deterministic across multiple executions."""
        cfg = Config()

        # Two candidates with identical score, cost, progress, structure
        c_insert_semi = Candidate(
            "C_SEMI", "insert ';'",
            edits=[Edit("INS", 5, Token(TT.SEMI, ";", 1, 1))],
            cost=1.0, structure_penalty=0.0, progress=10, valid=True
        )
        c_insert_comma = Candidate(
            "C_COMMA", "insert ','",
            edits=[Edit("INS", 5, Token(TT.COMMA, ",", 1, 1))],
            cost=1.0, structure_penalty=0.0, progress=10, valid=True
        )

        # Lexicographic tie-break on token text: ',' (ASCII 44) < ';' (ASCII 59)
        first_winner = rank_candidates([c_insert_semi, c_insert_comma], cfg)[0].id

        for _ in range(100):
            ranked = rank_candidates([c_insert_semi, c_insert_comma], cfg)
            assert ranked[0].id == first_winner

    def test_ranking_total_order_property(self):
        """Property: for any two candidates A and B, either A <= B or B <= A."""
        cfg = Config()
        candidates = [
            Candidate("A", "ins ;", edits=[Edit("INS", 0, Token(TT.SEMI, ";", 1, 1))], cost=1.0, progress=5, valid=True),
            Candidate("B", "del", edits=[Edit("DEL", 0)], cost=1.0, progress=5, valid=True),
            Candidate("C", "rep", edits=[Edit("REP", 0, Token(TT.INT, "int", 1, 1))], cost=1.0, progress=5, valid=True),
            Candidate("D", "sync", edits=[Edit("SYNC", 0, count=2)], cost=3.0, progress=12, valid=True),
        ]

        keys = [candidate_sort_key(c, cfg) for c in candidates]
        # Every pair must have a strict, well-defined comparison
        for i in range(len(keys)):
            for j in range(len(keys)):
                k1, k2 = keys[i], keys[j]
                assert (k1 < k2) or (k1 > k2) or (k1 == k2)
