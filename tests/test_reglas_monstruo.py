"""Las reglas propias de cada monstruo."""

from __future__ import annotations

import pytest

from runa.core.decisions import DecisorGuion, DecisorPorDefecto
from runa.core.rng import RandomSource
from runa.games.cco.combate import Combate
from runa.games.cco.juego import Juego
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


def montar(juego, monstruo, rng, clases=None, guion=None, **estado):
    clases = clases or [("Brakk", "guerrero"), ("Sela", "clerigo"),
                        ("Nim", "picaro"), ("Orin", "mago")]
    grupo = juego.crear_grupo(clases, RandomSource(1))
    if any(c == "mago" for _, c in clases):
        juego.preparar_hechizos(grupo.por_nombre("Orin"),
                                ["bola_de_fuego", "rayo", "dormir"])
    enc = juego.bestiario[monstruo].generar(RandomSource(0))
    for k, v in estado.items():
        setattr(enc, k, v)
    c = Combate(juego, grupo, enc, rng,
                decisor=DecisorGuion(guion or {}) if guion is not None
                else DecisorPorDefecto())
    return grupo, enc, c


class TestVenenosYHeridas:
    def test_el_veneno_del_ciempies_quita_una_vida_mas(self, juego):
        g, e, c = montar(juego, "ciempies_gigantes", ScriptedRandom([1]))
        brakk = g.por_nombre("Brakk")
        brakk.herir(1)
        juego.ganchos.tras_herir["ciempies_gigantes"](c, e, brakk)
        assert brakk.vida == brakk.vida_max - 2

    def test_salvar_el_veneno_evita_la_herida(self, juego):
        g, e, c = montar(juego, "ciempies_gigantes", ScriptedRandom([5]))
        brakk = g.por_nombre("Brakk")
        juego.ganchos.tras_herir["ciempies_gigantes"](c, e, brakk)
        assert not brakk.herido

    def test_el_halfling_suma_su_nivel_contra_el_veneno_de_los_hongos(self, juego):
        g, e, c = montar(juego, "funjis", ScriptedRandom([2]),
                         clases=[("Pip", "halfling")])
        pip = g.miembros[0]
        pip.nivel = 3
        juego.ganchos.tras_herir["funjis"](c, e, pip)
        assert not pip.herido            # 2 + 3 supera el veneno de nivel 3

    def test_la_mordedura_de_rata_se_infecta_uno_de_cada_seis(self, juego):
        g, e, c = montar(juego, "ratas", ScriptedRandom([1]))
        brakk = g.por_nombre("Brakk")
        juego.ganchos.tras_herir["ratas"](c, e, brakk)
        assert brakk.vida == brakk.vida_max - 1

        g, e, c = montar(juego, "ratas", ScriptedRandom([4]))
        brakk = g.por_nombre("Brakk")
        juego.ganchos.tras_herir["ratas"](c, e, brakk)
        assert not brakk.herido

    def test_un_muerto_ya_no_sufre_el_veneno(self, juego):
        g, e, c = montar(juego, "arana_gigante", ScriptedRandom([1]))
        orin = g.por_nombre("Orin")
        orin.herir(99)
        juego.ganchos.tras_herir["arana_gigante"](c, e, orin)
        assert c.reg.de_tipo("salvacion") == []


class TestMomia:
    def test_quien_muere_se_convierte_en_momia(self, juego):
        g, e, c = montar(juego, "momia", RandomSource(1))
        orin = g.por_nombre("Orin")
        orin.herir(99)
        juego.ganchos.tras_herir["momia"](c, e, orin)
        assert c.refuerzos == ["momia"]

    def test_quien_sobrevive_no_se_convierte(self, juego):
        g, e, c = montar(juego, "momia", RandomSource(1))
        juego.ganchos.tras_herir["momia"](c, e, g.por_nombre("Brakk"))
        assert c.refuerzos == []


class TestSenorDelCaos:
    def test_el_drenaje_puede_costar_un_nivel(self, juego):
        g, e, c = montar(juego, "senor_del_caos", ScriptedRandom([1]))
        c.marcas["drena_energia"] = True
        brakk = g.por_nombre("Brakk")
        brakk.nivel = 3
        juego.ganchos.tras_herir["senor_del_caos"](c, e, brakk)
        assert brakk.nivel == 2

    def test_sin_ese_poder_no_drena(self, juego):
        g, e, c = montar(juego, "senor_del_caos", ScriptedRandom([1]))
        brakk = g.por_nombre("Brakk")
        juego.ganchos.tras_herir["senor_del_caos"](c, e, brakk)
        assert brakk.nivel == 1

    def test_al_morir_puede_dejar_una_pista(self, juego):
        g, e, c = montar(juego, "senor_del_caos", ScriptedRandom([6]))
        juego.ganchos.al_morir["senor_del_caos"](c, e)
        assert c.sucesos == ["pista"]

    def test_con_cuatro_o_menos_no_deja_nada(self, juego):
        g, e, c = montar(juego, "senor_del_caos", ScriptedRandom([4]))
        juego.ganchos.al_morir["senor_del_caos"](c, e)
        assert c.sucesos == []


