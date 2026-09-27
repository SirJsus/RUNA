"""Tests de la interfaz de terminal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runa.apps.cli import consola
from runa.apps.cli.main import main
from runa.core.decisions import DecisionImposible, Opcion, Pregunta


class TestConsolaDecisor:
    def decisor(self, respuestas):
        salidas = []
        d = consola.ConsolaDecisor(entrada=lambda _: respuestas.pop(0),
                                   salida=salidas.append)
        return d, salidas

    def pregunta(self):
        return Pregunta.crear("prueba", "¿Que haces?", [
            Opcion("a", "Atacar", "con la espada"),
            Opcion("b", "Huir"),
            Opcion("c", "Esperar"),
        ])

    def test_elige_por_numero(self):
        d, _ = self.decisor(["2"])
        assert d.elegir(self.pregunta()) == "b"

    def test_enter_toma_la_recomendada(self):
        d, _ = self.decisor([""])
        assert d.elegir(self.pregunta()) == "a"

    def test_reintenta_ante_una_respuesta_invalida(self):
        d, salidas = self.decisor(["x", "9", "0", "3"])
        assert d.elegir(self.pregunta()) == "c"
        assert sum("numero entre 1 y 3" in s for s in salidas) == 3

    def test_no_pregunta_cuando_no_hay_alternativa(self):
        d, salidas = self.decisor([])       # si preguntara, reventaria
        unica = Pregunta.crear("p", "?", [Opcion("solo", "Unica")])
        assert d.elegir(unica) == "solo" and salidas == []

    def test_sin_opciones_es_un_error(self):
        d, _ = self.decisor([])
        with pytest.raises(DecisionImposible):
            d.elegir(Pregunta.crear("p", "?", []))

    def test_muestra_las_opciones_y_sus_detalles(self):
        d, salidas = self.decisor(["1"])
        d.elegir(self.pregunta())
        texto = "\n".join(salidas)
        assert "Atacar" in texto and "con la espada" in texto and "Huir" in texto

    def test_cortar_la_entrada_termina_la_partida(self):
        def corta(_):
            raise EOFError
        d = consola.ConsolaDecisor(entrada=corta, salida=lambda _: None)
        with pytest.raises(SystemExit):
            d.elegir(self.pregunta())


class TestProgramaCompleto:
    def test_una_partida_automatica_termina_bien(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        assert main(["--auto", "--semilla", "7", "--nombre", "prueba"]) == 0
        salida = capsys.readouterr().out
        assert "Cuatro contra la Oscuridad" in salida
        assert "Fin de la aventura" in salida

    def test_guarda_la_partida_y_se_puede_continuar(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "7", "--nombre", "prueba"])
        guardada = tmp_path / "partidas" / "prueba.json"
        assert guardada.exists()
        datos = json.loads(guardada.read_text(encoding="utf-8"))
        assert datos["nombre"] == "prueba" and datos["semilla"] == 7

        capsys.readouterr()
        assert main(["--auto", str(guardada)]) == 0
        assert "Continuando: prueba" in capsys.readouterr().out

    def test_escribe_el_plano_de_la_mazmorra(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "11", "--nombre", "con_plano"])
        svg = tmp_path / "partidas" / "con_plano-plano.svg"
        assert svg.exists() and svg.read_text(encoding="utf-8").startswith("<svg")
        md = (tmp_path / "partidas" / "con_plano.md").read_text(encoding="utf-8")
        assert "## El plano" in md and svg.name in md

    def test_el_modo_grafo_no_dibuja_nada(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--grafo", "--semilla", "11", "--nombre", "sin_plano"])
        assert not (tmp_path / "partidas" / "sin_plano-plano.svg").exists()
        md = (tmp_path / "partidas" / "sin_plano.md").read_text(encoding="utf-8")
        assert "## El plano" not in md

    def test_sin_guardar_no_escribe_nada(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "3", "--sin-guardar"])
        assert not (tmp_path / "partidas").exists()

    def test_la_misma_semilla_da_la_misma_partida(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "123", "--sin-guardar"])
        primera = capsys.readouterr().out
        main(["--auto", "--semilla", "123", "--sin-guardar"])
        assert capsys.readouterr().out == primera

    def test_avisa_si_la_partida_no_existe(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        assert main(["--auto", str(tmp_path / "no_existe.json")]) == 1
        assert "no existe la partida" in capsys.readouterr().out


def test_los_colores_se_desactivan_sin_tty():
    # En una tuberia o con NO_COLOR no debe salir ni un codigo de escape.
    if not consola.COLOR:
        assert consola.negrita("x") == "x"
