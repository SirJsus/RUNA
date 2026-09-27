"""Presentacion en terminal: colores, cajas y el decisor que pregunta al jugador."""

from __future__ import annotations

import os
import sys
from typing import Any

from runa.core.decisions import Decisor, DecisionImposible, Pregunta

ANCHO = 74


def _colores_activos() -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("RUNA_SIN_COLOR"):
        return False
    return sys.stdout.isatty()


COLOR = _colores_activos()


def _c(codigo: str, texto: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if COLOR else texto


def negrita(t: str) -> str:  return _c("1", t)
def apagado(t: str) -> str:  return _c("2", t)
def rojo(t: str) -> str:     return _c("31", t)
def verde(t: str) -> str:    return _c("32", t)
def amarillo(t: str) -> str: return _c("33", t)
def azul(t: str) -> str:     return _c("36", t)


# Como se pinta cada tipo de evento de la cronica.
ESTILOS = {
    "ataque": azul, "hechizo": azul, "defensa": apagado, "salvacion": apagado,
    "desarmar": apagado, "dano": verde, "herida": rojo, "curacion": verde,
    "victoria": verde, "derrota": rojo, "muerte": rojo, "botin": amarillo,
    "xp": amarillo, "jefe_final": rojo, "sorpresa": amarillo, "moral": amarillo,
    "prohibido": rojo, "pendiente": amarillo, "secreto": amarillo,
    "regeneracion": rojo, "aliento": rojo, "petrificado": rojo, "suerte": amarillo,
}


def titulo(texto: str) -> None:
    print()
    print(negrita("=" * ANCHO))
    print(negrita(f" {texto}"))
    print(negrita("=" * ANCHO))


def seccion(texto: str) -> None:
    print()
    print(negrita(texto))
    print(apagado("-" * ANCHO))


def linea(texto: str = "") -> None:
    print(texto)


def evento(tipo: str, texto: str) -> None:
    estilo = ESTILOS.get(tipo)
    for i, trozo in enumerate(texto.split("\n")):
        print(("  " if i else "") + (estilo(trozo) if estilo else trozo))


def aviso(texto: str) -> None:
    print(amarillo(f"  ! {texto}"))


def error(texto: str) -> None:
    print(rojo(f"  x {texto}"))


class ConsolaDecisor(Decisor):
    """Pregunta al jugador por la terminal. Este es el modo arbitro."""

    def __init__(self, entrada=input, salida=print) -> None:
        self.entrada = entrada
        self.salida = salida

    def elegir(self, pregunta: Pregunta) -> Any:
        if not pregunta.opciones:
            raise DecisionImposible(f"{pregunta.id!r} no ofrece ninguna opcion")
        if len(pregunta.opciones) == 1:
            # No se pregunta lo que no tiene alternativa.
            return pregunta.opciones[0].valor

        self.salida("")
        if plano := pregunta.contexto.get("plano"):
            for trozo in plano.split("\n"):
                self.salida(apagado(trozo))
            self.salida("")
        for trozo in pregunta.texto.split("\n"):
            self.salida(negrita(trozo))
        for i, opcion in enumerate(pregunta.opciones, 1):
            detalle = apagado(f"  ({opcion.detalle})") if opcion.detalle else ""
            self.salida(f"  {azul(str(i))}) {opcion.etiqueta}{detalle}")

        while True:
            try:
                bruto = self.entrada(f"  > [1-{len(pregunta.opciones)}] ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit("\nPartida interrumpida.") from None
            if not bruto:
                return pregunta.opciones[0].valor      # Enter = la recomendada
            if bruto.isdigit() and 1 <= int(bruto) <= len(pregunta.opciones):
                return pregunta.opciones[int(bruto) - 1].valor
            self.salida(rojo(f"  Escribe un numero entre 1 y {len(pregunta.opciones)}."))


def texto_libre(consulta: str, por_defecto: str = "") -> str:
    sufijo = apagado(f" [{por_defecto}]") if por_defecto else ""
    try:
        respuesta = input(f"  {consulta}{sufijo}: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nPartida interrumpida.") from None
    return respuesta or por_defecto
