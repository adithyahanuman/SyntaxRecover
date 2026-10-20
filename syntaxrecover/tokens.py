"""
tokens.py — Token type definitions and the Token dataclass.

Every token produced by the lexer is an instance of Token.  The `synthetic`
flag is set to True on tokens that were *inserted* by the recovery engine so
that AST nodes built from them can be distinguished from source-derived nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


class TT(str, Enum):
    """Token Types.  Inherits str so that values can be compared with strings."""

    # ── Keywords ────────────────────────────────────────────────────────────
    INT     = "int"
    FLOAT   = "float"
    CHAR    = "char"
    VOID    = "void"
    IF      = "if"
    ELSE    = "else"
    WHILE   = "while"
    FOR     = "for"
    RETURN  = "return"
    PRINT   = "print"

    # ── Identifiers and literals ─────────────────────────────────────────────
    IDENT     = "IDENT"
    INT_LIT   = "INT_LIT"
    FLOAT_LIT = "FLOAT_LIT"
    CHAR_LIT  = "CHAR_LIT"
    STRING_LIT = "STRING_LIT"

    # ── Operators ────────────────────────────────────────────────────────────
    PLUS    = "+"
    MINUS   = "-"
    STAR    = "*"
    SLASH   = "/"
    PERCENT = "%"
    EQ      = "="
    EQEQ    = "=="
    NEQ     = "!="
    LT      = "<"
    LTEQ    = "<="
    GT      = ">"
    GTEQ    = ">="
    AND     = "&&"
    OR      = "||"
    BANG    = "!"

    # ── Delimiters ───────────────────────────────────────────────────────────
    LPAREN    = "("
    RPAREN    = ")"
    LBRACE    = "{"
    RBRACE    = "}"
    LBRACKET  = "["
    RBRACKET  = "]"
    SEMI      = ";"
    COMMA     = ","
    DOT       = "."

    # ── Special ──────────────────────────────────────────────────────────────
    EOF     = "EOF"
    ILLEGAL = "ILLEGAL"   # Unknown character — never crashes the pipeline


# ── Keyword lookup table ─────────────────────────────────────────────────────
KEYWORDS: dict[str, TT] = {
    "int":    TT.INT,
    "float":  TT.FLOAT,
    "char":   TT.CHAR,
    "void":   TT.VOID,
    "if":     TT.IF,
    "else":   TT.ELSE,
    "while":  TT.WHILE,
    "for":    TT.FOR,
    "return": TT.RETURN,
    "print":  TT.PRINT,
}

# Tokens that the Synchronize operation treats as safe landing points
SYNC_TOKENS: frozenset[TT] = frozenset({
    TT.SEMI,
    TT.RBRACE,
    TT.IF,
    TT.WHILE,
    TT.FOR,
    TT.RETURN,
    TT.INT,
    TT.FLOAT,
    TT.CHAR,
    TT.VOID,
})


@dataclass
class Token:
    """A single lexical unit.

    Attributes
    ----------
    type:
        One of the ``TT`` enum values.
    text:
        The literal source text of the token.
    line:
        1-based source line number.
    col:
        1-based source column number of the first character.
    index:
        0-based position in the flat token list produced by the lexer.
        Used for random access, backtrack windows, and repair indexing.
    synthetic:
        True when this token was *inserted* by the recovery engine (not
        present in the original source).  Propagated into AST nodes.
    """

    type:      TT
    text:      str
    line:      int
    col:       int
    index:     int = 0
    synthetic: bool = False

    # ── Convenience helpers ──────────────────────────────────────────────────

    def is_keyword(self) -> bool:
        return self.type in KEYWORDS.values()

    def is_literal(self) -> bool:
        return self.type in (TT.INT_LIT, TT.FLOAT_LIT, TT.CHAR_LIT, TT.STRING_LIT)

    def is_sync(self) -> bool:
        return self.type in SYNC_TOKENS

    def is_type_spec(self) -> bool:
        return self.type in (TT.INT, TT.FLOAT, TT.CHAR, TT.VOID)

    def __repr__(self) -> str:
        synth = " [synthetic]" if self.synthetic else ""
        return f"Token({self.type!r}, {self.text!r}, {self.line}:{self.col}{synth})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return NotImplemented
        # Equality ignores index and synthetic so that a repaired token
        # stream can be compared to an original one for test assertions.
        return self.type == other.type and self.text == other.text

    def __hash__(self) -> int:
        return hash((self.type, self.text))


# ── Placeholder tokens inserted by the candidate engine ─────────────────────
def make_placeholder(tt: TT, at_line: int = 0, at_col: int = 0) -> Token:
    """Create a synthetic placeholder token of the given type.

    The *text* is chosen to be a valid, minimal representative of the type:
    ``__id__`` for IDENT, ``0`` for INT_LIT, ``0.0`` for FLOAT_LIT, etc.
    """
    _defaults: dict[TT, str] = {
        TT.IDENT:      "__id__",
        TT.INT_LIT:    "0",
        TT.FLOAT_LIT:  "0.0",
        TT.CHAR_LIT:   "'a'",
        TT.STRING_LIT: '""',
    }
    text = _defaults.get(tt, tt.value)
    return Token(type=tt, text=text, line=at_line, col=at_col, synthetic=True)
