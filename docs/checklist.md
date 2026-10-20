# SyntaxRecover — Project Checklist

Work top to bottom. **Do not start a phase until the previous phase's milestone is true.** Every task has a *Done when* line so you know exactly when to tick it. Durations are estimates for two people; stretch or compress them to match your actual review dates.

Legend: `[ ]` to do, `[x]` done. **A** = Adithya, **S** = Sai (suggested split, swap freely).

---

## Phase 0: Decisions and Setup  *(about 3 days, before Phase 2)*

- [x] **0.1 Choose the parser approach** (A and S together)
  Option A: Lark LALR interactive parser behind the `ParserState` interface. Option B: your own table-driven parser. Check with your faculty whether a hand-built parser is required for marks.
  *Done when:* decision written at the top of `design.md` §12.
- [x] **0.2 Choose the implementation language** (default Python 3)
  *Done when:* decision recorded, and you know how you will call Bison for the baseline (usually a C binary run from Python).
- [x] **0.3 Create the repo** with the folder layout from `design.md` §9, `.gitignore`, virtualenv, `requirements.txt`
  *Done when:* both of you can clone, install and run `pytest` green on a trivial test.
- [x] **0.4 Agree git workflow:** branch per task, PR or at least a review before merging to `main`, commit messages that name the checklist item
  *Done when:* written in `README.md`.
 - [ ] **0.5 Install Bison/Flex** (or confirm they work on your machine or WSL)
   *Done when:* a "hello" Bison grammar builds and runs.
- [x] **0.6 Set up a shared task tracker** (this file plus GitHub Issues or a simple board)

**Milestone M0:** repo builds, tests run, decisions recorded.

---

## Review 1 Closure: Specs on Paper  *(about 1 week)*

You already have the literature review, problem statement, objectives and architecture slides. This phase turns them into precise specifications you can code against.

- [x] **R1.1 Finalize the Mini-C grammar** (A)
  Start from `design.md` §3. Resolve every ambiguity (dangling else, operator precedence, `for` init forms).
  *Done when:* saved as `docs/minic_grammar.md`; 10 valid and 10 invalid sample programs each labelled legal or illegal.
- [x] **R1.2 Write the ranking specification** (S)
  Define Edit Cost, Parser Progress Distance, Source Structure Preservation, the score formula, default weights, tie-break order.
  *Done when:* `docs/ranking_spec.md` includes the three slide candidates (R1, R2, R3) calculated by hand with matching numbers.
- [x] **R1.3 Define the candidate generation rules precisely** (A)
  For each of Insert, Delete, Replace, Sync: exact trigger, position, cost, how placeholders work.
  *Done when:* a teammate could implement it from the document alone.
- [x] **R1.4 Hand-trace three errors end to end** (A and S)
  Pick: missing `;` (slide example), missing `)`, extra `}`. Write each step: error event → candidates → validation → ranking → log text.
  *Done when:* three traces saved in `docs/`; they become your first golden tests.
- [x] **R1.5 Define the log format** (S)
  Text layout and the JSON schema from `design.md` §5.8.
  *Done when:* schema file exists and one example log is written by hand.
- [x] **R1.6 Plan the evaluation** (S)
  Metrics, baselines, mutation types, dataset size, hypotheses H1 to H3.
  *Done when:* `docs/evaluation_plan.md` exists.
- [x] **R1.7 Mention the risks** from `design.md` §13 in your notes, with the wording you will use for each claim
  *Done when:* you have a one-line answer ready for "is the ranking really non-heuristic?" and "what does 100% compliance mean?"

**Milestone M1:** specs complete; the slide example can be calculated by hand with the same numbers as the deck.

---

## Phase 2: Lexer, Parser and Candidate Engine  *(about 3 weeks)*

### 2.1 Lexer (A) — about 3 days
- [x] Token types and `Token` class with line, col, index, synthetic flag
- [x] Skip whitespace, `//` and `/* */` comments
- [x] Keywords vs identifiers, int/float/char/string literals, all operators and delimiters
- [x] Unknown characters → `ILLEGAL` token (never crash)
- [x] Return a list (random access), ending with `EOF`
- [x] Tests: every token type, positions, unterminated comment, empty file

*Done when:* all sample programs tokenize; line/col are correct on a multi-line test.

### 2.2 Grammar and Parser Adapter (S) — about 5 days
- [x] Encode Mini-C in the parser tool's grammar format (`grammar/minic.lark`)
- [x] Resolve all shift/reduce conflicts deliberately (dangling else, precedence)
- [x] Implement `ParserState` interface: `clone`, `feed`, `expected`, `at_accept`
- [x] Build AST nodes (or a tree) with positions; support a `synthetic` flag
- [x] Verify `clone()` really isolates state (feeding the clone must not change the original)
- [x] Verify `expected()` is correct on 10 hand-picked states (after `int a = 10` expect `;` `,` and operators)
- [x] Tests: every valid sample parses; every invalid sample fails at the expected token

