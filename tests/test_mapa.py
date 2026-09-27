"""Tests del mapa como grafo."""

from __future__ import annotations

import pytest

from runa.core.mapa import Mapa, MapaError


@pytest.fixture
def mapa():
    m = Mapa()
    entrada = m.crear("entrada", salidas=2)
    a = m.crear("habitacion", salidas=3, plano="42")
    b = m.crear("corredor", salidas=2, plano="15")
    m.conectar(entrada.id, 0, a.id)
    m.conectar(a.id, 1, b.id)
    return m


def test_la_primera_sala_es_la_actual():
    m = Mapa()
    e = m.crear("entrada")
    assert m.actual == e.id and m.entrada is e


def test_conectar_gasta_una_salida_en_cada_lado(mapa):
    assert len(mapa[1].salidas_libres) == 1        # tenia 2, gasto 1
    assert len(mapa[2].salidas_libres) == 1        # tenia 3, gasto 2


def test_las_puertas_son_de_doble_sentido(mapa):
    assert 2 in mapa[1].conexiones.values()
    assert 1 in mapa[2].conexiones.values()


def test_no_se_puede_reutilizar_una_salida(mapa):
    with pytest.raises(MapaError, match="ya lleva"):
        mapa.conectar(1, 0, 3)


def test_no_se_puede_conectar_a_una_sala_sin_salidas():
    m = Mapa()
    a, b = m.crear(salidas=2), m.crear(salidas=1)
    c = m.crear(salidas=1)
    m.conectar(a.id, 0, b.id)                      # b agota su unica salida
    with pytest.raises(MapaError, match="salidas libres"):
        m.conectar(a.id, 1, b.id)


def test_moverse_a_una_sala_inexistente_falla(mapa):
    with pytest.raises(MapaError, match="no existe la sala 99"):
        mapa.mover(99)


def test_moverse_a_una_sala_no_adyacente_falla(mapa):
    assert mapa.actual == 1
    with pytest.raises(MapaError, match="no conecta"):
        mapa.mover(3)


def test_camino_a_la_entrada(mapa):
    mapa.mover(2)
    mapa.mover(3)
    assert mapa.camino_a_la_entrada() == [3, 2, 1]


def test_el_mapa_esta_completo_cuando_no_quedan_puertas():
    m = Mapa()
    a, b = m.crear(salidas=1), m.crear(salidas=1)
    assert not m.completo
    m.conectar(a.id, 0, b.id)
    assert m.completo


def test_corredor(mapa):
    assert mapa[3].es_corredor and not mapa[2].es_corredor


def test_round_trip_de_guardado(mapa):
    mapa.mover(2)
    mapa[2].contenido = "Esbirros"
    mapa[2].limpia = False
    mapa[2].anotar("hay sangre en el suelo")
    copia = Mapa.desde_dict(mapa.a_dict())
    assert copia.a_dict() == mapa.a_dict()
    assert copia[2].notas == ["hay sangre en el suelo"] and not copia[2].limpia
