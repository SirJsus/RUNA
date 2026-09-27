"""Perfiles de monstruo y sus instancias en juego.

Generico: aqui no hay ningun monstruo concreto, solo la forma que tienen. El
bestiario real vive en `games/<juego>/data/monstruos.yaml`.

Dos formas de existir, como en la mesa:

  * **Esbirros**: un grupo. Cada uno tiene 1 punto de Vida, asi que lo que se
    lleva es la cuenta de cuantos quedan.
  * **Jefes**: uno solo con varios puntos de Vida, que ademas pierde un nivel en
    cuanto baja de la mitad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .checks import Amenaza, ModifierRule
from .dice import roll
from .rng import RandomSource

ESBIRROS = frozenset({"bicho", "esbirro"})
JEFES = frozenset({"jefe", "extrano"})


@dataclass(frozen=True)
class Tesoro:
    """Cuantas tiradas de tesoro deja el monstruo y con que modificador."""

    tiradas: int = 0
    modificador: int = 0

    @classmethod
    def desde(cls, bruto: Any) -> "Tesoro":
        if bruto is None or bruto is False:
            return cls(0, 0)
        if bruto in ("normal", True):
            return cls(1, 0)
        if isinstance(bruto, int):
            return cls(1, bruto)
        if isinstance(bruto, str):          # "+1", "-1", "+2"
            return cls(1, int(bruto))
        return cls(int(bruto.get("tiradas", 1)), int(bruto.get("modificador", 0)))

    def __bool__(self) -> bool:
        return self.tiradas > 0


@dataclass(frozen=True)
class Moral:
    prueba: bool = True
    modificador: int = 0

    @classmethod
    def desde(cls, bruto: Any) -> "Moral":
        if bruto in (None, "normal"):
            return cls()
        if bruto == "nunca" or bruto is False:
            return cls(prueba=False)
        if isinstance(bruto, (int, str)):
            return cls(modificador=int(bruto))
        return cls(
            prueba=bool(bruto.get("prueba", True)),
            modificador=int(bruto.get("modificador", 0)),
        )


@dataclass
class PerfilMonstruo:
    id: str
    nombre: str
    tipo: str = "esbirro"              # bicho | esbirro | jefe | extrano
    nivel: int = 1
    vida: int = 1                      # por individuo; los esbirros siempre 1
    ataques: int = 1
    dano: int = 1
    cantidad: str = "1"                # expresion de dados
    etiquetas: frozenset[str] = frozenset()
    tesoro: Tesoro = field(default_factory=Tesoro)
    moral: Moral = field(default_factory=Moral)
    reacciones: str = ""               # id de la tabla de reacciones
    sin_objetos_magicos: str = ""      # expresion de oro que los sustituye
    reglas: tuple[ModifierRule, ...] = ()
    xp: bool = True
    errante: bool = True               # puede aparecer como monstruo errante
    combate: bool = True               # los gremlins no se pueden combatir
    notas: str = ""

    @property
    def es_esbirro(self) -> bool:
        return self.tipo in ESBIRROS

    @property
    def es_jefe(self) -> bool:
        return self.tipo in JEFES

    def amenaza(self, nivel: int | None = None) -> Amenaza:
        return Amenaza.crear(
            self.nombre,
            self.nivel if nivel is None else nivel,
            self.etiquetas | {self.tipo, "esbirro" if self.es_esbirro else "jefe"},
            self.reglas,
        )

    def generar(self, rng: RandomSource) -> "Encuentro":
        """Instancia el monstruo: tira cantidad (esbirros) o Vida (jefes)."""
        cantidad = roll(self.cantidad, rng).total if self.es_esbirro else 1
        return Encuentro(perfil=self, cantidad=max(1, cantidad), vida=self.vida)

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "PerfilMonstruo":
        nombre = str(bruto.get("nombre", id))
        etiquetas = set(bruto.get("etiquetas") or [])
        etiquetas.add(id)
        return cls(
            id=id,
            nombre=nombre,
            tipo=str(bruto.get("tipo", "esbirro")),
            nivel=int(bruto.get("nivel", 1)),
            vida=int(bruto.get("vida", 1)),
            ataques=int(bruto.get("ataques", 1)),
            dano=int(bruto.get("dano", 1)),
            cantidad=str(bruto.get("cantidad", "1")),
            etiquetas=frozenset(etiquetas),
            tesoro=Tesoro.desde(bruto.get("tesoro")),
            moral=Moral.desde(bruto.get("moral")),
            reacciones=str(bruto.get("reacciones", "")),
            sin_objetos_magicos=str(bruto.get("sin_objetos_magicos", "")),
            reglas=tuple(
                ModifierRule.desde_dict(r, texto_por_defecto=nombre)
                for r in (bruto.get("reglas") or [])
            ),
            xp=bool(bruto.get("xp", True)),
            errante=bool(bruto.get("errante", True)),
            combate=bool(bruto.get("combate", True)),
            notas=str(bruto.get("notas", "")),
        )


@dataclass
class Encuentro:
    """Los monstruos concretos que hay delante, con su estado actual."""

    perfil: PerfilMonstruo
    cantidad: int = 1
    vida: int = 1
    cantidad_inicial: int = 0
    vida_inicial: int = 0
    huido: bool = False

    def __post_init__(self) -> None:
        self.cantidad_inicial = self.cantidad_inicial or self.cantidad
        self.vida_inicial = self.vida_inicial or self.vida

    @property
    def nombre(self) -> str:
        return self.perfil.nombre

    @property
    def vivo(self) -> bool:
        return not self.huido and self.cantidad > 0 and self.vida > 0

    @property
    def nivel(self) -> int:
        """Un jefe pierde un nivel en cuanto baja de la mitad de su Vida.

        El libro insiste en que ocurre INMEDIATAMENTE, no al final del turno.
        """
        if self.perfil.es_jefe and self.vida * 2 < self.vida_inicial:
            return max(1, self.perfil.nivel - 1)
        return self.perfil.nivel

    @property
    def amenaza(self) -> Amenaza:
        return self.perfil.amenaza(self.nivel)

    @property
    def bajo_de_moral(self) -> bool:
        """Ha perdido mas de la mitad de lo que tenia al empezar."""
        if self.perfil.es_esbirro:
            return self.cantidad * 2 < self.cantidad_inicial
        return self.vida * 2 < self.vida_inicial

    def herir(self, heridas: int = 1) -> int:
        """Aplica heridas. Cada golpe mata a un esbirro; a un jefe le quita Vida."""
        if self.perfil.es_esbirro:
            muertos = min(heridas, self.cantidad)
            self.cantidad -= muertos
            return muertos
        perdidos = min(heridas, self.vida)
        self.vida -= perdidos
        return perdidos

    def huir(self) -> None:
        self.huido = True

    def __str__(self) -> str:
        if self.huido:
            return f"{self.nombre} (huyo)"
        if self.perfil.es_esbirro:
            return f"{self.cantidad}x {self.nombre} (nivel {self.nivel})"
        return f"{self.nombre} (nivel {self.nivel}, {self.vida}/{self.vida_inicial} Vida)"


class Bestiario:
    def __init__(self, perfiles: dict[str, PerfilMonstruo] | None = None) -> None:
        self.perfiles = dict(perfiles or {})

    def __getitem__(self, id: str) -> PerfilMonstruo:
        try:
            return self.perfiles[id]
        except KeyError:
            raise KeyError(f"no existe el monstruo {id!r} en el bestiario") from None

    def __contains__(self, id: str) -> bool:
        return id in self.perfiles

    def __len__(self) -> int:
        return len(self.perfiles)

    def de_tipo(self, tipo: str) -> list[PerfilMonstruo]:
        return [p for p in self.perfiles.values() if p.tipo == tipo]

    @classmethod
    def desde_dict(cls, bruto: dict[str, Any]) -> "Bestiario":
        return cls({id: PerfilMonstruo.desde_dict(id, d) for id, d in bruto.items()})
