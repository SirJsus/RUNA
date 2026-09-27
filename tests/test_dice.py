"""Tests del motor de dados."""

from __future__ import annotations

import pytest

from runa.core.dice import DiceError, roll
from runa.core.rng import RandomSource


class ScriptedRandom(RandomSource):
    """RandomSource que devuelve una secuencia fija: hace los tests exactos.

    `relleno` da un valor para cuando el guion se agota, util en pruebas largas
    como las de combate donde solo importan las primeras tiradas. No puede ser la
    cara maxima: con la regla explosiva activa, eso no termina nunca.
    """

    def __init__(self, results, relleno: int | None = None):
        super().__init__(seed=0)
        self._scripted = list(results)
        self._relleno = relleno

    def die(self, faces: int) -> int:
        self.count += 1
        if not self._scripted:
            if self._relleno is None:
                raise IndexError("el guion de dados se agoto")
            return min(self._relleno, faces)
        return self._scripted.pop(0)


def test_misma_semilla_mismo_resultado():
    a = [roll("2d6+1", RandomSource(123)).total for _ in range(5)]
    b = [roll("2d6+1", RandomSource(123)).total for _ in range(5)]
    assert a == b


def test_semillas_distintas_divergen():
    serie = lambda s: [roll("3d6", RandomSource(s)).total for _ in range(20)]
    assert serie(1) != serie(2)


@pytest.mark.parametrize("expr,caras,esperado", [
    ("d6", [4], 4),
    ("2d6", [3, 5], 8),
    ("2d6+1", [3, 5], 9),
    ("d6-1", [1], 0),
    ("d6xd6", [4, 5], 20),
    ("3d6x15", [1, 2, 3], 90),
    ("2d6xd6", [2, 3, 4], 20),
    ("d3", [2], 2),
])
def test_notacion_basica(expr, caras, esperado):
    assert roll(expr, ScriptedRandom(caras)).total == esperado


def test_d66_es_decenas_y_unidades():
    assert roll("d66", ScriptedRandom([3, 5])).total == 35
    assert roll("d66", ScriptedRandom([1, 1])).total == 11
    assert roll("d66", ScriptedRandom([6, 6])).total == 66


def test_d66_nunca_explota_aunque_este_activa_la_regla():
    # Sin esta salvaguarda, un 6 en las decenas relanzaria y daria un numero
    # de habitacion imposible.
    resultado = roll("d66", ScriptedRandom([6, 6]), explode=True)
    assert resultado.total == 66
    assert not resultado.exploded


def test_variable_de_nivel():
    assert roll("d6+N", ScriptedRandom([3]), N=4).total == 7


def test_medio_nivel_redondea_hacia_abajo():
    # Clerigo de nivel 5 => +2, como dice el reglamento.
    assert roll("d6+1/2N", ScriptedRandom([1]), N=5).total == 3
    assert roll("d6+N/2", ScriptedRandom([1]), N=5).total == 3
    assert roll("d6+1/2N", ScriptedRandom([1]), N=1).total == 1


def test_variable_sin_valor_da_error_claro():
    with pytest.raises(DiceError, match="N"):
        roll("d6+N", RandomSource(1))


@pytest.mark.parametrize("expr", ["", "d6+", "2d", "d6 d6", "1/3N", "d6+)"])
def test_expresiones_invalidas(expr):
    with pytest.raises(DiceError):
        roll(expr, RandomSource(1))


class TestReglaExplosivaDelSeis:
    def test_un_seis_relanza_y_suma(self):
        assert roll("d6", ScriptedRandom([6, 3]), explode=True).total == 9

    def test_es_acumulativa(self):
        assert roll("d6", ScriptedRandom([6, 6, 6, 2]), explode=True).total == 20

    def test_desactivada_por_defecto(self):
        # Las tablas de generacion de mazmorra no explotan.
        assert roll("d6", ScriptedRandom([6]), explode=False).total == 6

    def test_la_traza_muestra_la_explosion(self):
        resultado = roll("d6+N", ScriptedRandom([6, 4]), explode=True, N=2)
        assert resultado.exploded
        assert "6+4=10" in resultado.detail
        assert resultado.total == 12


def test_una_fuente_de_azar_rota_no_cuelga_el_juego():
    # Un dado que siempre saca 6 explotaria para siempre.
    class Roto(RandomSource):
        def die(self, faces):
            self.count += 1
            return faces

    with pytest.raises(DiceError, match="no es aleatoria"):
        roll("d6", Roto(0), explode=True)


def test_la_traza_explica_el_total():
    resultado = roll("d6+1/2N", ScriptedRandom([4]), N=5)
    assert str(resultado) == "d6+1/2N = d6[4] + 1/2N(5->2) = 6"
