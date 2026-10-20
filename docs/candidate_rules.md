# SyntaxRecover — Candidate Generation Rules Specification

*Detailed implementation specification for `candidates.py`. A teammate must be able to implement the candidate generator entirely from this specification.*

---

## 1. Input Interface

The candidate generation engine takes:
- `event: ErrorEvent`
  - `event.index`: index `i` of the unexpected token `t` in `tokens`
  - `event.token`: offending token `t = tokens[i]`
  - `event.prev_token`: preceding token `tokens[i - 1]` (if `i > 0`, else `None`)
  - `event.expected`: sorted list/set `E` of terminal token types acceptable to the parser at `i`
  - `event.line`, `event.col`: source location of `t`
- `state: ParserState`: the snapshot of the parser immediately before attempting to shift `t`
- `tokens: list[Token]`: full token sequence
- `cfg: Config`: tunable parameters (`max_edits`, `beam_width`, `backtrack_window`, `delete_span`, `placeholder_penalty`, `sync_tokens`)

---

## 2. Atomic Edit Operations

An edit is represented as:
```python
@dataclass(frozen=True)
class Edit:
    kind: str       # "INS" | "DEL" | "REP" | "SYNC"
    at_index: int   # Token index in the original stream where edit applies
    token: Optional[Token] = None  # Inserted/replacement token (for INS, REP)
    count: int = 1                 # Number of tokens removed/skipped (for DEL, SYNC)
```

### 2.1 Operation 1: Insert (`INS`)
- **Trigger:** Generated for each terminal type `a ∈ E` (the expected set).
- **Position:** Inserted immediately *before* the offending token at `event.index`.
  - When `backtrack_window >= 1` and `i > 0`, also generated before `event.prev_token` at `event.index - 1`.
- **Token Generation:**
  - Standard terminals (keywords, operators, punctuation): `Token(type=a, text=a.value, synthetic=True)`
  - Identifiers and literals: use canonical placeholders via `make_placeholder(a)`:
    - `IDENT` → `__id__`
    - `INT_LIT` → `0`
    - `FLOAT_LIT` → `0.0`
    - `CHAR_LIT` → `'a'`
    - `STRING_LIT` → `""`
- **Edit Cost (`C`):**
  - Base cost = `1.0`
  - If token is an identifier or literal placeholder: add `cfg.placeholder_penalty` (default `+1.0`, total = `2.0`).
- **Structure Penalty (`S`):**
  - `tokens_removed = 0`
  - `structural_tokens_changed`: `1` if `a ∈ {"{", "}", "(", ")"}` else `0`.

### 2.2 Operation 2: Delete (`DEL`)
- **Trigger:** Generated unconditionally at the error point, provided `t != EOF`.
- **Position:** Target index is `event.index`.
- **Span:** Deletes from `1` up to `cfg.delete_span` (default `1`) consecutive tokens:
  - Tokens deleted: `tokens[i : i + span]`
  - Deletion cannot delete past `EOF` or remove `EOF`.
- **Edit Cost (`C`):**
  - Cost = `1.0 * span`
- **Structure Penalty (`S`):**
  - `tokens_removed = span`
  - `structural_tokens_changed = count of { "{" , "}" , "(" , ")" }` among deleted tokens.

### 2.3 Operation 3: Replace (`REP`)
- **Trigger:** For each terminal type `a ∈ E`, replace `t` with `a`, provided `t != EOF` and `t.type != a`.
- **Position:** Target index is `event.index`.
- **Edit Cost (`C`):**
  - Base cost = `1.0`
  - If `a` is a placeholder (`IDENT`/literal), add `cfg.placeholder_penalty` (total = `2.0`).
- **Structure Penalty (`S`):**
  - `tokens_removed = 0` (token is substituted in-place, not dropped)
  - `structural_tokens_changed`:
    - `+1` if old token `t` was structural (`{ } ( )`)
    - `+1` if replacement token `a` is structural (`{ } ( )`)

### 2.4 Operation 4: Synchronize (`SYNC`)
- **Trigger:** Resynchronization scan starting at `t = tokens[i]`.
- **Scanning Rule:**
  - Advance index `j = i` forward until finding a token `tokens[j]` whose `type.value` is in `cfg.sync_tokens`:
    - Statement delimiters: `;`, `}`
    - Statement starters: `if`, `while`, `for`, `return`, `print`
    - Declaration starters: `int`, `float`, `char`, `void`
    - Or until reaching `EOF`.
  - Number of skipped tokens: `k = j - i`.
  - Unwind parser state stack until a state is reached that can accept `tokens[j]`.
- **Edit Cost (`C`):**
  - Cost = `1.0 + k`
- **Structure Penalty (`S`):**
  - `tokens_skipped = k`
  - `structural_tokens_changed = count of { "{" , "}" , "(" , ")" }` among skipped tokens.

---

## 3. Multi-Edit Composition & Beam Search

To repair errors requiring up to `max_edits` (default 2) actions (e.g., missing `)` followed by missing `;`):

1. **Depth 1 (Single edits):**
   - Generate all atomic single-edit candidates: `[INS(a), DEL(t), REP(t, a), SYNC]`.
   - Validate each in the sandbox to measure preliminary progress.
   - Retain the top `cfg.beam_width` (default 8) candidates ordered by lowest provisional score.

2. **Depth 2 (Two edits):**
   - For each surviving candidate from Depth 1 that did not already achieve `progress >= P_max` or reach `EOF`:
     - Apply candidate's virtual token edit.
     - Advance sandbox parser until next failure point `i'`.
     - At `i'`, query the parser's new expected set `E'`.
     - Generate secondary atomic edits `INS`, `DEL`, `REP`.
     - Compose: `Candidate(edits=[edit1, edit2])`.

3. **Pruning & Equivalence Deduplication:**
   - Normalize candidate effects on the token sequence:
     - Example: `REP(t -> a)` produces the identical token view as `DEL(t) + INS(a)`.
     - **Rule:** Keep the candidate with the lower edit cost description (`REP` cost 1 vs `DEL+INS` cost 2).
   - Drop duplicate token sequences produced by different edit combinations.

---

## 4. Candidate Identification & Formatting

Each candidate is assigned:
- `id`: Unique identifier, e.g., `R1`, `R2`, `R3`, ...
- `description`: Clear human-readable summary:
  - `insert ';' before 'if'`
  - `delete 'if'`
  - `replace '==' with '='`
  - `sync to next ';'`
- `edits`: `list[Edit]`
- `valid`: boolean (filled by Sandbox)
- `cost`: computed edit cost `C`
- `structure_penalty`: computed `S`
- `progress`: tokens parsed before next error or EOF (filled by Sandbox)
- `score`: total computed ranking score (filled by Ranker)
