"""Registro de eventos de la partida.

Todo lo que ocurre queda anotado aqui, en orden. De ese registro salen tres
cosas: la cronica narrada al final de la aventura, la posibilidad de deshacer, y
unos tests que pueden afirmar sobre lo que paso y no solo sobre el resultado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class Evento:
    tipo: str
    texto: str
    datos: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.texto


class Registro:
    def __init__(self, al_anotar: Callable[[Evento], None] | None = None) -> None:
        self.eventos: list[Evento] = []
        # Quien escuche aqui ve los eventos segun ocurren: es lo que permite a
        # la terminal narrar en vivo sin que el motor sepa que existe.
        self.al_anotar = al_anotar

    def anotar(self, tipo: str, texto: str, **datos: Any) -> Evento:
        evento = Evento(tipo, texto, datos)
        self.eventos.append(evento)
        if self.al_anotar is not None:
            self.al_anotar(evento)
        return evento

    def __iter__(self) -> Iterator[Evento]:
        return iter(self.eventos)

    def __len__(self) -> int:
        return len(self.eventos)

    def de_tipo(self, *tipos: str) -> list[Evento]:
        return [e for e in self.eventos if e.tipo in tipos]

    @property
    def tipos(self) -> list[str]:
        """La secuencia de tipos, util para comprobar el orden de las fases."""
        return [e.tipo for e in self.eventos]

    def cronica(self, desde: int = 0) -> str:
        return "\n".join(e.texto for e in self.eventos[desde:] if e.texto)

    def marca(self) -> int:
        """Posicion actual, para poder narrar solo lo que venga despues."""
        return len(self.eventos)
