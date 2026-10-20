# SyntaxRecover — Hand-Traced Golden Error Traces

*Three end-to-end hand traces serving as specification and test assertions for the first golden tests.*

---

## Trace 1: Missing Semicolon (Slide Example)

### Input Code
```c
int main() {
    int a = 10 if (a > 5) { print(a); }
}
```

### 1. Error Event
- **Token index:** 7 (`if`)
- **Location:** Line 2, Column 16
- **Offending Token:** `if`
- **Previous Token:** `10` (`INT_LIT`)
- **Parser State Context:** Inside `varDecl` / declaration item after initializer expression
- **Expected Terminals `E`:** `{";", ",", "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}`

### 2. Candidate Generation
- `R1` (INS): Insert `;` before `if`
- `R2` (DEL): Delete `if`
- `R3` (REP): Replace `if` with `;`
- `R4` (SYNC): Skip to next `;` (`tokens: if ( a > 5 ) { print ( a ) ;`)

### 3. Validation Sandbox (`K_min = 3, P_max = 20`)
- `R1`: Virtual tokens become `... 10 ; if ( a > 5 ) { print ( a ) ; } }`.
  - Parsed successfully: `;`, `if`, `(`, `a`, `>`, `5`, `)`, `{`, `print`, `(`, `a`, `)`, `;`, `}`, `}` (15 tokens to EOF).
  - `progress = 15 >= 3` -> **VALID**.
- `R2`: Virtual tokens become `... 10 ( a > 5 ) ...`.
  - Token `(` cannot follow integer literal `10` in Mini-C grammar (function calls require identifier).
  - Parser fails immediately at token `(` (0 tokens consumed).
  - `progress = 0 < 3` -> **INVALID** (Discarded).
- `R3`: Virtual tokens become `... 10 ; ( a > 5 ) ...`.
  - Token `(` can start an expression statement in block. Condition `(a > 5);` parsed. Next block `{ print(a); }` parsed.
  - `progress = 14 >= 3` -> **VALID**, but note replacement discarded original keyword `if`.
- `R4`: Virtual tokens skip to next `;`. Parser unwinds to statement level and resumes at `}`.
  - `progress = 8` -> **VALID**.

### 4. Ranking (`α = 1.0, β = 3.0, γ = 1.0, λ = 2.0`)
- `R1`:
  - `C = 1.0` (1 insertion)
  - `S = 0` (no tokens deleted/skipped, no structural delimiters changed)
  - `P = 15`, `p = 15 / 20 = 0.75`
  - `Score = 1.0 * 1.0 + 1.0 * 0 - 3.0 * 0.75 = 1.0 - 2.25 = -1.25`
- `R4`:
  - `C = 1.0 + 9 = 10.0` (9 skipped tokens)
  - `S = 9 + 2.0 * (2 structural: '(' and ')') = 13.0`
  - `P = 8`, `p = 8 / 20 = 0.40`
  - `Score = 1.0 * 10.0 + 1.0 * 13.0 - 3.0 * 0.40 = 23.0 - 1.2 = 21.80`

**Winner:** `R1` (Score = -1.25).

### 5. Rendered Log
```text
error[syntax]: prog.mc:2:16: unexpected 'if', expected ';' or binary operator
   2 |     int a = 10 if (a > 5) { print(a); }
                  ^
  R1 insert ';'        valid  cost=1  progress=15  score=-1.25   <- ACCEPTED
  R2 delete 'if'       invalid (parser stalls after 0 tokens)     rejected
  R4 sync to ';'       valid  cost=10 progress=8   score=21.80    rejected
  why: Inserted ';' after expression because declaration requires a statement terminator.
```

---

## Trace 2: Missing Closing Parenthesis

### Input Code
```c
int main() {
    int x = (3 + 4;
    return x;
}
```

### 1. Error Event
- **Token index:** 8 (`;`)
- **Location:** Line 2, Column 19
- **Offending Token:** `;`
- **Previous Token:** `4` (`INT_LIT`)
- **Parser State Context:** Inside parenthesized expression `(` waiting for closing `)`
- **Expected Terminals `E`:** `{")", "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}`

### 2. Candidate Generation
- `R1` (INS): Insert `)` before `;`
- `R2` (DEL): Delete `;`
- `R3` (REP): Replace `;` with `)`
- `R4` (SYNC): Skip to next `;`

