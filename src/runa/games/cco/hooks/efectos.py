"""Efectos de hechizos y poderes.

Es la frontera deliberada del sistema: lo declarativo (quien puede, cuando, que
gasta) vive en `hechizos.yaml`; lo que no cabe en datos —cuantos esbirros mata
una bola de fuego— se escribe aqui y se registra por nombre.
"""

from __future__ import annotations

from typing import Any

from runa.core.checks import AccionProhibida, CheckResult
from runa.core.decisions import Opcion, Pregunta
from runa.core.dice import roll
from runa.core.entities import Estado, Personaje
from runa.core.checks import ModifierRule


def registrar(juego: Any) -> None:
    """Asocia cada efecto declarado en los datos con su implementacion."""

    habilidades = juego.habilidades

    # -- utilidades compartidas -------------------------------------------- #

    def elegir_aliado(combate, personaje, id, texto, filtro=None) -> Personaje:
        candidatos = [p for p in combate.vivos if filtro is None or filtro(p)]
        if not candidatos:
            candidatos = [personaje]
        elegido = combate.decisor.elegir(Pregunta.crear(
            id, texto,
            [Opcion(p.nombre, p.nombre, f"{p.vida}/{p.vida_max} Vida") for p in candidatos],
        ))
        return next(p for p in candidatos if p.nombre == elegido)

    def lanzar(combate, personaje, habilidad, primer_turno) -> CheckResult | None:
        """Tirada de hechizo contra el encuentro, con la etiqueta del hechizo."""
        etiquetas = combate.etiquetas_de_ataque(primer_turno) | {habilidad.id, "hechizo"}
        try:
            r = juego.tirar("hechizo", personaje, combate.rng,
                            amenaza=combate.enc.amenaza, etiquetas=etiquetas)
        except AccionProhibida as e:
            combate.reg.anotar(
                "prohibido",
                f"{personaje.nombre} no puede lanzar {habilidad.nombre}: {e.motivos[0]}",
            )
            return None
        combate.reg.anotar("hechizo", r.describir(), tirada=r)
        return r

    # -- hechizos ofensivos ------------------------------------------------- #

    @habilidades.registrar("bola_de_fuego")
    def bola_de_fuego(personaje, combate, habilidad, primer_turno=False, **kw):
        r = lanzar(combate, personaje, habilidad, primer_turno)
        if r is None:
            return None
        personaje.gastar(habilidad.gasta)
        if combate.marcas.pop("sin_salida", None):
            combate.reg.anotar("telarana", "Las llamas queman la telarana: ya se puede huir.")
        if not r.exito:
            return r
        if combate.enc.perfil.es_esbirro:
            # "mata a una cantidad igual a la tirada menos el nivel de los
            # esbirros", con un minimo de uno.
            muertos = max(1, r.total - combate.enc.perfil.nivel)
            combate.herir_monstruo(muertos, por=f"{personaje.nombre} (Bola de Fuego)", por_hechizo=True)
        else:
            combate.herir_monstruo(1, por=f"{personaje.nombre} (Bola de Fuego)", por_hechizo=True)
        return r

    @habilidades.registrar("rayo")
    def rayo(personaje, combate, habilidad, primer_turno=False, **kw):
        r = lanzar(combate, personaje, habilidad, primer_turno)
        if r is None:
            return None
        personaje.gastar(habilidad.gasta)
        if r.exito:
            # Un solo esbirro, pero 2 puntos de Vida a un jefe.
            heridas = 1 if combate.enc.perfil.es_esbirro else 2
            combate.herir_monstruo(heridas, por=f"{personaje.nombre} (Rayo)", por_hechizo=True)
        return r

    @habilidades.registrar("dormir")
    def dormir(personaje, combate, habilidad, primer_turno=False, **kw):
        r = lanzar(combate, personaje, habilidad, primer_turno)
        if r is None:
            return None
        personaje.gastar(habilidad.gasta)
        if not r.exito:
            return r
        if combate.enc.perfil.es_esbirro:
            cuantos = roll("d6+N", combate.rng, N=personaje.nivel).total
            combate.herir_monstruo(cuantos, por=f"{personaje.nombre} (Dormir)", por_hechizo=True)
        else:
            # "Dormir derrotara a un jefe": cae entero, y queda sometido.
            combate.herir_monstruo(combate.enc.vida, por=f"{personaje.nombre} (Dormir)")
            combate.reg.anotar("sometido",
                               f"{combate.enc.nombre} queda dormido y puede ser atado.")
        return r

    # -- hechizos de apoyo -------------------------------------------------- #

    @habilidades.registrar("proteger")
    def proteger(personaje, combate, habilidad, **kw):
        objetivo = elegir_aliado(combate, personaje, "proteger",
                                 f"¿A quien protege {personaje.nombre}?")
        personaje.gastar(habilidad.gasta)
        objetivo.estados.append(juego.estado("protegido"))
        combate.reg.anotar("hechizo",
                           f"{personaje.nombre} protege a {objetivo.nombre} (+1 a la Defensa).")
        return None

    @habilidades.registrar("escapada")
    def escapada(personaje, combate, habilidad, **kw):
        personaje.gastar(habilidad.gasta)
        personaje.estados.append(juego.estado("fuera_de_combate"))
        combate.reg.anotar(
            "hechizo",
            f"{personaje.nombre} se desvanece y reaparece en la primera sala.",
        )
        return None

    @habilidades.registrar("quitar_condicion")
    def bendicion(personaje, combate, habilidad, **kw):
        afectados = [p for p in combate.grupo.miembros
                     if any(e.dura != "combate" for e in p.estados)]
        if not afectados:
            combate.reg.anotar("hechizo", "No hay ninguna condicion que levantar.")
            return None
        objetivo = elegir_aliado(combate, personaje, "bendicion",
                                 "¿A quien se le levanta la condicion?",
                                 filtro=lambda p: p in afectados)
        personaje.gastar(habilidad.gasta)
        condicion = next(e for e in objetivo.estados if e.dura != "combate")
        objetivo.estados.remove(condicion)
        combate.reg.anotar(
            "hechizo",
            f"{personaje.nombre} bendice a {objetivo.nombre}: se le quita "
            f"'{condicion.texto}'.",
        )
        return None

    # -- poderes de clase --------------------------------------------------- #

    @habilidades.registrar("curacion")
    def curacion(personaje, combate, habilidad, **kw):
        heridos = [p for p in combate.vivos if p.herido]
        if not heridos:
            # La Curacion es un recurso limitado: no se gasta sobre nadie sano.
            combate.reg.anotar("curacion", "Nadie esta herido: no se gasta la Curacion.")
            return None
        objetivo = elegir_aliado(combate, personaje, "curacion",
                                 f"¿A quien cura {personaje.nombre}?",
                                 filtro=lambda p: p.herido)
        personaje.gastar(habilidad.gasta)
        tirada = roll("d6+N", combate.rng, N=personaje.nivel)
        curadas = objetivo.curar(tirada.total)
        combate.reg.anotar(
            "curacion",
            f"{personaje.nombre} cura a {objetivo.nombre}: {tirada} -> "
            f"+{curadas} Vida ({objetivo.vida}/{objetivo.vida_max}).",
        )
        return None

    @habilidades.registrar("ataque_de_ira")
    def ataque_de_ira(personaje, combate, habilidad, primer_turno=False, **kw):
        personaje.gastar(habilidad.gasta)
        combate.reg.anotar("ira", f"¡{personaje.nombre} entra en colera!")
        # Tres tiradas, se queda la mejor; contra un jefe inflige dos heridas.
        return combate._atacar(personaje, primer_turno, ventaja=3)

    @habilidades.registrar("suerte")
    def suerte(personaje, combate, habilidad, **kw):
        # Se ofrece sola tras una tirada fallida; como accion suelta no hace nada.
        combate.reg.anotar("suerte", f"{personaje.nombre} guarda su suerte.")
        return None

    @habilidades.registrar("vendar")
    def vendar(personaje, combate=None, habilidad=None, **kw):
        curadas = personaje.curar(1)
        if combate is not None:
            combate.reg.anotar("vendaje", f"{personaje.nombre} se venda (+{curadas} Vida).")
        return None
