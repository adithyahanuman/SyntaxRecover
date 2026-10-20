# Mini-C Grammar Specification

*Reference document for SyntaxRecover — also the source of truth for the Lark grammar file.*

---

## EBNF Grammar

```ebnf
program      = { declaration } ;
declaration  = funcDef | varDecl ;
funcDef      = typeSpec IDENT "(" [ paramList ] ")" block ;
paramList    = param { "," param } ;
param        = typeSpec IDENT ;
typeSpec     = "int" | "float" | "char" | "void" ;

block        = "{" { blockItem } "}" ;
blockItem    = varDecl | statement ;
varDecl      = typeSpec declarator { "," declarator } ";" ;
declarator   = IDENT [ "=" expr ] ;

statement    = exprStmt | block | ifStmt | whileStmt | forStmt
             | returnStmt | printStmt | ";" ;
exprStmt     = expr ";" ;
ifStmt       = "if" "(" expr ")" statement [ "else" statement ] ;
whileStmt    = "while" "(" expr ")" statement ;
forStmt      = "for" "(" [ forInit ] ";" [ expr ] ";" [ expr ] ")" statement ;
forInit      = typeSpec declarator | expr ;
returnStmt   = "return" [ expr ] ";" ;
printStmt    = "print" "(" expr ")" ";" ;

expr         = assignment ;
assignment   = IDENT "=" assignment | logicOr ;
logicOr      = logicAnd { "||" logicAnd } ;
logicAnd     = equality  { "&&" equality } ;
equality     = relational { ("==" | "!=") relational } ;
relational   = additive   { ("<" | "<=" | ">" | ">=") additive } ;
additive     = term       { ("+" | "-") term } ;
term         = unary      { ("*" | "/" | "%") unary } ;
unary        = ("!" | "-") unary | postfix ;
postfix      = primary | IDENT "(" [ args ] ")" ;
args         = expr { "," expr } ;
primary      = INT_LIT | FLOAT_LIT | CHAR_LIT | STRING_LIT | IDENT | "(" expr ")" ;
```

---

## Ambiguity Resolutions

### 1. Dangling `else`
**Rule:** bind `else` to the **nearest** enclosing `if`.

```
if (a) if (b) S1 else S2
  => if (a) { if (b) S1 else S2 }     ← NOT if (a) { if (b) S1 } else S2
```

**Implementation:** expressed as a shift/reduce conflict resolved by *shift* preference in Lark (`priority="auto"` or an explicit terminal priority).  The Lark grammar uses terminal priorities so that `else` always shifts.

### 2. Operator Precedence (low → high, left-associative unless noted)

| Level | Operators | Assoc |
|---|---|---|
| 1 (lowest) | assignment `=` | **right** |
| 2 | `\|\|` | left |
| 3 | `&&` | left |
| 4 | `==` `!=` | left |
| 5 | `<` `<=` `>` `>=` | left |
| 6 | `+` `-` | left |
| 7 | `*` `/` `%` | left |
| 8 | unary `!` `-` | **right** |
| 9 (highest) | function call postfix `f(…)` | left |

These are encoded directly in the grammar hierarchy (separate non-terminals per level) and are therefore unambiguous.

### 3. `for` initializer ambiguity
`forInit` can start with a type keyword *or* an IDENT (expression).  Type keywords have a disjoint first set from expression-starters (except IDENT), so a one-token lookahead resolves this.  In Lark LALR this is handled automatically.

### 4. Function call vs. parenthesized expression
A call `f(…)` is only possible when the immediately preceding token is `IDENT`.  `primary → IDENT` handles the plain-variable case; `postfix → IDENT "(" … ")"` handles the call.  This is what makes the slide example work: after `int a = 10`, the `(` cannot follow `10` (an INT_LIT), so the Delete-`if` candidate immediately stalls.

---

## Tokens

