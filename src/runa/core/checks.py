"""Resolucion de tiradas con modificadores.

Casi todo lo que ocurre en la mesa es la misma operacion:

    dado + suma de modificadores  comparado con  el nivel de una amenaza

Este modulo la implementa una sola vez, de forma generica. Lo que cambia entre
tiradas (que modificadores entran, si el exito es `>=` o `>`, si el 1 natural
falla siempre) llega como datos, no como codigo.

El mecanismo central son las **etiquetas**. Una tirada arrastra un conjunto
plano de etiquetas que aportan, juntas, tres fuentes:

  * la situacion   -> {"cuerpo_a_cuerpo", "superados_en_numero", "sorpresa"}
  * el equipo      -> {"dos_manos", "aplastante"}
  * la amenaza     -> {"no_muerto", "esqueleto"}

Asi, "las armas aplastantes suman +1 contra esqueletos" es una sola regla
declarativa que exige las etiquetas `aplastante` y `esqueleto`, sin que el
motor sepa que es un arma ni que es un esqueleto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence

from .dice import RollResult, roll
from .rng import RandomSource

# Alias comodos para escribir las reglas en castellano dentro del YAML.
_ALIAS_SUMA = {
    "nivel": "N",
    "medio_nivel": "1/2N",
    "mitad_nivel": "1/2N",
}


class Actor(Protocol):
    """Lo minimo que el resolutor necesita de quien tira."""

    nombre: str
    nivel: int

    def reglas(self) -> Sequence["ModifierRule"]: ...
    def etiquetas_activas(self) -> set[str]: ...


@dataclass(frozen=True)
class Amenaza:
    """Aquello contra lo que se tira.

    El reglamento trata igual a un monstruo de nivel 4, a un veneno de nivel 3 y
    a un acertijo de nivel 5: todos son "un numero que hay que superar". Se
    modelan con la misma pieza a proposito.
    """

    nombre: str
    nivel: int
    etiquetas: frozenset[str] = frozenset()
    reglas: tuple["ModifierRule", ...] = ()

    @classmethod
    def crear(
        cls,
        nombre: str,
        nivel: int,
        etiquetas: Iterable[str] = (),
        reglas: Iterable["ModifierRule"] = (),
    ) -> "Amenaza":
        return cls(nombre, nivel, frozenset(etiquetas), tuple(reglas))


@dataclass(frozen=True)
class Modifier:
    """Un modificador ya calculado, con su procedencia para la traza."""

    valor: int
    fuente: str

    def __str__(self) -> str:
        return f"{self.valor:+d} {self.fuente}"


class AccionProhibida(ValueError):
    """El reglamento no permite esta accion en estas condiciones."""

    def __init__(self, tipo: str, motivos: Sequence[str]) -> None:
        self.tipo = tipo
        self.motivos = list(motivos)
        super().__init__(f"no se puede {tipo}: " + "; ".join(motivos))


@dataclass(frozen=True)
class ModifierRule:
    """Regla declarativa condicionada por etiquetas.

    Hace dos cosas, segun se rellene `suma` o `prohibe`:

        - en: ataque                     # modifica
          suma: nivel
          si: [aplastante, esqueleto]
          texto: las armas aplastantes suman +1 contra esqueletos

        - prohibe: hechizo               # veta
          si: [dos_manos]
          texto: no se puede lanzar con las dos manos ocupadas
    """

    suma: str = "0"
    texto: str = "modificador"
    prohibe: frozenset[str] = frozenset()
    en: frozenset[str] = frozenset()          # tipos de tirada; vacio = todas
    si: frozenset[str] = frozenset()          # exige TODAS estas etiquetas
    si_alguno: frozenset[str] = frozenset()   # exige AL MENOS UNA
    si_no: frozenset[str] = frozenset()       # exige NINGUNA

    @property
    def veta(self) -> bool:
        return bool(self.prohibe)

    def condiciones_ok(self, etiquetas: set[str]) -> bool:
        if not self.si <= etiquetas:
            return False
        if self.si_alguno and not (self.si_alguno & etiquetas):
            return False
        if self.si_no & etiquetas:
            return False
        return True

    def prohibe_tipo(self, tipo: str, etiquetas: set[str]) -> bool:
        return tipo in self.prohibe and self.condiciones_ok(etiquetas)

    def aplica(self, tipo: str, etiquetas: set[str]) -> bool:
        if self.veta or (self.en and tipo not in self.en):
            return False
        return self.condiciones_ok(etiquetas)

    def valor(self, nivel: int) -> int:
        return roll(self.suma, _SIN_AZAR, N=nivel).total

    def modificador(self, nivel: int) -> Modifier:
        return Modifier(self.valor(nivel), self.texto)

    @classmethod
    def desde_dict(cls, bruto: dict[str, Any], texto_por_defecto: str = "") -> "ModifierRule":
        def conjunto(clave: str) -> frozenset[str]:
            valor = bruto.get(clave) or ()
            return frozenset([valor] if isinstance(valor, str) else valor)

        suma = bruto.get("suma", 0)
        suma = _ALIAS_SUMA.get(str(suma), str(suma))
        return cls(
            suma=suma,
            texto=str(bruto.get("texto") or texto_por_defecto or "modificador"),
            prohibe=conjunto("prohibe"),
            en=conjunto("en"),
            si=conjunto("si"),
            si_alguno=conjunto("si_alguno"),
            si_no=conjunto("si_no"),
        )


# Las reglas no tiran dados: sus "expresiones" son aritmetica sobre el nivel.
_SIN_AZAR = RandomSource(0)


@dataclass(frozen=True)
class TipoTirada:
    """Como se resuelve una clase de tirada. Viene del YAML del juego."""

    id: str
    dado: str = "d6"
    comparacion: str = ">="
    explosiva: bool = True
    exito_natural: int | None = None
    fallo_natural: int | None = None

    def compara(self, total: int, dificultad: int) -> bool:
        if self.comparacion == ">":
            return total > dificultad
        if self.comparacion == "<=":
            # La resurreccion va al reves: se logra sacando igual o menos que el
            # nivel del personaje, asi que a los veteranos les cuesta menos volver.
            return total <= dificultad
        return total >= dificultad

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "TipoTirada":
        comparacion = str(bruto.get("comparacion", ">="))
        if comparacion not in (">=", ">", "<="):
            raise ValueError(
                f"tirada {id!r}: comparacion debe ser '>=', '>' o '<=', "
                f"no {comparacion!r}"
            )
        return cls(
            id=id,
            dado=str(bruto.get("dado", "d6")),
            comparacion=comparacion,
            explosiva=bool(bruto.get("explosiva", True)),
            exito_natural=bruto.get("exito_natural"),
            fallo_natural=bruto.get("fallo_natural"),
        )


@dataclass
class Check:
    """Una tirada concreta, ya con todo su contexto."""

    tipo: str
    actor: Actor
    dificultad: int
    amenaza: Amenaza | None = None
    etiquetas: set[str] = field(default_factory=set)
    ventaja: int = 1          # numero de tiradas de las que se toma la mejor
    motivo: str = ""

    def etiquetas_totales(self) -> set[str]:
        """Situacion + actor (clase, equipo, estados) + amenaza."""
        todas = set(self.etiquetas) | self.actor.etiquetas_activas()
        if self.amenaza:
            todas |= self.amenaza.etiquetas
        return todas


@dataclass(frozen=True)
class CheckResult:
    tipo: str
    actor: str
    dificultad: int
    tirada: RollResult
    modificadores: tuple[Modifier, ...]
    total: int
    exito: bool
    amenaza: str | None = None
    motivo: str = ""
    descartadas: tuple[RollResult, ...] = ()   # tiradas perdidas por ventaja

    @property
    def bonificacion(self) -> int:
        return sum(m.valor for m in self.modificadores)

    def describir(self) -> str:
        cabecera = f"{self.tipo.replace('_', ' ').capitalize()} de {self.actor}"
        if self.amenaza:
            cabecera += f" contra {self.amenaza} (nivel {self.dificultad})"
        else:
            cabecera += f" (dificultad {self.dificultad})"
        lineas = [cabecera, f"  {self.tirada.detail}"]
        lineas += [f"  {m}" for m in self.modificadores]
        veredicto = "EXITO" if self.exito else "FALLO"
        cierre = f"  = {self.total} vs {self.dificultad} -> {veredicto}"
        if self.motivo:
            cierre += f" ({self.motivo})"
        lineas.append(cierre)
        return "\n".join(lineas)

    def __str__(self) -> str:
        return self.describir()


class Resolutor:
    """Resuelve tiradas aplicando las reglas globales del juego mas las del actor."""

    def __init__(
        self,
        tipos: dict[str, TipoTirada] | None = None,
        reglas_globales: Sequence[ModifierRule] = (),
    ) -> None:
        self.tipos = dict(tipos or {})
        self.reglas_globales = tuple(reglas_globales)

    def tipo(self, id: str) -> TipoTirada:
        return self.tipos.get(id) or TipoTirada(id)

    def _reglas(self, check: Check) -> list[ModifierRule]:
        amenaza = check.amenaza.reglas if check.amenaza else ()
        return [*check.actor.reglas(), *amenaza, *self.reglas_globales]

    def prohibiciones(self, check: Check) -> list[str]:
        """Motivos por los que esta tirada no esta permitida. Vacio = adelante."""
        etiquetas = check.etiquetas_totales()
        return [
            r.texto for r in self._reglas(check)
            if r.prohibe_tipo(check.tipo, etiquetas)
        ]

    def modificadores(self, check: Check) -> tuple[Modifier, ...]:
        etiquetas = check.etiquetas_totales()
        aplicables = [r for r in self._reglas(check) if r.aplica(check.tipo, etiquetas)]
        modificadores = [r.modificador(check.actor.nivel) for r in aplicables]
        # Un +0 solo ensucia la traza.
        return tuple(m for m in modificadores if m.valor)

    def resolver(self, check: Check, rng: RandomSource) -> CheckResult:
        if motivos := self.prohibiciones(check):
            raise AccionProhibida(check.tipo, motivos)
        tipo = self.tipo(check.tipo)
        modificadores = self.modificadores(check)
        bonificacion = sum(m.valor for m in modificadores)

        if check.ventaja < 1:
            raise ValueError("la ventaja debe ser al menos 1 tirada")
        tiradas = [
            roll(tipo.dado, rng, explode=tipo.explosiva) for _ in range(check.ventaja)
        ]
        mejor = max(tiradas, key=lambda t: t.total)
        descartadas = tuple(t for t in tiradas if t is not mejor)

        total = mejor.total + bonificacion
        exito = tipo.compara(total, check.dificultad)
        motivo = check.motivo

        # El 1 y el 6 naturales mandan sobre el resultado modificado. "Natural"
        # es la primera cara del dado: una explosion no lo convierte en otra cosa.
        natural = mejor.dice[0].rolls[0] if mejor.dice else None
        if natural is not None:
            if tipo.fallo_natural is not None and natural == tipo.fallo_natural:
                exito, motivo = False, f"{natural} natural: fallo automatico"
            elif tipo.exito_natural is not None and natural == tipo.exito_natural:
                exito, motivo = True, f"{natural} natural: exito automatico"

        return CheckResult(
            tipo=check.tipo,
            actor=check.actor.nombre,
            dificultad=check.dificultad,
            tirada=mejor,
            modificadores=modificadores,
            total=total,
            exito=exito,
            amenaza=check.amenaza.nombre if check.amenaza else None,
            motivo=motivo,
            descartadas=descartadas,
        )
