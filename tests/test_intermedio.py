"""Tests del ciclo entre aventuras."""

from __future__ import annotations

import pytest

from runa.core.decisions import DecisorGuion, DecisorPorDefecto
from runa.core.rng import RandomSource
from runa.games.cco.intermedio import RESURRECCION, Intermedio
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Partida
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


def montar(juego, clases=None, guion=None, semilla=1):
    clases = clases or [("Brakk", "guerrero"), ("Thrunn", "enano"), ("Orin", "mago")]
    grupo = juego.crear_grupo(clases, RandomSource(semilla))
    p = Partida(juego, grupo, semilla=semilla)
    return p, Intermedio(p, DecisorGuion(guion or {}))


class TestPreciosDeVenta:
    @pytest.mark.parametrize("id,esperado", [
        ("pocion_curacion", 50),               # pociones y anillos, 50
        ("anillo_teletransportacion", 50),
        ("pergamino", 100),                    # 100 por hechizo que contengan
        ("baston_bola_fuego", 200),            # 2 cargas
        ("varita_sueno", 300),                 # 3 cargas
        ("arma_dos_manos", 7),                 # la mitad de 15, hacia abajo
        ("armadura_pesada", 15),
    ])
    def test_precio(self, juego, id, esperado):
        p, i = montar(juego)
        assert i.precio_de_venta(juego.objeto(id), p.grupo.miembros[0]) == esperado

    def test_el_enano_saca_un_veinte_por_ciento_mas_por_las_gemas(self, juego):
        p, i = montar(juego)
        gema = juego.objeto("gema").copia(precio=100)
        assert i.precio_de_venta(gema, p.grupo.por_nombre("Brakk")) == 100
        assert i.precio_de_venta(gema, p.grupo.por_nombre("Thrunn")) == 120

    def test_la_bonificacion_del_enano_no_alcanza_a_las_armas(self, juego):
        p, i = montar(juego)
        arma = juego.objeto("arma_dos_manos")
        assert i.precio_de_venta(arma, p.grupo.por_nombre("Thrunn")) == 7


class TestVenta:
    def test_vender_da_oro_y_quita_el_objeto(self, juego):
        p, i = montar(juego, guion={"vender": [1, "", "", ""]})
        brakk = p.grupo.por_nombre("Brakk")
        oro = brakk.oro
        objetos = len(brakk.equipo)
        i.vender()
        assert brakk.oro > oro and len(brakk.equipo) == objetos - 1

    def test_no_vender_nada_deja_todo_igual(self, juego):
        p, i = montar(juego, guion={"vender": ""})
        antes = [(x.oro, len(x.equipo)) for x in p.grupo]
        assert i.vender() == 0
        assert [(x.oro, len(x.equipo)) for x in p.grupo] == antes


class TestResurreccion:
    def test_se_logra_sacando_igual_o_menos_que_el_nivel(self, juego):
        # Al reves que todas las demas tiradas: al veterano le cuesta menos.
        p, i = montar(juego, guion={"resucitar": True})
        orin = p.grupo.por_nombre("Orin")
        orin.nivel = 4
        orin.herir(99)
        p.grupo.miembros[0].oro = RESURRECCION
        p.rng = ScriptedRandom([4])
        i.resucitar()
        assert not orin.muerto and orin.vida == orin.vida_max

    def test_fallar_pierde_el_oro_y_al_personaje(self, juego):
        p, i = montar(juego, guion={"resucitar": True})
        orin = p.grupo.por_nombre("Orin")
        orin.nivel = 2
        orin.herir(99)
        p.grupo.miembros[0].oro = RESURRECCION
        p.rng = ScriptedRandom([5])
        i.resucitar()
        assert orin.muerto and p.grupo.oro < RESURRECCION

    def test_sin_oro_no_hay_ritual(self, juego):
        p, i = montar(juego)
        orin = p.grupo.por_nombre("Orin")
        orin.herir(99)
        i.resucitar()
        assert orin.muerto
        assert any("solo tiene" in e.texto for e in p.registro)

    def test_se_puede_renunciar_al_ritual(self, juego):
        p, i = montar(juego, guion={"resucitar": False})
        orin = p.grupo.por_nombre("Orin")
        orin.herir(99)
        p.grupo.miembros[0].oro = RESURRECCION
        i.resucitar()
        assert orin.muerto and p.grupo.oro >= RESURRECCION
        assert any("sepultura" in e.texto for e in p.registro)


