"""
test_lexer.py — Comprehensive unit tests for Mini-C Lexer.

Tests token types, positions, comments, edge cases, illegal chars, and sample programs.
"""

import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.lexer import Lexer, tokenize


class TestLexerBasics:
    def test_empty_source(self):
        tokens = tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type == TT.EOF
        assert tokens[0].line == 1
        assert tokens[0].col == 1
        assert tokens[0].index == 0

    def test_whitespace_only(self):
        tokens = tokenize("   \t  \r\n   ")
        assert len(tokens) == 1
        assert tokens[0].type == TT.EOF
        assert tokens[0].line == 2

    def test_all_keywords(self):
        src = "int float char void if else while for return print"
        tokens = tokenize(src)
        expected_types = [
            TT.INT, TT.FLOAT, TT.CHAR, TT.VOID, TT.IF,
            TT.ELSE, TT.WHILE, TT.FOR, TT.RETURN, TT.PRINT,
            TT.EOF
        ]
        assert [t.type for t in tokens] == expected_types
        assert all(t.is_keyword() for t in tokens[:-1])

    def test_identifiers(self):
        src = "x var1 _count my_var_2"
        tokens = tokenize(src)
        assert [t.type for t in tokens] == [TT.IDENT, TT.IDENT, TT.IDENT, TT.IDENT, TT.EOF]
        assert [t.text for t in tokens[:-1]] == ["x", "var1", "_count", "my_var_2"]

    def test_literals(self):
        src = "123 3.14 'a' \"hello world\""
        tokens = tokenize(src)
        assert [t.type for t in tokens] == [TT.INT_LIT, TT.FLOAT_LIT, TT.CHAR_LIT, TT.STRING_LIT, TT.EOF]
        assert tokens[0].text == "123"
        assert tokens[1].text == "3.14"
        assert tokens[2].text == "'a'"
        assert tokens[3].text == '"hello world"'

    def test_operators_and_delimiters(self):
        src = "+ - * / % = == != < <= > >= && || ! ( ) { } [ ] ; , ."
        tokens = tokenize(src)
        expected = [
            TT.PLUS, TT.MINUS, TT.STAR, TT.SLASH, TT.PERCENT,
            TT.EQ, TT.EQEQ, TT.NEQ, TT.LT, TT.LTEQ, TT.GT, TT.GTEQ,
            TT.AND, TT.OR, TT.BANG,
            TT.LPAREN, TT.RPAREN, TT.LBRACE, TT.RBRACE, TT.LBRACKET, TT.RBRACKET,
            TT.SEMI, TT.COMMA, TT.DOT,
            TT.EOF
        ]
        assert [t.type for t in tokens] == expected


class TestLexerPositions:
    def test_line_and_col_tracking(self):
        src = "int a = 10;\nfloat b = 3.14;"
        tokens = tokenize(src)

        # Line 1: int a = 10;
        assert tokens[0] == Token(TT.INT, "int", 1, 1)
        assert tokens[0].line == 1 and tokens[0].col == 1
        assert tokens[1].type == TT.IDENT and tokens[1].line == 1 and tokens[1].col == 5
        assert tokens[2].type == TT.EQ and tokens[2].line == 1 and tokens[2].col == 7
        assert tokens[3].type == TT.INT_LIT and tokens[3].line == 1 and tokens[3].col == 9
        assert tokens[4].type == TT.SEMI and tokens[4].line == 1 and tokens[4].col == 11

        # Line 2: float b = 3.14;
        assert tokens[5].type == TT.FLOAT and tokens[5].line == 2 and tokens[5].col == 1
        assert tokens[6].type == TT.IDENT and tokens[6].line == 2 and tokens[6].col == 7


class TestLexerComments:
    def test_single_line_comment(self):
        src = "int x; // this is a comment\nint y;"
        tokens = tokenize(src)
        types = [t.type for t in tokens]
        assert types == [TT.INT, TT.IDENT, TT.SEMI, TT.INT, TT.IDENT, TT.SEMI, TT.EOF]

    def test_block_comment(self):
        src = "int /* comment inside */ x = 5;"
        tokens = tokenize(src)
        types = [t.type for t in tokens]
        assert types == [TT.INT, TT.IDENT, TT.EQ, TT.INT_LIT, TT.SEMI, TT.EOF]

    def test_unterminated_block_comment(self):
        src = "int x; /* unclosed comment"
        tokens = tokenize(src)
        # Unterminated comment produces an ILLEGAL token without crashing
        assert any(t.type == TT.ILLEGAL for t in tokens)
        assert tokens[-1].type == TT.EOF


class TestLexerErrorTolerance:
    def test_illegal_characters_never_crash(self):
        src = "int @ $ # ~ x;"
        tokens = tokenize(src)
        illegal_tokens = [t for t in tokens if t.type == TT.ILLEGAL]
        assert len(illegal_tokens) == 4
        assert [t.text for t in illegal_tokens] == ["@", "$", "#", "~"]
        # Normal tokens are still recognized
        assert tokens[0].type == TT.INT
        assert tokens[-2].type == TT.SEMI
        assert tokens[-1].type == TT.EOF


class TestSlideExampleTokenization:
    def test_slide_sample(self):
        src = "int main() { int a = 10 if (a > 5) { print(a); } }"
        tokens = tokenize(src)
        types = [t.type for t in tokens]
        assert types == [
            TT.INT, TT.IDENT, TT.LPAREN, TT.RPAREN, TT.LBRACE,
            TT.INT, TT.IDENT, TT.EQ, TT.INT_LIT,
            TT.IF, TT.LPAREN, TT.IDENT, TT.GT, TT.INT_LIT, TT.RPAREN,
            TT.LBRACE, TT.PRINT, TT.LPAREN, TT.IDENT, TT.RPAREN, TT.SEMI,
            TT.RBRACE, TT.RBRACE, TT.EOF
        ]
        # Sequential indices
        for i, t in enumerate(tokens):
            assert t.index == i
