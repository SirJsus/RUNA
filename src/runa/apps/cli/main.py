"""Cuatro contra la Oscuridad en la terminal, en modo arbitro.

El programa tira los dados, aplica los modificadores y lleva las cuentas; tu
decides a quien atacas, que hechizo lanzas y si huyes o sobornas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from runa.apps.cli import consola as c
from runa.core.decisions import DecisorPorDefecto, Opcion, Pregunta
from runa.core.rng import RandomSource
from runa.games.cco import cronica
from runa.games.cco.exploracion import Exploracion
from runa.games.cco.intermedio import Intermedio
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Partida

PARTIDAS = Path("partidas")
GRUPO_SUGERIDO = [("Brakk", "guerrero"), ("Sela", "clerigo"),
                  ("Nim", "picaro"), ("Orin", "mago")]


# --------------------------------------------------------------------------- #
# Creacion del grupo
# --------------------------------------------------------------------------- #


def crear_grupo(juego: Juego, decisor, rng):
    eleccion = decisor.elegir(Pregunta.crear(
        "grupo", "¿Como formamos el grupo?", [
            Opcion("sugerido", "Grupo recomendado",
                   "guerrero, clerigo, picaro y mago"),
            Opcion("elegir", "Elegirlo yo", "cuatro personajes a mano"),
        ],
    ))
    if eleccion == "sugerido":
        return juego.crear_grupo(GRUPO_SUGERIDO, rng)

    composicion = []
    for i in range(1, 5):
        c.linea()
        clase = decisor.elegir(Pregunta.crear(
            "clase", f"Personaje {i} de 4: ¿que clase?",
            [Opcion(k, v.nombre, f"{v.vida_a_nivel(1)} Vida, "
                    f"{v.riqueza_inicial} de oro")
             for k, v in juego.clases.items()],
        ))
        por_defecto = GRUPO_SUGERIDO[i - 1][0]
        nombre = c.texto_libre("Nombre", por_defecto)
        composicion.append((nombre, clase))
    return juego.crear_grupo(composicion, rng)


def preparar_hechizos(juego: Juego, grupo, decisor) -> None:
    for personaje in grupo:
        limite = personaje.recursos.get("hechizos", 0)
        if not limite:
            continue
        c.seccion(f"{personaje.nombre} prepara {limite} hechizo(s)")
        c.linea(c.apagado("  Se pueden repetir copias del mismo hechizo."))
        disponibles = [h for h in juego.habilidades.para(personaje.clase.id)
                       if h.gasta == "hechizos"]
        # La primera opcion es la recomendada, y para un lanzador de nivel 1 lo
        # util es pegar fuerte antes que quitar maldiciones.
        preferencia = ["bola_de_fuego", "rayo", "dormir", "proteger",
                       "escapada", "bendicion"]
        disponibles.sort(key=lambda h: preferencia.index(h.id)
                         if h.id in preferencia else len(preferencia))
        elegidos = []
        for n in range(limite):
            id = decisor.elegir(Pregunta.crear(
                "hechizo", f"Hechizo {n + 1} de {limite}",
                [Opcion(h.id, h.nombre, h.notas.split(".")[0]) for h in disponibles],
            ))
            elegidos.append(id)
        juego.preparar_hechizos(personaje, elegidos)
        c.linea("  " + c.verde(", ".join(
            juego.habilidades[i].nombre for i in elegidos)))


def comprar(juego: Juego, grupo, decisor) -> None:
    catalogo = [o for o in juego.catalogo.values() if o.precio > 0
                and o.tipo != "servicio"]
    for personaje in grupo:
        while True:
            asequibles = [o for o in catalogo
                          if o.precio <= personaje.oro
                          and personaje.clase.permite_objeto(o)]
            if not asequibles:
                break
            opciones = [Opcion("", "Seguir asi", f"le quedan {personaje.oro} de oro")]
            opciones += [Opcion(o.id, o.nombre, f"{o.precio} oro") for o in asequibles]
            id = decisor.elegir(Pregunta.crear(
                "comprar", f"{personaje.nombre} tiene {personaje.oro} piezas de oro.",
                opciones,
            ))
            if not id:
                break
            objeto = juego.catalogo[id]
            if objeto.variantes:
                variante = decisor.elegir(Pregunta.crear(
                    "variante", f"¿{objeto.nombre} aplastante o cortante?",
                    [Opcion(v, v.capitalize()) for v in objeto.variantes],
                ))
                objeto = objeto.con_variante(variante)
            personaje.oro -= objeto.precio
            personaje.anadir(objeto)
            c.linea("  " + c.verde(f"{personaje.nombre} compra {objeto.nombre}."))
            for problema in personaje.problemas_de_equipo():
                c.aviso(problema)


# --------------------------------------------------------------------------- #
# Partida
# --------------------------------------------------------------------------- #


def mostrar_grupo(grupo) -> None:
    c.seccion("El grupo")
    for i, p in enumerate(grupo, 1):
        equipo = ", ".join(o.nombre for o in p.equipo if o.activo) or "sin equipo"
        estado = c.rojo("muerto") if p.muerto else f"{p.vida}/{p.vida_max} Vida"
        c.linea(f"  {i}. {c.negrita(p.nombre)} — {p.clase.nombre} nivel {p.nivel}"
                f", {estado}, {p.oro} oro")
        c.linea(c.apagado(f"     {equipo}"))


def intermedio(partida: Partida, decisor) -> bool:
    """Vuelta al pueblo. Devuelve True si el grupo baja otra vez."""
    c.titulo("De vuelta en el pueblo")
    partida.registro.al_anotar = lambda e: c.evento(e.tipo, e.texto)
    entre = Intermedio(partida, decisor)
    try:
        entre.anotar("intermedio", "De vuelta en el pueblo.")
        entre.vender()
        entre.resucitar()
        entre.reemplazar_caidos()
        entre.curar()
        c.seccion("Compra de equipo")
        comprar(partida.juego, partida.grupo, decisor)
        entre.reponer()
    finally:
        partida.registro.al_anotar = None

    mostrar_grupo(partida.grupo)
    seguir = decisor.elegir(Pregunta.crear(
        "seguir", "¿El grupo vuelve a bajar?", [
            Opcion(True, "Si, otra aventura"),
            Opcion(False, "No, dejarlo por hoy", "la partida queda guardada"),
        ],
    ))
    if not seguir:
        return False
    preparar_hechizos(partida.juego, partida.grupo, decisor)
    entre.nueva_aventura()
    return True


def jugar(partida: Partida, decisor, autoguardado: Path | None,
          limite: int = 500) -> None:
    partida.registro.al_anotar = lambda e: c.evento(e.tipo, e.texto)
    exploracion = Exploracion(partida, decisor)

    c.titulo("La mazmorra")
    if not partida.mapa.salas:
        exploracion.entrar()
    turnos = 0
    try:
        while exploracion.turno():
            turnos += 1
            if turnos >= limite:
                c.aviso(f"Limite de {limite} turnos alcanzado: se cierra la aventura.")
                break
            if autoguardado:
                partida.guardar(autoguardado)
    except SystemExit:
        raise
    finally:
        partida.registro.al_anotar = None

    c.titulo(f"Fin de la aventura {partida.campana.aventuras_jugadas + 1}")
    mostrar_grupo(partida.grupo)
    c.seccion("Mazmorra recorrida")
    c.linea(partida.mapa.describir())
    c.seccion("Resumen")
    c.linea("  " + partida.resumen())
    if partida.aventura.jefe_final_derrotado:
        c.linea("  " + c.verde("¡El jefe final ha caido!"))
    caidos = [p.nombre for p in partida.grupo.miembros if p.muerto]
    if caidos:
        c.linea("  " + c.rojo("Caidos: " + ", ".join(caidos)))
    partida.campana.aventuras_jugadas += 1


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #


def partida_nueva(juego: Juego, decisor, semilla: int | None, nombre: str,
                  rejilla: bool = True) -> Partida:
    c.titulo("Cuatro contra la Oscuridad")
    c.linea(c.apagado("  Tu decides; el programa tira los dados y lleva las cuentas."))
    rng = RandomSource(semilla)
    grupo = crear_grupo(juego, decisor, rng)
    mostrar_grupo(grupo)
    preparar_hechizos(juego, grupo, decisor)
    c.seccion("Compra de equipo")
    comprar(juego, grupo, decisor)
    mostrar_grupo(grupo)

    partida = Partida(juego, grupo, semilla=rng.seed, nombre=nombre,
                      rejilla=rejilla)
    partida.rng = rng          # se sigue con el mismo azar de la creacion
    return partida


def mostrar_losetas(juego: Juego, cual: str) -> int:
    """Dibuja las losetas para poder compararlas con las del reglamento.

    Estan transcritas a ojo de unos dibujos a mano, asi que conviene poder
    mirarlas: corregir una es editar su bloque `forma` en planos.yaml.
    """
    catalogo = juego.planos
    if cual == "todas":
        elegidas = [(k, v) for k, v in catalogo.entradas.items()]
        elegidas += sorted(catalogo.planos.items())
        c.titulo("Las losetas de la mazmorra")
        c.linea(c.apagado("  Transcritas a ojo del reglamento. Para corregir una, "
                          "edita su `forma` en planos.yaml."))
    else:
        if cual not in catalogo:
            c.error(f"no existe la loseta {cual!r}")
            return 1
        elegidas = [(cual, catalogo[cual])]

    for id, plano in elegidas:
        c.seccion(f"{id} — {plano.tipo}, {plano.ancho}x{plano.alto}")
        if plano.notas:
            c.linea(c.apagado(f"  {plano.notas}"))
        for fila in plano.dibujo().split("\n"):
            c.linea("    " + fila.replace("#", "██").replace(".", "  "))
        puertas = [str(s) for s in plano.salidas if s.puerta]
        abiertas = [str(s) for s in plano.salidas if not s.puerta]
        if puertas:
            c.linea(f"    puertas:   {', '.join(puertas)}")
        if abiertas:
            c.linea(f"    aberturas: {', '.join(abiertas)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="runa",
        description="Cuatro contra la Oscuridad en la terminal (modo arbitro).",
    )
    analizador.add_argument("archivo", nargs="?",
                            help="partida guardada que continuar")
    analizador.add_argument("--semilla", type=int,
                            help="semilla del azar, para repetir una partida")
    analizador.add_argument("--nombre", default="",
                            help="nombre de la partida (por defecto, uno con la semilla)")
    analizador.add_argument("--auto", action="store_true",
                            help="juega solo tomando siempre la opcion recomendada")
    analizador.add_argument("--sin-guardar", action="store_true",
                            help="no escribe ningun archivo de partida")
    analizador.add_argument("--aventuras", type=int, default=0,
                            help="cuantas aventuras encadenar como maximo "
                                 "(por defecto, sin limite; con --auto, una)")
    analizador.add_argument("--grafo", action="store_true",
                            help="no dibujar la mazmorra: llevarla solo como grafo "
                                 "y preguntar la forma de cada sala")
    analizador.add_argument("--exportar", metavar="ARCHIVO.md",
                            help="escribe la cronica de una partida guardada y termina")
    analizador.add_argument("--sin-cronica", action="store_true",
                            help="no escribe el archivo .md de la cronica")
    analizador.add_argument("--losetas", nargs="?", const="todas", metavar="d66",
                            help="enseña las losetas para cotejarlas con el libro")
    args = analizador.parse_args(argv)

    juego = Juego()
    if problemas := juego.validar():
        for p in problemas:
            c.error(p)
        return 2

    if args.losetas:
        return mostrar_losetas(juego, args.losetas)

    decisor = DecisorPorDefecto() if args.auto else c.ConsolaDecisor()

    if args.archivo:
        ruta = Path(args.archivo)
        if not ruta.exists():
            c.error(f"no existe la partida {ruta}")
            return 1
        partida = Partida.cargar(ruta, juego)
        if args.exportar:
            destino_md = Path(args.exportar)
            destino_md.parent.mkdir(parents=True, exist_ok=True)
            svg = ""
            if partida.mapa.rejilla is not None and len(partida.mapa.rejilla):
                plano = destino_md.with_name(destino_md.stem + "-plano.svg")
                plano.write_text(
                    partida.mapa.rejilla.svg(partida.mapa.puertas()), encoding="utf-8")
                svg = plano.name
            destino_md.write_text(cronica.escribir(partida, svg=svg), encoding="utf-8")
            c.linea(f"  Cronica escrita en {c.negrita(str(destino_md))}")
            return 0
        c.titulo(f"Continuando: {partida.nombre}")
        mostrar_grupo(partida.grupo)
    else:
        if args.exportar:
            c.error("--exportar necesita una partida guardada")
            return 1
        partida = partida_nueva(juego, decisor, args.semilla, args.nombre,
                                rejilla=not args.grafo)
        ruta = PARTIDAS / f"{partida.nombre}.json"

    destino = None if args.sin_guardar else ruta
    limite = 60 if args.auto else 500
    maximo = args.aventuras or (1 if args.auto else 10**6)
    while True:
        jugar(partida, decisor, destino, limite=limite)
        if destino:
            partida.guardar(destino)
        if partida.campana.aventuras_jugadas >= maximo:
            break
        if not partida.grupo.miembros or not intermedio(partida, decisor):
            break

    if destino:
        partida.guardar(destino)
        c.linea()
        c.linea(f"  Partida guardada en {c.negrita(str(destino))}")
        if not args.sin_cronica:
            svg = ""
            if partida.mapa.rejilla is not None and len(partida.mapa.rejilla):
                plano = destino.with_name(destino.stem + "-plano.svg")
                plano.write_text(
                    partida.mapa.rejilla.svg(partida.mapa.puertas()), encoding="utf-8")
                svg = plano.name
                c.linea(f"  Plano escrito en   {c.negrita(str(plano))}")
            cronica_md = destino.with_suffix(".md")
            cronica_md.write_text(cronica.escribir(partida, svg=svg), encoding="utf-8")
            c.linea(f"  Cronica escrita en {c.negrita(str(cronica_md))}")
        c.linea(c.apagado(f"  Continuala con:  runa {destino}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
