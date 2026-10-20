"""
test_commit.py — Unit tests for Commit, Resume, and Cascade Guard (Phase 3.4).

Verifies:
- Synthetic token tagging
- Parser loop never resets between errors
- Termination guard on recursive/repeating errors
- Cascade guard: errors within suppression window marked possibly_secondary
- Multi-error recovery: files with 2, 3, and 5 errors produce 2, 3, and 5 independent events
"""

import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.lexer import tokenize
from syntaxrecover.config import Config
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.cli import recover_all


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestCommitAndCascadeGuard:
    def test_synthetic_token_tagging(self):
        """Inserted repair tokens must be marked synthetic=True."""
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        # The inserted semicolon must have synthetic=True
        synthetic_tokens = [t for t in result.tokens if t.synthetic]
        assert len(synthetic_tokens) >= 1
        assert any(t.text == ";" for t in synthetic_tokens)

    def test_two_error_file_diagnosed_in_one_run(self, adapter):
        """File with 2 separated syntax errors yields exactly 2 events."""
        src = """
        int main() {
            int a = 10 if (a > 5) { print(a); }
            int b = (1 + 2;
            return 0;
        }
        """
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) == 2
        assert result.events[0].unexpected == "if"
        assert result.events[1].unexpected == ";"

        repaired_tokens = tokenize(result.repaired_source)
        success, _, _ = adapter.parse_tokens(repaired_tokens)
        assert success is True

    def test_three_error_file_diagnosed_in_one_run(self, adapter):
        """File with 3 separated errors yields exactly 3 events."""
        src = """
        int f1() { int a = 10 if (1) { print(a); } return 0; }
        int f2() { int b = (2 + 3; return b; }
        int f3() { print(42) return 0; }
        """
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) == 3
        repaired_tokens = tokenize(result.repaired_source)
        success, _, _ = adapter.parse_tokens(repaired_tokens)
        assert success is True

    def test_five_error_file_diagnosed_in_one_run(self, adapter):
        """File with 5 separated errors yields 5 events and valid final program."""
        src = """
        int f1() { int a = 10 if (1) { print(a); } return 0; }
        int f2() { int b = (2 + 3; return b; }
        int f3() { print(1) return 0; }
        int f4() { int c = 5 if (c) { print(c); } return 0; }
        int f5() { int d = (4 + 5; return d; }
        """
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) == 5
        repaired_tokens = tokenize(result.repaired_source)
        success, _, _ = adapter.parse_tokens(repaired_tokens)
        assert success is True

    def test_cascade_guard_suppression_window(self):
        """Errors occurring immediately after a repair are tagged possibly_secondary."""
        # Two errors right next to each other
        src = "int main() { int a = 10 if ( { print(1); } }"
        tokens = tokenize(src)
        cfg = Config(suppression_window=5)
        result = recover_all(tokens, cfg=cfg, source=src)

        assert len(result.events) >= 2
        # Second error occurred within 5 tokens of first commit
        assert result.events[1].possibly_secondary is True

    def test_max_errors_safety_cap(self):
        """Recovery terminates when max_errors limit is reached."""
        # Infinitely malformed sequence
        tokens = [Token(TT.ILLEGAL, "@", 1, i, i) for i in range(50)]
        tokens.append(Token(TT.EOF, "", 1, 51, 50))

        cfg = Config(max_errors=5)
        result = recover_all(tokens, cfg=cfg)

        assert len(result.events) <= 5
