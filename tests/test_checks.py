"""Tests del resolutor de tiradas."""

from __future__ import annotations

import pytest

from runa.core.checks import (
    Amenaza, Check, ModifierRule, Resolutor, TipoTirada,
)
from runa.core.entities import ClasePersonaje, Personaje
from tests.test_dice import ScriptedRandom


def clase(**extra):
    return ClasePersonaje.desde_dict("prueba", {"nombre": "Prueba", "vida": "5+N", **extra})


@pytest.fixture
def resolutor():
    return Resolutor(
        tipos={
            "ataque": TipoTirada.desde_dict("ataque", {"comparacion": ">="}),
            "defensa": TipoTirada.desde_dict(
                "defensa",
                {"comparacion": ">", "exito_natural": 6, "fallo_natural": 1},
            ),
        }
    )


class TestCondicionesDeLasReglas:
    @pytest.mark.parametrize("regla,etiquetas,esperado", [
        ({"en": "ataque", "suma": 1}, set(), True),
        ({"en": "defensa", "suma": 1}, set(), False),
        ({"suma": 1}, set(), True),                                   # sin 'en' = siempre
        ({"si": ["a", "b"], "suma": 1}, {"a"}, False),                # exige TODAS
        ({"si": ["a", "b"], "suma": 1}, {"a", "b"}, True),
        ({"si_alguno": ["a", "b"], "suma": 1}, {"b"}, True),          # exige UNA
        ({"si_alguno": ["a", "b"], "suma": 1}, {"c"}, False),
        ({"si_no": ["a"], "suma": 1}, {"a"}, False),                  # exige NINGUNA
        ({"si_no": ["a"], "suma": 1}, {"b"}, True),
    ])
    def test_aplica(self, regla, etiquetas, esperado):
        assert ModifierRule.desde_dict(regla).aplica("ataque", etiquetas) is esperado


def test_las_etiquetas_de_la_amenaza_entran_en_la_tirada(resolutor):
    p = Personaje("X", clase(reglas=[
        {"en": "ataque", "suma": 2, "si": ["no_muerto"], "texto": "contra no muertos"},
    ]))
    esqueleto = Amenaza.crear("Esqueleto", 3, ["no_muerto", "esqueleto"])
    r = resolutor.resolver(Check("ataque", p, 3, esqueleto), ScriptedRandom([3]))
    assert r.total == 5 and r.exito
    assert [m.fuente for m in r.modificadores] == ["contra no muertos"]


def test_el_modificador_cero_no_ensucia_la_traza(resolutor):
    p = Personaje("X", clase(reglas=[{"en": "ataque", "suma": 0, "texto": "nada"}]))
    r = resolutor.resolver(Check("ataque", p, 1), ScriptedRandom([3]))
    assert r.modificadores == ()


class TestComparacion:
    """El ataque acierta igualando el nivel; la defensa tiene que superarlo."""

    def test_ataque_acierta_igualando_el_nivel(self, resolutor):
        r = resolutor.resolver(Check("ataque", Personaje("X", clase()), 4), ScriptedRandom([4]))
        assert r.exito

    def test_defensa_no_basta_con_igualar(self, resolutor):
        r = resolutor.resolver(Check("defensa", Personaje("X", clase()), 4), ScriptedRandom([4]))
        assert not r.exito

    def test_defensa_tiene_exito_superando(self, resolutor):
        r = resolutor.resolver(Check("defensa", Personaje("X", clase()), 4), ScriptedRandom([5]))
        assert r.exito


class TestNaturales:
    def test_el_uno_natural_falla_pese_a_los_modificadores(self, resolutor):
        p = Personaje("X", clase(reglas=[{"en": "defensa", "suma": 5, "texto": "coraza"}]))
        r = resolutor.resolver(Check("defensa", p, 2), ScriptedRandom([1]))
        assert not r.exito and "1 natural" in r.motivo
        assert r.total == 6  # el total se calcula igual, pero no manda

    def test_el_seis_natural_salva_contra_cualquier_nivel(self, resolutor):
        r = resolutor.resolver(
            Check("defensa", Personaje("X", clase()), 20), ScriptedRandom([6, 1])
        )
        assert r.exito and "6 natural" in r.motivo

    def test_natural_es_la_primera_cara_no_el_total_explotado(self, resolutor):
        # 6+... sigue siendo un 6 natural; 1 tras una explosion no es un 1 natural.
        r = resolutor.resolver(
            Check("defensa", Personaje("X", clase()), 3), ScriptedRandom([6, 6, 1])
        )
        assert r.exito and r.tirada.total == 13


class TestVentaja:
    def test_toma_la_mejor_de_varias_tiradas(self, resolutor):
        # Ataque de Ira del barbaro: tres tiradas, se elige la mejor.
        r = resolutor.resolver(
            Check("ataque", Personaje("X", clase()), 5, ventaja=3),
            ScriptedRandom([2, 5, 3]),
        )
        assert r.tirada.total == 5 and r.exito
        assert sorted(t.total for t in r.descartadas) == [2, 3]

    def test_ventaja_invalida(self, resolutor):
        with pytest.raises(ValueError, match="al menos 1"):
            resolutor.resolver(
                Check("ataque", Personaje("X", clase()), 5, ventaja=0), ScriptedRandom([1])
            )


def test_comparacion_invalida_en_los_datos():
    with pytest.raises(ValueError, match="comparacion"):
        TipoTirada.desde_dict("x", {"comparacion": "=="})


def test_la_traza_es_legible(resolutor):
    p = Personaje("Brakk", clase(reglas=[
        {"en": "ataque", "suma": "nivel", "texto": "nivel de guerrero"},
    ]), nivel=3)
    r = resolutor.resolver(
        Check("ataque", p, 4, Amenaza.crear("Orco", 4)), ScriptedRandom([4])
    )
    assert r.describir() == (
        "Ataque de Brakk contra Orco (nivel 4)\n"
        "  d6[4]\n"
        "  +3 nivel de guerrero\n"
        "  = 7 vs 4 -> EXITO"
    )
