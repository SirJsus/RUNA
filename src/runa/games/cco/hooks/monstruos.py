"""Reglas propias de cada monstruo que no caben en datos.

Los modificadores y prohibiciones de un monstruo van en `monstruos.yaml`; lo que
necesita logica —regenerar, exhalar fuego, petrificar al empezar— se registra
aqui por id y el bucle de combate lo llama en dos momentos:

  * `antes_del_combate(combate, encuentro)`    una sola vez, al empezar
  * `turno(combate, encuentro) -> bool`        cada turno del monstruo;
                                               True = sustituye a sus ataques
"""

from __future__ import annotations

from typing import Any, Callable

from runa.core.dice import roll


PUNTOS = ("antes", "turno", "al_herir", "tras_herir", "al_morir", "tras_hechizo")


class GanchosMonstruo:
    """Registro de reglas propias, indexadas por id de monstruo y momento.

      antes(combate, enc)                  una vez, al empezar el combate
      turno(combate, enc) -> bool          su turno; True sustituye sus ataques
      al_herir(combate, enc, personaje)    antes de aplicar dano; True lo sustituye
      tras_herir(combate, enc, personaje)  despues del dano (venenos, contagios)
      al_morir(combate, enc)               al ser derrotado de verdad
      tras_hechizo(combate, enc, muertos)  cuando un hechizo le hace bajas
    """

    def __init__(self) -> None:
        for punto in PUNTOS:
            setattr(self, punto, {})

    def registrar(self, punto: str, id: str) -> Callable:
        if punto not in PUNTOS:
            raise ValueError(f"punto de gancho desconocido: {punto!r}")

        def envoltorio(f: Callable) -> Callable:
            getattr(self, punto)[id] = f
            return f
        return envoltorio

    def registrar_antes(self, id: str) -> Callable:
        return self.registrar("antes", id)

    def registrar_turno(self, id: str) -> Callable:
        return self.registrar("turno", id)


