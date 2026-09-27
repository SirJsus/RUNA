"""La cronica de una partida de Cuatro contra la Oscuridad, en Markdown.

Aqui vive el vocabulario: que evento es un encabezado, cual una tirada que se
pliega y cual merece destacarse. La maquinaria esta en `core/cronica`.
"""

from __future__ import annotations

from typing import Any

from runa.core.cronica import Cronista, Estilo, tabla

ESTILOS: dict[str, Estilo] = {
    # Encabezados
    "aventura": Estilo("seccion", "⚔", nivel=2),
    "intermedio": Estilo("seccion", "🏘", nivel=2),
    "entrada": Estilo("seccion", "🚪", nivel=3),
    "sala": Estilo("seccion", "🚪", nivel=3),

    # Escenas dentro de una sala
    "combate_inicio": Estilo("escena", "⚔"),
    "errantes": Estilo("escena", "👣"),
    "refuerzos": Estilo("escena", "💀"),

    # Tiradas: estan, pero plegadas para no estorbar la lectura
    "ataque": Estilo("detalle"),
    "defensa": Estilo("detalle"),
    "hechizo": Estilo("detalle"),
    "salvacion": Estilo("detalle"),
    "desarmar": Estilo("detalle"),
    "resurreccion": Estilo("detalle"),
    "fantasma": Estilo("detalle"),
    "turno_monstruos": Estilo("detalle"),

    # Lo que uno recuerda de una partida
    "victoria": Estilo("destacado", "🏆"),
    "derrota": Estilo("destacado", "☠"),
    "muerte": Estilo("destacado", "☠"),
    "botin": Estilo("destacado", "💰"),
    "xp": Estilo("destacado", "✨"),
    "jefe_final": Estilo("destacado", "👑"),
    "pista": Estilo("destacado", "🔎"),
    "secreto": Estilo("destacado", "🔎"),
    "fin": Estilo("destacado", "🕯"),
    "pendiente": Estilo("destacado", "📌"),

    # Ruido que no aporta a la lectura
    "accion": Estilo("omitir"),
    "movimiento": Estilo("omitir"),
    "contenido": Estilo("linea"),
}


def cronista() -> Cronista:
    return Cronista(ESTILOS)


# --------------------------------------------------------------------------- #
# Secciones propias de la partida
# --------------------------------------------------------------------------- #


def _fila_de_personaje(personaje) -> list:
    estado = "muerto" if personaje.muerto else f"{personaje.vida}/{personaje.vida_max}"
    equipo = ", ".join(o.nombre for o in personaje.equipo if o.activo) or "—"
    return [personaje.nombre, personaje.clase.nombre, personaje.nivel,
            estado, personaje.oro, equipo]


def seccion_grupo(grupo, titulo: str = "El grupo") -> str:
    return f"## {titulo}\n\n" + tabla(
        ["Personaje", "Clase", "Nivel", "Vida", "Oro", "Equipo"],
        [_fila_de_personaje(p) for p in grupo],
    )


def seccion_mazmorra(mapa) -> str:
    """Solo refleja la aventura en curso: cada incursion estrena mazmorra."""
    if not len(mapa):
        return ""
    filas = []
    for sala in mapa:
        marcas = []
        if not sala.limpia:
            marcas.append("con monstruos")
        if sala.buscada:
            marcas.append("registrada")
        if sala.secreta:
            marcas.append("secreta")
        filas.append([sala.id, sala.tipo, sala.plano or "—",
                      sala.contenido or "sin resolver", ", ".join(marcas) or "—"])
    return "## La mazmorra recorrida\n\n" + tabla(
        ["Sala", "Tipo", "Plano", "Contenido", "Notas"], filas)


def seccion_plano(partida, svg: str = "") -> str:
    """El dibujo de la mazmorra: en texto siempre, y enlazado en SVG si lo hay."""
    rejilla = partida.mapa.rejilla
    if rejilla is None or not len(rejilla):
        return ""
    partes = ["## El plano"]
    if svg:
        partes.append(f"![Plano de la mazmorra]({svg})")
    partes.append("```\n" + rejilla.ascii(partida.mapa.puertas()) + "\n```")
    partes.append("*`--` y `|` son muros, un hueco es un paso entre salas y `*` "
                  "una salida por explorar.*")
    return "\n\n".join(partes)


def seccion_campana(partida) -> str:
    campana, aventura = partida.campana, partida.aventura
    filas = [
        ["Aventuras jugadas", campana.aventuras_jugadas],
        ["Salas recorridas", len(partida.mapa)],
        ["Encuentros con esbirros", f"{aventura.encuentros_esbirros}/10"],
        ["Jefes encontrados", aventura.jefes_vistos],
        ["Oro del grupo", partida.grupo.oro],
        ["Semilla", partida.rng.seed],
    ]
    if campana.pistas:
        filas.append(["Pistas", ", ".join(
            f"{n}: {v}" for n, v in sorted(campana.pistas.items()) if v) or "—"])
    if aventura.jefe_final_derrotado:
        filas.append(["Jefe final", "derrotado"])
    elif aventura.jefe_final_encontrado:
        filas.append(["Jefe final", "encontrado, sin derrotar"])
    caidos = [p.nombre for p in partida.grupo.miembros if p.muerto]
    if caidos:
        filas.append(["Caidos", ", ".join(caidos)])
    return "## Resumen\n\n" + tabla(["Dato", "Valor"], filas)


def escribir(partida: Any, titulo: str = "", svg: str = "") -> str:
    """El documento entero: cabecera, grupo, cronica, plano, mazmorra y resumen."""
    partes = [
        f"# {titulo or f'Cronica de {partida.nombre}'}",
        "*Cuatro contra la Oscuridad — partida jugada con RUNA.*",
        seccion_grupo(partida.grupo, "El grupo al terminar"),
        "## La cronica",
        cronista().markdown(partida.registro) or "*No paso nada digno de mencion.*",
        seccion_plano(partida, svg),
        seccion_mazmorra(partida.mapa),
        seccion_campana(partida),
    ]
    return "\n\n".join(p for p in partes if p.strip()) + "\n"
