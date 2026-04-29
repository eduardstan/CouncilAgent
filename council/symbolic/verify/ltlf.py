"""L1 verification — LTL_f formula AST and recursive-descent parser.

No external parser libraries (Constitution §8). Grammar:

  expr     ::= weak_until
  weak_until ::= or_expr (('U' | 'W') weak_until)?   # right-associative
  or_expr  ::= and_expr ('||' | '|' | 'or' and_expr)*
  and_expr ::= unary ('&&' | '&' | 'and' unary)*
  unary    ::= '!' unary | 'not' unary | 'X' unary | 'F' unary | 'G' unary | primary
  primary  ::= atom | '(' expr ')'
  atom     ::= [A-Za-z_][A-Za-z0-9_]*
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AST node hierarchy
# ---------------------------------------------------------------------------

class LTLf(ABC):
    """Base class for LTL_f formula AST nodes."""

    @abstractmethod
    def __str__(self) -> str: ...


@dataclass(frozen=True, slots=True)
class Atom(LTLf):
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Neg(LTLf):
    arg: LTLf

    def __str__(self) -> str:
        return f"!{self.arg}"


@dataclass(frozen=True, slots=True)
class And(LTLf):
    left: LTLf
    right: LTLf

    def __str__(self) -> str:
        return f"({self.left} && {self.right})"


@dataclass(frozen=True, slots=True)
class Or(LTLf):
    left: LTLf
    right: LTLf

    def __str__(self) -> str:
        return f"({self.left} || {self.right})"


@dataclass(frozen=True, slots=True)
class Next(LTLf):
    arg: LTLf

    def __str__(self) -> str:
        return f"X({self.arg})"


@dataclass(frozen=True, slots=True)
class Until(LTLf):
    left: LTLf
    right: LTLf

    def __str__(self) -> str:
        return f"({self.left} U {self.right})"


@dataclass(frozen=True, slots=True)
class Finally(LTLf):
    arg: LTLf

    def __str__(self) -> str:
        return f"F({self.arg})"


@dataclass(frozen=True, slots=True)
class Globally(LTLf):
    arg: LTLf

    def __str__(self) -> str:
        return f"G({self.arg})"


@dataclass(frozen=True, slots=True)
class WeakUntil(LTLf):
    left: LTLf
    right: LTLf

    def __str__(self) -> str:
        return f"({self.left} W {self.right})"


@dataclass(frozen=True, slots=True)
class Implies(LTLf):
    left: LTLf
    right: LTLf

    def __str__(self) -> str:
        return f"({self.left} -> {self.right})"


# ---------------------------------------------------------------------------
# SPOT-compatible renderer
# ---------------------------------------------------------------------------

def to_spot_str(f: LTLf) -> str:
    """Render an LTL_f AST to the SPOT ltl2tgba formula string format.

    SPOT uses: ! & | X F G U W, parenthesised infixes.
    This renderer is the bridge used by spot_backend.py.
    """
    match f:
        case Atom(name=n):
            return n
        case Neg(arg=a):
            return f"!{to_spot_str(a)}"
        case And(left=l, right=r):
            return f"({to_spot_str(l)} & {to_spot_str(r)})"
        case Or(left=l, right=r):
            return f"({to_spot_str(l)} | {to_spot_str(r)})"
        case Next(arg=a):
            return f"X({to_spot_str(a)})"
        case Until(left=l, right=r):
            return f"({to_spot_str(l)} U {to_spot_str(r)})"
        case Finally(arg=a):
            return f"F({to_spot_str(a)})"
        case Globally(arg=a):
            return f"G({to_spot_str(a)})"
        case WeakUntil(left=l, right=r):
            return f"({to_spot_str(l)} W {to_spot_str(r)})"
        case Implies(left=l, right=r):
            return f"({to_spot_str(l)} -> {to_spot_str(r)})"
        case _:
            raise ValueError(f"Unknown LTLf node: {type(f)}")


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_KEYWORDS = frozenset({"and", "or", "not"})
_UNARY_KEYWORDS = frozenset({"X", "F", "G", "not"})


def _tokenize(formula: str) -> list[str]:
    """Split formula into tokens: operators, keywords, atoms, and parentheses."""
    tokens: list[str] = []
    i = 0
    n = len(formula)
    while i < n:
        c = formula[i]
        if c.isspace():
            i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif formula[i:i+2] in ("&&", "||", "->"):
            tokens.append(formula[i:i+2])
            i += 2
        elif c in "&|!":
            tokens.append(c)
            i += 1
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (formula[j].isalnum() or formula[j] == "_"):
                j += 1
            tokens.append(formula[i:j])
            i = j
        else:
            raise ValueError(f"Unexpected character {c!r} at position {i} in {formula!r}")
    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> str | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self, expected: str | None = None) -> str:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of formula")
        if expected is not None and tok != expected:
            raise ValueError(f"Expected {expected!r}, got {tok!r}")
        self._pos += 1
        return tok

    def parse(self) -> LTLf:
        node = self._parse_weak_until()
        if self._peek() is not None:
            raise ValueError(f"Unexpected token {self._peek()!r} after complete formula")
        return node

    def _parse_weak_until(self) -> LTLf:
        """weak_until ::= or_expr (('U' | 'W' | '->') weak_until)?  — right-associative."""
        left = self._parse_or()
        tok = self._peek()
        if tok == "U":
            self._consume()
            right = self._parse_weak_until()
            return Until(left=left, right=right)
        if tok == "W":
            self._consume()
            right = self._parse_weak_until()
            return WeakUntil(left=left, right=right)
        if tok == "->":
            self._consume()
            right = self._parse_weak_until()
            return Implies(left=left, right=right)
        return left

    def _parse_or(self) -> LTLf:
        left = self._parse_and()
        while self._peek() in ("||", "|", "or"):
            self._consume()
            right = self._parse_and()
            left = Or(left=left, right=right)
        return left

    def _parse_and(self) -> LTLf:
        left = self._parse_unary()
        while self._peek() in ("&&", "&", "and"):
            self._consume()
            right = self._parse_unary()
            left = And(left=left, right=right)
        return left

    def _parse_unary(self) -> LTLf:
        tok = self._peek()
        if tok in ("!", "not"):
            self._consume()
            return Neg(arg=self._parse_unary())
        if tok == "X":
            self._consume()
            return Next(arg=self._parse_unary())
        if tok == "F":
            self._consume()
            return Finally(arg=self._parse_unary())
        if tok == "G":
            self._consume()
            return Globally(arg=self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> LTLf:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of formula: expected atom or '('")
        if tok == "(":
            self._consume("(")
            node = self._parse_weak_until()
            self._consume(")")
            return node
        if tok == ")":
            raise ValueError("Unexpected ')' without matching '('")
        # Operator tokens that appear here mean the user omitted an operand
        if tok in ("U", "W", "&&", "||", "&", "|"):
            raise ValueError(f"Unexpected operator {tok!r}: missing left operand")
        # Keywords X/F/G must be handled in _parse_unary; reaching here means
        # they appeared as atoms, which we reject
        if tok in ("X", "F", "G"):
            raise ValueError(
                f"Operator {tok!r} must be followed by a formula, not used as an atom"
            )
        # Plain atom
        self._consume()
        return Atom(name=tok)


def parse(formula: str) -> LTLf:
    """Parse an LTL_f formula string into an AST.

    Raises ValueError on syntax errors, empty input, or bare operators.
    """
    stripped = formula.strip()
    if not stripped:
        raise ValueError("Empty formula string")
    tokens = _tokenize(stripped)
    if not tokens:
        raise ValueError("Formula contains no tokens")
    return _Parser(tokens).parse()
