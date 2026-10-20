# SyntaxRecover — Evaluation Plan

---

## Hypotheses

| Id | Hypothesis |
|---|---|
| **H1** | Ranked, validated repairs identify the programmer's intended fix more often than panic-mode recovery (Bison `error` rules). |
| **H2** | SyntaxRecover reports fewer spurious (cascading) errors than the baselines on multi-error files. |
| **H3** | The overhead per error is small enough for interactive use (target: ≤ 10 ms per error on files of ≤ 200 lines). |

---

## Dataset

### Seed Corpus
- **40+ valid** Mini-C programs, hand-written.
- Sizes: 20 to 150 lines.
- Cover: simple declarations, nested blocks, `if/else`, `while`, `for`, function calls.

### Mutator (`eval/mutator.py`)
Inject errors with **known ground truth** (original = correct program):

| Mutation | Description |
|---|---|
| `del_one` | Delete one random token |
| `ins_one` | Insert one random token from the grammar's terminal set |
| `rep_one` | Replace one token with a different terminal |
| `swap_two` | Swap two adjacent tokens |

**Error counts:** 1, 2 or 3 injected errors per file.

**Target:** **1,000+ mutated files**, balanced across mutation type and error count.

**Reproducibility:** fixed random seed (`--seed 42`); one command regenerates identically.

---

## Baselines

| Id | System | Description |
|---|---|---|
| **B1** | Bison/Yacc | Mini-C grammar with `error` productions: `stmt: error ';'`, `block: '{' error '}'`, etc. |
| **B2** | Panic-mode | Synchronize-only: skip to the next sync token, no ranking. |
| **B3** | No-ranking | Full candidate generation + validation, but pick the *first* valid candidate. |

---

## Metrics

| Metric | Definition | Measures |
|---|---|---|
| **Exact-fix rate (Top-1)** | Repaired token stream == original program | H1 |
| **Exact-fix rate (Top-3)** | Original in top-3 ranked candidates | H1 |
| **Edit distance to original** | Token-level Levenshtein when not exact | H1 |
| **Localization error** | Distance (tokens/lines) between reported and true error | Accuracy |
| **Spurious errors** | Reported errors − injected errors | H2 |
| **Tokens discarded** | Original tokens deleted or skipped | Quality |
| **Runtime per error** | Wall-clock ms, averaged over 10 runs | H3 |
| **Total runtime** | Wall-clock ms for the whole file | H3 |

Each metric is computed per-file; the evaluation script produces both a per-file CSV and a summary table.

---

## Ablations

Run SyntaxRecover with one component disabled at a time:

| Ablation | Config change | Purpose |
|---|---|---|
| No progress term | `beta = 0` | How much does progress reward matter? |
| No structure penalty | `gamma = 0` | How much does structure preservation matter? |
| No cost term | `alpha = 0` | Does edit cost contribute? |
| No Sync | `no_sync = true` | Sync as last resort vs. never |
| `K_min = 1` | `K_min = 1` | Effect of lookahead threshold |
| `K_min = 5` | `K_min = 5` | Stricter validation |
| `max_edits = 1` | `max_edits = 1` | Single-edit vs. multi-edit |

---

## Analysis Outputs

- Tables and charts per hypothesis (saved to `eval/results/`).
- Failure analysis: 5–10 cases where recovery chose the wrong repair — documented with root cause.
- Honest statement per hypothesis: **"supported / not supported / partly supported"** with data.

---

## Fair Benchmarking Notes

- Same Mini-C grammar for both SyntaxRecover and Bison (verified identical test inputs).
- Bison error rules documented in `eval/baselines/bison/README.md` (no straw-man).
- All runs on the same machine; timing includes process startup for Bison.
- Config logged with every run (`eval/results/<run_id>/config.json`).
