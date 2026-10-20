"""
test_hardening.py — Hardening, Property Tests, Golden Corpus, and Fuzzing (Phase 3.6).

Verifies:
- Property 1: Termination guarantee (never enters infinite loop)
- Property 2: Determinism (identical input produces bit-identical repaired code)
- Property 3: Repaired stream compliance (repaired output parses)
- 32 golden tests covering all error types
- Fuzzing: random perturbations on clean programs never crash the engine
"""

import random
import pytest
from syntaxrecover.tokens import TT, Token
from syntaxrecover.lexer import tokenize
from syntaxrecover.parser_adapter import create_parser_adapter
from syntaxrecover.cli import recover_all
from syntaxrecover.config import Config


@pytest.fixture(scope="module")
def adapter():
    return create_parser_adapter()


# ── Golden Corpus: 32 diverse error programs across all syntactic forms ─────
GOLDEN_CORPUS = [
    # Missing semicolon (1-8)
    "int main() { int a = 10 if (a > 5) { print(a); } }",
    "int main() { int x = 5 return 0; }",
    "int main() { print(42) return 0; }",
    "int main() { int a = 1; int b = 2 return a + b; }",
    "int f() { float y = 3.14 return y; }",
    "int main() { int i = 0; while (i < 5) { i = i + 1 print(i); } }",
    "int main() { for (int i = 0; i < 5; i = i + 1) { print(i) } }",
    "int main() { int a = 1, b = 2 return 0; }",

    # Missing delimiters (parentheses, braces) (9-16)
    "int main() { int x = (3 + 4; return x; }",
    "int main() { if (x > 0 { print(1); } }",
    "int main() { while (i < 10 { i = i + 1; } }",
    "int main() { int y = 2 * (x + 1; return y; }",
    "int main() { print((5 + 3); }",
    "int main() { if (1) { print(1); }",             # unclosed function
    "int main() { while (1) { int a = 1; }",         # unclosed while
    "int main() { { int x = 1; }",                   # unclosed nested block

    # Extraneous delimiters & missing tokens (17-22)
    "int main() { print(1); } }",                    # extra closing brace
    "int main() { int a = ; return a; }",            # missing initializer expression
    "int main() { int a = (1 + 2)); return a; }",    # extra closing paren
    "int main() { print(1); } };",
    "int main() { int 123; return 0; }",             # number literal instead of identifier
    "int main() { int x = 5; } } int y = 10;",

    # Wrong / swapped tokens & operators (23-28)
    "int main() { int a == 5; return a; }",          # == instead of =
    "int main() { int a = 5 = 10; return a; }",
    "int main() { if a > 5 { print(a); } }",         # missing parens around if
    "int main() { while x < 10 { x = x + 1; } }",
    "int main() { return 1 + ; }",                   # missing operand after +
    "int main() { int a = + * 5; return a; }",

    # Multi-error programs (29-32)
    "int main() { int a = 10 if (a > 5 { print(a); } }",
    "int main() { int x = (1 + 2; int y = 3 return x + y; }",
    "int f1() { print(1) return 0; } int f2() { int a = (2; return a; }",
    "int main() { int a = 10 if (1) { int b = (3; return b; } }",
]


class TestGoldenCorpus:
    @pytest.mark.parametrize("idx, src", list(enumerate(GOLDEN_CORPUS)))
    def test_golden_cases_terminate_and_repair(self, adapter, idx, src):
        """Every golden error program must be recovered and result must parse."""
        tokens = tokenize(src)
        result = recover_all(tokens, source=src)

        # Must record at least one repair event
        assert len(result.events) >= 1

        # Repaired source must be non-empty and parse cleanly!
        assert len(result.repaired_source.strip()) > 0
        repaired_tokens = tokenize(result.repaired_source)
        success, tree, err = adapter.parse_tokens(repaired_tokens)
        assert success is True, f"Case {idx} failed to parse after repair: {result.repaired_source}"


class TestProperties:
    def test_determinism_property(self):
        """Property: syntax recovery is completely deterministic across runs."""
        src = "int main() { int a = 10 if (a > 5) { print(a); } int b = (1+2; return 0; }"
        tokens = tokenize(src)

        res1 = recover_all(tokens, source=src)
        res2 = recover_all(tokens, source=src)

        assert len(res1.events) == len(res2.events)
        assert res1.repaired_source == res2.repaired_source
        for e1, e2 in zip(res1.events, res2.events):
            assert e1.chosen == e2.chosen
            assert e1.explanation == e2.explanation

    def test_termination_property_on_arbitrary_garbage(self):
        """Property: engine never enters infinite loops even on complete random garbage."""
        random.seed(42)
        chars = ["@", "#", "$", "%", "^", "&", ";", "}", ")", "int", "10", "ident"]
        for _ in range(20):
            garbage_src = " ".join(random.choices(chars, k=30))
            tokens = tokenize(garbage_src)
            cfg = Config(max_errors=15)
            # Must return without hanging or raising unhandled exceptions
            res = recover_all(tokens, cfg=cfg, source=garbage_src)
            assert isinstance(res.events, list)


class TestFuzzing:
    def test_random_mutations_never_crash_engine(self, adapter):
        """Fuzz testing: inject random deletions and mutations into valid code; engine never crashes."""
        random.seed(1337)
        clean_seed = """
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int x = 10;
            int y = 20;
            if (x < y) {
                print(add(x, y));
            }
            return 0;
        }
        """
        orig_tokens = tokenize(clean_seed)
        assert len(orig_tokens) > 10

        # Run 50 random perturbation iterations
        for _ in range(50):
            mutated = [Token(t.type, t.text, t.line, t.col, t.index) for t in orig_tokens]

            mutation_type = random.choice(["del", "swap", "insert_garbage"])
            if mutation_type == "del" and len(mutated) > 5:
                del_idx = random.randint(0, len(mutated) - 2)
                mutated.pop(del_idx)
            elif mutation_type == "swap" and len(mutated) > 5:
                idx = random.randint(0, len(mutated) - 3)
                mutated[idx], mutated[idx + 1] = mutated[idx + 1], mutated[idx]
            elif mutation_type == "insert_garbage":
                idx = random.randint(0, len(mutated) - 2)
                mutated.insert(idx, Token(TT.ILLEGAL, "@", 1, 1))

            # Re-index
            for i, t in enumerate(mutated):
                t.index = i

            # Must process safely without crashing
            res = recover_all(mutated)
            assert res is not None
            assert isinstance(res.events, list)
