"""
ast_nodes.py — Abstract Syntax Tree node definitions for Mini-C.

Nodes are plain dataclasses.  The ``synthetic`` flag is propagated from the
Token that triggered creation of the node; downstream tools (pretty-printer,
evaluator, code-gen) can use it to distinguish source-derived structure from
repair-inserted structure.

Design principle: keep nodes *dumb* (no methods beyond __repr__).  All
traversal and analysis live in visitor modules.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Union


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    """Abstract base for every AST node.

    Attributes
    ----------
    line, col:
        Source position of the first token that produced this node.
    synthetic:
        True when the node was created from a token inserted by the
        recovery engine (not present in the original source).
    """
    line:      int  = field(default=0, compare=False, repr=False)
    col:       int  = field(default=0, compare=False, repr=False)
    synthetic: bool = field(default=False, compare=False, repr=False)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    """Root node.  ``declarations`` is a list of FuncDef | VarDecl."""
    declarations: List[ASTNode] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Declarations
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TypeSpec(ASTNode):
    """int | float | char | void"""
    name: str = ""


@dataclass
class Declarator(ASTNode):
    """IDENT [ '=' expr ]"""
    name:  str              = ""
    init:  Optional[ASTNode] = None


@dataclass
class VarDecl(ASTNode):
    """typeSpec declarator { ',' declarator } ';'"""
    type_spec:   TypeSpec        = field(default_factory=TypeSpec)
    declarators: List[Declarator] = field(default_factory=list)


@dataclass
class Param(ASTNode):
    """typeSpec IDENT"""
    type_spec: TypeSpec = field(default_factory=TypeSpec)
    name:      str      = ""


@dataclass
class FuncDef(ASTNode):
    """typeSpec IDENT '(' [ paramList ] ')' block"""
    return_type: TypeSpec       = field(default_factory=TypeSpec)
    name:        str            = ""
    params:      List[Param]    = field(default_factory=list)
    body:        "Block"        = field(default_factory=lambda: Block())


# ─────────────────────────────────────────────────────────────────────────────
# Statements
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Block(ASTNode):
    """'{' { blockItem } '}'"""
    items: List[ASTNode] = field(default_factory=list)


@dataclass
class ExprStmt(ASTNode):
    """expr ';'"""
    expr: Optional[ASTNode] = None


@dataclass
class IfStmt(ASTNode):
    """'if' '(' expr ')' statement [ 'else' statement ]"""
    condition:   ASTNode          = field(default_factory=ASTNode)
    then_branch: ASTNode          = field(default_factory=ASTNode)
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode = field(default_factory=ASTNode)
    body:      ASTNode = field(default_factory=ASTNode)


@dataclass
class ForStmt(ASTNode):
    """'for' '(' [ forInit ] ';' [ expr ] ';' [ expr ] ')' statement"""
    init:      Optional[ASTNode] = None
    condition: Optional[ASTNode] = None
    update:    Optional[ASTNode] = None
    body:      ASTNode           = field(default_factory=ASTNode)


@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None


@dataclass
class PrintStmt(ASTNode):
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class EmptyStmt(ASTNode):
    """Bare ';'"""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Expressions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Assign(ASTNode):
    """IDENT '=' assignment"""
    name:  str     = ""
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class BinaryOp(ASTNode):
    """left op right"""
    op:    str     = ""
    left:  ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)


@dataclass
class UnaryOp(ASTNode):
    """( '!' | '-' ) operand"""
    op:      str     = ""
    operand: ASTNode = field(default_factory=ASTNode)


@dataclass
class Call(ASTNode):
    """IDENT '(' [ args ] ')'"""
    name: str            = ""
    args: List[ASTNode]  = field(default_factory=list)


@dataclass
class Ident(ASTNode):
    name: str = ""


@dataclass
class IntLit(ASTNode):
    value: int = 0


@dataclass
class FloatLit(ASTNode):
    value: float = 0.0


@dataclass
class CharLit(ASTNode):
    value: str = ""


@dataclass
class StringLit(ASTNode):
    value: str = ""
