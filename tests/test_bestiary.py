"""Tests de perfiles de monstruo y encuentros."""

from __future__ import annotations

import pytest

from runa.core.bestiary import Bestiario, Encuentro, Moral, PerfilMonstruo, Tesoro
from tests.test_dice import ScriptedRandom


def perfil(**extra):
    return PerfilMonstruo.desde_dict("x", {"nombre": "X", **extra})


class TestLecturaDeDatos:
    @pytest.mark.parametrize("bruto,tiradas,mod", [
        (None, 0, 0), ("normal", 1, 0), ("+1", 1, 1), ("-1", 1, -1),
        (2, 1, 2), ({"tiradas": 3, "modificador": 1}, 3, 1),
    ])
    def test_tesoro(self, bruto, tiradas, mod):
        t = Tesoro.desde(bruto)
        assert (t.tiradas, t.modificador) == (tiradas, mod)
        assert bool(t) is (tiradas > 0)

    @pytest.mark.parametrize("bruto,prueba,mod", [
        (None, True, 0), ("nunca", False, 0), (-1, True, -1),
    ])
    def test_moral(self, bruto, prueba, mod):
        m = Moral.desde(bruto)
        assert (m.prueba, m.modificador) == (prueba, mod)

    def test_el_id_es_siempre_una_etiqueta(self):
        assert "x" in perfil(etiquetas=["goblin"]).etiquetas


class TestEsbirros:
    def test_la_cantidad_se_tira_al_generar(self):
        p = perfil(tipo="esbirro", cantidad="d6+2", nivel=3)
        e = p.generar(ScriptedRandom([4]))
        assert e.cantidad == 6 and e.cantidad_inicial == 6

    def test_cada_golpe_mata_a_uno(self):
        e = perfil(tipo="esbirro", cantidad="8").generar(ScriptedRandom([]))
        e.cantidad = e.cantidad_inicial = 8
        assert e.herir() == 1 and e.cantidad == 7
        assert e.herir(3) == 3 and e.cantidad == 4

    def test_moral_al_perder_mas_de_la_mitad(self):
        e = Encuentro(perfil(tipo="esbirro"), cantidad=8)
        e.herir(4)
        assert not e.bajo_de_moral      # 4 de 8 no es "mas de la mitad"
        e.herir(1)
        assert e.bajo_de_moral

    def test_el_nivel_de_un_esbirro_no_baja(self):
        e = Encuentro(perfil(tipo="esbirro", nivel=3), cantidad=8)
        e.herir(7)
        assert e.nivel == 3


class TestJefes:
    def test_pierden_vida_en_vez_de_numero(self):
        e = perfil(tipo="jefe", vida=5, nivel=5).generar(ScriptedRandom([]))
        assert (e.cantidad, e.vida) == (1, 5)
        assert e.herir(2) == 2 and e.vida == 3

    def test_el_nivel_baja_al_pasar_de_la_mitad(self):
        # Ejemplo del libro: jefe de nivel 6 con 5 de Vida pasa a nivel 5 al
        # recibir 3 heridas, y ocurre inmediatamente.
        e = perfil(tipo="jefe", vida=5, nivel=6).generar(ScriptedRandom([]))
        e.herir(2)
        assert e.nivel == 6
        e.herir(1)
        assert e.nivel == 5 and e.vida == 2

    def test_el_nivel_nunca_baja_de_uno(self):
        e = perfil(tipo="jefe", vida=4, nivel=1).generar(ScriptedRandom([]))
        e.herir(3)
        assert e.nivel == 1

    def test_muere_al_llegar_a_cero(self):
        e = perfil(tipo="jefe", vida=3).generar(ScriptedRandom([]))
        e.herir(3)
        assert not e.vivo


def test_la_amenaza_arrastra_las_etiquetas_del_perfil():
    a = perfil(tipo="jefe", nivel=5, etiquetas=["no_muerto"]).amenaza()
    assert {"no_muerto", "jefe", "x"} <= a.etiquetas and a.nivel == 5


def test_la_amenaza_usa_el_nivel_rebajado_del_jefe():
    e = perfil(tipo="jefe", vida=5, nivel=6).generar(ScriptedRandom([]))
    e.herir(3)
    assert e.amenaza.nivel == 5


def test_huir_lo_saca_del_combate():
    e = perfil(tipo="esbirro").generar(ScriptedRandom([]))
    e.huir()
    assert not e.vivo and "huyo" in str(e)


def test_bestiario_avisa_de_monstruos_inexistentes():
    with pytest.raises(KeyError, match="dragon_rojo"):
        Bestiario({})["dragon_rojo"]
