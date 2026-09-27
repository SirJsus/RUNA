"""Las clases de Cuatro contra la Oscuridad, contrastadas con el reglamento.

Los tres primeros tests son los ejemplos numerados del propio libro (pagina 25).
"""

from __future__ import annotations

import pytest

from runa.core.entities import ReglaDeJuego
from runa.core.rng import RandomSource
from runa.games.cco.juego import Juego
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


def personaje(juego, clase, nivel=1, equipo=None, variante=""):
    return juego.crear_personaje(
        "X", clase, RandomSource(0), nivel=nivel,
        equipo_inicial=equipo, variante_arma=variante,
    )


def esqueleto(juego):
    return juego.amenaza("Esqueleto", 3, ["no_muerto", "esqueleto"])


class TestEjemplosDelLibro:
    def test_ejemplo_1_clerigo_nivel_5_con_maza_a_dos_manos_contra_esqueleto(self, juego):
        # d6 +5 (nivel completo contra no muertos) +1 (dos manos) +1 (aplastante)
        clerigo = personaje(juego, "clerigo", nivel=5,
                            equipo=["arma_dos_manos"], variante="aplastante")
        r = juego.atacar(clerigo, esqueleto(juego), ScriptedRandom([3]))
        assert r.bonificacion == 7
        assert sorted(m.valor for m in r.modificadores) == [1, 1, 5]
        assert r.total == 10

    def test_ejemplo_2_guerrero_nivel_4_con_espada(self, juego):
        guerrero = personaje(juego, "guerrero", nivel=4, equipo=["arma_mano"])
        r = juego.atacar(guerrero, juego.amenaza("Orco", 4), ScriptedRandom([2]))
        assert r.bonificacion == 4 and r.total == 6

    def test_ejemplo_3_mago_con_daga_no_suma_nivel(self, juego):
        # "un mago de nivel 5 lucha como un mago de nivel 1"
        mago = personaje(juego, "mago", nivel=5, equipo=["arma_mano_ligera"])
        r = juego.atacar(mago, juego.amenaza("Orco", 4), ScriptedRandom([4]))
        assert r.bonificacion == -1 and r.total == 3 and not r.exito


