"""Tests de personajes, objetos y grupo."""

from __future__ import annotations

import pytest

from runa.core.entities import ClasePersonaje, Grupo, Objeto, Personaje, ReglaDeJuego
from runa.core.rng import RandomSource


@pytest.fixture
def clase():
    return ClasePersonaje.desde_dict("guerrero", {
        "nombre": "Guerrero", "vida": "6+N", "riqueza_inicial": "2d6",
        "permite": {"armaduras": ["ligera"], "escudo": True, "armas": ["mano"]},
        "recursos": {"suerte": "N+1"},
    })


@pytest.fixture
def limitada():
    return ClasePersonaje.desde_dict("mago", {
        "nombre": "Mago", "vida": "2+N", "nivel_maximo": 3,
        "permite": {"armaduras": [], "escudo": False, "armas": ["ligera"],
                    "objetos_magicos": False},
    })


class TestVidaYHeridas:
    def test_la_vida_sale_de_la_formula_de_la_clase(self, clase):
        assert Personaje("X", clase, nivel=1).vida_max == 7
        assert Personaje("X", clase, nivel=4).vida_max == 10

    def test_herir_y_morir(self, clase):
        p = Personaje("X", clase)
        assert p.herir(3) == 3 and p.vida == 4 and p.vivo
        assert p.herir(10) == 4 and p.vida == 0 and not p.vivo and p.muerto

    def test_curar_no_pasa_del_maximo_ni_resucita(self, clase):
        p = Personaje("X", clase)
        p.herir(3)
        assert p.curar(10) == 3 and p.vida == 7
        p.herir(99)
        assert p.curar(5) == 0 and p.muerto


class TestNivel:
    def test_subir_nivel_sube_maximo_y_cura_esa_cantidad(self, clase):
        p = Personaje("X", clase)
        p.herir(3)          # 4/7
        p.subir_nivel()
        assert (p.nivel, p.vida, p.vida_max) == (2, 5, 8)

    def test_no_se_pasa_del_nivel_maximo(self, limitada):
        p = Personaje("X", limitada, nivel=3)
        with pytest.raises(ReglaDeJuego, match="nivel 3"):
            p.subir_nivel()


class TestRecursos:
    def test_se_calculan_con_el_nivel(self, clase):
        assert Personaje("X", clase, nivel=3).recursos["suerte"] == 4

    def test_gastar_de_mas_da_error_claro(self, clase):
        p = Personaje("X", clase)
        p.gastar("suerte", 2)
        with pytest.raises(ReglaDeJuego, match="le quedan 0"):
            p.gastar("suerte")


class TestEquipo:
    def test_solo_lo_equipado_aporta_etiquetas(self, clase):
        p = Personaje("X", clase)
        arma = Objeto.desde_dict("a", {"tipo": "arma", "categoria": "mano",
                                       "etiquetas": ["cortante"]})
        p.anadir(arma, equipar=False)
        assert "cortante" not in p.etiquetas_activas()
        p.equipo[0].equipado = True
        assert {"cortante", "mano"} <= p.etiquetas_activas()

    def test_un_consumible_nunca_se_equipa(self, clase):
        p = Personaje("X", clase)
        p.anadir(Objeto.desde_dict("v", {"tipo": "consumible"}), equipar=True)
        assert not p.equipo[0].activo

    def test_detecta_equipo_no_permitido(self, limitada):
        p = Personaje("X", limitada)
        p.anadir(Objeto.desde_dict("e", {"nombre": "Escudo", "tipo": "escudo"}), equipar=True)
        assert "no puede usar Escudo" in p.problemas_de_equipo()[0]

    def test_detecta_exceso_de_manos(self, clase):
        p = Personaje("X", clase)
        for id in "ab":
            p.anadir(Objeto.desde_dict(id, {"tipo": "armadura", "categoria": "ligera",
                                            "manos": 2}), equipar=True)
        assert any("4 manos" in x for x in p.problemas_de_equipo())

    def test_variante_invalida(self):
        arma = Objeto.desde_dict("a", {"tipo": "arma", "variantes": ["aplastante"]})
        with pytest.raises(ReglaDeJuego, match="admite: aplastante"):
            arma.con_variante("magica")

    def test_precio_de_venta_es_la_mitad_hacia_abajo(self):
        assert Objeto.desde_dict("a", {"precio": 15}).precio_venta() == 7


class TestGrupo:
    def test_orden_de_marcha_y_reordenacion(self, clase):
        grupo = Grupo([Personaje(n, clase) for n in ("Ana", "Bru", "Cal")])
        grupo.reordenar(["Cal", "Ana", "Bru"])
        assert [p.nombre for p in grupo] == ["Cal", "Ana", "Bru"]

    def test_reordenar_exige_el_grupo_completo(self, clase):
        grupo = Grupo([Personaje(n, clase) for n in ("Ana", "Bru")])
        with pytest.raises(ReglaDeJuego, match="todo el grupo"):
            grupo.reordenar(["Ana"])

    def test_vivos_y_oro(self, clase):
        grupo = Grupo([Personaje(n, clase) for n in ("Ana", "Bru")])
        grupo.miembros[0].oro, grupo.miembros[1].oro = 10, 5
        grupo.miembros[1].herir(99)
        assert [p.nombre for p in grupo.vivos] == ["Ana"] and grupo.oro == 15

    def test_buscar_por_nombre_ignora_mayusculas(self, clase):
        grupo = Grupo([Personaje("Ana", clase)])
        assert grupo.por_nombre("ANA").nombre == "Ana"
        with pytest.raises(ReglaDeJuego):
            grupo.por_nombre("Zoe")
