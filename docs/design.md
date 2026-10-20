# SyntaxRecover — Design Document

**Grammar-Guided & Explainable Syntax Error Recovery for Mini-C**
Compiler Design Project (Review 1 → Phase 2 → Phase 3 → Final Review)

---

## 1. Summary

A traditional LR/LALR parser stops at the first unexpected token, or recovers so crudely that it reports dozens of misleading follow-on errors. SyntaxRecover replaces that with a recovery engine that, at every syntax error:

1. Asks the parser what it *expected* at that point.
2. Generates **candidate repairs** (Insert, Delete, Replace, Synchronize).
3. **Validates** every candidate in a cloned (sandbox) parser state against the real grammar.
4. **Ranks** the survivors with explicit, documented metrics (edit cost, parser progress distance, source structure preservation).
5. **Commits** the winner, resumes parsing, and writes a **human-readable explanation** of why it was chosen.

It is deterministic, needs no training data, and can be benchmarked against Yacc/Bison error recovery.

### Hypotheses to test (these drive the evaluation)
- **H1:** Ranked, validated repairs identify the programmer's intended fix more often than panic-mode recovery (Bison `error` rules).
- **H2:** SyntaxRecover reports fewer spurious (cascading) errors than the baselines on multi-error files.
- **H3:** The overhead per error is small enough for interactive use (target: milliseconds on files of a few hundred lines).

---

## 2. Scope

| In scope (v1) | Out of scope (v1) |
|---|---|
| Lexer and parser for Mini-C | Semantic / type errors |
| Error diagnosis (unexpected vs expected tokens) | Preprocessor, headers, macros |
| 4 repair operations, up to 2 edits per error | Code generation / execution |
| Sandbox validation and transparent ranking | ML-based repair (only discussed as related work) |
| Explainable log, repaired source, resume parsing | IDE / editor integration |
| Evaluation harness vs Bison and ablations | Lexical error recovery (illegal chars are reported, not repaired) |

---

## 3. Mini-C Language