*Done when:* valid programs parse to ASTs; `feed` returns False on bad input without changing state; `expected()` matches your hand-computed sets.

### 2.3 Error Diagnoser (A) — about 2 days
- [ ] On the first `feed` failure, build `ErrorEvent` (token, previous token, line, col, expected set, optional context)
- [ ] Handle `EOF`-time errors (unexpected end of file)
- [ ] Pretty-print the source line with a caret
- [ ] Tests: slide example gives unexpected `if` at line 2, expected set contains `;`

*Done when:* three different errors produce correct `ErrorEvent`s.

### 2.4 Candidate Generator (A and S) — about 6 days
- [ ] **Insert** from the expected set, including placeholders for `IDENT` / literals with penalty
- [ ] **Delete** (single token first, then `delete_span`)
- [ ] **Replace** from the expected set
- [ ] **Backtrack window:** also generate candidates positioned before the previous token
- [ ] **Compose** up to 2 edits with a beam; **deduplicate** equivalent candidates
- [ ] Give each candidate an id (R1, R2, …) and a one-line description
- [ ] Tests: slide example yields at least the Insert `;`, Delete `if`, and a Replace; candidate count stays bounded

*Done when:* candidate lists are correct and bounded on all golden inputs.

### 2.5 End-to-End Skeleton (A and S) — about 3 days
- [ ] Controller loop from `design.md` §6 with a **temporary** policy: take the first valid candidate (no ranking yet)
- [ ] Simple commit: apply edits, resume
- [ ] Simple Sync fallback (skip to `;` or `}`) so the loop always terminates
- [ ] CLI: `syntaxrecover file.mc` prints repaired source

*Done when:* the slide example `int main() { int a = 10 if (a > 5) { print(a); } }` is repaired to a parseable program.

**Milestone M2 (Phase 2 review demo):**
- [ ] Lexer + parser working on a sample set
- [ ] Error diagnosis shows unexpected vs expected tokens
- [ ] Candidates generated for 3 different errors
- [ ] Slide example repaired end to end
- [ ] Short demo script prepared and rehearsed

---

## Phase 3: Validation, Ranking, Logging, Resume  *(about 3 weeks)*

### 3.1 Validation Sandbox (S) — about 5 days
- [ ] Clone-and-replay over a *virtual* token view (real stream untouched)
- [ ] Compute `progress` up to `P_max`; apply `K_min` lookahead rule
- [ ] Accept stream that reaches `EOF` cleanly even if shorter than `K_min`
- [ ] Record failure reasons ("parser stalls after 0 tokens", "re-triggers error at token X")
- [ ] Test that the live parser state is bit-for-bit unchanged after validating 100 candidates
- [ ] Tests: R2 (delete `if`) is invalid; R1 is valid with progress close to the hand calculation

*Done when:* sandbox results match your hand-computed numbers from R1.4.

### 3.2 Ranker (A) — about 4 days
- [ ] Implement Edit Cost, Progress, Structure penalty
- [ ] Combine into the score; deterministic tie-break
- [ ] Load weights from config
- [ ] Tests: the three slide candidates rank R1 < R3 with the documented numbers; tie-break gives identical order across 100 runs
- [ ] Property test: ranking is a total order (no ties left unresolved)

*Done when:* ranker output equals `docs/ranking_spec.md` worked examples.

### 3.3 Synchronize Operation, done properly (A and S) — about 5 days
*This is the hardest piece; give it its own time.*
- [ ] Skip to the next sync token (`;`, `}`, statement-start keywords)
- [ ] `unwind_to_sync`: pop parser state until the sync token can be accepted
- [ ] Guarantee progress: always consumes at least one token; worst case skips to `EOF`
- [ ] Cost = 1 + skipped tokens; structure penalty counts skipped tokens
- [ ] Tests: unbalanced braces, garbage in the middle of a function, error right before `EOF`

*Done when:* Sync never loops forever and always leaves a state that parses on.

### 3.4 Commit, Resume and Cascade Guard (A) — about 3 days
- [ ] Apply the winning edits to the real token list and live parser
- [ ] Mark inserted tokens `synthetic`; propagate to AST nodes
- [ ] Never reset the parser between errors
- [ ] Termination guard (`max_errors`, must consume at least one original token per commit)
- [ ] Suppression window: tag follow-on errors `possibly_secondary`
- [ ] Tests: files with 2, 3 and 5 errors give 2, 3 and 5 independent events

*Done when:* multi-error files are diagnosed completely in one run.

### 3.5 Explainable Logger (S) — about 4 days
- [ ] `RecoveryEvent` records and JSON serialization
- [ ] Text renderer with caret, expected set, all candidates with scores, chosen repair, reason
- [ ] Template table for explanations keyed by (operation, token, context)
- [ ] `--json` and `--repaired` outputs
- [ ] Tests: golden log for the slide example matches your hand-written log from R1.5