class TestClerigo:
    def test_medio_nivel_contra_criaturas_normales(self, juego):
        clerigo = personaje(juego, "clerigo", nivel=5, equipo=["arma_mano"])
        r = juego.atacar(clerigo, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        assert r.bonificacion == 2  # 5 // 2

    def test_nivel_completo_contra_no_muertos_sin_acumular_el_medio(self, juego):
        clerigo = personaje(juego, "clerigo", nivel=5, equipo=["arma_mano"])
        r = juego.atacar(clerigo, juego.amenaza("Zombi", 3, ["no_muerto"]), ScriptedRandom([3]))
        assert r.bonificacion == 5


class TestPicaro:
    def test_suma_nivel_a_la_defensa(self, juego):
        picaro = personaje(juego, "picaro", nivel=3)
        r = juego.defender(picaro, juego.amenaza("Orco", 4), ScriptedRandom([2]))
        assert r.bonificacion == 3 + 1  # nivel + armadura ligera

    def test_no_suma_al_ataque_sin_superar_en_numero(self, juego):
        picaro = personaje(juego, "picaro", nivel=3, equipo=["arma_mano"])
        r = juego.atacar(picaro, juego.amenaza("Orco", 4, ["esbirro"]), ScriptedRandom([3]))
        assert r.bonificacion == 0

    def test_suma_al_ataque_contra_esbirros_superados_en_numero(self, juego):
        picaro = personaje(juego, "picaro", nivel=3, equipo=["arma_mano"])
        r = juego.atacar(
            picaro, juego.amenaza("Orco", 4, ["esbirro"]),
            ScriptedRandom([3]), etiquetas={"superados_en_numero"},
        )
        assert r.bonificacion == 3

    def test_no_suma_contra_un_jefe_aunque_le_superen_en_numero(self, juego):
        picaro = personaje(juego, "picaro", nivel=3, equipo=["arma_mano"])
        r = juego.atacar(
            picaro, juego.amenaza("Ogro", 5, ["jefe"]),
            ScriptedRandom([3]), etiquetas={"superados_en_numero"},
        )
        assert r.bonificacion == 0


class TestEnano:
    def test_suma_nivel_cuerpo_a_cuerpo(self, juego):
        enano = personaje(juego, "enano", nivel=4, equipo=["arma_mano"])
        r = juego.atacar(enano, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        assert r.bonificacion == 4

    def test_no_suma_nivel_con_arma_a_distancia(self, juego):
        enano = personaje(juego, "enano", nivel=4, equipo=["arco"])
        r = juego.atacar(enano, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        assert r.bonificacion == 0

    def test_mas_uno_contra_goblins(self, juego):
        enano = personaje(juego, "enano", nivel=2, equipo=["arma_mano"])
        r = juego.atacar(enano, juego.amenaza("Goblin", 3, ["goblin"]), ScriptedRandom([3]))
        assert r.bonificacion == 3  # nivel 2 + 1

    def test_mas_uno_a_la_defensa_contra_gigantes(self, juego):
        enano = personaje(juego, "enano", nivel=2)
        r = juego.defender(enano, juego.amenaza("Troll", 5, ["troll"]), ScriptedRandom([3]))
        assert r.bonificacion == 1 + 1 + 1  # armadura + escudo + enano


class TestElfoYHalfling:
    def test_elfo_mas_uno_contra_orcos(self, juego):
        elfo = personaje(juego, "elfo", nivel=2, equipo=["arma_mano"])
        r = juego.atacar(elfo, juego.amenaza("Orco", 4, ["orco"]), ScriptedRandom([3]))
        assert r.bonificacion == 3

    def test_elfo_no_pasa_de_nivel_3(self, juego):
        with pytest.raises(ReglaDeJuego, match="nivel 3"):
            personaje(juego, "elfo", nivel=4)

    def test_halfling_suma_nivel_defendiendo_de_ogros(self, juego):
        h = personaje(juego, "halfling", nivel=3)
        normal = juego.defender(h, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        contra_ogro = juego.defender(
            h, juego.amenaza("Ogro", 5, ["ogro"]), ScriptedRandom([3])
        )
        assert normal.bonificacion == 1                 # solo armadura ligera
        assert contra_ogro.bonificacion == 1 + 3

    def test_halfling_arranca_con_nivel_mas_uno_de_suerte(self, juego):
        assert personaje(juego, "halfling").recursos["suerte"] == 2
        assert personaje(juego, "halfling", nivel=3).recursos["suerte"] == 4


class TestBarbaro:
    def test_ataque_de_ira_toma_la_mejor_de_tres(self, juego):
        b = personaje(juego, "barbaro", nivel=2, equipo=["arma_mano"])
        r = juego.atacar(
            b, juego.amenaza("Ogro", 5), ScriptedRandom([1, 4, 2]), ventaja=3
        )
        assert r.tirada.total == 4 and r.total == 6 and r.exito

    def test_no_puede_usar_objetos_magicos(self, juego):
        b = personaje(juego, "barbaro")
        assert not b.clase.permite_objeto(juego.objeto("pocion_curacion"))


class TestArmasYArmaduras:
    def test_arma_a_dos_manos_suma_uno(self, juego):
        g = personaje(juego, "guerrero", nivel=1, equipo=["arma_dos_manos"])
        r = juego.atacar(g, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        assert r.bonificacion == 1 + 1  # nivel + dos manos

    def test_en_manos_de_un_mago_el_arma_a_dos_manos_cuenta_como_ligera(self, juego):
        # FAQ: "aun contara como arma ligera (-1) en sus manos".
        mago = personaje(juego, "mago", nivel=3, equipo=["arma_dos_manos"])
        r = juego.atacar(mago, juego.amenaza("Orco", 4), ScriptedRandom([3]))
        assert r.bonificacion == -1

    def test_aplastante_suma_uno_contra_esqueletos(self, juego):
        g = personaje(juego, "guerrero", nivel=1, equipo=["arma_mano"], variante="aplastante")
        cortante = personaje(juego, "guerrero", nivel=1, equipo=["arma_mano"], variante="cortante")
        assert juego.atacar(g, esqueleto(juego), ScriptedRandom([3])).bonificacion == 2
        assert juego.atacar(cortante, esqueleto(juego), ScriptedRandom([3])).bonificacion == 1

    def test_el_escudo_no_protege_al_huir_ni_por_sorpresa(self, juego):
        g = personaje(juego, "guerrero")
        orco = juego.amenaza("Orco", 4)
        assert juego.defender(g, orco, ScriptedRandom([3])).bonificacion == 2
        for etiqueta in ("huida", "sorpresa"):
            r = juego.defender(g, orco, ScriptedRandom([3]), etiquetas={etiqueta})
            assert r.bonificacion == 1, etiqueta

    def test_ataques_que_ignoran_la_armadura(self, juego):
        g = personaje(juego, "guerrero", equipo=["armadura_pesada", "escudo"])
        r = juego.defender(
            g, juego.amenaza("Plaga del Hierro", 3), ScriptedRandom([3]),
            etiquetas={"ignora_armadura_pesada"},
        )
        assert r.bonificacion == 1  # se conserva el escudo, no la armadura pesada


class TestCreacionDeGrupo:
    def test_vida_inicial_de_cada_clase(self, juego):
        esperado = {"guerrero": 7, "clerigo": 5, "picaro": 4, "mago": 3,
                    "barbaro": 8, "elfo": 5, "enano": 6, "halfling": 4}
        for clase, vida in esperado.items():
            assert personaje(juego, clase).vida_max == vida, clase

    def test_el_elfo_lleva_arco_y_espada_pero_solo_empuna_una(self, juego):
        elfo = personaje(juego, "elfo")
        armas = [o for o in elfo.equipo if o.tipo == "arma"]
        assert len(armas) == 2
        assert sum(1 for a in armas if a.equipado) == 1
        assert elfo.problemas_de_equipo() == []

    def test_los_datos_del_juego_son_coherentes(self, juego):
        # Solo deben quedar avisos de tablas aun sin transcribir.
        assert [p for p in juego.validar() if "tabla inexistente" not in p] == []

    def test_clase_inexistente(self, juego):
        with pytest.raises(ReglaDeJuego, match="hay:"):
            personaje(juego, "paladin")


def test_dos_juegos_con_datos_distintos_no_se_pisan(tmp_path):
    """La carpeta de datos va en la instancia, no en una global."""
    import shutil
    from runa.games.cco.juego import DATOS

    propios = tmp_path / "data"
    shutil.copytree(DATOS, propios)
    clases = propios / "clases.yaml"
    clases.write_text(
        clases.read_text(encoding="utf-8")
        + "\npaladin:\n  nombre: Paladin\n  vida: 5+N\n"
          "  permite: {armas: [mano]}\n  equipo_inicial: [arma_mano]\n",
        encoding="utf-8",
    )
    por_defecto = Juego()
    a_medida = Juego(datos=propios)
    assert "paladin" in a_medida.clases and "paladin" not in por_defecto.clases
    # Y el de despues sigue viendo los datos de siempre.
    assert "paladin" not in Juego().clases
