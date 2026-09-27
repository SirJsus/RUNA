"""Habilidades: hechizos, poderes de clase y usos de objeto.

Una habilidad describe **cuando** se puede usar, **contra que** y **que recurso
gasta**. El efecto concreto (cuantos esbirros mata una bola de fuego) no cabe en
datos, asi que la habilidad solo nombra su efecto y el juego registra el gancho
que lo implementa.

Es la frontera deliberada entre "esto es una tabla" y "esto es codigo".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

MOMENTOS = frozenset({"turno", "defensa", "libre", "fuera_de_combate", "siempre"})


@dataclass(frozen=True)
class Habilidad:
    id: str
    nombre: str
    tipo: str = "hechizo"           # hechizo | poder | objeto
    tirada: str = "hechizo"         # tipo de tirada; "" = automatica
    momentos: frozenset[str] = frozenset({"turno"})   # cuando se puede usar
    objetivo: str = "monstruo"      # monstruo | aliado | uno_mismo | grupo | ninguno
    gasta: str = ""                 # recurso consumido (hechizos, curacion, ira...)
    usable_por: frozenset[str] = frozenset()   # ids de clase; vacio = cualquiera
    etiquetas: frozenset[str] = frozenset()
    efecto: str = ""                # clave del gancho que lo implementa
    notas: str = ""

    @property
    def automatica(self) -> bool:
        return not self.tirada

    def en_momento(self, momento: str) -> bool:
        return momento in self.momentos

    def puede_usarla(self, clase_id: str) -> bool:
        return not self.usable_por or clase_id in self.usable_por

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "Habilidad":
        def conjunto(clave: str) -> frozenset[str]:
            valor = bruto.get(clave) or ()
            return frozenset([valor] if isinstance(valor, str) else valor)

        momentos = bruto.get("momentos", bruto.get("momento", "turno"))
        momentos = frozenset([momentos] if isinstance(momentos, str) else momentos)
        if desconocidos := momentos - MOMENTOS:
            raise ValueError(
                f"habilidad {id!r}: momento(s) {sorted(desconocidos)} desconocidos "
                f"(validos: {', '.join(sorted(MOMENTOS))})"
            )
        return cls(
            id=id,
            nombre=str(bruto.get("nombre", id)),
            tipo=str(bruto.get("tipo", "hechizo")),
            tirada=str(bruto.get("tirada", "hechizo")),
            momentos=momentos,
            objetivo=str(bruto.get("objetivo", "monstruo")),
            gasta=str(bruto.get("gasta", "")),
            usable_por=conjunto("usable_por"),
            etiquetas=conjunto("etiquetas") | {id},
            efecto=str(bruto.get("efecto", id)),
            notas=str(bruto.get("notas", "")),
        )


class Habilidades:
    """Catalogo de habilidades y registro de los ganchos que las implementan."""

    def __init__(self, catalogo: dict[str, Habilidad] | None = None) -> None:
        self.catalogo = dict(catalogo or {})
        self.efectos: dict[str, Callable[..., Any]] = {}

    def __getitem__(self, id: str) -> Habilidad:
        try:
            return self.catalogo[id]
        except KeyError:
            raise KeyError(
                f"no existe la habilidad {id!r} "
                f"(hay: {', '.join(sorted(self.catalogo))})"
            ) from None

    def __contains__(self, id: str) -> bool:
        return id in self.catalogo

    def __len__(self) -> int:
        return len(self.catalogo)

    def para(self, clase_id: str, momento: str = "") -> list[Habilidad]:
        return [
            h for h in self.catalogo.values()
            if h.puede_usarla(clase_id) and (not momento or h.en_momento(momento))
        ]

    def registrar(self, efecto: str) -> Callable:
        """Decorador: asocia una funcion al efecto nombrado en los datos."""

        def envoltorio(funcion: Callable[..., Any]) -> Callable[..., Any]:
            self.efectos[efecto] = funcion
            return funcion

        return envoltorio

    def sin_implementar(self) -> list[str]:
        return sorted(
            h.efecto for h in self.catalogo.values() if h.efecto not in self.efectos
        )

    @classmethod
    def desde_dict(cls, bruto: dict[str, Any]) -> "Habilidades":
        return cls({id: Habilidad.desde_dict(id, d) for id, d in bruto.items()})