*Done when:* the output for the slide example contains the same information as slides "Candidate Ranking Matrix" and "Explainable Diagnostic Logs".

### 3.6 Hardening (A and S) — about 3 days
- [ ] Property tests: recovery terminates; repaired stream parses; same input gives same output
- [ ] 30+ golden tests across error types
- [ ] Fuzz: random token deletions/insertions on valid programs never crash the engine
- [ ] Profile; remove obvious hot spots (state cloning cost, repeated expected-set computation)

*Done when:* test suite green; no crashes in a 10,000-input fuzz run.

**Milestone M3 (Phase 3 review demo):**
- [ ] Sandbox + ranking + logger working together
- [ ] Live demo: broken file in, ranked candidates and explanation out, repaired file out
- [ ] Multi-error file handled in a single run
- [ ] First numbers from a small experiment (even 50 files) to show the direction of results

---

## Final Review: Benchmarking and Evaluation  *(about 3 weeks)*

### F1 Mutation Dataset (S) — about 4 days
- [ ] Seed corpus: 40+ valid Mini-C programs
- [ ] Mutator: delete token, insert token, replace token, swap adjacent; 1/2/3 errors per file
- [ ] Store ground truth (original file and injected edits) alongside each mutant
- [ ] Fixed random seed; dataset is regenerable
- [ ] 1,000+ mutated files, balanced across error types

*Done when:* one command regenerates the dataset identically.

### F2 Baselines (A) — about 5 days
- [ ] Mini-C Lex/Yacc grammar for Bison with sensible `error` productions
- [ ] Runner that records Bison's reported errors, positions and exit status
- [ ] Own panic-mode baseline (Sync only)
- [ ] No-ranking baseline (first valid candidate)
- [ ] Document the Bison error rules you chose (so it is not a straw man)

*Done when:* all baselines run on the full dataset without manual steps.

### F3 Metrics (S) — about 3 days
- [ ] Exact-fix rate (Top-1, Top-3), edit distance to original, localization error
- [ ] Spurious error count, tokens discarded, runtime per error
- [ ] Validate each metric on 5 hand-checked examples

*Done when:* `metrics.py` outputs a per-file CSV and a summary table.

### F4 Experiments (A and S) — about 5 days
- [ ] Run SyntaxRecover vs all baselines on the dataset
- [ ] Ablations: drop each ranking term, vary `K_min`, `P_max`, `max_edits`, disable Sync
- [ ] Repeat timing runs to get stable numbers
- [ ] Keep raw results and config for every run

*Done when:* results exist for H1, H2 and H3.

### F5 Analysis and Plots (S) — about 3 days
- [ ] Tables and charts per hypothesis
- [ ] Failure analysis: collect 5 to 10 cases where recovery chose a wrong repair and explain why
- [ ] State clearly where SyntaxRecover loses to a baseline, if it does

*Done when:* each hypothesis has a clear "supported / not supported / partly" statement with data.

### F6 Report, Slides and Demo (A and S) — about 5 days
- [ ] Update `design.md` to match what was actually built
- [ ] Report: motivation, related work, design, implementation, evaluation, limitations
- [ ] Slides (reuse the Review 1 style) with the final results
- [ ] Demo script: one broken file → log → repaired file → benchmark chart
- [ ] Rehearse; prepare answers for the risks in `design.md` §13

### F7 Freeze (A) — about 1 day
- [ ] Final README with install and usage
- [ ] Tag `v1.0`; archive results and the dataset seed

**Milestone M4 (Final Review):**
- [ ] Reproducible experiment run (one command)
- [ ] Results against Bison and ablations
- [ ] Honest limitations slide
- [ ] Working demo

---

## Suggested Timeline

| Weeks | Work |
|---|---|
| 0 | Phase 0 |
| 1 | Review 1 closure (M1) |
| 2–4 | Phase 2 (M2) |
| 5–7 | Phase 3 (M3) |
| 8–10 | Final Review work (M4) |

Slide in a 1-week buffer before each review; the usual overruns are the parser adapter (2.2), Sync (3.3) and the Bison baseline (F2).

---

## Working Rhythm (each task)
1. Pick one unchecked item and say who owns it.
2. Write the test first (or immediately after).
3. Implement until the test passes.
4. Run the whole suite.
5. Commit with the task id in the message (for example `3.2 ranker: tie-break`).
6. Tick the box here.

---

## Review Preparation Checklists

**Before every review**
- [ ] Demo runs on a clean clone
- [ ] Backup recording of the demo
- [ ] Both of you can explain every module
- [ ] Slides match the code that exists today

**Questions to be ready for**
- [ ] Why is this better than Bison `error` rules? (answer with H1 and H2 numbers)
- [ ] What does "100% grammar compliance" actually guarantee?
- [ ] How are the ranking weights chosen, and is ranking really non-heuristic?
- [ ] What happens when the error is detected far from the real mistake?
- [ ] What is the worst-case cost of candidate generation, and how is it bounded?