def registrar(juego: Any) -> GanchosMonstruo:
    ganchos = GanchosMonstruo()

    def salvacion_de_todos(combate, nombre, nivel, etiquetas, castigo) -> None:
        amenaza = juego.amenaza(nombre, nivel, etiquetas)
        for personaje in list(combate.vivos):
            r = juego.tirar("salvacion", personaje, combate.rng, amenaza=amenaza)
            combate.reg.anotar("salvacion", r.describir(), tirada=r)
            if not r.exito:
                castigo(personaje)

    # -- al empezar el combate ---------------------------------------------- #

    @ganchos.registrar_antes("medusa")
    def mirada_de_medusa(combate, encuentro):
        def petrificar(personaje):
            personaje.estados.append(juego.estado("petrificado"))
            combate.reg.anotar("petrificado",
                               f"{personaje.nombre} queda convertido en piedra.")
        salvacion_de_todos(combate, "Mirada de la medusa", 4, ["mirada"], petrificar)

    @ganchos.registrar_antes("catoblepas")
    def mirada_de_catoblepas(combate, encuentro):
        def herir(personaje):
            personaje.herir(1)
            combate.reg.anotar("herida", f"{personaje.nombre} pierde 1 Vida.")
        salvacion_de_todos(combate, "Mirada del catoblepas", 4, ["mirada"], herir)

    @ganchos.registrar_antes("senor_del_caos")
    def poderes_del_senor_del_caos(combate, encuentro):
        tirada = roll("d6", combate.rng)
        if tirada.total <= 3:
            combate.reg.anotar("poder", "El Senor del Caos no tiene poderes especiales.")
            return
        if tirada.total == 4:
            combate.reg.anotar("poder", "Mal de ojo: hay que salvar con 4+.")
            amenaza = juego.amenaza("Mal de ojo", 4, ["mirada"])
            for personaje in list(combate.vivos):
                r = juego.tirar("salvacion", personaje, combate.rng, amenaza=amenaza)
                combate.reg.anotar("salvacion", r.describir(), tirada=r)
                if not r.exito:
                    personaje.estados.append(juego.estado("mal_de_ojo"))
        elif tirada.total == 5:
            combate.reg.anotar("poder", "Drenaje de energia: cada herida puede costar un nivel.")
            combate.marcas["drena_energia"] = True
        else:
            combate.reg.anotar("poder", "¡Explosion de fuego del infierno! Salvar con 6+.")
            def quemar(personaje):
                personaje.herir(2)
                combate.reg.anotar("herida", f"{personaje.nombre} pierde 2 Vida.")
            salvacion_de_todos(combate, "Fuego del infierno", 6, ["fuego"], quemar)

    # -- en cada turno del monstruo ------------------------------------------ #

    @ganchos.registrar_turno("trolls")
    def regeneracion_de_los_trolls(combate, encuentro) -> bool:
        """Cada troll caido tira d6: con 5-6 se levanta y sigue luchando."""
        caidos = encuentro.cantidad_inicial - encuentro.cantidad
        if caidos <= 0:
            return False
        vueltos = 0
        for _ in range(caidos):
            if roll("d6", combate.rng).total >= 5:
                vueltos += 1
        if vueltos:
            encuentro.cantidad += vueltos
            combate.reg.anotar(
                "regeneracion",
                f"{vueltos} troll(s) se regeneran y vuelven a la pelea "
                f"(quedan {encuentro.cantidad}).",
            )
        return False

    def aliento(combate, encuentro, nivel: int, medio_nivel: bool, dano: int) -> bool:
        tirada = roll("d6", combate.rng)
        if tirada.total > 2:
            return False
        combate.reg.anotar("aliento", f"¡{encuentro.nombre} exhala fuego!")
        amenaza = juego.amenaza(f"Aliento de {encuentro.nombre}", nivel, ["fuego", "aliento"])
        for personaje in list(combate.vivos):
            etiquetas = {"aliento_de_dragon"} if medio_nivel else set()
            r = juego.tirar("salvacion", personaje, combate.rng,
                            amenaza=amenaza, etiquetas=etiquetas)
            combate.reg.anotar("salvacion", r.describir(), tirada=r)
            if not r.exito:
                personaje.herir(dano)
                combate.reg.anotar("herida", f"{personaje.nombre} pierde {dano} Vida.")
        return True

    @ganchos.registrar_turno("dragon_pequeno")
    def aliento_del_dragon(combate, encuentro) -> bool:
        # Con 1-2 exhala en vez de morder; cada personaje suma medio nivel.
        return aliento(combate, encuentro, nivel=6, medio_nivel=True, dano=1)

    @ganchos.registrar_turno("quimera")
    def aliento_de_la_quimera(combate, encuentro) -> bool:
        return aliento(combate, encuentro, nivel=4, medio_nivel=False, dano=1)

    # -- venenos y heridas infectadas ---------------------------------------- #

    def veneno(id: str, nivel: int, etiqueta: str = "veneno"):
        """Quien resulte herido salva contra el veneno o pierde 1 Vida mas."""

        @ganchos.registrar("tras_herir", id)
        def _(combate, encuentro, personaje):
            if not personaje.vivo:
                return
            amenaza = juego.amenaza(f"Veneno (nivel {nivel})", nivel, ["veneno", etiqueta])
            r = juego.tirar("salvacion", personaje, combate.rng, amenaza=amenaza,
                            etiquetas={etiqueta})
            combate.reg.anotar("salvacion", r.describir(), tirada=r)
            if not r.exito:
                personaje.herir(1)
                combate.reg.anotar("herida",
                                   f"{personaje.nombre} pierde 1 Vida mas por el veneno.")

    veneno("ciempies_gigantes", 2)
    veneno("arana_gigante", 3)
    veneno("funjis", 3, etiqueta="veneno_hongo")   # los halflings suman su nivel

    @ganchos.registrar("tras_herir", "ratas")
    def herida_infectada(combate, encuentro, personaje):
        """1 entre 6 de perder 1 Vida adicional por la mordedura."""
        if not personaje.vivo:
            return
        if roll("d6", combate.rng).total == 1:
            personaje.herir(1)
            combate.reg.anotar(
                "herida", f"La herida de {personaje.nombre} se infecta: 1 Vida mas.")

    @ganchos.registrar("tras_herir", "momia")
    def contagio_de_momia(combate, encuentro, personaje):
        """Quien muere a manos de una momia se convierte en otra momia."""
        if personaje.vivo:
            return
        combate.refuerzos.append("momia")
        combate.reg.anotar(
            "contagio",
            f"{personaje.nombre} se levanta convertido en momia: habra que combatirla.",
        )

    @ganchos.registrar("tras_herir", "senor_del_caos")
    def drenaje_de_energia(combate, encuentro, personaje):
        if not combate.marcas.get("drena_energia") or not personaje.vivo:
            return
        amenaza = juego.amenaza("Drenaje de energia", 4, ["drenaje"])
        r = juego.tirar("salvacion", personaje, combate.rng, amenaza=amenaza)
        combate.reg.anotar("salvacion", r.describir(), tirada=r)
        if not r.exito:
            personaje.bajar_nivel()
            combate.reg.anotar(
                "drenaje",
                f"{personaje.nombre} pierde un nivel (ahora {personaje.nivel}).")

    @ganchos.registrar("al_morir", "senor_del_caos")
    def secreto_del_senor_del_caos(combate, encuentro):
        """Al matarlo, con 5-6 un personaje encuentra una Pista."""
        tirada = roll("d6", combate.rng)
        if tirada.total >= 5:
            combate.sucesos.append("pista")
            combate.reg.anotar("pista", "Entre los restos del Senor del Caos hay una pista.")

    # -- la Plaga del Hierro roba en vez de herir ------------------------------ #

    ORDEN_DE_ROBO = ("armadura", "escudo", "arma")

    @ganchos.registrar("al_herir", "plaga_del_hierro")
    def devorar_metal(combate, encuentro, personaje) -> bool:
        for tipo in ORDEN_DE_ROBO:
            objeto = personaje.equipado(tipo)
            if objeto is not None:
                personaje.equipo.remove(objeto)
                combate.reg.anotar(
                    "robo", f"La Plaga del Hierro devora {objeto.nombre} de {personaje.nombre}.")
                return True
        perdido = min(personaje.oro, roll("3d6", combate.rng).total)
        personaje.oro -= perdido
        combate.reg.anotar(
            "robo",
            f"La Plaga del Hierro se lleva {perdido} de oro de {personaje.nombre}."
            if perdido else f"{personaje.nombre} ya no tiene nada de metal que perder.")
        return True

    # -- gremlins invisibles --------------------------------------------------- #

    PRIORIDAD_GREMLIN = ("magico", "pergamino", "consumible", "arma", "tesoro")

    @ganchos.registrar_antes("gremlins_invisibles")
    def robo_de_gremlins(combate, encuentro):
        """Roban d6+3 objetos por orden de preferencia; el oro va en paquetes de 10."""
        cuantos = roll("d6+3", combate.rng).total
        robados = 0
        for categoria in PRIORIDAD_GREMLIN:
            for personaje in combate.grupo.miembros:
                for objeto in list(personaje.equipo):
                    if robados >= cuantos:
                        break
                    if categoria in objeto.etiquetas or objeto.tipo == categoria:
                        personaje.equipo.remove(objeto)
                        combate.reg.anotar(
                            "robo", f"Los gremlins se llevan {objeto.nombre} de {personaje.nombre}.")
                        robados += 1
        for personaje in combate.grupo.miembros:
            while robados < cuantos and personaje.oro >= 10:
                personaje.oro -= 10
                robados += 1
                combate.reg.anotar("robo", f"Los gremlins se llevan 10 de oro de {personaje.nombre}.")
        if robados < cuantos:
            # "Si los gremlins roban TODO tu equipo, dejaran una nota de agradecimiento."
            combate.sucesos.append("pista")
            combate.reg.anotar("pista", "Los gremlins dejan una nota de agradecimiento: cuenta como pista.")
        combate.reg.anotar("robo", f"Los gremlins desaparecen con {robados} cosas.")

    # -- reacciones y sorpresas ------------------------------------------------- #

    @ganchos.registrar_antes("arana_gigante")
    def telarana(combate, encuentro):
        combate.marcas["sin_salida"] = "la telarana bloquea la retirada"
        combate.reg.anotar(
            "telarana",
            "La telarana cierra la sala: no se puede huir sin quemarla con Bola de Fuego.",
        )

    @ganchos.registrar_antes("trolls")
    def trolls_contra_enanos(combate, encuentro):
        if combate.grupo.con_clase("enano") and combate.reaccion != "lucha_hasta_muerte":
            combate.reaccion = "lucha_hasta_muerte"
            combate.reg.anotar(
                "reaccion", "Hay un enano en el grupo: los trolls luchan hasta la muerte.")

    @ganchos.registrar_antes("goblins")
    def sorpresa_de_los_goblins(combate, encuentro):
        """1 entre 6 de actuar antes que el grupo."""
        if combate.reaccion in ("huir", "soborno"):
            return
        if roll("d6", combate.rng).total == 1:
            combate._monstruos_primero = True
            combate.reg.anotar("sorpresa", "¡Los goblins sorprenden al grupo!")

    @ganchos.registrar("tras_hechizo", "orcos")
    def orcos_temen_la_magia(combate, encuentro, muertos):
        """Prueban moral cada vez que un hechizo mata, y a -1 si les baja del 50%."""
        if not encuentro.vivo:
            return
        modificador = -1 if encuentro.bajo_de_moral else 0
        tirada = roll("d6", combate.rng).total + modificador
        combate.moral_probada = True
        if tirada < 4:
            encuentro.huir()
            combate.reg.anotar("moral", "Los orcos, aterrados por la magia, huyen.")
        else:
            combate.reg.anotar("moral", "Los orcos aguantan pese a la magia.")

    return ganchos