| Pattern | Token type |
|---|---|
| `int\|float\|char\|void\|if\|else\|while\|for\|return\|print` | keyword |
| `[a-zA-Z_][a-zA-Z0-9_]*` | `IDENT` |
| `[0-9]+` | `INT_LIT` |
| `[0-9]+\.[0-9]*\|[0-9]*\.[0-9]+` | `FLOAT_LIT` |
| `'[^'\\]'` or `'\\'` etc. | `CHAR_LIT` |
| `"[^"\\]*"` | `STRING_LIT` |
| Operators and delimiters | as shown in the table |
| Any other character | `ILLEGAL` (emitted, not dropped) |
| End of input | `EOF` |

Whitespace (`[ \t\r\n]+`) and comments (`//…\n` and `/* … */`) are skipped.

---

## 10 Valid Sample Programs

### V1 — Hello, main
```c
int main() {
    print("hello");
    return 0;
}
```

### V2 — Variable declarations
```c
int main() {
    int a = 5;
    float b = 3.14;
    char c = 'x';
    return 0;
}
```

### V3 — if / else
```c
int max(int a, int b) {
    if (a > b)
        return a;
    else
        return b;
}
int main() {
    print(max(3, 7));
    return 0;
}
```

### V4 — while loop
```c
int main() {
    int i = 0;
    while (i < 10) {
        print(i);
        i = i + 1;
    }
    return 0;
}
```

### V5 — for loop
```c
int main() {
    int i;
    for (i = 0; i < 5; i = i + 1) {
        print(i);
    }
    return 0;
}
```

### V6 — Nested if / dangling else
```c
int main() {
    int a = 1;
    int b = 2;
    if (a > 0)
        if (b > 0)
            print(a);
        else
            print(b);
    return 0;
}
```

### V7 — Arithmetic and logic
```c
int main() {
    int x = (3 + 4) * 2 - 1;
    if (x > 10 && x < 20)
        print(x);
    return 0;
}
```

### V8 — Multiple functions
```c
int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int main() {
    print(add(10, sub(7, 3)));
    return 0;
}
```

### V9 — Variable init with call
```c
int square(int n) { return n * n; }
int main() {
    int s = square(5);
    print(s);
    return 0;
}
```

### V10 — Empty for body, multiple declarations
```c
int main() {
    int a = 0, b = 1, c = 2;
    for (a = 0; a < 3; a = a + 1);
    return 0;
}
```

---

## 10 Invalid Sample Programs

### I1 — Missing semicolon (slide example)
```c
int main() { int a = 10 if (a > 5) { print(a); } }
```
**Expected error:** unexpected `if` at the position after `10`; expected `;`.

### I2 — Missing closing paren
```c
int main() {
    int x = (3 + 4;
    return 0;
}
```
**Expected error:** unexpected `;` after `4`; expected `)`.

### I3 — Extra closing brace
```c
int main() {
    print(1);
}
}
```
**Expected error:** unexpected `}` at line 4.

### I4 — Missing return type
```c
main() {
    return 0;
}
```
**Expected error:** unexpected `main` (IDENT); expected a type specifier.

### I5 — Missing function body
```c
int foo(int x);
```
**Expected error:** unexpected `;` after `)`.

### I6 — Unclosed block
```c
int main() {
    if (1) {
        print(1);
}
```
**Expected error:** unexpected EOF; expected `}`.

### I7 — Bad operator
```c
int main() {
    int a = 5 ++ 3;
    return 0;
}
```
**Expected error:** `++` is two tokens (`+` then `+`); second `+` unexpected after unary/postfix.

### I8 — Missing comma in parameter list
```c
int add(int a int b) { return a + b; }
```
**Expected error:** unexpected `int` after `a`; expected `,` or `)`.

### I9 — Type in wrong position
```c
int main() {
    print(int);
    return 0;
}
```
**Expected error:** `int` keyword where an expression is expected.

### I10 — Multiple errors
```c
int main() {
    int a = ;
    while (a > 0 {
        a = a - 1
    }
    return 0;
}
```
**Expected errors:** (1) `;` where expression expected; (2) missing `)` before `{`; (3) missing `;` after `a - 1`.
