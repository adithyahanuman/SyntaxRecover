"""
config.py — All tunable parameters for SyntaxRecover.

Load defaults directly, or override from a TOML file via ``Config.from_toml()``.
Every experiment run should log the config it used so results are reproducible.
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Python 3.11+ has tomllib in stdlib; fall back to the tomli backport.
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib          # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]


@dataclass
class Config:
    """All SyntaxRecover parameters.

    Attributes
    ----------
    K_min:
        Minimum tokens a repair must survive validation to be considered valid.
    P_max:
        Progress cap used for normalization in the ranker (``p = P / P_max``).
    max_edits:
        Maximum number of atomic edits composed per error event.
    beam_width:
        Maximum number of partial candidates kept when composing multi-edits.
    backtrack_window:
        How many tokens *before* the error point are also considered for edits.
    delete_span:
        Maximum number of consecutive tokens a single Delete operation may remove.
    alpha:
        Weight for Edit Cost in the score formula.
    beta:
        Weight for Parser Progress (reward) in the score formula.
    gamma:
        Weight for Structure Penalty in the score formula.
    lambda_:
        Extra multiplier applied to structural tokens (``{ } ( )``) in the
        structure penalty.
    placeholder_penalty:
        Extra cost charged when the candidate engine must invent an IDENT or
        literal placeholder.
    suppression_window:
        Tokens after a commit during which follow-on errors are tagged
        ``possibly_secondary`` rather than independent.
    max_errors:
        Hard safety cap: stop after this many errors even if EOF is not reached.
    no_sync:
        Ablation switch — disable the Synchronize operation entirely.
    sync_tokens:
        Set of token type strings that Synchronize may land on.
    """

    # ── Validation thresholds ────────────────────────────────────────────────
    K_min: int = 3
    P_max: int = 20

    # ── Candidate generation ─────────────────────────────────────────────────
    max_edits:        int = 2
    beam_width:       int = 8
    backtrack_window: int = 1
    delete_span:      int = 1

    # ── Score weights ────────────────────────────────────────────────────────
    alpha:               float = 1.0   # edit cost
    beta:                float = 3.0   # progress reward
    gamma:               float = 1.0   # structure penalty
    lambda_:             float = 2.0   # structural token multiplier
    placeholder_penalty: float = 1.0   # extra cost for invented tokens

    # ── Control flow ─────────────────────────────────────────────────────────
    suppression_window: int  = 3
    max_errors:         int  = 100
    no_sync:            bool = False

    # ── Sync landing tokens (str values, matched against TT.value) ───────────
    sync_tokens: list[str] = field(default_factory=lambda: [
        ";", "}", "if", "while", "for", "return", "int", "float", "char", "void"
    ])

    # ────────────────────────────────────────────────────────────────────────
    # Factory / serialization
    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_toml(cls, path: str | Path) -> "Config":
        """Load config from a TOML file, falling back to defaults for any
        missing keys.

        Example TOML::

            K_min = 5
            beta = 4.0
            no_sync = true
        """
        if tomllib is None:
            raise ImportError(
                "tomllib / tomli is required to load TOML configs.  "
                "Install it with: pip install tomli"
            )
        with open(path, "rb") as fh:
            data: dict[str, Any] = tomllib.load(fh)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        """Return all parameters as a plain dict (for logging with each run)."""
        return asdict(self)

    def __repr__(self) -> str:
        pairs = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"Config({pairs})"


# Module-level default instance — import and use directly in tests / quick scripts.
DEFAULT_CONFIG = Config()
