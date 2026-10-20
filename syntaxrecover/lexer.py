"""
lexer.py — Hand-written scanner for Mini-C.

Produces a flat List[Token] ending with an EOF token, allowing random-access,
lookahead, backtracking, and token stream mutations by the recovery controller.
"""

from __future__ import annotations
from typing import List, Optional
from syntaxrecover.tokens import TT, Token, KEYWORDS


class LexerError(Exception):
    """Raised only for unrecoverable lexer internal faults."""
    pass


class Lexer:
    """Hand-written scanner for Mini-C.

    Attributes
    ----------
    source:
        The full source string being tokenized.
    pos:
        Current character index in source.
    line:
        1-based line number.
    col:
        1-based column number.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return ""

    def _advance(self) -> str:
        if self.pos >= self.length:
            return ""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> Optional[Token]:
        """Skip whitespace and comments. If an unterminated comment is found at
        EOF, return an ILLEGAL token representing it without crashing."""
        while self.pos < self.length:
            ch = self._peek()

            # Whitespace
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
                continue

            # Comments
            if ch == "/" and self._peek(1) == "/":
                # Line comment: skip until newline or EOF
                self._advance()
                self._advance()
                while self.pos < self.length and self._peek() != "\n":
                    self._advance()
                continue

            if ch == "/" and self._peek(1) == "*":
                # Block comment: skip until */ or EOF
                start_line, start_col = self.line, self.col
                self._advance()
                self._advance()
                closed = False
                while self.pos < self.length:
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance()
                        self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    # Unterminated block comment -> emit ILLEGAL token so lexer never crashes
                    return Token(
                        type=TT.ILLEGAL,
                        text="/*",
                        line=start_line,
                        col=start_col,
                    )
                continue

            break
        return None

    def _scan_number(self) -> Token:
        start_pos = self.pos
        start_line, start_col = self.line, self.col
        is_float = False

        while self.pos < self.length and self._peek().isdigit():
            self._advance()

        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()  # consume '.'
            while self.pos < self.length and self._peek().isdigit():
                self._advance()

        text = self.source[start_pos:self.pos]
        tt = TT.FLOAT_LIT if is_float else TT.INT_LIT
        return Token(type=tt, text=text, line=start_line, col=start_col)

    def _scan_identifier_or_keyword(self) -> Token:
        start_pos = self.pos
        start_line, start_col = self.line, self.col

        while self.pos < self.length:
            ch = self._peek()
            if ch.isalnum() or ch == "_":
                self._advance()
            else:
                break

        text = self.source[start_pos:self.pos]
        tt = KEYWORDS.get(text, TT.IDENT)
        return Token(type=tt, text=text, line=start_line, col=start_col)

    def _scan_string(self) -> Token:
        start_line, start_col = self.line, self.col
        self._advance()  # consume leading "
        chars: list[str] = ['"']

        closed = False
        while self.pos < self.length:
            ch = self._peek()
            if ch == '"':
                chars.append(self._advance())
                closed = True
                break
            elif ch == "\n":
                # Unterminated string on current line
                break
            elif ch == "\\":
                chars.append(self._advance())
                if self.pos < self.length:
                    chars.append(self._advance())
            else:
                chars.append(self._advance())

        text = "".join(chars)
        tt = TT.STRING_LIT if closed else TT.ILLEGAL
        return Token(type=tt, text=text, line=start_line, col=start_col)

    def _scan_char(self) -> Token:
        start_line, start_col = self.line, self.col
        self._advance()  # consume leading '
        chars: list[str] = ["'"]

        closed = False
        while self.pos < self.length:
            ch = self._peek()
            if ch == "'":
                chars.append(self._advance())
                closed = True
                break
            elif ch == "\n":
                break
            elif ch == "\\":
                chars.append(self._advance())
                if self.pos < self.length:
                    chars.append(self._advance())
            else:
                chars.append(self._advance())

        text = "".join(chars)
        tt = TT.CHAR_LIT if (closed and len(text) >= 3) else TT.ILLEGAL
        return Token(type=tt, text=text, line=start_line, col=start_col)

    def tokenize(self) -> List[Token]:
        """Tokenize the entire source string into a List[Token] ending with EOF."""
        tokens: List[Token] = []

        while self.pos < self.length:
            err_tok = self._skip_whitespace_and_comments()
            if err_tok:
                err_tok.index = len(tokens)
                tokens.append(err_tok)

            if self.pos >= self.length:
                break

            ch = self._peek()
            cur_line, cur_col = self.line, self.col

            # Identifier or Keyword
            if ch.isalpha() or ch == "_":
                tok = self._scan_identifier_or_keyword()
                tok.index = len(tokens)
                tokens.append(tok)
                continue

            # Number literal (Integer or Float)
            if ch.isdigit():
                tok = self._scan_number()
                tok.index = len(tokens)
                tokens.append(tok)
                continue

            # String literal
            if ch == '"':
                tok = self._scan_string()
                tok.index = len(tokens)
                tokens.append(tok)
                continue

            # Character literal
            if ch == "'":
                tok = self._scan_char()
                tok.index = len(tokens)
                tokens.append(tok)
                continue

            # Two-character operators
            two_chars = self.source[self.pos:self.pos + 2]
            two_char_map = {
                "==": TT.EQEQ,
                "!=": TT.NEQ,
                "<=": TT.LTEQ,
                ">=": TT.GTEQ,
                "&&": TT.AND,
                "||": TT.OR,
            }
            if two_chars in two_char_map:
                self._advance()
                self._advance()
                tokens.append(Token(
                    type=two_char_map[two_chars],
                    text=two_chars,
                    line=cur_line,
                    col=cur_col,
                    index=len(tokens),
                ))
                continue

            # Single-character operators and delimiters
            single_char_map = {
                "+": TT.PLUS,
                "-": TT.MINUS,
                "*": TT.STAR,
                "/": TT.SLASH,
                "%": TT.PERCENT,
                "=": TT.EQ,
                "<": TT.LT,
                ">": TT.GT,
                "!": TT.BANG,
                "(": TT.LPAREN,
                ")": TT.RPAREN,
                "{": TT.LBRACE,
                "}": TT.RBRACE,
                "[": TT.LBRACKET,
                "]": TT.RBRACKET,
                ";": TT.SEMI,
                ",": TT.COMMA,
                ".": TT.DOT,
            }
            if ch in single_char_map:
                self._advance()
                tokens.append(Token(
                    type=single_char_map[ch],
                    text=ch,
                    line=cur_line,
                    col=cur_col,
                    index=len(tokens),
                ))
                continue

            # Unknown character -> ILLEGAL token (never crash)
            bad_ch = self._advance()
            tokens.append(Token(
                type=TT.ILLEGAL,
                text=bad_ch,
                line=cur_line,
                col=cur_col,
                index=len(tokens),
            ))

        # Append terminal EOF token
        tokens.append(Token(
            type=TT.EOF,
            text="",
            line=self.line,
            col=self.col,
            index=len(tokens),
        ))

        return tokens


def tokenize(source: str) -> List[Token]:
    """Helper function to tokenize source string."""
    return Lexer(source).tokenize()
