"""Notacion de dados y su evaluacion.

Cubre los codigos del reglamento de Cuatro contra la Oscuridad:

    d6        2d6       3d6+2     d6-1
    d6xd6     3d6x15    d6x50               (multiplicacion)
    d66                                     (decenas y unidades)
    d6+N      d6+1/2N   d6+N/2              (N = variable de contexto, p.ej. nivel)

Cada tirada devuelve un `RollResult` con la traza completa: que dados salieron,
cuales explotaron y como se compuso el total. Esa traza es lo que luego se
muestra al jugador y lo que se guarda en el registro de la partida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .rng import RandomSource

# --------------------------------------------------------------------------- #
# Resultados
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DieRoll:
    """Un dado concreto ya lanzado. Varias caras = exploto."""

    faces: int
    rolls: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.rolls)

    @property
    def exploded(self) -> bool:
        return len(self.rolls) > 1

    def __str__(self) -> str:
        if self.exploded:
            return f"d{self.faces}[{'+'.join(map(str, self.rolls))}={self.total}]"
        return f"d{self.faces}[{self.rolls[0]}]"


@dataclass(frozen=True)
class RollResult:
    """Total mas la traza de como se obtuvo."""

    total: int
    expression: str
    detail: str
    dice: tuple[DieRoll, ...] = ()

    @property
    def exploded(self) -> bool:
        return any(d.exploded for d in self.dice)

    def __int__(self) -> int:
        return self.total

    def __str__(self) -> str:
        return f"{self.expression} = {self.detail} = {self.total}"


# --------------------------------------------------------------------------- #
# Analisis sintactico
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(
    r"""
    (?P<FRACVAR> \d+ \s* / \s* \d+ \s* [A-Za-z_]\w* )   # 1/2N
  | (?P<DICE>    \d* \s* [dD] \s* \d+ )                 # 2d6, d6, d66
  | (?P<NUMBER>  \d+ )
  | (?P<OP>      [-+x*/()] )                          # antes que IDENT: "x" es producto
  | (?P<IDENT>   [A-Za-z_]\w* )
  | (?P<SPACE>   \s+ )
    """,
    re.VERBOSE,
)


# Un d6 legitimo no explota 100 veces seguidas (probabilidad 6^-100). Si pasa,
# la fuente de azar esta rota, y es mejor un error que un cuelgue.
MAX_EXPLOSIONES = 100


class DiceError(ValueError):
    """Expresion de dados invalida, o azar imposible."""


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise DiceError(f"no entiendo {text[pos]!r} en {text!r}")
        kind = match.lastgroup
        assert kind is not None
        if kind != "SPACE":
            tokens.append((kind, match.group().replace(" ", "")))
        pos = match.end()
    return tokens


@dataclass
class _Ctx:
    """Estado vivo de una evaluacion."""

    rng: RandomSource
    variables: dict[str, int]
    explode: bool
    dice: list[DieRoll] = field(default_factory=list)

    def roll_die(self, faces: int) -> DieRoll:
        rolls = [self.rng.die(faces)]
        # Regla explosiva del seis: al sacar la cara maxima, se vuelve a tirar
        # y se suma, de forma acumulativa.
        while self.explode and rolls[-1] == faces:
            if len(rolls) > MAX_EXPLOSIONES:
                raise DiceError(
                    f"un d{faces} ha explotado {MAX_EXPLOSIONES} veces seguidas: "
                    "la fuente de azar no es aleatoria"
                )
            rolls.append(self.rng.die(faces))
        die = DieRoll(faces, tuple(rolls))
        self.dice.append(die)
        return die

    def variable(self, name: str) -> int:
        try:
            return self.variables[name]
        except KeyError:
            known = ", ".join(sorted(self.variables)) or "ninguna"
            raise DiceError(
                f"la expresion usa la variable {name!r} pero no se dio valor "
                f"(disponibles: {known})"
            ) from None


class _Node:
    def eval(self, ctx: _Ctx) -> tuple[int, str]:  # pragma: no cover - interfaz
        raise NotImplementedError


@dataclass
class _Const(_Node):
    value: int

    def eval(self, ctx: _Ctx) -> tuple[int, str]:
        return self.value, str(self.value)


@dataclass
class _Var(_Node):
    name: str
    divisor: int = 1

    def eval(self, ctx: _Ctx) -> tuple[int, str]:
        raw = ctx.variable(self.name)
        value = raw // self.divisor  # redondeo hacia abajo, como pide el libro
        if self.divisor == 1:
            return value, f"{self.name}({value})"
        return value, f"1/{self.divisor}{self.name}({raw}->{value})"


@dataclass
class _Dice(_Node):
    count: int
    faces: int

    def eval(self, ctx: _Ctx) -> tuple[int, str]:
        rolled = [ctx.roll_die(self.faces) for _ in range(self.count)]
        total = sum(d.total for d in rolled)
        return total, "+".join(str(d) for d in rolled)


@dataclass
class _D66(_Node):
    """Dos dados: el primero son las decenas, el segundo las unidades (11-66)."""

    def eval(self, ctx: _Ctx) -> tuple[int, str]:
        # El d66 se lee, no se suma: nunca explota.
        explode, ctx.explode = ctx.explode, False
        try:
            tens = ctx.roll_die(6).total
            units = ctx.roll_die(6).total
        finally:
            ctx.explode = explode
        return tens * 10 + units, f"d66[{tens},{units}]"


@dataclass
class _BinOp(_Node):
    op: str
    left: _Node
    right: _Node

    def eval(self, ctx: _Ctx) -> tuple[int, str]:
        lhs, ltxt = self.left.eval(ctx)
        rhs, rtxt = self.right.eval(ctx)
        if self.op == "+":
            value = lhs + rhs
        elif self.op == "-":
            value = lhs - rhs
        elif self.op in "x*":
            value = lhs * rhs
        elif self.op == "/":
            value = lhs // rhs  # redondeo hacia abajo
        else:  # pragma: no cover - el parser no genera otros
            raise DiceError(f"operador desconocido {self.op!r}")
        symbol = "x" if self.op in "x*" else self.op
        return value, f"{ltxt} {symbol} {rtxt}"


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> tuple[str, str]:
        token = self.peek()
        if token is None:
            raise DiceError("la expresion termina antes de tiempo")
        self.pos += 1
        return token

    def parse(self) -> _Node:
        node = self.expr()
        if self.peek() is not None:
            raise DiceError(f"sobra {self.peek()[1]!r} al final de la expresion")
        return node

    def expr(self) -> _Node:
        node = self.term()
        while (token := self.peek()) and token[0] == "OP" and token[1] in "+-":
            op = self.take()[1]
            node = _BinOp(op, node, self.term())
        return node

    def term(self) -> _Node:
        node = self.factor()
        while (token := self.peek()) and token[0] == "OP" and token[1] in "x*/":
            op = self.take()[1]
            node = _BinOp(op, node, self.factor())
        return node

    def factor(self) -> _Node:
        kind, text = self.take()
        if kind == "OP" and text == "(":
            node = self.expr()
            if self.take() != ("OP", ")"):
                raise DiceError("falta un parentesis de cierre")
            return node
        if kind == "OP" and text == "-":
            return _BinOp("-", _Const(0), self.factor())
        if kind == "NUMBER":
            return _Const(int(text))
        if kind == "IDENT":
            return _Var(text)
        if kind == "FRACVAR":
            numerator, rest = text.split("/", 1)
            match = re.fullmatch(r"(\d+)([A-Za-z_]\w*)", rest)
            if match is None or numerator != "1":
                raise DiceError(f"solo se admiten fracciones 1/nN, no {text!r}")
            return _Var(match.group(2), divisor=int(match.group(1)))
        if kind == "DICE":
            count_txt, faces_txt = re.fullmatch(r"(\d*)[dD](\d+)", text).groups()
            faces = int(faces_txt)
            if faces == 66 and count_txt in ("", "1"):
                return _D66()
            return _Dice(int(count_txt or 1), faces)
        raise DiceError(f"no esperaba {text!r} aqui")


# --------------------------------------------------------------------------- #
# API publica
# --------------------------------------------------------------------------- #

_CACHE: dict[str, _Node] = {}


def parse(expression: str) -> _Node:
    """Compila una expresion (se cachea: las tablas repiten mucho las mismas)."""
    if expression not in _CACHE:
        if not expression or not expression.strip():
            raise DiceError("expresion de dados vacia")
        _CACHE[expression] = _Parser(_tokenize(expression)).parse()
    return _CACHE[expression]


def roll(
    expression: str | int,
    rng: RandomSource,
    *,
    explode: bool = False,
    **variables: int,
) -> RollResult:
    """Evalua una expresion de dados.

    `explode` activa la regla explosiva del seis; se aplica a las acciones de
    personaje, no a las tablas de generacion de mazmorra.
    Las variables sueltas (nivel, etc.) se pasan como argumentos por nombre:
    `roll("d6+N", rng, N=3)`.
    """
    if isinstance(expression, int):
        return RollResult(expression, str(expression), str(expression))
    ctx = _Ctx(rng=rng, variables=variables, explode=explode)
    total, detail = parse(expression).eval(ctx)
    return RollResult(total, expression, detail, tuple(ctx.dice))
