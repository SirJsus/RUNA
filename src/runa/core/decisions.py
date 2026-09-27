"""Puerto de decisiones.

El motor nunca decide por el jugador: cuando hace falta una eleccion, pregunta a
traves de esta interfaz. Quien la implemente determina el modo de juego:

  * `DecisorGuion`      -> respuestas prefijadas (tests)
  * `DecisorPorDefecto` -> siempre la opcion recomendada (humo, y semilla del
                           futuro modo automatico)
  * la CLI              -> pregunta al jugador (modo arbitro)

Por eso el bucle de juego se escribe una sola vez y sirve para los dos modos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


class DecisionImposible(RuntimeError):
    """Se pregunto algo sin opciones validas, o el guion se quedo sin respuestas."""


@dataclass(frozen=True)
class Opcion:
    valor: Any
    etiqueta: str
    detalle: str = ""

    def __str__(self) -> str:
        return f"{self.etiqueta} ({self.detalle})" if self.detalle else self.etiqueta


@dataclass(frozen=True)
class Pregunta:
    id: str
    texto: str
    opciones: tuple[Opcion, ...] = ()
    contexto: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def crear(
        cls, id: str, texto: str, opciones: Iterable[Opcion | tuple | Any], **contexto: Any
    ) -> "Pregunta":
        normalizadas = []
        for opcion in opciones:
            if isinstance(opcion, Opcion):
                normalizadas.append(opcion)
            elif isinstance(opcion, tuple):
                normalizadas.append(Opcion(*opcion))
            else:
                normalizadas.append(Opcion(opcion, str(opcion)))
        return cls(id, texto, tuple(normalizadas), contexto)

    @property
    def valores(self) -> list[Any]:
        return [o.valor for o in self.opciones]


class Decisor(ABC):
    @abstractmethod
    def elegir(self, pregunta: Pregunta) -> Any:
        """Devuelve el `valor` de una de las opciones de la pregunta."""

    def _validar(self, pregunta: Pregunta, valor: Any) -> Any:
        if valor not in pregunta.valores:
            raise DecisionImposible(
                f"{valor!r} no es una respuesta valida a {pregunta.id!r} "
                f"(validas: {pregunta.valores})"
            )
        return valor


class DecisorPorDefecto(Decisor):
    """Siempre la primera opcion, que por convenio es la recomendada."""

    def elegir(self, pregunta: Pregunta) -> Any:
        if not pregunta.opciones:
            raise DecisionImposible(f"{pregunta.id!r} no ofrece ninguna opcion")
        return pregunta.opciones[0].valor


class DecisorGuion(Decisor):
    """Respuestas prefijadas por id de pregunta, con reserva por defecto.

        DecisorGuion({"accion": ["atacar", "atacar"], "objetivo": "goblins"})

    Una lista se consume en orden; un valor suelto se repite siempre. Lo que no
    este en el guion cae en la primera opcion.
    """

    def __init__(self, respuestas: dict[str, Any] | None = None, estricto: bool = False) -> None:
        self.guion: dict[str, Any] = dict(respuestas or {})
        self.estricto = estricto
        self.preguntadas: list[str] = []

    def elegir(self, pregunta: Pregunta) -> Any:
        self.preguntadas.append(pregunta.id)
        if not pregunta.opciones:
            raise DecisionImposible(f"{pregunta.id!r} no ofrece ninguna opcion")
        if pregunta.id not in self.guion:
            if self.estricto:
                raise DecisionImposible(f"el guion no contempla {pregunta.id!r}")
            return pregunta.opciones[0].valor
        respuesta = self.guion[pregunta.id]
        if isinstance(respuesta, list):
            if not respuesta:
                if self.estricto:
                    raise DecisionImposible(f"el guion se quedo sin respuestas para {pregunta.id!r}")
                return pregunta.opciones[0].valor
            respuesta = respuesta.pop(0)
        if callable(respuesta):
            respuesta = respuesta(pregunta)
        return self._validar(pregunta, respuesta)