class TestReemplazos:
    def test_un_caido_se_sustituye_por_uno_de_nivel_uno(self, juego):
        p, i = montar(juego, guion={"reemplazo": "clerigo"})
        p.grupo.por_nombre("Orin").herir(99)
        i.reemplazar_caidos()
        nuevo = p.grupo.miembros[2]
        assert nuevo.clase.id == "clerigo" and nuevo.nivel == 1 and nuevo.vivo
        assert len(p.grupo) == 3          # el grupo mantiene su tamano

    def test_el_reemplazo_ocupa_el_mismo_puesto_de_marcha(self, juego):
        p, i = montar(juego, guion={"reemplazo": "guerrero"})
        p.grupo.miembros[0].herir(99)
        i.reemplazar_caidos()
        assert p.grupo.miembros[0].vivo and p.grupo.miembros[1].nombre == "Thrunn"


class TestDescanso:
    def test_reponer_devuelve_los_recursos_por_aventura(self, juego):
        p, i = montar(juego, clases=[("Sela", "clerigo"), ("Pip", "halfling")])
        sela, pip = p.grupo.miembros
        sela.gastar("curacion", 3)
        pip.gastar("suerte", 2)
        i.reponer()
        assert sela.recursos["curacion"] == 3 and pip.recursos["suerte"] == 2

    def test_reponer_limpia_las_condiciones_de_la_aventura(self, juego):
        p, i = montar(juego)
        brakk = p.grupo.por_nombre("Brakk")
        brakk.estados.append(juego.estado("maldito"))
        i.reponer()
        assert brakk.estados == []

    def test_reponer_no_resucita_ni_cura(self, juego):
        p, i = montar(juego)
        brakk = p.grupo.por_nombre("Brakk")
        brakk.herir(3)
        p.grupo.por_nombre("Orin").herir(99)
        i.reponer()
        assert brakk.vida == brakk.vida_max - 3
        assert p.grupo.por_nombre("Orin").muerto

    def test_la_iglesia_cura_a_diez_el_punto(self, juego):
        p, i = montar(juego, guion={"curar": [True, True, False]})
        brakk = p.grupo.por_nombre("Brakk")
        brakk.herir(3)
        brakk.oro = 100
        i.curar()
        assert brakk.vida == brakk.vida_max - 1 and brakk.oro == 80

    def test_sin_oro_no_hay_cura(self, juego):
        p, i = montar(juego, guion={"curar": True})
        brakk = p.grupo.por_nombre("Brakk")
        brakk.herir(3)
        brakk.oro = 5
        i.curar()
        assert brakk.vida == brakk.vida_max - 3


class TestNuevaAventura:
    def test_reinicia_la_mazmorra_pero_conserva_la_campana(self, juego):
        p, i = montar(juego)
        p.mapa.crear("entrada", salidas=2)
        p.aventura.jefes_vistos = 3
        p.campana.pistas["Brakk"] = 2
        p.campana.aventuras_jugadas = 1
        i.nueva_aventura()
        assert len(p.mapa) == 0 and p.aventura.jefes_vistos == 0
        assert p.campana.pistas == {"Brakk": 2} and p.campana.aventuras_jugadas == 1

    def test_los_niveles_y_el_oro_sobreviven(self, juego):
        p, i = montar(juego)
        brakk = p.grupo.por_nombre("Brakk")
        brakk.subir_nivel()
        brakk.oro = 250
        i.nueva_aventura()
        assert brakk.nivel == 2 and brakk.oro == 250


def test_un_intermedio_entero_en_automatico(juego):
    p, _ = montar(juego)
    entre = Intermedio(p, DecisorPorDefecto())
    p.grupo.por_nombre("Orin").herir(99)
    entre.resolver()
    assert all(x.vivo for x in p.grupo)      # el caido fue reemplazado
    assert p.grupo.por_nombre("Brakk").recursos == \
           p.grupo.por_nombre("Brakk").clase.recursos_a_nivel(1)
