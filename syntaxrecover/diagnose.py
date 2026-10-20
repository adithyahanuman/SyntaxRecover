"""
diagnose.py — Error Diagnoser for SyntaxRecover.

Builds structured ErrorEvent instances upon feed() failure at token index i:
- Offending token and preceding token
- 1-based source coordinates (line, col)
- Sorted expected terminal set from the parser state
- Syntax context description
- Pretty-printed source line snippet with directional caret
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from syntaxrecover.tokens import TT, Token
from syntaxrecover.parser_adapter import ParserState


@dataclass
class ErrorEvent:
    """Diagnostic details captured at the point of syntax failure.

    Attributes
    ----------
    index:
        0-based index of offending token in the token stream.
    token:
        The token that the parser failed to accept.
    prev_token:
        The preceding token in the stream, if index > 0.
    line:
        1-based source line of the offending token.
    col:
        1-based source column of the offending token.
    expected:
        Sorted list of terminal strings acceptable by the grammar at this point.
    context:
        Short descriptive string about the surrounding syntax construct.
    source_line:
        The literal line of source code containing the error.
    caret_line:
        A formatted string with a '^' indicating the offending column.
    """
    index:       int
    token:       Token
    prev_token:  Optional[Token]
    line:        int
    col:         int
    expected:    List[str]
    context:     str = ""
    source_line: str = ""
    caret_line:  str = ""

    def format_diagnostic(self) -> str:
        """Render a rustc/clang style diagnostic snippet."""
        exp_str = ", ".join(f"'{e}'" for e in self.expected[:8])
        if len(self.expected) > 8:
            exp_str += f", ... (+{len(self.expected) - 8} more)"

        tok_desc = f"'{self.token.text}'" if self.token.type != TT.EOF else "end of file"
        lines = [
            f"error[syntax]: {self.line}:{self.col}: unexpected {tok_desc}, expected one of: {exp_str}"
        ]
        if self.source_line:
            prefix = f"{self.line:4d} | "
            lines.append(f"{prefix}{self.source_line}")
            lines.append(self.caret_line)
        return "\n".join(lines)


def render_caret(line_text: str, line_no: int, col: int) -> Tuple[str, str]:
    """Build source snippet and caret pointer matching line and col."""
    prefix = f"{line_no:4d} | "
    indent = len(prefix) + max(0, col - 1)
    caret = (" " * indent) + "^"
    return line_text, caret


def infer_context(prev_token: Optional[Token], expected: List[str]) -> str:
    """Infer human-friendly context phrase from previous token and expected set."""
    if prev_token is None:
        return "at start of program"

    if prev_token.type in (TT.INT, TT.FLOAT, TT.CHAR, TT.VOID):
        return "in declaration after type specifier"
    if prev_token.type == TT.IDENT:
        if ";" in expected:
            return "in statement or declaration after identifier"
        if "(" in expected:
            return "after function or variable name"
    if prev_token.type in (TT.INT_LIT, TT.FLOAT_LIT, TT.STRING_LIT, TT.CHAR_LIT):
        return "after literal expression"
    if prev_token.type == TT.EQ:
        return "in variable initializer"
    if prev_token.type == TT.LPAREN:
        return "inside parentheses"
    if prev_token.type == TT.RPAREN:
        return "after closing parenthesis"
    if prev_token.type == TT.LBRACE:
        return "at beginning of block"
    if prev_token.type == TT.SEMI:
        return "after statement semicolon"

    return "in statement"


def diagnose(
    state: ParserState,
    tokens: List[Token],
    error_index: int,
    source: Optional[str] = None
) -> ErrorEvent:
    """Analyze the parser state at error_index and construct an ErrorEvent."""
    if error_index >= len(tokens):
        # Fallback to EOF
        tok = tokens[-1] if tokens else Token(TT.EOF, "", 1, 1)
        prev_tok = tokens[-2] if len(tokens) >= 2 else None
    else:
        tok = tokens[error_index]
        prev_tok = tokens[error_index - 1] if error_index > 0 else None

    line = tok.line
    col = tok.col
    expected_list = sorted(list(state.expected()))
    context_desc = infer_context(prev_tok, expected_list)

    src_line = ""
    caret = ""
    if source is not None:
        lines = source.splitlines()
        if 1 <= line <= len(lines):
            raw_line = lines[line - 1]
            src_line, caret = render_caret(raw_line, line, col)

    return ErrorEvent(
        index=error_index,
        token=tok,
        prev_token=prev_tok,
        line=line,
        col=col,
        expected=expected_list,
        context=context_desc,
        source_line=src_line,
        caret_line=caret,
    )
