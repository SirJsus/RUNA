"""Entre una aventura y la siguiente.

Vender el botin, curar heridas, resucitar caidos, comprar equipo y preparar de
nuevo los hechizos. Es lo que convierte varias incursiones en una campana.

Como el resto del juego, todas las elecciones salen por el puerto `Decisor`.
"""

from __future__ import annotations

from typing import Any

from runa.core.decisions import Decisor, Opcion, Pregunta
from runa.core.dice import roll
from runa.core.entities import Objeto, Personaje

# Precios de venta del equipo magico (pagina 24). El resto se vende a mitad.
VENTA_MAGICA = {"pocion": 50, "anillo": 50, "varita": 100, "pergamino": 100,
                "baston": 100}
RESURRECCION = 1000
BONIFICACION_ENANO = 20     # por ciento, al vender gemas y joyas


class Intermedio:
    def __init__(self, partida: Any, decisor: Decisor) -> None:
        self.p = partida
        self.juego = partida.juego
        self.decisor = decisor

    @property
    def rng(self):
        # Se lee de la partida, no se copia: si la partida cambia de fuente de
        # azar (al cargarla, por ejemplo), aqui no puede quedarse una vieja.
        return self.p.rng

    @rng.setter
    def rng(self, fuente) -> None:
        self.p.rng = fuente

    @property
    def grupo(self):
        return self.p.grupo

    def anotar(self, tipo: str, texto: str, **datos):
        return self.p.anotar(tipo, texto, **datos)

    def preguntar(self, id: str, texto: str, opciones, **ctx):
        return self.decisor.elegir(Pregunta.crear(id, texto, opciones, **ctx))

    # -- venta ---------------------------------------------------------------- #

    def precio_de_venta(self, objeto: Objeto, vendedor: Personaje) -> int:
        """La mitad del precio, salvo el equipo magico, que tiene tarifa propia.

        Un enano saca un 20% mas por gemas y joyas: es orfebre de nacimiento.
        """
        if "magico" in objeto.etiquetas:
            for etiqueta, precio in VENTA_MAGICA.items():
                if etiqueta in objeto.etiquetas:
                    # "100 piezas de oro por cada hechizo que contengan"
                    base = precio * max(1, objeto.usos)
                    break
            else:
                base = roll("d6xd6", self.rng).total
        elif objeto.tipo == "tesoro":
            base = objeto.precio          # gemas y joyas valen su tasacion
        else:
            base = objeto.precio_venta()

        if "gema" in objeto.etiquetas and vendedor.clase.id == "enano":
            base += base * BONIFICACION_ENANO // 100
        return base

    def vender(self) -> int:
        total = 0
        for personaje in self.grupo.vivos:
            while True:
                vendibles = [o for o in personaje.equipo
                             if self.precio_de_venta(o, personaje) > 0]
                if not vendibles:
                    break
                opciones = [Opcion("", "No vender nada mas",
                                   f"{personaje.nombre} tiene {personaje.oro} de oro")]
                opciones += [
                    Opcion(i, o.nombre, f"{self.precio_de_venta(o, personaje)} oro")
                    for i, o in enumerate(vendibles)
                ]
                elegido = self.preguntar(
                    "vender", f"¿Vende {personaje.nombre} algo?", opciones,
                    personaje=personaje,
                )
                if elegido == "":
                    break
                objeto = vendibles[int(elegido)]
                precio = self.precio_de_venta(objeto, personaje)
                personaje.equipo.remove(objeto)
                personaje.oro += precio
                total += precio
                self.anotar("venta",
                            f"{personaje.nombre} vende {objeto.nombre} por {precio} de oro.")
        return total

    # -- caidos ---------------------------------------------------------------- #

    def resucitar(self) -> None:
        """1000 de oro por intento; se logra sacando IGUAL O MENOS que su nivel."""
        for muerto in [p for p in self.grupo.miembros if p.muerto]:
            pagadores = [p for p in self.grupo.vivos if p.oro >= RESURRECCION]
            fondo_comun = self.grupo.oro >= RESURRECCION
            if not fondo_comun:
                self.anotar(
                    "iglesia",
                    f"El ritual por {muerto.nombre} cuesta {RESURRECCION} y el grupo "
                    f"solo tiene {self.grupo.oro}.",
                )
                continue
            if self.preguntar(
                "resucitar",
                f"¿Pagar {RESURRECCION} de oro por resucitar a {muerto.nombre} "
                f"({muerto.clase.nombre} nivel {muerto.nivel})?",
                [Opcion(False, "No, darle sepultura"),
                 Opcion(True, "Si, pagar el ritual",
                        f"se logra con {muerto.nivel} o menos en d6")],
            ) is not True:
                self.anotar("iglesia", f"{muerto.nombre} recibe sepultura.")
                continue

            self._cobrar_al_grupo(RESURRECCION)
            r = self.juego.tirar("resurreccion", muerto, self.rng,
                                 dificultad=muerto.nivel)
            self.anotar("resurreccion", r.describir(), tirada=r)
            if r.exito:
                muerto.muerto = False
                muerto.vida = muerto.vida_max
                self.anotar("resurreccion", f"¡{muerto.nombre} vuelve a la vida!")
            else:
                self.anotar("resurreccion",
                            f"El ritual falla. {muerto.nombre} se pierde para siempre.")

    def _cobrar_al_grupo(self, cantidad: int) -> None:
        for personaje in sorted(self.grupo.miembros, key=lambda p: -p.oro):
            if cantidad <= 0:
                break
            pagado = min(personaje.oro, cantidad)
            personaje.oro -= pagado
            cantidad -= pagado

    def reemplazar_caidos(self) -> None:
        """"Se debe elegir un nuevo personaje de primer nivel para reemplazarlo"."""
        for i, caido in list(enumerate(self.grupo.miembros)):
            if not caido.muerto:
                continue
            clase = self.preguntar(
                "reemplazo",
                f"{caido.nombre} ya no vuelve. ¿Que clase le reemplaza?",
                [Opcion(k, v.nombre, f"{v.vida_a_nivel(1)} Vida")
                 for k, v in self.juego.clases.items()],
            )
            nuevo = self.juego.crear_personaje(
                f"{self.juego.clases[clase].nombre} novato", clase, self.rng
            )
            self.grupo.miembros[i] = nuevo
            self.anotar("reclutamiento",
                        f"{nuevo.nombre} ocupa el puesto de {caido.nombre}.")

    # -- descanso --------------------------------------------------------------- #

    def curar(self) -> None:
        """La iglesia cura a 10 de oro el punto, como el curandero errante."""
        for personaje in self.grupo.vivos:
            while personaje.herido and personaje.oro >= 10:
                if self.preguntar(
                    "curar",
                    f"{personaje.nombre} esta a {personaje.vida}/{personaje.vida_max} "
                    f"y tiene {personaje.oro} de oro.",
                    [Opcion(True, "Pagar 10 por 1 punto de Vida"),
                     Opcion(False, "Dejarlo asi")],
                ) is not True:
                    break
                personaje.oro -= 10
                personaje.curar(1)
                self.anotar("curacion",
                            f"{personaje.nombre} se cura ({personaje.vida}/{personaje.vida_max}).")

    def reponer(self) -> None:
        """Reinicia lo que se agota por aventura y limpia las condiciones."""
        for personaje in self.grupo.miembros:
            if personaje.muerto:
                continue
            personaje.recursos = personaje.clase.recursos_a_nivel(personaje.nivel)
            personaje.limpiar_estados("aventura")
            personaje.limpiar_estados("combate")
        self.anotar("descanso",
                    "El grupo descansa: bendiciones, curaciones, suerte e ira al completo.")

    def preparar_hechizos(self) -> None:
        for personaje in self.grupo.vivos:
            limite = personaje.recursos.get("hechizos", 0)
            if not limite:
                continue
            disponibles = [h for h in self.juego.habilidades.para(personaje.clase.id)
                           if h.gasta == "hechizos"]
            elegidos = []
            for n in range(limite):
                elegidos.append(self.preguntar(
                    "hechizo",
                    f"{personaje.nombre} prepara el hechizo {n + 1} de {limite}",
                    [Opcion(h.id, h.nombre) for h in disponibles],
                ))
            self.juego.preparar_hechizos(personaje, elegidos)
            self.anotar(
                "hechizos",
                f"{personaje.nombre} prepara: " + ", ".join(
                    self.juego.habilidades[i].nombre for i in elegidos),
            )

    # -- la vuelta a la mazmorra -------------------------------------------------- #

    def nueva_aventura(self) -> None:
        """Deja la partida lista para volver a bajar: mapa nuevo, campana intacta."""
        from runa.core.mapa import Mapa
        from runa.core.rejilla import Rejilla
        from runa.games.cco.partida import Aventura

        con_rejilla = self.p.mapa.rejilla is not None
        self.p.mapa = Mapa(Rejilla() if con_rejilla else None)
        self.p.aventura = Aventura()
        self.p.xp_pendientes = 0
        self.anotar("aventura",
                    f"Comienza la aventura {self.p.campana.aventuras_jugadas + 1}.")

    def resolver(self, con_compra=None) -> None:
        """El intermedio completo, en el orden en que tiene sentido hacerlo."""
        self.anotar("intermedio", "De vuelta en el pueblo.")
        self.vender()
        self.resucitar()
        self.reemplazar_caidos()
        self.curar()
        if con_compra is not None:
            con_compra(self.grupo)
        self.reponer()
        self.preparar_hechizos()
