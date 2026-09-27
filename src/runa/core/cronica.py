"""Convierte un registro de eventos en un documento legible.

El motor no sabe que eventos existen en cada juego: recibe un diccionario de
estilos que dice como tratar cada tipo. Asi, la maquinaria de agrupar, plegar
las tiradas y destacar lo importante se escribe una vez, y cada juego aporta
solo su vocabulario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from .events import Evento, Registro

# Como se trata cada tipo de evento.
FORMATOS = frozenset({"seccion", "escena", "linea", "detalle", "destacado", "omitir"})


@dataclass(frozen=True)
class Estilo:
    formato: str = "linea"
    icono: str = ""
    nivel: int = 3          # profundidad del encabezado, solo para "seccion"

    def __post_init__(self) -> None:
        if self.formato not in FORMATOS:
            raise ValueError(
                f"formato {self.formato!r} desconocido "
                f"(validos: {', '.join(sorted(FORMATOS))})"
            )


@dataclass
class Bloque:
    """Un tramo de cronica: un encabezado y lo que cae debajo."""

    titulo: str = ""
    nivel: int = 3
    partes: list[tuple[str, str]] = field(default_factory=list)  # (formato, texto)

    def anadir(self, formato: str, texto: str) -> None:
        self.partes.append((formato, texto))

    @property
    def vacio(self) -> bool:
        return not self.partes and not self.titulo


def escapar_celda(texto: str) -> str:
    """Una barra vertical en un nombre romperia la tabla."""
    return str(texto).replace("|", "\\|")


def tabla(cabeceras: Iterable[str], filas: Iterable[Iterable]) -> str:
    cabeceras = list(cabeceras)
    lineas = ["| " + " | ".join(cabeceras) + " |",
              "|" + "|".join("---" for _ in cabeceras) + "|"]
    for fila in filas:
        lineas.append("| " + " | ".join(escapar_celda(c) for c in fila) + " |")
    return "\n".join(lineas)


class Cronista:
    def __init__(self, estilos: dict[str, Estilo],
                 por_defecto: Estilo | None = None) -> None:
        self.estilos = dict(estilos)
        self.por_defecto = por_defecto or Estilo()

    def estilo(self, tipo: str) -> Estilo:
        return self.estilos.get(tipo, self.por_defecto)

    # -- agrupacion ---------------------------------------------------------- #

    def bloques(self, eventos: Iterable[Evento]) -> Iterator[Bloque]:
        actual = Bloque()
        for evento in eventos:
            estilo = self.estilo(evento.tipo)
            if estilo.formato == "omitir":
                continue
            if estilo.formato == "seccion":
                if not actual.vacio:
                    yield actual
                actual = Bloque(titulo=f"{estilo.icono} {evento.texto}".strip(),
                                nivel=estilo.nivel)
                continue
            actual.anadir(estilo.formato,
                          f"{estilo.icono} {evento.texto}".strip()
                          if estilo.icono else evento.texto)
        if not actual.vacio:
            yield actual

    # -- salida --------------------------------------------------------------- #

    def markdown(self, registro: Registro | Iterable[Evento]) -> str:
        eventos = registro if isinstance(registro, Iterable) else list(registro)
        partes: list[str] = []
        for bloque in self.bloques(eventos):
            partes.append(self._bloque_a_markdown(bloque))
        return "\n\n".join(p for p in partes if p.strip())

    def _bloque_a_markdown(self, bloque: Bloque) -> str:
        salida: list[str] = []
        if bloque.titulo:
            salida.append(f"{'#' * bloque.nivel} {bloque.titulo}")

        detalles: list[str] = []

        def volcar_detalles() -> None:
            """Las tiradas van plegadas: estan, pero no estorban la lectura."""
            if not detalles:
                return
            salida.append(
                "<details>\n<summary>Tiradas</summary>\n\n```\n"
                + "\n".join(detalles)
                + "\n```\n\n</details>"
            )
            detalles.clear()

        for formato, texto in bloque.partes:
            if formato == "detalle":
                detalles.append(texto)
                continue
            volcar_detalles()
            if formato == "escena":
                salida.append(f"**{texto}**")
            elif formato == "destacado":
                salida.append(f"> {texto}")
            else:
                salida.append(texto)
        volcar_detalles()
        return "\n\n".join(salida)
