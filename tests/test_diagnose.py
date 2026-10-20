"""
test_diagnose.py — Unit tests for Error Diagnoser.

Verifies ErrorEvent creation, unexpected token reporting, expected set sorting,
EOF error handling, and caret formatting across multiple error types.
"""

import pytest
from syntaxrecover.tokens import TT
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.diagnose import diagnose


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


class TestDiagnose:
    def test_slide_example_diagnosis(self, adapter):
        src = "int main() {\n    int a = 10 if (a > 5) { print(a); }\n}"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        assert err_idx is not None
        assert tokens[err_idx].type == TT.IF
        assert tokens[err_idx].line == 2

        event = diagnose(state, tokens, err_idx, source=src)

        assert event.index == err_idx
        assert event.token.type == TT.IF
        assert event.token.text == "if"
        assert event.prev_token is not None
        assert event.prev_token.type == TT.INT_LIT
        assert event.prev_token.text == "10"
        assert event.line == 2
        assert ";" in event.expected
        assert "if" not in event.expected
        assert "after literal expression" in event.context

        # Caret pointer test
        diag_str = event.format_diagnostic()
        assert "error[syntax]" in diag_str
        assert "unexpected 'if'" in diag_str
        assert "^" in event.caret_line

    def test_missing_closing_paren_diagnosis(self, adapter):
        src = "int main() {\n    int x = (3 + 4;\n    return x;\n}"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        assert err_idx is not None
        event = diagnose(state, tokens, err_idx, source=src)

        assert event.token.type == TT.SEMI
        assert event.token.text == ";"
        assert ")" in event.expected

    def test_unexpected_eof_diagnosis(self, adapter):
        src = "int main() {"
        tokens = tokenize(src)
        state = adapter.initial_state()

        err_idx = None
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                err_idx = i
                break

        assert err_idx is not None
        assert tokens[err_idx].type == TT.EOF

        event = diagnose(state, tokens, err_idx, source=src)
        assert event.token.type == TT.EOF
        assert "}" in event.expected
        assert "end of file" in event.format_diagnostic()
