"""
test_parser.py — Comprehensive unit tests for ParserAdapter and LarkParserState.

Tests state isolation via clone(), feed() safety, expected set computation,
unwind_to_sync(), and parses valid/invalid Mini-C sample programs.
"""

import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import ParserAdapter, create_parser_adapter


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestParserStateIsolation:
    def test_clone_isolation(self, adapter):
        """Feeding a cloned state must not affect the original state."""
        state = adapter.initial_state()
        tok_int = Token(TT.INT, "int", 1, 1)

        # Clone at initial state
        clone = state.clone()

        # Both start with identical expected sets
        assert state.expected() == clone.expected()
        assert "int" in state.expected()

        # Feed token to clone only
        assert clone.feed(tok_int) is True

        # Clone should now expect IDENT; original state must still expect int/types!
        assert "IDENT" in clone.expected()
        assert "int" not in clone.expected()
        assert "int" in state.expected()

    def test_feed_failure_does_not_mutate_state(self, adapter):
        """When feed() returns False, the parser state remains completely unmutated."""
        state = adapter.initial_state()
        bad_tok = Token(TT.SEMI, ";", 1, 1)

        expected_before = state.expected()
        success = state.feed(bad_tok)

        assert success is False
        assert state.expected() == expected_before

        # State can still accept valid token afterwards
        assert state.feed(Token(TT.INT, "int", 1, 1)) is True


class TestExpectedSets:
    def test_initial_expected_set(self, adapter):
        state = adapter.initial_state()
        exp = state.expected()
        assert {"int", "float", "char", "void", "EOF"}.issubset(exp)
        assert ";" not in exp

    def test_slide_example_expected_set(self, adapter):
        """After 'int main() { int a = 10', expected set must contain ';' and operators."""
        tokens = tokenize("int main() { int a = 10")
        state = adapter.initial_state()

        for tok in tokens[:-1]:  # exclude EOF
            assert state.feed(tok) is True

        exp = state.expected()
        assert ";" in exp
        assert "," in exp
        assert "+" in exp
        assert "==" in exp
        assert "if" not in exp  # 'if' is unexpected here!

    def test_after_if_paren_expected_set(self, adapter):
        """After 'int main() { if (', an expression is expected."""
        tokens = tokenize("int main() { if (")
        state = adapter.initial_state()

        for tok in tokens[:-1]:
            assert state.feed(tok) is True

        exp = state.expected()
        assert "IDENT" in exp
        assert "INT_LIT" in exp
        assert ")" not in exp  # condition cannot be empty


class TestAtAcceptAndUnwind:
    def test_at_accept_empty_program(self, adapter):
        state = adapter.initial_state()
        assert state.at_accept() is True  # an empty program (0 declarations) is valid

    def test_at_accept_complete_function(self, adapter):
        tokens = tokenize("int main() {}")
        state = adapter.initial_state()
        for tok in tokens[:-1]:
            assert state.feed(tok) is True
        assert state.at_accept() is True

    def test_unwind_to_sync(self, adapter):
        """Unwind parser stack to land at ';' during a stalled statement."""
        tokens = tokenize("int main() { int a =")
        state = adapter.initial_state()
        for tok in tokens[:-1]:
            assert state.feed(tok) is True

        # ';' is not acceptable right after '='
        assert ";" not in state.expected()

        # Unwind to ';'
        success = state.unwind_to_sync(Token(TT.SEMI, ";", 1, 20))
        assert success is True
        assert ";" in state.expected()


class TestValidPrograms:
    @pytest.mark.parametrize("src", [
        "int main() { return 0; }",
        "int a = 5; float b = 3.14;",
        "int max(int a, int b) { if (a > b) return a; else return b; }",
        "int main() { int i = 0; while (i < 10) { i = i + 1; } return 0; }",
        "int main() { int i; for (i = 0; i < 5; i = i + 1) { print(i); } return 0; }",
        "int main() { int x = (3 + 4) * 2 - 1; if (x > 10 && x < 20) print(x); return 0; }",
        "int add(int a, int b) { return a + b; } int main() { return add(1, 2); }",
    ])
    def test_valid_samples_parse(self, adapter, src):
        tokens = tokenize(src)
        success, tree, err_idx = adapter.parse_tokens(tokens)
        assert success is True
        assert err_idx is None
        assert tree is not None


class TestInvalidPrograms:
    def test_slide_sample_fails_at_if(self, adapter):
        tokens = tokenize("int main() { int a = 10 if (a > 5) { print(a); } }")
        success, _, err_idx = adapter.parse_tokens(tokens)
        assert success is False
        assert err_idx is not None
        assert tokens[err_idx].type == TT.IF

    def test_missing_closing_paren_fails_at_semi(self, adapter):
        tokens = tokenize("int main() { int x = (3 + 4; return 0; }")
        success, _, err_idx = adapter.parse_tokens(tokens)
        assert success is False
        assert err_idx is not None
        assert tokens[err_idx].type == TT.SEMI
