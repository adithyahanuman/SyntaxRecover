# SyntaxRecover — Log Format Specification

*Documents the human-readable terminal output and the machine-readable JSON log schema.*

---

## 1. Terminal Output Layout

Syntax errors are rendered with diagnostic carets, candidate ranking tables, and natural language explanations:

```text
error[syntax]: prog.mc:2:16: unexpected 'if', expected ';' or binary operator
   2 |     int a = 10 if (a > 5) { print(a); }
                  ^
  Candidates evaluated:
  R1  insert ';'         valid    cost=1.0  progress=15  score=-1.25   <- ACCEPTED
  R2  delete 'if'        invalid  (parser stalls after 0 tokens)       rejected
  R3  sync to ';'        valid    cost=10.0 progress=8   score=21.80   rejected

  Explanation: Inserted ';' after expression because statement grammar requires a terminator.
```

### Components
1. **Header line:** `error[syntax]: <filename>:<line>:<col>: unexpected '<token>', expected <expected summary>`
2. **Context snippet:** Source code line with line number and `^` caret indicator pointing to the offending character column.
3. **Candidate table:**
   - Candidate ID (`R1`, `R2`, ...)
   - Operation summary (`insert ';'`, `delete 'if'`, `replace '==' with '='`, `sync to ';'`)
   - Validity status (`valid` or `invalid`)
   - Metrics (when valid): `cost`, `progress`, `score`
   - Rejection reason (when invalid): e.g., `(parser stalls after 0 tokens)`
   - Decision badge: `<- ACCEPTED` or `rejected`
4. **Explanation line:** Plain English rationale keyed to the grammar production rule and chosen candidate.

---

## 2. Machine-Readable JSON Output (`--json out.json`)

Formal schema: [recovery_log_schema.json](file:///c:/Users/narne/Desktop/compiler%20project/syntaxrecover/docs/recovery_log_schema.json)  
Sample file: [example_recovery_log.json](file:///c:/Users/narne/Desktop/compiler%20project/syntaxrecover/docs/example_recovery_log.json)

Key fields:
- `source_file`: path to original source
- `total_errors`: number of recovered error events
- `events[]`:
  - `id`: 1-based sequential error event counter
  - `line`, `col`: 1-based coordinates
  - `unexpected`: string of unexpected token text
  - `expected`: list of string terminals acceptable at that state
  - `possibly_secondary`: boolean indicating if error occurred within cascade suppression window
  - `candidates[]`: list of all generated candidates with cost, progress, score, validity, and decision
  - `chosen`: ID of winning candidate
  - `explanation`: human-readable explanation
- `repaired_source`: full synthesized source code string after applying all accepted repairs
