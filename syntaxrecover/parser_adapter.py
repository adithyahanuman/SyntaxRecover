"""
parser_adapter.py — Parser abstraction and Lark LALR interactive adapter.

Hides the underlying parser behind the ParserState interface:
- clone(): create an isolated sandbox state
- feed(token): step parser forward by one token; returns False if error without mutating state
- expected(): set of canonical terminal strings acceptable right now
- at_accept(): can the input cleanly terminate (EOF accepted) now?
- unwind_to_sync(tok): unwind state stack until sync token is accepted
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Protocol, Set, List, Optional, Any, Tuple
from lark import Lark, Token as LarkToken, Tree, UnexpectedToken

from syntaxrecover.tokens import TT, Token
from syntaxrecover import ast_nodes as ast


# Terminal mappings: Lexer TT -> Lark terminal name
TT_TO_LARK: dict[TT, str] = {
    TT.INT:        "TYPE_INT",
    TT.FLOAT:      "TYPE_FLOAT",
    TT.CHAR:       "TYPE_CHAR",
    TT.VOID:       "TYPE_VOID",
    TT.IF:         "IF",
    TT.ELSE:       "ELSE",
    TT.WHILE:      "WHILE",
    TT.FOR:        "FOR",
    TT.RETURN:     "RETURN",
    TT.PRINT:      "PRINT",
    TT.IDENT:      "IDENT",
    TT.INT_LIT:    "INT_LIT",
    TT.FLOAT_LIT:  "FLOAT_LIT",
    TT.CHAR_LIT:   "CHAR_LIT",
    TT.STRING_LIT: "STRING_LIT",
    TT.EQ:         "ASSIGN",
    TT.EQEQ:       "EQ_OP",
    TT.NEQ:        "EQ_OP",
    TT.LT:         "REL_OP",
    TT.LTEQ:       "REL_OP",
    TT.GT:         "REL_OP",
    TT.GTEQ:       "REL_OP",
    TT.PLUS:       "ADD_OP",
    TT.MINUS:      "ADD_OP",
    TT.STAR:       "MUL_OP",
    TT.SLASH:      "MUL_OP",
    TT.PERCENT:    "MUL_OP",
    TT.BANG:       "UNARY_OP",
    TT.AND:        "AND",
    TT.OR:         "OR",
    TT.LPAREN:     "LPAREN",
    TT.RPAREN:     "RPAREN",
    TT.LBRACE:     "LBRACE",
    TT.RBRACE:     "RBRACE",
    TT.SEMI:       "SEMI",
    TT.COMMA:      "COMMA",
    TT.EOF:        "$END",
}

# Reverse mapping: Lark terminal name -> Set of canonical terminal strings
LARK_TO_EXPECTED: dict[str, set[str]] = {
    "TYPE_INT":    {"int"},
    "TYPE_FLOAT":  {"float"},
    "TYPE_CHAR":   {"char"},
    "TYPE_VOID":   {"void"},
    "IF":          {"if"},
    "ELSE":        {"else"},
    "WHILE":       {"while"},
    "FOR":         {"for"},
    "RETURN":      {"return"},
    "PRINT":       {"print"},
    "IDENT":       {"IDENT"},
    "INT_LIT":     {"INT_LIT"},
    "FLOAT_LIT":   {"FLOAT_LIT"},
    "CHAR_LIT":    {"CHAR_LIT"},
    "STRING_LIT":  {"STRING_LIT"},
    "ASSIGN":      {"="},
    "EQ_OP":       {"==", "!="},
    "REL_OP":      {"<", "<=", ">", ">="},
    "ADD_OP":      {"+", "-"},
    "MUL_OP":      {"*", "/", "%"},
    "UNARY_OP":    {"!"},
    "AND":         {"&&"},
    "OR":          {"||"},
    "LPAREN":      {"("},
    "RPAREN":      {")"},
    "LBRACE":      {"{"},
    "RBRACE":      {"}"},
    "SEMI":        {";"},
    "COMMA":       {","},
    "$END":        {"EOF"},
}


class ParserState(Protocol):
    """Abstract interface hiding parser mechanics from recovery engine."""

    def clone(self) -> "ParserState":
        """Cheap snapshot for sandboxing."""
        ...

    def feed(self, tok: Token) -> bool:
        """True = accepted, False = error (state unchanged)."""
        ...

    def expected(self) -> set[str]:
        """Terminals acceptable right now."""
        ...

    def at_accept(self) -> bool:
        """Can EOF be accepted now?"""
        ...

    def unwind_to_sync(self, sync_tok: Token) -> bool:
        """Unwind state until sync_tok is acceptable."""
        ...


class LarkParserState:
    """Concrete implementation of ParserState wrapping Lark's interactive parser."""

    def __init__(self, ip: Any, lark_instance: Lark) -> None:
        self.ip = ip
        self.lark_instance = lark_instance

    def clone(self) -> "LarkParserState":
        """Snapshot the interactive parser state. Feeding the clone does not
        mutate self."""
        return LarkParserState(self.ip.copy(), self.lark_instance)

    def _lark_terminal(self, tok: Token) -> Optional[str]:
        return TT_TO_LARK.get(tok.type)

    def expected(self) -> set[str]:
        """Return the set of user-level terminal strings currently acceptable."""
        terminals = self.ip.accepts()
        exp: set[str] = set()
        for term in terminals:
            if term in LARK_TO_EXPECTED:
                exp.update(LARK_TO_EXPECTED[term])
        return exp

    def at_accept(self) -> bool:
        """Returns True if the parser can accept EOF in its current state."""
        return "$END" in self.ip.accepts()

    def feed(self, tok: Token) -> bool:
        """Attempt to consume token. Return True if accepted. If rejected,
        leave state unchanged and return False."""
        lark_term = self._lark_terminal(tok)
        if not lark_term:
            return False

        # If not acceptable according to LALR table, fail safely
        if lark_term not in self.ip.accepts():
            return False

        try:
            self.ip.feed_token(LarkToken(lark_term, tok.text))
            return True
        except (UnexpectedToken, Exception):
            return False

    def unwind_to_sync(self, sync_tok: Token) -> bool:
        """Unwind state stack until sync_tok can be accepted."""
        lark_term = self._lark_terminal(sync_tok)
        if not lark_term:
            return False

        # If already acceptable, we're done
        if lark_term in self.ip.accepts():
            return True

        # Unwind state stack iteratively
        state_stack = self.ip.parser_state.state_stack
        val_stack = self.ip.parser_state.value_stack
        while len(state_stack) > 1:
            state_stack.pop()
            if val_stack:
                val_stack.pop()
            if lark_term in self.ip.accepts():
                return True

        return False

    def finish_tree(self) -> Any:
        """Finish the interactive parse and return the resulting parse tree."""
        if "$END" in self.ip.accepts():
            self.ip.feed_token(LarkToken("$END", ""))
        return self.ip.as_immutable()