class TestPlagaDelHierro:
    def test_devora_el_equipo_en_orden_y_no_hace_dano(self, juego):
        g, e, c = montar(juego, "plaga_del_hierro", RandomSource(1))
        brakk = g.por_nombre("Brakk")
        assert juego.ganchos.al_herir["plaga_del_hierro"](c, e, brakk) is True
        assert not brakk.herido
        assert brakk.equipado("armadura") is None      # primero la armadura
        juego.ganchos.al_herir["plaga_del_hierro"](c, e, brakk)
        assert brakk.equipado("escudo") is None        # luego el escudo
        juego.ganchos.al_herir["plaga_del_hierro"](c, e, brakk)
        assert brakk.arma is None                      # y por ultimo el arma

    def test_sin_metal_se_lleva_el_oro(self, juego):
        g, e, c = montar(juego, "plaga_del_hierro", ScriptedRandom([2, 2, 2]))
        orin = g.por_nombre("Orin")
        orin.equipo.clear()
        orin.oro = 100
        juego.ganchos.al_herir["plaga_del_hierro"](c, e, orin)
        assert orin.oro == 94                          # 3d6 = 6

    def test_no_anula_el_escudo_ni_la_armadura_ligera(self, juego):
        # Su etiqueta solo ignora la armadura pesada.
        g, _, _ = montar(juego, "plaga_del_hierro", RandomSource(1))
        brakk = g.por_nombre("Brakk")
        r = juego.defender(brakk, juego.bestiario["plaga_del_hierro"].amenaza(),
                           ScriptedRandom([3]))
        assert r.bonificacion == 2                     # armadura ligera + escudo


class TestGremlins:
    def test_roban_objetos_y_oro(self, juego):
        g, e, c = montar(juego, "gremlins_invisibles", ScriptedRandom([1], relleno=1))
        for p in g:
            p.oro = 100
        objetos_antes = sum(len(p.equipo) for p in g)
        juego.ganchos.antes["gremlins_invisibles"](c, e)
        assert sum(len(p.equipo) for p in g) < objetos_antes
        assert any(e.tipo == "robo" for e in c.reg)

    def test_si_no_encuentran_bastante_dejan_una_pista(self, juego):
        g, e, c = montar(juego, "gremlins_invisibles", ScriptedRandom([], relleno=5))
        for p in g:
            p.equipo.clear()
            p.oro = 0
        juego.ganchos.antes["gremlins_invisibles"](c, e)
        assert c.sucesos == ["pista"]

    def test_no_se_les_puede_combatir_ni_dan_experiencia(self, juego):
        g, e, c = montar(juego, "gremlins_invisibles", ScriptedRandom([], relleno=3))
        r = c.resolver()
        assert r.desenlace == "victoria" and r.rondas == 0 and not r.xp
        assert not e.perfil.combate
        assert not e.perfil.tesoro          # no dejan nada que saquear


class TestAranaGigante:
    def test_la_telarana_impide_huir(self, juego):
        g, e, c = montar(juego, "arana_gigante", ScriptedRandom([], relleno=3),
                         guion={"abordaje": "atacar_ya"})
        juego.ganchos.antes["arana_gigante"](c, e)
        assert c._salida() is None
        assert any("No hay escapatoria" in x.texto for x in c.reg)

    def test_la_bola_de_fuego_quema_la_telarana(self, juego):
        g, e, c = montar(juego, "arana_gigante", ScriptedRandom([], relleno=3))
        juego.ganchos.antes["arana_gigante"](c, e)
        juego.usar_habilidad("bola_de_fuego", g.por_nombre("Orin"), c)
        assert "sin_salida" not in c.marcas


class TestReaccionesEspeciales:
    def test_los_trolls_luchan_a_muerte_si_hay_un_enano(self, juego):
        g, e, c = montar(juego, "trolls", RandomSource(1),
                         clases=[("Thrunn", "enano"), ("Brakk", "guerrero")])
        c.reaccion = "lucha"
        juego.ganchos.antes["trolls"](c, e)
        assert c.reaccion == "lucha_hasta_muerte"

    def test_sin_enano_la_reaccion_no_cambia(self, juego):
        g, e, c = montar(juego, "trolls", RandomSource(1))
        c.reaccion = "lucha"
        juego.ganchos.antes["trolls"](c, e)
        assert c.reaccion == "lucha"

    def test_los_goblins_sorprenden_uno_de_cada_seis(self, juego):
        g, e, c = montar(juego, "goblins", ScriptedRandom([1]))
        c.reaccion = "lucha"
        c._monstruos_primero = False
        juego.ganchos.antes["goblins"](c, e)
        assert c._monstruos_primero is True

        g, e, c = montar(juego, "goblins", ScriptedRandom([4]))
        c.reaccion = "lucha"
        c._monstruos_primero = False
        juego.ganchos.antes["goblins"](c, e)
        assert c._monstruos_primero is False


class TestOrcos:
    def test_prueban_moral_cuando_un_hechizo_los_mata(self, juego):
        g, e, c = montar(juego, "orcos", ScriptedRandom([2]), cantidad=5,
                         cantidad_inicial=5)
        juego.ganchos.tras_hechizo["orcos"](c, e, 2)
        assert e.huido and any("aterrados por la magia" in x.texto for x in c.reg)

    def test_con_cuatro_o_mas_aguantan(self, juego):
        g, e, c = montar(juego, "orcos", ScriptedRandom([5]), cantidad=5,
                         cantidad_inicial=5)
        juego.ganchos.tras_hechizo["orcos"](c, e, 2)
        assert not e.huido

    def test_nunca_llevan_objetos_magicos(self, juego):
        perfil = juego.bestiario["orcos"]
        assert perfil.sin_objetos_magicos == "d6xd6"
        # Un tesoro magico (tirada 6) se convierte en oro.
        botin = juego.saquear(perfil.tesoro, ScriptedRandom([6], relleno=3),
                              sin_objetos_magicos=perfil.sin_objetos_magicos)
        assert not any("magico" in o.etiquetas for o in botin.objetos)
        assert botin.oro > 0
