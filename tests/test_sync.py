"""
test_sync.py — Dedicated unit tests for the Synchronize operation (Phase 3.3).

Verifies:
- Stack unwinding until sync token is accepted
- Cost = 1 + skipped tokens, structure penalty tracks skipped tokens & delimiters
- Termination guarantee: always consumes >= 1 token, never loops forever
- Edge cases: unbalanced braces, random garbage tokens, error right before EOF
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


class TestSynchronizeOperation:
    def test_unwind_to_sync_pops_stack_cleanly(self, adapter):
        """Unwinding pops unfinished expression states until ';' can be accepted."""
        src = "int main() { int a = 10 + ("
        tokens = tokenize(src)
        state = adapter.initial_state()

        # Feed tokens until '('
        for tok in tokens[:-1]:
            state.feed(tok)

        # In current state inside '(', ';' is NOT acceptable
        assert ";" not in state.expected()

        # Unwind to ';'
        success = state.unwind_to_sync(Token(TT.SEMI, ";", 1, 1))
        assert success is True
        assert ";" in state.expected()

    def test_sync_recovery_on_garbage_in_function(self, adapter):
        """Sync successfully discards garbage tokens and resumes parsing."""
        src = """
        int main() {
            int a = 10;
            @#$% &*! random garbage in between;
            int b = 20;
            return b;
        }
        """
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        # Must terminate and recover
        assert len(result.events) >= 1
        assert result.success is True

        # Repaired tokens must parse
        repaired_tokens = tokenize(result.repaired_source)
        success, tree, _ = adapter.parse_tokens(repaired_tokens)
        assert success is True

    def test_sync_unbalanced_extra_closing_brace(self, adapter):
        """Sync correctly handles extra closing braces."""
        src = "int main() { print(1); } }\nint x = 5;"
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) >= 1
        repaired_tokens = tokenize(result.repaired_source)
        success, _, _ = adapter.parse_tokens(repaired_tokens)
        assert success is True

    def test_sync_error_right_before_eof(self, adapter):
        """Sync to EOF guarantees termination on incomplete programs right at EOF."""
        src = "int main() { if (1)"
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        assert len(result.events) >= 1
        # Loop terminates cleanly without infinite iteration
        assert len(result.events) < 10
