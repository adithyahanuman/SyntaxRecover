# SyntaxRecover — Ranking Specification

*Covers Edit Cost (C), Parser Progress Distance (P), Source Structure Preservation (S),
the composite score formula, tie-break order, and a complete hand-worked example.*

---

## 1. Metrics

### 1.1 Edit Cost  `C`

The total cost of all atomic edits in a candidate.

| Operation | Base cost | Modifier |
|---|---|---|
| Insert a keyword or punctuation token | 1 | — |
| Insert an `IDENT` or literal (placeholder) | 1 + `placeholder_penalty` | `placeholder_penalty` = 1 by default, so cost = 2 |
| Delete a token | 1 per deleted token | — |
| Replace a token | 1 | — |
| Synchronize | 1 + *n* | *n* = number of tokens skipped |

**Multi-edit:** `C` = sum of costs of all individual edits in the candidate.

### 1.2 Parser Progress Distance  `P`

The number of *original* tokens consumed successfully after the repair is applied, before the next error or EOF, capped at `P_max` (default 20).

```
p = P / P_max          (normalized to [0, 1])
```

Measured inside the Validation Sandbox:
1. Clone the current parser state.
2. Apply the candidate's edits (virtual token view).
3. Feed tokens one by one until an error or EOF.
4. `P` = count of tokens fed successfully.

### 1.3 Source Structure Preservation  `S`  *(penalty — higher is worse)*

```
S = (tokens_removed + tokens_skipped) + λ · structural_tokens_changed
```

Where:
- `tokens_removed` = original source tokens deleted by Delete operations.
- `tokens_skipped` = original source tokens discarded by Synchronize.
- `structural_tokens_changed` = count of structural tokens (`{ } ( )`) that were inserted, deleted, or replaced.
- `λ` = 2 (default).

**Rationale:** structural delimiters bracket major syntactic units; changing them is more disruptive to source layout than changing, say, a semicolon.

---

## 2. Score Formula

**Lower score = better candidate.**

```
score = α·C + γ·S − β·p
```

Default weights: `α = 1, γ = 1, β = 3`.

| Component | Effect |
|---|---|
| `α·C` | Penalizes large / complex repairs |
| `γ·S` | Penalizes loss of original source structure |
| `−β·p` | Rewards candidates that let the parser make more progress |

The strong progress reward (`β = 3`) means a repair that lets the parser advance significantly can dominate even if it has a slightly higher edit cost.

---

## 3. Deterministic Tie-Break

When two or more candidates share the same score, break ties in this order (prefer the *earlier* criterion):

1. **Higher P** (more parser progress) — the candidate that parsed further wins.
2. **Lower C** (fewer edits) — the simpler repair wins.
3. **Operation priority:** Insert > Replace > Delete > Synchronize.
4. **Lexicographic order of inserted/replaced token text** — e.g. `"("` < `")"` < `";"`.

This ensures that identical input always produces identical output, which is required for reproducible evaluation.

---

## 4. Worked Example — Slide Error

**Source (line 2):**
```
int main() { int a = 10 if (a > 5) { print(a); } }
```

**Error event:** unexpected token `if` at position after `10`; expected one of: `; , + - * / % == != < <= > >= && ||`

**Candidates generated:**

| Id | Op | Edit description | C | S | P (sandbox) | p (P/20) |
|---|---|---|---|---|---|---|
| R1 | Insert | Insert `;` before `if` | 1 | 0 | 15 | 0.75 |
| R2 | Delete | Delete `if` | 1 | 0 | 0 *(stalls)* | — |
| R3 | Sync | Skip tokens to next `;` (skips `if ( a > 5 ) { print ( a ) ; }`) | ~10 | ~9 | 8 | 0.40 |

**Validation:**
- R1: valid — parser accepts `; if (a > 5) { print(a); }` with progress = 15 ≥ K_min = 3.
- R2: **invalid** — after deleting `if`, the next token is `(` which cannot follow `10` (INT_LIT) in any context; progress = 0 < K_min.  **Discarded.**
- R3: valid — parser accepts `}` (end of main) after sync; progress = 8 ≥ K_min.

**Score calculations** (`α=1, β=3, γ=1`):

| Id | Formula | Score |
|---|---|---|
| R1 | 1·1 + 1·0 − 3·0.75 | **−1.25** ← selected |
| R3 | 1·10 + 1·9 − 3·0.40 | **17.80** ← rejected |

**Decision:** R1 selected.  R2 discarded (invalid).  R3 rejected (score too high).

**Log text:**
```
error[syntax] prog.mc:2:24  unexpected 'if', expected one of: ';' ',' '+' ...
   2 | int main() { int a = 10 if (a > 5) { print(a); } }
                               ^
  R1 insert ';'        valid  cost=1  progress=15  score=-1.25   <- ACCEPTED
  R2 delete 'if'       invalid (parser stalls after 0 tokens)     rejected
  R3 sync to ';'       valid  cost=10 progress=8   score=17.80    rejected
  why: Inserted ';' after 10 because the statement grammar requires a terminator.
```

---

## 5. Edge Cases

| Situation | Behaviour |
|---|---|
| All candidates invalid | Fall back to Synchronize (guaranteed to make progress) |
| Multiple candidates with identical score | Apply tie-break rules from §3 |
| Sync skips to EOF | Valid (at_accept() iff grammar allows empty body); progress = remaining tokens |
| Insert produces an IDENT placeholder | Cost +1 (placeholder_penalty); explanation notes "placeholder inserted" |
| max_edits = 1 | Only single-edit candidates are generated; R1 still wins above |
