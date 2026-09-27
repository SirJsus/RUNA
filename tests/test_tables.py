"""Tests del motor de tablas aleatorias."""

from __future__ import annotations

import textwrap

import pytest

from runa.core.tables import TableError, TableSet
from runa.core.rng import RandomSource
from tests.test_dice import ScriptedRandom

FIXTURE = """
sencilla:
  nombre: Tabla Sencilla
  dado: d6
  entradas:
    - {rango: 1-2, texto: Bajo}
    - {rango: 3-4, texto: Medio}
    - {rango: 5-6, texto: Alto}

encadena:
  nombre: Encadena
  dado: d6
  entradas:
    - {rango: 1-5, texto: Nada}
    - {rango: 6, texto: Algo mas, tirar: [sencilla], si_corredor: vacio}

premios:
  nombre: Premios
  dado: d6
  entradas:
    - {rango: 1-3, texto: Comun}
    - {rango: 4-6, texto: Irrepetible, unica: true, id: joya}
"""


@pytest.fixture
def tablas(tmp_path):
    archivo = tmp_path / "t.yaml"
    archivo.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
    return TableSet.desde_yaml(archivo)


def test_carga_desde_yaml(tablas):
    assert len(tablas) == 3
    assert tablas["sencilla"].nombre == "Tabla Sencilla"
    assert tablas["sencilla"].minimo == 1 and tablas["sencilla"].maximo == 6


def test_busca_por_rango(tablas):
    assert tablas["sencilla"].buscar(1).texto == "Bajo"
    assert tablas["sencilla"].buscar(4).texto == "Medio"
    assert tablas["sencilla"].buscar(6).texto == "Alto"


def test_el_modificador_se_recorta_al_rango(tablas):
    # "tesoro +1" sobre un 6 no se sale de la tabla: se queda en el extremo.
    assert tablas["sencilla"].buscar(99).texto == "Alto"
    assert tablas["sencilla"].buscar(-5).texto == "Bajo"


def test_tirada_con_modificador(tablas):
    r = tablas.tirar("sencilla", ScriptedRandom([1]), modificador=2)
    assert r.valor == 3 and r.texto == "Medio" and r.modificador == 2


def test_encadena_a_otra_tabla(tablas):
    r = tablas.tirar("encadena", ScriptedRandom([6, 5]))
    assert r.texto == "Algo mas"
    assert [h.texto for h in r.hijos] == ["Alto"]
    assert [x.tabla for x in r.recorrer()] == ["encadena", "sencilla"]


def test_el_predicado_puede_cortar_el_encadenado(tablas):
    # Asi resuelve el juego "si es un corredor, vacio": el motor no sabe que es
    # un corredor, solo aplica el predicado que le pasan.
    es_corredor = lambda entrada: not entrada.datos.get("si_corredor")
    r = tablas.tirar("encadena", ScriptedRandom([6]), encadenar=es_corredor)
    assert r.hijos == ()


def test_entrada_unica_se_vuelve_a_tirar_si_ya_salio(tablas):
    r = tablas.tirar("premios", ScriptedRandom([5, 6, 2]), excluir={"joya"})
    assert r.texto == "Comun"


def test_error_si_solo_quedan_entradas_gastadas(tmp_path):
    archivo = tmp_path / "t.yaml"
    archivo.write_text(
        "unica:\n  dado: d6\n  entradas:\n"
        "    - {rango: 1-6, texto: Solo una, unica: true, id: x}\n",
        encoding="utf-8",
    )
    tablas = TableSet.desde_yaml(archivo)
    with pytest.raises(TableError, match="ya gastadas"):
        tablas.tirar("unica", RandomSource(1), excluir={"x"})


def test_tabla_inexistente_sugiere_las_disponibles(tablas):
    with pytest.raises(TableError, match="sencilla"):
        tablas.tirar("fantasma", RandomSource(1))


def test_rangos_solapados_se_rechazan(tmp_path):
    archivo = tmp_path / "t.yaml"
    archivo.write_text(
        "mala:\n  dado: d6\n  entradas:\n"
        "    - {rango: 1-3, texto: A}\n    - {rango: 3-6, texto: B}\n",
        encoding="utf-8",
    )
    with pytest.raises(TableError, match="solapa"):
        TableSet.desde_yaml(archivo)


def test_validar_detecta_encadenados_rotos(tmp_path):
    archivo = tmp_path / "t.yaml"
    archivo.write_text(
        "a:\n  dado: d6\n  entradas:\n"
        "    - {rango: 1-6, texto: X, tirar: [no_existe]}\n",
        encoding="utf-8",
    )
    problemas = TableSet.desde_yaml(archivo).validar()
    assert len(problemas) == 1 and "no_existe" in problemas[0]
