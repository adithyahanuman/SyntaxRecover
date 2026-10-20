"""
test_end_to_end.py — End-to-end integration tests for SyntaxRecover.

Tests complete recovery loop on multiple broken programs:
1. Missing semicolon (slide example)
2. Missing closing parenthesis
3. Multiple sequential syntax errors
4. Verifies that every repaired program successfully parses!
"""

import pytest
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.cli import recover_all


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestEndToEndRecovery:
    def test_slide_example_end_to_end(self, adapter):
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) == 1
        ev = result.events[0]
        assert ev.unexpected == "if"
        assert ";" in ev.expected
        assert "insert ';'" in result.repaired_source or ";" in result.repaired_source

        # Verification: Repaired source code must parse cleanly!
        repaired_tokens = tokenize(result.repaired_source)
        success, tree, err = adapter.parse_tokens(repaired_tokens)
        assert success is True
        assert err is None
        assert tree is not None

    def test_missing_parenthesis_end_to_end(self, adapter):
        src = "int main() { int x = (3 + 4; return x; }"
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) >= 1
        repaired_tokens = tokenize(result.repaired_source)
        success, tree, err = adapter.parse_tokens(repaired_tokens)
        assert success is True
        assert err is None

    def test_multi_error_end_to_end(self, adapter):
        src = """
        int main() {
            int a = 10 if (a > 5) {
                print(a);
            }
            int b = (1 + 2;
            return 0;
        }
        """
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        # Diagnosed both errors in a single pass without crashing or resetting
        assert len(result.events) == 2

        # Final repaired code parses cleanly!
        repaired_tokens = tokenize(result.repaired_source)
        success, tree, err = adapter.parse_tokens(repaired_tokens)
        assert success is True
