# SyntaxRecover

**Grammar-Guided & Explainable Syntax Error Recovery for Mini-C**

---

## Overview

SyntaxRecover is a syntax error recovery engine for the Mini-C language. Instead of stopping at the first error or using crude panic-mode recovery, it:

1. Asks the parser what it *expected* at the error point
2. Generates **candidate repairs** (Insert, Delete, Replace, Synchronize)
3. **Validates** each candidate in a sandboxed clone of the parser state
4. **Ranks** survivors with transparent, documented metrics
5. **Commits** the best repair and writes a **human-readable explanation**

## Design Decisions (Phase 0 — §12)

| Decision | Choice | Why |
|---|---|---|
| **Parser** | **Option A: Lark LALR** behind the `ParserState` interface | `clone` / `feed` / `expected` exist out of the box; fastest path to a working engine |
| **Language** | **Python 3.12** | Fast iteration, easy experiment scripts and plots |
| **Ranking** | Weighted score with deterministic tie-break | Simple, explainable, tunable |
| **Validation** | Clone-and-replay sandbox | Cannot corrupt live state |
| **Baseline** | Real Bison build (via subprocess) | Credible comparison |
| **Output** | Text log + JSON + repaired source | Human and machine readable |

---

## Quick Start

```bash
# 1. Clone and set up the environment
git clone <repo-url> syntaxrecover
cd syntaxrecover
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the test suite
pytest

# 4. Run on a Mini-C file
python -m syntaxrecover.cli prog.mc
python -m syntaxrecover.cli prog.mc --json out.json
python -m syntaxrecover.cli prog.mc --repaired out.mc
python -m syntaxrecover.cli prog.mc --ast
```

---

## CLI Usage

```
usage: syntaxrecover [-h] [--json JSON] [--repaired REPAIRED] [--ast]
                     [--config CONFIG] [--no-sync]
                     source

positional arguments:
  source             Mini-C source file (.mc)

options:
  --json JSON        Write machine-readable recovery log to JSON file
  --repaired FILE    Write repaired source to FILE
  --ast              Dump AST (synthetic nodes flagged)
  --config CFG       Load config overrides from TOML file
  --no-sync          Disable Synchronize (ablation)
```

**Exit codes:** `0` = no errors, `1` = errors found and repaired, `2` = internal failure.

---

## Project Structure

```
syntaxrecover/
├── README.md
├── requirements.txt
├── docs/
│   ├── design.md
│   ├── checklist.md
│   ├── minic_grammar.md
│   ├── ranking_spec.md
│   └── evaluation_plan.md
├── grammar/
│   └── minic.lark
├── syntaxrecover/
│   ├── tokens.py
│   ├── lexer.py
│   ├── ast_nodes.py
│   ├── parser_adapter.py
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
│   ├── corpus/valid/
│   ├── mutator.py
│   ├── baselines/
│   │   ├── bison/
│   │   └── panic_mode.py
│   ├── metrics.py
│   ├── run_experiments.py
│   └── results/
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_diagnose.py
    ├── test_candidates.py
    ├── test_sandbox.py
    ├── test_ranker.py
    ├── test_commit.py
    ├── test_explain.py
    └── golden/
```

---

## Git Workflow

- **Branch naming:** `task/<checklist-id>-short-description`
  - Examples: `task/2.1-lexer`, `task/2.2-parser-adapter`, `task/3.2-ranker`
- **Commit messages:** always include the checklist item ID
  - Example: `2.1 lexer: add ILLEGAL token for unknown chars`
- **Merging:** PR (or at minimum a review) before merging to `main`
- **Main branch:** always green (all tests passing)
- **Checklist item owners:** **A** = Adithya, **S** = Sai (swap freely)

---

## Configuration

All parameters can be overridden via a TOML config file (`--config cfg.toml`):

| Parameter | Default | Meaning |
|---|---|---|
| `K_min` | 3 | Minimum tokens a repair must survive |
| `P_max` | 20 | Progress cap for normalization |
| `max_edits` | 2 | Atomic edits composed per error |
| `beam_width` | 8 | Partial candidates kept during composition |
| `alpha` | 1.0 | Edit cost weight |
| `beta` | 3.0 | Progress reward weight |
| `gamma` | 1.0 | Structure penalty weight |
| `lambda_` | 2.0 | Structural token multiplier |
| `max_errors` | 100 | Safety cap on errors per file |

---

## Hypotheses Under Test

- **H1:** Ranked, validated repairs identify the programmer's intended fix more often than panic-mode recovery (Bison `error` rules).
- **H2:** SyntaxRecover reports fewer spurious (cascading) errors than the baselines on multi-error files.
- **H3:** The overhead per error is small enough for interactive use (target: milliseconds on files of a few hundred lines).

---

## Authors

- **Adithya** — Lexer, Diagnoser, Candidate Generator, Ranker, Commit/Resume
- **Sai** — Grammar/Parser Adapter, Sandbox, Logger, Evaluation
