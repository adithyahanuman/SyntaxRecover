# SyntaxRecover — Risk Management & Reviewer Q&A

*Prepared one-line answers and detailed responses for questions likely to be challenged by reviewers (§13 of `design.md`).*

---

### Q1: Is the ranking really "non-heuristic"?
**One-line answer:**
> *"The ranking is transparent, deterministic, and parameterized—not heuristic black magic—with every metric (cost, progress, structure) mathematically defined and weights justified via ablation studies."*

**Detailed explanation:**
Unlike ad-hoc heuristics or opaque ML weights, SyntaxRecover scores candidates using formal language properties:
- Edit distance (number of elementary transformations)
- Parser progress (tokens consumed under formal grammar transitions)
- Structural delimiter conservation
Every tie-break is fully deterministic, ensuring identical inputs produce bit-identical recovery results.

---

### Q2: What does "guarantees 100% formal grammar compliance" actually mean?
**One-line answer:**
> *"It guarantees that the synthesized, repaired token stream is 100% syntactically valid and strictly parseable by the grammar, not that it clairvoyantly guesses the programmer's intent in all cases."*

**Detailed explanation:**
Every committed repair is verified inside an isolated parser sandbox before application. A repair cannot be selected unless the sandbox proves lookahead survival (`progress >= K_min` or clean EOF accept). Exact semantic fidelity to the programmer's intent is evaluated separately as Top-1 and Top-3 exact-fix accuracy.

---

### Q3: What happens when the error detection point is not the true error location?
**One-line answer:**
> *"SyntaxRecover couples an 'insert before offending token' rule with a configurable backtrack window (`b = 1`), enabling repairs to be positioned before the preceding token when late error detection occurs."*

**Detailed explanation:**
In LR parsers, missing semicolons or unmatched delimiters are often shifted until the subsequent statement's initial token triggers an invalid action. By evaluating candidate edits both at `index` and `index - 1`, SyntaxRecover routinely recovers the true omission point.

---

### Q4: How is candidate combinatorial explosion prevented for multi-edits?
**One-line answer:**
> *"We bound candidate generation with a beam search (`beam_width = 8`), cap maximum composed edits at `max_edits = 2`, and aggressively prune redundant or equivalent token streams."*

---

### Q5: How do placeholders avoid introducing arbitrary code?
**One-line answer:**
> *"Placeholders (e.g., `__id__`, `0`) incur an explicit placeholder penalty (`+1.0` cost) and are explicitly flagged as synthetic tokens in the AST and diagnostic logs."*
