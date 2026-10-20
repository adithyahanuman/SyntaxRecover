"""
run_small_experiment.py — M3 Milestone Benchmark Run (50 mutated files).

Measures:
- Exact-fix rate (Top-1)
- Parseable repair rate
- Average runtime per error (ms)
- Total errors diagnosed
Outputs summary table and CSV to eval/results/m3_initial_experiment.csv.
"""

import time
import random
import csv
import sys
from pathlib import Path

# Ensure syntaxrecover package is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from syntaxrecover.lexer import tokenize
from syntaxrecover.tokens import TT, Token
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.cli import recover_all


def run_experiment(num_trials: int = 50) -> None:
    random.seed(42)
    adapter = create_parser_adapter()
    valid_dir = Path(__file__).resolve().parent / "corpus" / "valid"
    valid_files = list(valid_dir.glob("*.mc"))
    if not valid_files:
        print("No seed files found!")
        return

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "m3_initial_experiment.csv"

    records = []
    exact_fixes = 0
    parseable_repairs = 0
    total_time_ms = 0.0

    print(f"Starting M3 Benchmark on {num_trials} mutated files...")

    for trial_id in range(1, num_trials + 1):
        seed_path = random.choice(valid_files)
        orig_code = seed_path.read_text(encoding="utf-8")
        orig_tokens = tokenize(orig_code)

        # Non-EOF token indices
        candidates_to_mutate = [i for i, t in enumerate(orig_tokens) if t.type != TT.EOF]
        if not candidates_to_mutate:
            continue

        target_idx = random.choice(candidates_to_mutate)
        target_tok = orig_tokens[target_idx]

        # Mutate: delete or replace
        mut_type = random.choice(["delete", "swap", "replace"])
        mutated_tokens = [Token(t.type, t.text, t.line, t.col, t.index) for t in orig_tokens]

        if mut_type == "delete":
            mutated_tokens.pop(target_idx)
        elif mut_type == "swap" and target_idx + 1 < len(mutated_tokens) - 1:
            mutated_tokens[target_idx], mutated_tokens[target_idx + 1] = mutated_tokens[target_idx + 1], mutated_tokens[target_idx]
        else:
            mutated_tokens[target_idx] = Token(TT.ILLEGAL, "@", target_tok.line, target_tok.col)

        for i, t in enumerate(mutated_tokens):
            t.index = i

        t0 = time.perf_counter()
        res = recover_all(mutated_tokens)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        total_time_ms += elapsed_ms

        # Check parseability of repaired stream
        repaired_tokens = tokenize(res.repaired_source)
        success, _, _ = adapter.parse_tokens(repaired_tokens)
        if success:
            parseable_repairs += 1

        # Check exact fix
        is_exact = False
        if len(res.tokens) == len(orig_tokens):
            is_exact = all(r.type == o.type and r.text == o.text for r, o in zip(res.tokens, orig_tokens))
        if is_exact:
            exact_fixes += 1

        records.append({
            "trial_id": trial_id,
            "seed_file": seed_path.name,
            "mutation": mut_type,
            "injected_token": target_tok.text,
            "repaired_parseable": success,
            "exact_fix": is_exact,
            "errors_reported": len(res.events),
            "runtime_ms": round(elapsed_ms, 2),
        })

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    exact_pct = (exact_fixes / num_trials) * 100.0
    parse_pct = (parseable_repairs / num_trials) * 100.0
    avg_time = total_time_ms / num_trials

    print("\n--- M3 Milestone Initial Experiment Results ---")
    print(f"Total Mutated Files:       {num_trials}")
    print(f"Parseable Repair Rate:     {parse_pct:.1f}% ({parseable_repairs}/{num_trials})")
    print(f"Exact Fix Rate (Top-1):    {exact_pct:.1f}% ({exact_fixes}/{num_trials})")
    print(f"Average Runtime per File:  {avg_time:.2f} ms")
    print(f"Results CSV written to:    {csv_path}\n")


if __name__ == "__main__":
    run_experiment(50)
