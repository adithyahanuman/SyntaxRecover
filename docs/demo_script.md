# SyntaxRecover — Phase 2 Review Demo Script

*Step-by-step walkthrough script for the Phase 2 review presentation / faculty demo.*

---

## 1. Setup & Environment
Ensure the environment is activated and test suite is green:
```bash
python -m pytest -v
```
*(Shows all 56 tests passing across Lexer, Parser, Diagnoser, Candidates, Sandbox, Ranker, and End-to-End).*

---

## 2. Core Demo: Slide Example Recovery
Run SyntaxRecover on the canonical presentation example:
```bash
python -m syntaxrecover.cli tests/golden/slide_example.mc --repaired repaired.mc --json report.json
```

### What to explain to the faculty:
1. **Error Diagnosis (`diagnose.py`):**
   - The LR parser shifts `int a = 10` and fails at the unexpected keyword `if`.
   - The diagnostic shows line 2, col 16 with a source caret pointer.
   - The expected terminal set shows `{";", ",", "+", "-", "*", "/", "%", "==", "!=", "<", ...}`.

2. **Candidate Generation (`candidates.py`):**
   - The candidate engine synthesizes all possible single-edit repairs:
     - `Insert ';'` before `if`
     - `Delete 'if'`
     - `Replace 'if'` with expected operators/terminators
     - `Synchronize` skipping to `;`

3. **Isolated Sandboxing (`sandbox.py`):**
   - Each candidate is fed to an isolated `ParserState` clone.
   - `Delete 'if'` fails immediately because `(` cannot follow integer literal `10` in Mini-C.
   - `Insert ';'` survives lookahead and parses all 16 subsequent tokens to EOF.

4. **Transparent Ranking (`ranker.py`):**
   - R1 (`Insert ';'`) achieves score `-1.40` (Cost = 1.0, Progress = 16).
   - R47 (`Sync`) gets rejected due to heavy skipped token cost (`cost = 12.0`, score = `32.70`).
   - The engine commits `Insert ';'` and outputs the explanation:
     *"Inserted ';' because the statement grammar requires a statement terminator."*

5. **Formal Verification of Repaired Output:**
```bash
cat repaired.mc
```
Notice the semicolon was cleanly placed and the resulting code is 100% grammatically compliant.
