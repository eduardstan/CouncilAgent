"""Tests for council/symbolic/verify/ltlf.py — LTL_f AST and parser."""

import pytest

from council.symbolic.verify.ltlf import (
    And,
    Atom,
    Finally,
    Globally,
    Implies,
    Neg,
    Next,
    Or,
    Until,
    WeakUntil,
    parse,
    to_spot_str,
)

# ---------------------------------------------------------------------------
# Round-trip idempotence: to_spot_str(parse(s)) == to_spot_str(parse(to_spot_str(parse(s))))
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula", [
    # Atoms
    "a",
    "is_vote",
    "has_evidence",
    # Negation
    "!a",
    "!is_concede",
    # Conjunction
    "a && b",
    "a & b",
    "a and b",
    # Disjunction
    "a || b",
    "a | b",
    "a or b",
    # Next
    "X(a)",
    "X(is_propose)",
    # Finally / Eventually
    "F(a)",
    "F is_vote",
    # Globally
    "G(a)",
    "G !is_concede",
    # Until (right-associative)
    "a U b",
    "a U b U c",
    # Weak Until
    "a W b",
    "a W b W c",
    # Implication
    "a -> b",
    "a -> b -> c",
    # Named property formulae
    "G(is_vote -> F(is_propose))",
    "G(is_propose -> F(is_challenge || is_vote))",
    "G(is_vote -> (!(! is_challenge) U is_challenge))",
    "F(is_challenge && F(is_vote))",
    "G(!is_propose || F(is_challenge || is_vote))",
    # Nested
    "G(!a && F(b || c))",
    "X(G(a U b))",
    "!(a && b) || c",
])
def test_round_trip_idempotent(formula: str) -> None:
    """to_spot_str is idempotent: a second parse+render produces the same string."""
    first = to_spot_str(parse(formula))
    second = to_spot_str(parse(first))
    assert first == second, f"Round-trip failed for {formula!r}: {first!r} != {second!r}"


# ---------------------------------------------------------------------------
# Structural / associativity tests
# ---------------------------------------------------------------------------

def test_until_right_associative() -> None:
    """A U B U C is parsed as A U (B U C)."""
    result = parse("A U B U C")
    assert isinstance(result, Until)
    assert result.left == Atom("A")
    assert isinstance(result.right, Until)
    assert result.right.left == Atom("B")
    assert result.right.right == Atom("C")


def test_implies_right_associative() -> None:
    """a -> b -> c is parsed as a -> (b -> c)."""
    result = parse("a -> b -> c")
    assert isinstance(result, Implies)
    assert result.left == Atom("a")
    assert isinstance(result.right, Implies)
    assert result.right.left == Atom("b")
    assert result.right.right == Atom("c")


def test_and_left_associative() -> None:
    """a && b && c parses left-associatively: (a && b) && c."""
    result = parse("a && b && c")
    assert isinstance(result, And)
    assert isinstance(result.left, And)
    assert result.left.left == Atom("a")
    assert result.left.right == Atom("b")
    assert result.right == Atom("c")


def test_or_left_associative() -> None:
    """a || b || c parses left-associatively: (a || b) || c."""
    result = parse("a || b || c")
    assert isinstance(result, Or)
    assert isinstance(result.left, Or)
    assert result.left.left == Atom("a")


def test_neg_globally_nesting() -> None:
    """!G(a) parses as Neg(Globally(Atom('a')))."""
    result = parse("!G(a)")
    assert isinstance(result, Neg)
    assert isinstance(result.arg, Globally)
    assert result.arg.arg == Atom("a")


def test_finally_atom() -> None:
    result = parse("F is_vote")
    assert isinstance(result, Finally)
    assert result.arg == Atom("is_vote")


def test_globally_neg_atom() -> None:
    result = parse("G !is_concede")
    assert isinstance(result, Globally)
    assert isinstance(result.arg, Neg)
    assert result.arg.arg == Atom("is_concede")


def test_next_wraps_atom() -> None:
    result = parse("X(is_propose)")
    assert isinstance(result, Next)
    assert result.arg == Atom("is_propose")


def test_weak_until_right_associative() -> None:
    """a W b W c is parsed as a W (b W c)."""
    result = parse("a W b W c")
    assert isinstance(result, WeakUntil)
    assert result.left == Atom("a")
    assert isinstance(result.right, WeakUntil)


def test_implies_parsed_correctly() -> None:
    result = parse("a -> b")
    assert isinstance(result, Implies)
    assert result.left == Atom("a")
    assert result.right == Atom("b")


# ---------------------------------------------------------------------------
# Operator alias tests
# ---------------------------------------------------------------------------

def test_and_keyword_alias() -> None:
    """'a and b' produces the same AST as 'a && b'."""
    assert parse("a and b") == parse("a && b")


def test_and_single_amp_alias() -> None:
    assert parse("a & b") == parse("a && b")


def test_or_keyword_alias() -> None:
    assert parse("a or b") == parse("a || b")


def test_or_single_pipe_alias() -> None:
    assert parse("a | b") == parse("a || b")


def test_not_keyword_alias() -> None:
    assert parse("not a") == parse("!a")


# ---------------------------------------------------------------------------
# Named property formulae — must parse without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula", [
    "F is_vote",
    "G !is_concede",
    "G(is_vote -> F(is_propose))",
    "G(is_propose -> F(is_challenge || is_vote))",
    "G(is_vote -> (!(! is_challenge) U is_challenge))",
    "F(is_challenge && F(is_vote))",
    "G(!is_propose || F(is_challenge || is_vote))",
    "G(is_vote -> (is_challenge || (! is_vote) U is_challenge))",
    "F(is_propose && F(is_challenge))",
    "G(is_vote -> F(is_challenge || is_vote))",
])
def test_named_property_formulae_parse(formula: str) -> None:
    """Every named property formula must parse without raising."""
    node = parse(formula)
    assert node is not None


# ---------------------------------------------------------------------------
# to_spot_str output shape tests
# ---------------------------------------------------------------------------

def test_to_spot_str_atom() -> None:
    assert to_spot_str(Atom("is_vote")) == "is_vote"


def test_to_spot_str_neg() -> None:
    assert to_spot_str(Neg(Atom("a"))) == "!a"


def test_to_spot_str_and_uses_single_amp() -> None:
    result = to_spot_str(And(Atom("a"), Atom("b")))
    assert "&" in result and "&&" not in result


def test_to_spot_str_or_uses_single_pipe() -> None:
    result = to_spot_str(Or(Atom("a"), Atom("b")))
    assert "|" in result and "||" not in result


def test_to_spot_str_implies() -> None:
    result = to_spot_str(Implies(Atom("a"), Atom("b")))
    assert "->" in result


# ---------------------------------------------------------------------------
# Parse error cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_formula", [
    "",           # empty
    "(",          # unmatched paren
    "A &&",       # incomplete binary
    "U B",        # missing left operand for U (U is parsed as an atom — but then no closing)
    ")",          # unexpected close paren
])
def test_parse_errors(bad_formula: str) -> None:
    with pytest.raises(ValueError):
        parse(bad_formula)


def test_parse_error_bare_f_operator() -> None:
    """Bare 'F' at end of input raises ValueError."""
    with pytest.raises(ValueError):
        parse("F")


def test_parse_error_extra_token() -> None:
    """'a b' (two atoms with no operator) raises ValueError."""
    with pytest.raises(ValueError):
        parse("a b")