Small enough to fully specify, large enough to have real recovery problems (nested blocks, `if/else`, loops, calls, declarations).

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
logicAnd     = equality { "&&" equality } ;
equality     = relational { ("==" | "!=") relational } ;
relational   = additive { ("<" | "<=" | ">" | ">=") additive } ;
additive     = term { ("+" | "-") term } ;
term         = unary { ("*" | "/" | "%") unary } ;
unary        = ("!" | "-") unary | postfix ;
postfix      = primary | IDENT "(" [ args ] ")" ;
args         = expr { "," expr } ;
primary      = INT_LIT | FLOAT_LIT | CHAR_LIT | STRING_LIT | IDENT | "(" expr ")" ;
```

**Dangling else:** bind `else` to the nearest `if` (resolve as shift preference / precedence in the parser generator).
**Tokens:** keywords, `IDENT`, literals, operators, delimiters, `EOF`, plus an `ILLEGAL` token for unknown characters (so the lexer never crashes the pipeline).
**Why a call needs `IDENT`:** this is what makes the slide example work: after deleting `if` in `int a = 10 (a > 5)`, the `(` cannot follow `10`, so that candidate stalls.

---

## 4. Architecture

### 4.1 Pipeline

```
 source.mc
    |
    v
+---------+   Token[]   +-------------------------------------------------------+
|  Lexer  | ----------> |                 Recovery Controller                   |
+---------+             |                                                       |
                        |   +-----------------+                                 |
                        |   | Parser Adapter  |  feed / clone / expected        |
                        |   | (Mini-C grammar)|<-------------------------+      |
                        |   +--------+--------+                          |      |
                        |            | error                             |      |
                        |            v                                   |      |
                        |   +-----------------+  ErrorEvent              |      |
                        |   | 2. Diagnoser    |----------+               |      |
                        |   +-----------------+          v               |      |
                        |                      +-------------------+     |      |
                        |                      | 3. Candidate Gen  |     |      |
                        |                      | Ins/Del/Rep/Sync  |     |      |
                        |                      +---------+---------+     |      |
                        |                                v               |      |
                        |                      +-------------------+     |      |
                        |                      | 4a. Validation    |-----+      |
                        |                      |     Sandbox       | (clones)   |
                        |                      +---------+---------+            |
                        |                                v                      |
                        |                      +-------------------+            |
                        |                      | 4b. Ranker        |            |
                        |                      +---------+---------+            |
                        |                                v                      |
                        |                      +-------------------+            |
                        |   resume <-----------| 5. Committer      |            |
                        |                      +---------+---------+            |
                        +----------------------------------|--------------------+
                                                           v
                                                   +---------------+
                                                   | Explain Logger|
                                                   +-------+-------+
                                                           v
                              AST (with synthetic markers) | repaired source | log (text + JSON)
```

### 4.2 Mapping to the five stages in the presentation

| Slide stage | Module | Responsibility |
|---|---|---|
| 1. Lexical & Syntax Analysis | `lexer.py`, `parser_adapter.py` | Tokenize; parse Mini-C; detect the first failure |
| 2. Error Diagnosis | `diagnose.py` | Build `ErrorEvent`: unexpected token, expected set, position |
| 3. Candidate Repair Engine | `candidates.py` | Generate Insert / Delete / Replace / Sync candidates |
| 4. Grammar Validation & Ranking | `sandbox.py`, `ranker.py` | Validate in cloned state; score and order |
| 5. Recovery & Resume | `commit.py`, `explain.py` | Apply best repair, log it, continue parsing |

---

## 5. Components

### 5.1 Lexer (`lexer.py`)
- Hand-written scanner. Output is a **list** `Token(type, text, line, col, index)` (not a one-shot generator), because the engine needs random access for lookahead, backtrack and rewriting.
- Skips whitespace, `//` and `/* */` comments.
- Unknown characters become `ILLEGAL` tokens and are treated like any other unexpected token.

### 5.2 Parser Adapter (`parser_adapter.py`)
The single most important design decision: **hide the parser behind a small interface** so recovery logic never touches parser internals.

```python
class ParserState(Protocol):
    def clone(self) -> "ParserState": ...            # cheap snapshot for sandboxing
    def feed(self, tok: Token) -> bool: ...          # True = accepted, False = error (state unchanged)
    def expected(self) -> set[str]: ...              # terminals acceptable right now
    def at_accept(self) -> bool: ...                 # can EOF be accepted now?
    def unwind_to_sync(self, sync_tok: Token) -> bool: ...  # for Synchronize (see 5.4)
```

Two implementations (decide in Phase 0, see §12):
- **Option A (recommended to start): Lark LALR interactive parser.** Lark's interactive parser can be copied, fed one token at a time, and asked which tokens it would accept, which maps directly onto `clone / feed / expected`.
- **Option B: your own table-driven parser** (LL(1) with an explicit stack, or an LALR generator). More work and more marks for a compiler course; state is just *stack + position*, so cloning is trivial. Build it behind the same interface so nothing else changes.

### 5.3 Error Diagnoser (`diagnose.py`)
On `feed()` failure at token index `i`, produce:

```python
ErrorEvent(
  index=i, token=tokens[i], prev_token=tokens[i-1],
  line, col,
  expected=sorted(state.expected()),
  context=...   # e.g. "inside block of main()" (optional, from parser stack)
)
```

**Detection vs cause:** an LR parser reports the error at the first token that cannot be shifted, which is often *just after* the real mistake (missing `;` is detected at the next statement's first token). So candidates are generated at the detection point, with a configurable **backtrack window** `b` (default 1) that also tries edits positioned before the previous token.

### 5.4 Candidate Generator (`candidates.py`)

Let `t` = offending token, `E` = expected set.

| Op | Rule | Cost basis |
|---|---|---|
| **Insert** | For each terminal `a ∈ E`, insert `a` *before* `t`. Insertable punctuation and keywords directly. `IDENT` / literals use a placeholder (`__id__`, `0`) and carry a small extra cost because they invent content. | 1 per inserted token (+1 for placeholder) |
| **Delete** | Remove `t` (optionally up to `d` consecutive tokens, default 1). | 1 per deleted token |
| **Replace** | For each `a ∈ E`, replace `t` with `a`. | 1 |
| **Synchronize** | Skip tokens from `t` until a **sync token** (`;`, `}` or a statement-start keyword such as `if while for return int float char void`), then unwind parser state until that token is acceptable. Always succeeds (worst case, skip to `EOF`). | 1 + number of skipped tokens |

**Multi-mutation:** compose up to `max_edits` (default 2) atomic edits per error, using a small beam (e.g. keep best 8 partial candidates) to avoid combinatorial blow-up. Example: a missing `)` followed by a missing `;`.

**Pruning:** drop duplicates (e.g. Replace-with-`a` and Delete+Insert-`a` produce the same token stream; keep the cheaper description).

### 5.5 Validation Sandbox (`sandbox.py`)
For each candidate:

1. `s = state.clone()`
2. Apply the candidate's edits to a *virtual* token view (the real stream is untouched).
3. Feed the edited tokens, then continue with the next original tokens.
4. Record `progress` = number of tokens consumed successfully before the next error (or `EOF` accept), capped at `P_max`.
5. **Valid** iff `progress ≥ K_min` (lookahead validation) or the stream reaches `EOF` and `at_accept()`.
6. Candidates that fail again immediately are discarded (**safety isolation**).

Because it works on clones, a bad candidate can never corrupt the live parse.

### 5.6 Ranker (`ranker.py`)

Three documented metrics, matching the presentation:

| Metric | Definition |
|---|---|
| **Edit Cost** `C` | Sum of per-operation costs from §5.4 |
| **Parser Progress Distance** `P` | Tokens parsed successfully after the repair, capped at `P_max`; use `p = P / P_max` |
| **Source Structure Preservation** `S` (a *penalty*) | `S = (original tokens removed or skipped) + λ · (structural tokens changed)`, where structural tokens are `{ } ( )` inserted, removed or replaced, and `λ = 2` |

**Score (lower is better):**

```
score = α·C + γ·S − β·p          defaults: α = 1, γ = 1, β = 3
```

**Deterministic tie-break:** higher `P` → lower `C` → operation priority (Insert, Replace, Delete, Sync) → lexicographic inserted token. Identical input therefore always gives identical output.

**Worked check against the slide example** (`int a = 10 if (a > 5) { print(a); } }`, `P_max = 20`):

| Candidate | C | S | P | score |
|---|---|---|---|---|
| R1 Insert `;` before `if` | 1 | 0 | 15 → p=0.75 | 1 + 0 − 2.25 = **−1.25** (selected) |
| R2 Delete `if` | 1 | 1 | 0 (`(` cannot follow `10`) → fails `K_min`, discarded | n/a |
| R3 Sync to next `;` | ~10 | ~9 | 8 → p=0.40 | ~10 + 9 − 1.2 = **~17.8** (rejected) |

### 5.7 Committer and Resumer (`commit.py`)
- Applies the winning edits to the **real** token list and the live parser state.
- Marks inserted tokens `synthetic=True` so AST nodes built from them are flagged.
- Resumes parsing from the first token after the repair. **The parser loop is never reset**, so the whole file is processed in one run.
- **Termination guarantee:** every commit must consume at least one original token or lead to consuming one; Synchronize always does. A global `max_errors` cap is a second safety net.
- **Cascade guard:** for `suppression_window` tokens after a commit, a new error is tagged `possibly_secondary` in the log instead of being presented as an independent mistake.

### 5.8 Explainable Logger (`explain.py`)

Each recovery produces one structured `RecoveryEvent` (serialized to JSON) and a rendered text form.

```json
{
  "id": 1,
  "line": 2, "col": 20,
  "unexpected": "if",
  "expected": [";", ",", "+", "-", "*", "/", "..."],
  "candidates": [
    {"id": "R1", "op": "insert", "edit": "insert ';' before 'if'", "valid": true,
     "cost": 1, "structure_penalty": 0, "progress": 15, "score": -1.25, "decision": "accepted"},
    {"id": "R2", "op": "delete", "edit": "delete 'if'", "valid": false,
     "reason": "parser stalls after 0 tokens", "decision": "rejected"},
    {"id": "R3", "op": "sync", "edit": "skip to next ';'", "valid": true,
     "cost": 10, "structure_penalty": 9, "progress": 8, "score": 17.8, "decision": "rejected"}
  ],
  "chosen": "R1",
  "explanation": "Inserted ';' after 10 because the statement grammar requires a terminator. Minimal edit cost selected."
}
```

Text form:
```
error[syntax] prog.mc:2:20  unexpected 'if', expected one of: ';' ',' '+' '-' ...
   2 | int main() { int a = 10 if (a > 5) { print(a); } }
                              ^
  R1 insert ';'        valid  cost=1  progress=15  score=-1.25   <- ACCEPTED
  R2 delete 'if'       invalid (parser stalls)                    rejected
  R3 sync to ';'       valid  cost=10 progress=8   score=17.80    rejected
  why: Inserted ';' after 10 because the statement grammar requires a terminator.
```

**Explanations** come from templates keyed by *(operation, token, grammar context)*, e.g. `";"` in a declaration or statement → "statement grammar requires a terminator". Keep the context phrases in one table (`explain_templates.py`) so they are easy to review and extend.

### 5.9 Driver and Outputs (`cli.py`)
```
syntaxrecover prog.mc                      # diagnose + recover, print log
syntaxrecover prog.mc --json out.json      # machine-readable log
syntaxrecover prog.mc --repaired out.mc    # write repaired source
syntaxrecover prog.mc --ast                # dump AST (synthetic nodes flagged)
syntaxrecover prog.mc --config cfg.toml    # override weights / K / P_max
syntaxrecover prog.mc --no-sync            # ablation switches
```
Exit codes: `0` no errors, `1` errors found and repaired, `2` internal failure.

---

## 6. Core Algorithm

```python
def recover_all(tokens, cfg):
    state, i, events = parser.initial(), 0, []
    while i < len(tokens):
        if state.feed(tokens[i]):
            i += 1
            continue

        ev    = diagnose(state, tokens, i)
        cands = generate_candidates(ev, state, tokens, cfg)      # Ins / Del / Rep / Sync, up to max_edits
        valid = [c for c in map(lambda c: validate(c, state, tokens, cfg), cands) if c.valid]
        if not valid:
            valid = [fallback_sync(ev, state, tokens)]           # always succeeds
        ranked = rank(valid, cfg)
        best   = ranked[0]

        state, tokens, i = commit(best, state, tokens)           # real stream + live state
        events.append(explain(ev, ranked, best))

        if len(events) >= cfg.max_errors:
            break
    return RecoveryResult(tokens, ast, events)
```

---

## 7. Data Structures

| Type | Fields |
|---|---|
| `Token` | `type, text, line, col, index, synthetic` |
| `Edit` | `kind (INS/DEL/REP/SYNC), at_index, token (for INS/REP), count (for DEL/SYNC)` |
| `Candidate` | `edits: list[Edit], id, description` |
| `Validation` | `valid, progress, failure_reason` |
| `Score` | `cost, structure_penalty, progress, total` |
| `ErrorEvent` | `index, token, prev_token, line, col, expected, context` |
| `RecoveryEvent` | `error, candidates (with Validation + Score), chosen, explanation, possibly_secondary` |
| `RecoveryResult` | `repaired_tokens, ast, events, stats` |

---

## 8. Configuration

| Parameter | Default | Meaning |
|---|---|---|
| `K_min` | 3 | Minimum tokens a repair must survive to be valid |
| `P_max` | 20 | Progress cap used for normalization |
| `max_edits` | 2 | Atomic edits composed per error |
| `beam_width` | 8 | Partial candidates kept while composing edits |
| `backtrack_window` | 1 | Tokens before the error also considered for edits |
| `delete_span` | 1 | Max consecutive tokens a Delete may remove |
| `α, β, γ, λ` | 1, 3, 1, 2 | Score weights and structure multiplier |
| `placeholder_penalty` | 1 | Extra cost for inserting `IDENT`/literal |
| `sync_tokens` | `; }` + statement-start keywords | Resynchronization points |
| `suppression_window` | 3 | Tokens after a commit where new errors are tagged secondary |
| `max_errors` | 100 | Safety cap |

All of these must be loadable from a config file and logged with every experiment run, so results are reproducible.

---

## 9. Project Structure

```
syntaxrecover/
├── README.md
├── docs/
│   ├── design.md
│   ├── checklist.md
│   ├── minic_grammar.md
│   └── ranking_spec.md          # formulas + worked examples
├── grammar/
│   └── minic.lark               # (or minic.y for the Bison baseline)
├── syntaxrecover/
│   ├── tokens.py
│   ├── lexer.py
│   ├── ast_nodes.py
│   ├── parser_adapter.py        # interface + LarkAdapter (+ own parser later)
│   ├── diagnose.py
│   ├── candidates.py
│   ├── sandbox.py
│   ├── ranker.py
│   ├── commit.py
│   ├── explain.py
│   ├── explain_templates.py
│   ├── config.py
│   └── cli.py
├── eval/
│   ├── corpus/valid/            # clean Mini-C programs
│   ├── mutator.py               # error injection with ground truth
│   ├── baselines/
│   │   ├── bison/               # minic.y, minic.l, Makefile, runner
│   │   └── panic_mode.py        # sync-only baseline in your own parser
│   ├── metrics.py
│   ├── run_experiments.py
│   └── results/                 # CSVs, plots
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_diagnose.py
    ├── test_candidates.py
    ├── test_sandbox.py
    ├── test_ranker.py
    ├── test_commit.py
    ├── test_explain.py
    └── golden/                  # input .mc + expected log/repaired output
```

---

## 10. Testing Strategy

| Level | What | How |
|---|---|---|
| Unit | Each module with hand-built inputs | `pytest` |
| Golden | Slide example and ~30 more: input → exact expected repair + log | golden files |
| Property | After recovery, the repaired token stream always parses; recovery always terminates; output is deterministic | `hypothesis` or randomized loops |
| Regression | Every bug found gets a permanent test | `tests/golden/` |
| Differential | Compare against Bison on the same inputs (see §11) | `eval/` |

---

## 11. Evaluation Plan (Final Review)

### Dataset
- **Seed corpus:** 40+ valid Mini-C programs (hand-written plus a few generated from the grammar), 20 to 150 lines.
- **Mutator** injects errors with **known ground truth** (the original program):
  - delete one token (missing `;`, `)`, `}`, operator)
  - insert one extra token
  - replace a token with a wrong one
  - swap adjacent tokens
  - combine 1, 2 or 3 injected errors per file
- Target: 1,000+ mutated files, split by error type and error count.

### Baselines
| Id | System |
|---|---|
| B1 | **Bison/Yacc** with the Mini-C grammar and the usual `error` productions (`stmt: error ';'`, `block: '{' error '}'`) |
| B2 | Panic-mode only (Synchronize), in your own parser |
| B3 | Your engine with **no ranking** (first valid candidate wins) |

### Metrics
| Metric | Meaning |
|---|---|
| **Exact-fix rate** (Top-1 and Top-3) | Repaired token stream equals the original program |
| **Edit distance to original** | Token-level distance when not exact |
| **Localization error** | Distance in tokens/lines between reported and true error location |
| **Spurious errors** | Reported errors minus injected errors (cascade measure) |
| **Tokens discarded** | Original tokens deleted or skipped |
| **Runtime per error** and total | ms, with the same machine for all systems |

### Ablations
Remove each ranking term (no progress, no structure, no cost), vary `K_min` and `P_max`, disable Sync, vary `max_edits`. Report which components matter.

---

## 12. Key Design Decisions

| Decision | Choice | Why | Alternative |
|---|---|---|---|
| Parser | Lark LALR behind `ParserState` interface | Clone / feed / expected exist out of the box; fastest path to a working engine | Own table-driven parser (more effort, deeper course content) |
| Language | Python 3 | Fast iteration, easy experiment scripts and plots | C/C++ (closer to Bison, slower to write) |
| Ranking | Weighted score with deterministic tie-break | Simple, explainable, tunable | Lexicographic ordering |
| Validation | Clone-and-replay | Cannot corrupt live state | Backtracking in place |
| Baseline | Real Bison build | Credible comparison | Only own panic mode |
| Output | Text log plus JSON plus repaired source | Human and machine use | Text only |

---

## 13. Risks and Claims to Word Carefully

These are the points a reviewer is most likely to challenge.

1. **"Non-heuristic" ranking.** The metrics are transparent and deterministic, but the weights (`α, β, γ`) are tunable parameters. Safer wording: *"transparent, deterministic, parameterized ranking"*, and justify the defaults with the ablation study.
2. **"Guarantees 100% formal grammar compliance."** True for the **repaired token stream** (it parses by construction). It does *not* mean the repair matches what the programmer meant, especially for Synchronize, which discards code. Report exact-fix rate separately from validity.
3. **Detection point vs true error point.** Missing-token errors are detected late. The backtrack window and "insert before the offending token" rule address this; show a failure case in the report.
4. **Placeholders for `IDENT` / literals.** Inserting invented names is guesswork. Keep the penalty, log it explicitly as "placeholder inserted".
5. **Candidate explosion.** `max_edits = 2` with a large expected set can blow up; the beam and pruning are mandatory, not optional.
6. **Sync correctness.** Unwinding the parser stack to a state that accepts the sync token is the hardest part. Build it last and test it separately.
7. **Fair benchmarking.** Same grammar, same inputs, same machine; document the Bison error rules you wrote so the baseline is not a straw man.

---

## 14. Traceability: Slides → Implementation

| Slide claim | Implemented in | Verified by |
|---|---|---|
| Formal validation of candidates | `sandbox.py` | `test_sandbox.py`, property tests |
| Insert / Delete / Replace / Synchronize | `candidates.py` | `test_candidates.py` |
| Lookahead validation (K tokens) | `sandbox.py` (`K_min`) | golden + unit tests |
| Safety isolation | `sandbox.py` (clone-and-replay) | test that live state is unchanged |
| Edit Cost / Progress / Structure ranking | `ranker.py` | `test_ranker.py`, ablations |
| Human-readable explanations | `explain.py` | `test_explain.py`, golden logs |
| Continuous parsing, full-file diagnostics | `commit.py`, controller loop | multi-error golden tests |
| Benchmark against Yacc/Bison | `eval/` | experiment results |
