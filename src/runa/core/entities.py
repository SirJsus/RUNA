"""Personajes, clases, objetos y grupo.

Piezas genericas: ninguna sabe que existe Cuatro contra la Oscuridad. Todo lo
propio del juego (que clases hay, cuanta Vida dan, que arma suma +1) entra desde
los YAML de `games/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Sequence

from .checks import Modifier, ModifierRule
from .dice import roll
from .rng import RandomSource


class ReglaDeJuego(ValueError):
    """Se intento algo que el reglamento no permite."""


# --------------------------------------------------------------------------- #
# Objetos
# --------------------------------------------------------------------------- #

TIPOS_EQUIPABLES = frozenset({"arma", "armadura", "escudo", "luz"})


@dataclass
class Objeto:
    id: str
    nombre: str
    tipo: str = "util"
    categoria: str = ""            # ligera, mano, dos_manos, arco, honda, pesada...
    precio: int = 0
    manos: int = 0
    etiquetas: frozenset[str] = frozenset()
    reglas: tuple[ModifierRule, ...] = ()
    valor: str = ""                # expresion de dados para gemas y joyeria
    variantes: tuple[str, ...] = ()   # p.ej. aplastante / cortante, a elegir
    usos: int = 0                     # cargas restantes de un objeto magico
    equipado: bool = False
    notas: str = ""

    def con_variante(self, variante: str) -> "Objeto":
        """Fija una variante del objeto (aplastante o cortante) como etiqueta."""
        if variante not in self.variantes:
            raise ReglaDeJuego(
                f"{self.nombre} no admite la variante {variante!r} "
                f"(admite: {', '.join(self.variantes) or 'ninguna'})"
            )
        return self.copia(etiquetas=self.etiquetas | {variante}, variantes=())

    @property
    def equipable(self) -> bool:
        return self.tipo in TIPOS_EQUIPABLES

    @property
    def activo(self) -> bool:
        """Solo lo equipado aporta modificadores y etiquetas."""
        return self.equipado and self.equipable

    def precio_venta(self) -> int:
        return self.precio // 2  # la mitad, redondeando hacia abajo

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "Objeto":
        etiquetas = bruto.get("etiquetas") or []
        reglas = tuple(
            ModifierRule.desde_dict(r, texto_por_defecto=str(bruto.get("nombre", id)))
            for r in (bruto.get("reglas") or [])
        )
        return cls(
            id=id,
            nombre=str(bruto.get("nombre", id)),
            tipo=str(bruto.get("tipo", "util")),
            categoria=str(bruto.get("categoria", "")),
            precio=int(bruto.get("precio", 0)),
            manos=int(bruto.get("manos", 0)),
            etiquetas=frozenset([etiquetas] if isinstance(etiquetas, str) else etiquetas),
            reglas=reglas,
            valor=str(bruto.get("valor", "")),
            variantes=tuple(bruto.get("variantes") or []),
            usos=int(bruto.get("usos", 0)),
            notas=str(bruto.get("notas", "")),
        )

    def copia(self, **cambios: Any) -> "Objeto":
        datos = {**self.__dict__, **cambios}
        return Objeto(**datos)

    def a_dict(self) -> dict[str, Any]:
        """Se guarda por id de catalogo mas lo que difiera.

        Las reglas no se serializan: se recuperan del catalogo al cargar, asi
        que un ajuste del reglamento se aplica a las partidas ya guardadas.
        """
        return {"id": self.id, "etiquetas": sorted(self.etiquetas),
                "equipado": self.equipado, "usos": self.usos}

    def __str__(self) -> str:
        return self.nombre


# --------------------------------------------------------------------------- #
# Estados temporales
# --------------------------------------------------------------------------- #


@dataclass
class Estado:
    """Condicion temporal: maldito, bendecido, petrificado, envenenado..."""

    id: str
    texto: str = ""
    reglas: tuple[ModifierRule, ...] = ()
    etiquetas: frozenset[str] = frozenset()
    dura: str = "aventura"     # aventura | combate | permanente

    def a_dict(self) -> dict[str, Any]:
        return {"id": self.id}

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "Estado":
        etiquetas = bruto.get("etiquetas") or []
        return cls(
            id=id,
            texto=str(bruto.get("texto", id)),
            reglas=tuple(
                ModifierRule.desde_dict(r, texto_por_defecto=str(bruto.get("texto", id)))
                for r in (bruto.get("reglas") or [])
            ),
            etiquetas=frozenset([etiquetas] if isinstance(etiquetas, str) else etiquetas),
            dura=str(bruto.get("dura", "aventura")),
        )


# --------------------------------------------------------------------------- #
# Clases de personaje
# --------------------------------------------------------------------------- #


@dataclass
class ClasePersonaje:
    id: str
    nombre: str
    vida: str = "N"                # expresion con N = nivel, p.ej. "6+N"
    riqueza_inicial: str = "d6"
    nivel_maximo: int | None = None
    reglas: tuple[ModifierRule, ...] = ()
    permite: dict[str, Any] = field(default_factory=dict)
    equipo_inicial: tuple[str, ...] = ()
    recursos: dict[str, str] = field(default_factory=dict)
    etiquetas: frozenset[str] = frozenset()
    notas: str = ""

    def vida_a_nivel(self, nivel: int) -> int:
        return roll(self.vida, _SIN_AZAR, N=nivel).total

    def recursos_a_nivel(self, nivel: int) -> dict[str, int]:
        return {k: roll(v, _SIN_AZAR, N=nivel).total for k, v in self.recursos.items()}

    def permite_objeto(self, objeto: Objeto) -> bool:
        if objeto.tipo == "escudo":
            return bool(self.permite.get("escudo", True))
        if objeto.tipo == "armadura":
            return objeto.categoria in (self.permite.get("armaduras") or [])
        if objeto.tipo == "arma":
            return objeto.categoria in (self.permite.get("armas") or [])
        if "magico" in objeto.etiquetas:
            return bool(self.permite.get("objetos_magicos", True))
        return True

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "ClasePersonaje":
        nombre = str(bruto.get("nombre", id))
        reglas = tuple(
            ModifierRule.desde_dict(r, texto_por_defecto=nombre)
            for r in (bruto.get("reglas") or [])
        )
        etiquetas = set(bruto.get("etiquetas") or [])
        etiquetas.add(id)  # la propia clase siempre es una etiqueta
        return cls(
            id=id,
            nombre=nombre,
            vida=str(bruto.get("vida", "N")),
            riqueza_inicial=str(bruto.get("riqueza_inicial", "d6")),
            nivel_maximo=bruto.get("nivel_maximo"),
            reglas=reglas,
            permite=dict(bruto.get("permite") or {}),
            equipo_inicial=tuple(bruto.get("equipo_inicial") or []),
            recursos={k: str(v) for k, v in (bruto.get("recursos") or {}).items()},
            etiquetas=frozenset(etiquetas),
            notas=str(bruto.get("notas", "")),
        )


_SIN_AZAR = RandomSource(0)


# --------------------------------------------------------------------------- #
# Personaje
# --------------------------------------------------------------------------- #


@dataclass
class Personaje:
    nombre: str
    clase: ClasePersonaje
    nivel: int = 1
    vida_max: int = 0
    vida: int = 0
    oro: int = 0
    equipo: list[Objeto] = field(default_factory=list)
    estados: list[Estado] = field(default_factory=list)
    recursos: dict[str, int] = field(default_factory=dict)
    preparados: list[str] = field(default_factory=list)
    muerto: bool = False

    def __post_init__(self) -> None:
        if not self.vida_max:
            self.vida_max = self.clase.vida_a_nivel(self.nivel)
        if not self.vida:
            self.vida = self.vida_max
        if not self.recursos:
            self.recursos = self.clase.recursos_a_nivel(self.nivel)

    # -- estado ------------------------------------------------------------ #

    @property
    def vivo(self) -> bool:
        return not self.muerto and self.vida > 0

    @property
    def herido(self) -> bool:
        return self.vida < self.vida_max

    def herir(self, cantidad: int = 1) -> int:
        """Aplica heridas. Devuelve las que realmente se aplicaron."""
        aplicadas = min(cantidad, self.vida)
        self.vida -= aplicadas
        if self.vida <= 0:
            self.muerto = True
        return aplicadas

    def curar(self, cantidad: int) -> int:
        """Cura sin pasar del maximo. La curacion no resucita."""
        if self.muerto:
            return 0
        curadas = min(cantidad, self.vida_max - self.vida)
        self.vida += curadas
        return curadas

    @property
    def fuera_de_combate(self) -> bool:
        return any(e.id == "fuera_de_combate" for e in self.estados)

    def estado(self, id: str) -> Estado | None:
        return next((e for e in self.estados if e.id == id), None)

    def quitar_estado(self, id: str) -> Estado | None:
        if (estado := self.estado(id)) is not None:
            self.estados.remove(estado)
        return estado

    def limpiar_estados(self, dura: str) -> None:
        self.estados = [e for e in self.estados if e.dura != dura]

    def gastar(self, recurso: str, cantidad: int = 1) -> None:
        disponible = self.recursos.get(recurso, 0)
        if disponible < cantidad:
            raise ReglaDeJuego(
                f"{self.nombre} no tiene {recurso} suficiente "
                f"(le quedan {disponible}, necesita {cantidad})"
            )
        self.recursos[recurso] = disponible - cantidad

    # -- equipo ------------------------------------------------------------ #

    def equipado(self, tipo: str) -> Objeto | None:
        return next((o for o in self.equipo if o.activo and o.tipo == tipo), None)

    @property
    def arma(self) -> Objeto | None:
        return self.equipado("arma")

    def anadir(self, objeto: Objeto, equipar: bool = False) -> Objeto:
        copia = objeto.copia(equipado=equipar and objeto.equipable)
        self.equipo.append(copia)
        return copia

    def manos_ocupadas(self) -> int:
        return sum(o.manos for o in self.equipo if o.activo)

    def problemas_de_equipo(self) -> list[str]:
        """Comprueba el equipo contra las limitaciones de la clase.

        No lanza: devuelve la lista para que la interfaz la muestre. Al crear
        personajes conviene poder ver todos los problemas de golpe.
        """
        problemas = []
        for objeto in self.equipo:
            if not self.clase.permite_objeto(objeto):
                problemas.append(f"un {self.clase.nombre} no puede usar {objeto.nombre}")
        manos = self.manos_ocupadas()
        if manos > 2:
            problemas.append(
                f"{self.nombre} lleva equipo para {manos} manos y solo tiene 2"
            )
        armas = [o for o in self.equipo if o.activo and o.tipo == "arma"]
        if len(armas) > 1:
            problemas.append(
                "solo se puede empunar un arma a la vez: "
                + ", ".join(a.nombre for a in armas)
            )
        return problemas

    # -- reglas ------------------------------------------------------------ #

    def reglas(self) -> Sequence[ModifierRule]:
        reglas = list(self.clase.reglas)
        for objeto in self.equipo:
            if objeto.activo:
                reglas.extend(objeto.reglas)
        for estado in self.estados:
            reglas.extend(estado.reglas)
        return reglas

    def etiquetas_activas(self) -> set[str]:
        etiquetas = set(self.clase.etiquetas)
        for objeto in self.equipo:
            if objeto.activo:
                etiquetas |= objeto.etiquetas
                if objeto.categoria:
                    etiquetas.add(objeto.categoria)
        for estado in self.estados:
            etiquetas |= estado.etiquetas
            etiquetas.add(estado.id)
        return etiquetas

    def subir_nivel(self) -> int:
        maximo = self.clase.nivel_maximo
        if maximo is not None and self.nivel >= maximo:
            raise ReglaDeJuego(
                f"un {self.clase.nombre} no pasa del nivel {maximo}"
            )
        self.nivel += 1
        nueva_max = self.clase.vida_a_nivel(self.nivel)
        self.vida += nueva_max - self.vida_max   # la Vida ganada tambien cura
        self.vida_max = nueva_max
        return self.nivel

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre, "clase": self.clase.id, "nivel": self.nivel,
            "vida_max": self.vida_max, "vida": self.vida, "oro": self.oro,
            "equipo": [o.a_dict() for o in self.equipo],
            "estados": [e.a_dict() for e in self.estados],
            "recursos": dict(self.recursos), "preparados": list(self.preparados),
            "muerto": self.muerto,
        }

    def bajar_nivel(self) -> int:
        """Drenaje de energia. Un mago puede caer a nivel 0 y dejar de lanzar."""
        if self.nivel <= 0:
            return 0
        self.nivel -= 1
        nueva_max = max(1, self.clase.vida_a_nivel(self.nivel))
        self.vida_max = nueva_max
        self.vida = min(self.vida, nueva_max)
        return self.nivel

    def __str__(self) -> str:
        estado = "muerto" if self.muerto else f"{self.vida}/{self.vida_max} Vida"
        return f"{self.nombre}, {self.clase.nombre} nivel {self.nivel} ({estado})"


# --------------------------------------------------------------------------- #
# Grupo
# --------------------------------------------------------------------------- #


@dataclass
class Grupo:
    """El grupo de aventureros. El orden de la lista ES el orden de marcha."""

    miembros: list[Personaje] = field(default_factory=list)

    def __iter__(self) -> Iterator[Personaje]:
        return iter(self.miembros)

    def __len__(self) -> int:
        return len(self.miembros)

    @property
    def vivos(self) -> list[Personaje]:
        return [p for p in self.miembros if p.vivo]

    @property
    def oro(self) -> int:
        return sum(p.oro for p in self.miembros)

    def por_nombre(self, nombre: str) -> Personaje:
        for p in self.miembros:
            if p.nombre.lower() == nombre.lower():
                return p
        raise ReglaDeJuego(f"no hay nadie llamado {nombre!r} en el grupo")

    def con_clase(self, clase_id: str) -> list[Personaje]:
        return [p for p in self.miembros if p.clase.id == clase_id]

    def reordenar(self, nombres: Sequence[str]) -> None:
        if sorted(n.lower() for n in nombres) != sorted(p.nombre.lower() for p in self.miembros):
            raise ReglaDeJuego("el orden de marcha debe incluir a todo el grupo una vez")
        self.miembros = [self.por_nombre(n) for n in nombres]

    def describir(self) -> str:
        return "\n".join(f"  {i}. {p}" for i, p in enumerate(self.miembros, 1))

    def a_dict(self) -> dict[str, Any]:
        return {"miembros": [p.a_dict() for p in self.miembros]}
