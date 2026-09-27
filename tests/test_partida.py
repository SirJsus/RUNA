"""Tests del estado de partida y su guardado."""

from __future__ import annotations

import json

import pytest

from runa.core.rng import RandomSource
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Aventura, Campana, Partida


@pytest.fixture(scope="module")
def juego():
    return Juego()


@pytest.fixture
def partida(juego):
    grupo = juego.crear_grupo(
        [("Brakk", "guerrero"), ("Orin", "mago"), ("Thrunn", "enano")],
        RandomSource(5),
    )
    juego.preparar_hechizos(grupo.por_nombre("Orin"), ["rayo", "proteger", "dormir"])
    p = Partida(juego, grupo, semilla=99)
    entrada = p.mapa.crear("entrada", salidas=2)
    sala = p.mapa.crear("corredor", salidas=2, plano="15")
    p.mapa.conectar(entrada.id, 0, sala.id)
    p.mapa.mover(sala.id)
    return p


def test_lo_de_una_vez_por_aventura_solo_pasa_una_vez():
    a = Aventura()
    assert a.gastar("fuente") is True
    assert a.gastar("fuente") is False


class TestGuardado:
    def guardar_y_cargar(self, partida, tmp_path, juego):
        ruta = partida.guardar(tmp_path / "p.json")
        return Partida.cargar(ruta, juego)

    def test_conserva_al_grupo(self, partida, tmp_path, juego):
        partida.grupo.por_nombre("Brakk").herir(3)
        partida.grupo.por_nombre("Brakk").oro = 42
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        brakk = copia.grupo.por_nombre("Brakk")
        assert brakk.vida == brakk.vida_max - 3 and brakk.oro == 42
        assert [o.nombre for o in brakk.equipo] == \
               [o.nombre for o in partida.grupo.por_nombre("Brakk").equipo]

    def test_conserva_las_variantes_del_equipo(self, partida, tmp_path, juego):
        arma = partida.grupo.por_nombre("Brakk").arma
        assert "cortante" in arma.etiquetas
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        assert "cortante" in copia.grupo.por_nombre("Brakk").arma.etiquetas

    def test_conserva_estados_y_sus_reglas(self, partida, tmp_path, juego):
        partida.grupo.por_nombre("Orin").estados.append(juego.estado("maldito"))
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        orin = copia.grupo.por_nombre("Orin")
        assert [e.id for e in orin.estados] == ["maldito"]
        # Las reglas se releen del YAML, no se guardan.
        assert any("maldicion" in r.texto for r in orin.reglas())

    def test_conserva_hechizos_preparados_y_recursos(self, partida, tmp_path, juego):
        partida.grupo.por_nombre("Orin").preparados.remove("rayo")
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        assert copia.grupo.por_nombre("Orin").preparados == ["proteger", "dormir"]

    def test_conserva_mapa_aventura_y_campana(self, partida, tmp_path, juego):
        partida.aventura.jefes_vistos = 2
        partida.aventura.gastar("curandero")
        partida.campana.pistas["Brakk"] = 2
        partida.campana.ultimo_en_subir = "Orin"
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        assert copia.mapa.actual == 2 and len(copia.mapa) == 2
        assert copia.aventura.jefes_vistos == 2
        assert copia.aventura.gastar("curandero") is False
        assert copia.campana.pistas == {"Brakk": 2}
        assert copia.campana.ultimo_en_subir == "Orin"

    def test_conserva_la_cronica(self, partida, tmp_path, juego):
        partida.anotar("nota", "El grupo entra.")
        partida.anotar("nota", "Se oye un ruido.")
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        assert copia.registro.cronica() == "El grupo entra.\nSe oye un ruido."

    def test_el_azar_continua_donde_estaba(self, partida, tmp_path, juego):
        for _ in range(7):
            partida.rng.die(6)
        copia = self.guardar_y_cargar(partida, tmp_path, juego)
        assert copia.rng.count == partida.rng.count
        # Y la siguiente tirada coincide: continuar no cambia la partida.
        assert copia.rng.die(6) == partida.rng.die(6)

    def test_el_json_es_legible(self, partida, tmp_path):
        ruta = partida.guardar(tmp_path / "p.json")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["juego"] == "cuatro-contra-la-oscuridad"
        assert datos["grupo"]["miembros"][0]["clase"] == "guerrero"

    def test_reconstruye_el_dibujo_de_la_mazmorra(self, juego, tmp_path):
        """La rejilla no se guarda: se rehace de la loseta y el sitio de cada sala."""
        from runa.core.decisions import DecisorPorDefecto
        from runa.games.cco.exploracion import Exploracion

        grupo = juego.crear_grupo([("A", "guerrero")], RandomSource(4))
        original = Partida(juego, grupo, semilla=4, nombre="con_plano")
        Exploracion(original, DecisorPorDefecto()).jugar(limite=12)
        assert len(original.mapa.rejilla) > 1

        copia = Partida.cargar(original.guardar(tmp_path / "p.json"), juego)
        assert copia.mapa.rejilla is not None
        assert copia.mapa.rejilla.ocupadas == original.mapa.rejilla.ocupadas
        assert copia.mapa.rejilla.ascii() == original.mapa.rejilla.ascii()

    def test_el_modo_solo_grafo_se_conserva(self, juego, tmp_path):
        grupo = juego.crear_grupo([("A", "guerrero")], RandomSource(4))
        sin_dibujo = Partida(juego, grupo, semilla=4, rejilla=False)
        copia = Partida.cargar(sin_dibujo.guardar(tmp_path / "g.json"), juego)
        assert copia.mapa.rejilla is None

    def test_se_rechaza_una_partida_de_version_futura(self, partida, juego):
        datos = partida.a_dict()
        datos["version"] = 999
        with pytest.raises(ValueError, match="actualiza"):
            Partida.desde_dict(datos, juego)

    def test_error_claro_si_falta_un_objeto_del_catalogo(self, partida, juego):
        datos = partida.a_dict()
        datos["grupo"]["miembros"][0]["equipo"][0]["id"] = "espada_laser"
        with pytest.raises(Exception, match="espada_laser"):
            Partida.desde_dict(datos, juego)
