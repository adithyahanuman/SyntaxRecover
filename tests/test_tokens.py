"""
test_tokens.py — Phase 0 sanity tests for the Token class and TT enum.

These tests are intentionally minimal: they confirm the data structures are
importable and have the correct shape.  Substantive token-stream tests live
in test_lexer.py (Phase 2).
"""

import pytest
from syntaxrecover.tokens import TT, Token, KEYWORDS, SYNC_TOKENS, make_placeholder


class TestTokenType:
    def test_keyword_values(self):
        assert TT.INT.value == "int"
        assert TT.FLOAT.value == "float"
        assert TT.IF.value == "if"
        assert TT.EOF.value == "EOF"
        assert TT.ILLEGAL.value == "ILLEGAL"

    def test_keywords_dict_coverage(self):
        """Every Mini-C keyword must be in the lookup table."""
        for kw in ("int", "float", "char", "void", "if", "else",
                   "while", "for", "return", "print"):
            assert kw in KEYWORDS, f"Keyword '{kw}' missing from KEYWORDS"

    def test_sync_tokens_nonempty(self):
        assert TT.SEMI in SYNC_TOKENS
        assert TT.RBRACE in SYNC_TOKENS
        assert TT.IF in SYNC_TOKENS


class TestToken:
    def test_basic_construction(self):
        tok = Token(type=TT.INT, text="int", line=1, col=1)
        assert tok.type == TT.INT
        assert tok.text == "int"
        assert tok.synthetic is False

    def test_synthetic_flag(self):
        tok = Token(type=TT.SEMI, text=";", line=0, col=0, synthetic=True)
        assert tok.synthetic is True

    def test_equality_ignores_index_and_synthetic(self):
        a = Token(type=TT.SEMI, text=";", line=1, col=5, index=3, synthetic=False)
        b = Token(type=TT.SEMI, text=";", line=2, col=1, index=7, synthetic=True)
        assert a == b

    def test_is_keyword(self):
        assert Token(TT.INT, "int", 1, 1).is_keyword()
        assert not Token(TT.IDENT, "foo", 1, 1).is_keyword()

    def test_is_literal(self):
        assert Token(TT.INT_LIT, "42", 1, 1).is_literal()
        assert not Token(TT.IDENT, "foo", 1, 1).is_literal()

    def test_is_sync(self):
        assert Token(TT.SEMI, ";", 1, 1).is_sync()
        assert not Token(TT.PLUS, "+", 1, 1).is_sync()

    def test_is_type_spec(self):
        for tt in (TT.INT, TT.FLOAT, TT.CHAR, TT.VOID):
            assert Token(tt, tt.value, 1, 1).is_type_spec()
        assert not Token(TT.IDENT, "foo", 1, 1).is_type_spec()


class TestMakePlaceholder:
    def test_ident_placeholder(self):
        tok = make_placeholder(TT.IDENT)
        assert tok.type == TT.IDENT
        assert tok.text == "__id__"
        assert tok.synthetic is True

    def test_int_lit_placeholder(self):
        tok = make_placeholder(TT.INT_LIT)
        assert tok.text == "0"

    def test_float_lit_placeholder(self):
        tok = make_placeholder(TT.FLOAT_LIT)
        assert tok.text == "0.0"

    def test_char_lit_placeholder(self):
        tok = make_placeholder(TT.CHAR_LIT)
        assert tok.text == "'a'"

    def test_other_falls_back_to_value(self):
        tok = make_placeholder(TT.SEMI)
        assert tok.text == ";"


class TestConfig:
    def test_default_config_importable(self):
        from syntaxrecover.config import Config, DEFAULT_CONFIG
        cfg = DEFAULT_CONFIG
        assert cfg.K_min == 3
        assert cfg.P_max == 20
        assert cfg.alpha == 1.0
        assert cfg.beta == 3.0
        assert cfg.gamma == 1.0
        assert cfg.lambda_ == 2.0
        assert cfg.max_errors == 100
        assert cfg.no_sync is False

    def test_config_to_dict(self):
        from syntaxrecover.config import Config
        d = Config().to_dict()
        assert "K_min" in d
        assert "alpha" in d

    def test_config_override(self):
        from syntaxrecover.config import Config
        cfg = Config(K_min=5, beta=4.0)
        assert cfg.K_min == 5
        assert cfg.beta == 4.0