class ParserAdapter:
    """Main driver for parsing Mini-C tokens with Lark."""

    _cached_lark: Optional[Lark] = None

    def __init__(self, grammar_path: Optional[str] = None) -> None:
        if grammar_path is None:
            # Locate grammar/minic.lark relative to this file
            root = Path(__file__).resolve().parent.parent
            grammar_path = str(root / "grammar" / "minic.lark")

        if ParserAdapter._cached_lark is None:
            ParserAdapter._cached_lark = Lark.open(
                grammar_path,
                parser="lalr",
                start="program"
            )
        self.lark = ParserAdapter._cached_lark

    def initial_state(self) -> LarkParserState:
        """Create a fresh ParserState positioned at start of input."""
        ip = self.lark.parse_interactive("")
        return LarkParserState(ip, self.lark)

    def parse_source(self, source: str) -> Tree:
        """Directly parse a string source code into a parse tree."""
        return self.lark.parse(source)

    def parse_tokens(self, tokens: List[Token]) -> Tuple[bool, Optional[Tree], Optional[int]]:
        """Feed a sequence of tokens into a fresh parser state.

        Returns (success: bool, tree: Optional[Tree], error_index: Optional[int]).
        """
        state = self.initial_state()
        for i, tok in enumerate(tokens):
            if not state.feed(tok):
                return False, None, i
        return True, state.finish_tree(), None


def create_parser_adapter() -> ParserAdapter:
    """Helper factory for ParserAdapter."""
    return ParserAdapter()