### 3. Validation Sandbox (`K_min = 3, P_max = 20`)
- `R1`: Virtual tokens become `( 3 + 4 ) ; return x ; }`.
  - Parsed successfully: `)`, `;`, `return`, `x`, `;`, `}` (6 tokens to EOF accept).
  - `progress = 6 >= 3` -> **VALID**.
- `R2`: Virtual tokens become `( 3 + 4 return x ; }`.
  - `return` cannot appear inside an arithmetic expression.
  - `progress = 0 < 3` -> **INVALID**.
- `R3`: Virtual tokens become `( 3 + 4 ) return x ; }`.
  - Next token `return` directly follows without statement terminator `;`.
  - Fails at `return` (progress = 1 < 3) -> **INVALID**.
- `R4`: Sync skips `;` and advances to `return x ;`.
  - Progress = 4 -> **VALID**, but drops original statement terminator.

### 4. Ranking
- `R1`:
  - `C = 1.0` (1 insertion)
  - `S = 0 + 2.0 * 1 = 2.0` (1 structural parenthesis inserted)
  - `P = 6`, `p = 6 / 20 = 0.30`
  - `Score = 1.0 * 1.0 + 1.0 * 2.0 - 3.0 * 0.30 = 3.0 - 0.9 = 2.10`
- `R4`:
  - `C = 1.0 + 1 = 2.0`
  - `S = 1 + 2.0 * 0 = 1.0`
  - `P = 4`, `p = 4 / 20 = 0.20`
  - `Score = 1.0 * 2.0 + 1.0 * 1.0 - 3.0 * 0.20 = 3.0 - 0.6 = 2.40`

**Winner:** `R1` (Score = 2.10).

### 5. Rendered Log
```text
error[syntax]: prog.mc:2:19: unexpected ';', expected ')'
   2 |     int x = (3 + 4;
                     ^
  R1 insert ')'        valid  cost=1  progress=6   score=2.10    <- ACCEPTED
  R2 delete ';'        invalid (parser stalls after 0 tokens)     rejected
  R3 replace with ')'  invalid (missing ';' after expression)    rejected
  R4 sync to ';'       valid  cost=2  progress=4   score=2.40    rejected
  why: Inserted ')' before ';' to close opened parenthesis expression.
```

---

## Trace 3: Extra Closing Brace

### Input Code
```c
int main() {
    print(1);
}
}
```

### 1. Error Event
- **Token index:** 8 (`}`)
- **Location:** Line 4, Column 1
- **Offending Token:** `}`
- **Previous Token:** `}` (closing brace of `main` function)
- **Parser State Context:** Top-level program declaration scope; program has accepted `FuncDef`
- **Expected Terminals `E`:** `{"int", "float", "char", "void", "EOF"}`

### 2. Candidate Generation
- `R1` (DEL): Delete stray `}`
- `R2` (REP): Replace `}` with declaration type keyword (e.g. `int`)
- `R3` (SYNC): Skip to next sync token or `EOF`

### 3. Validation Sandbox (`K_min = 3, P_max = 20`)
- `R1`: Virtual tokens become `EOF`.
  - Stream cleanly terminates at `EOF`, parser reports `at_accept() == True`.
  - Reaching clean `EOF` is valid even if stream ends -> **VALID** (`progress = 1`).
- `R2`: Replace with `int`.
  - Virtual stream becomes `int EOF`. An incomplete type specifier stalls immediately at EOF.
  - `progress = 0 < 3` -> **INVALID**.
- `R3`: Sync to `EOF` removes 1 token (`}`) and lands at `EOF`.

### 4. Ranking
- `R1`:
  - `C = 1.0` (1 deletion)
  - `S = 1 + 2.0 * 1 = 3.0` (1 structural delimiter deleted)
  - `P = 1` (EOF reached cleanly)
  - `Score = 1.0 * 1.0 + 1.0 * 3.0 - 3.0 * (1.0) = 4.0 - 3.0 = 1.00` (EOF accept gets maximum progress weight)

**Winner:** `R1` (Delete stray `}`).

### 5. Rendered Log
```text
error[syntax]: prog.mc:4:1: unexpected '}', expected function or variable declaration, or EOF
   4 | }
       ^
  R1 delete '}'        valid  cost=1  progress=1   score=1.00    <- ACCEPTED
  R2 replace with 'int' invalid (incomplete declaration at EOF)   rejected
  why: Deleted extraneous closing brace to complete program cleanly at EOF.
```
