"""
cli.py — Command-Line Interface and Recovery Driver for SyntaxRecover.

Implements the central recovery loop (§6 of design.md):
- Drives lexing, diagnosis, candidate generation, sandbox validation, ranking, and commit
- Continuous parsing without resetting the parser loop
- Outputs human-readable diagnostic reports, machine-readable JSON, and repaired code
"""

from __future__ import annotations
import sys
import json
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from syntaxrecover.tokens import TT, Token
from syntaxrecover.config import Config, DEFAULT_CONFIG
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import create_parser_adapter, ParserAdapter, ParserState
from syntaxrecover.diagnose import diagnose, ErrorEvent
from syntaxrecover.candidates import generate_candidates, Candidate, Edit
from syntaxrecover.sandbox import validate_all
from syntaxrecover.ranker import rank_candidates
from syntaxrecover.commit import commit_repair
from syntaxrecover.explain import build_recovery_event, RecoveryEvent


@dataclass
class RecoveryResult:
    """Summary result of a SyntaxRecover run."""
    tokens: List[Token]
    events: List[RecoveryEvent]
    repaired_source: str
    success: bool = True


def reconstruct_source(tokens: List[Token]) -> str:
    """Reconstruct formatted Mini-C source code from a token sequence."""
    out: list[str] = []
    indent_level = 0
    prev_tok: Optional[Token] = None

    for tok in tokens:
        if tok.type == TT.EOF:
            break

        if tok.text == "}":
            indent_level = max(0, indent_level - 1)
            out.append("\n" + ("    " * indent_level) + "}")
            prev_tok = tok
            continue

        if prev_tok is not None and prev_tok.text in (";", "{"):
            out.append("\n" + ("    " * indent_level))

        # Spacing logic
        needs_space = False
        if prev_tok is not None:
            if prev_tok.text not in ("(", "[", "\n") and tok.text not in (";", ",", ")", "]"):
                if prev_tok.is_keyword() or prev_tok.type == TT.IDENT or prev_tok.is_literal():
                    needs_space = True
                elif prev_tok.text in ("=", "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                    needs_space = True
                elif tok.text in ("=", "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                    needs_space = True

        if needs_space and out and not out[-1].endswith(("\n", " ", "    ")):
            out.append(" ")

        out.append(tok.text)

        if tok.text == "{":
            indent_level += 1

        prev_tok = tok

    out.append("\n")
    return "".join(out).lstrip("\n")


def recover_all(
    tokens: List[Token],
    cfg: Optional[Config] = None,
    source: Optional[str] = None
) -> RecoveryResult:
    """Run full syntax error recovery pipeline on token stream."""
    if cfg is None:
        cfg = DEFAULT_CONFIG

    adapter = create_parser_adapter()
    state = adapter.initial_state()
    i = 0
    events: List[RecoveryEvent] = []
    last_commit_idx = -999

    while i < len(tokens):
        tok = tokens[i]

        if tok.type == TT.EOF and state.at_accept():
            break

        if state.feed(tok):
            i += 1
            continue

        # Syntax error encountered at index i
        err_ev = diagnose(state, tokens, i, source=source)
        all_cands = generate_candidates(err_ev, state, tokens, cfg)
        evaluated_cands = validate_all(all_cands, state, tokens, cfg)
        ranked = rank_candidates(evaluated_cands, cfg)

        if not ranked:
            # Emergency fallback: synchronize to EOF
            skip_count = max(1, len(tokens) - 1 - i)
            fallback_cand = Candidate(
                id=f"R{len(evaluated_cands) + 1}",
                description="emergency sync to EOF",
                edits=[Edit(kind="SYNC", at_index=i, count=skip_count)],
                cost=1.0 + float(skip_count),
                valid=True,
                progress=1,
            )
            evaluated_cands.append(fallback_cand)
            best = fallback_cand
        else:
            best = ranked[0]

        is_secondary = (i - last_commit_idx) <= cfg.suppression_window
        rec_ev = build_recovery_event(
            event_id=len(events) + 1,
            error=err_ev,
            all_candidates=evaluated_cands,
            chosen=best,
            possibly_secondary=is_secondary
        )
        events.append(rec_ev)

        # Commit winning repair
        state, tokens, i = commit_repair(best, state, tokens)
        last_commit_idx = i

        if len(events) >= cfg.max_errors:
            break

    repaired_code = reconstruct_source(tokens)
    return RecoveryResult(
        tokens=tokens,
        events=events,
        repaired_source=repaired_code,
        success=len(events) == 0 or state.at_accept(),
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="syntaxrecover",
        description="Grammar-Guided & Explainable Syntax Error Recovery for Mini-C"
    )
    parser.add_argument("source", help="Mini-C source file (.mc)")
    parser.add_argument("--json", dest="json_out", help="Write machine-readable recovery log to JSON file")
    parser.add_argument("--repaired", dest="repaired_out", help="Write repaired source to FILE")
    parser.add_argument("--ast", action="store_true", help="Dump AST (synthetic nodes flagged)")
    parser.add_argument("--config", dest="config_path", help="Load config overrides from TOML file")
    parser.add_argument("--no-sync", action="store_true", help="Disable Synchronize operation (ablation)")

    args = parser.parse_args(argv)

    src_path = Path(args.source)
    if not src_path.exists():
        sys.stderr.write(f"Error: file not found: {args.source}\n")
        return 2

    source_text = src_path.read_text(encoding="utf-8")

    # Load config
    if args.config_path:
        cfg = Config.from_toml(args.config_path)
    else:
        cfg = Config()

    if args.no_sync:
        cfg.no_sync = True

    # Tokenize
    tokens = tokenize(source_text)

    # Recover
    result = recover_all(tokens, cfg=cfg, source=source_text)

    # Print human diagnostics to terminal
    for ev in result.events:
        print(ev.format_text())
        print()

    # Write JSON output if requested
    if args.json_out:
        log_data = {
            "source_file": str(src_path),
            "total_errors": len(result.events),
            "events": [e.to_dict() for e in result.events],
            "repaired_source": result.repaired_source,
        }
        Path(args.json_out).write_text(json.dumps(log_data, indent=2), encoding="utf-8")

    # Write repaired source if requested
    if args.repaired_out:
        Path(args.repaired_out).write_text(result.repaired_source, encoding="utf-8")

    # Exit code: 0 = no errors, 1 = errors repaired, 2 = failure
    if len(result.events) == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
