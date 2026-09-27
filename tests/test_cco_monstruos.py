"""El bestiario y las tablas de Cuatro contra la Oscuridad."""

from __future__ import annotations

import pytest

from runa.core.rng import RandomSource
from runa.games.cco.juego import Juego
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


def test_los_datos_son_coherentes(juego):
    """Referencias cruzadas entre tablas, bestiario, catalogo y habilidades."""
    assert juego.validar() == []


def test_todas_las_tablas_de_reacciones_cubren_el_d6_entero(juego):
    # Asi se detecto que el minotauro se dejaba el 5 sin asignar en el libro.
    huecos = []
    for id, tabla in juego.tablas.tablas.items():
        if not id.startswith("reacciones_"):
            continue
        cubierto = {v for e in tabla.entradas for v in range(e.minimo, e.maximo + 1)}
        if faltan := set(range(1, 7)) - cubierto:
            huecos.append(f"{id}: falta {sorted(faltan)}")
    assert huecos == []


@pytest.mark.parametrize("tabla,esperados", [
    ("bichos", 6), ("esbirros", 6), ("jefes", 6), ("monstruos_extranos", 6),
])
def test_las_tablas_de_aparicion_tienen_seis_entradas(juego, tabla, esperados):
    assert len(juego.tablas[tabla].entradas) == esperados


class TestPerfilesConcretos:
    @pytest.mark.parametrize("id,nivel,vida,ataques", [
        ("momia", 5, 4, 2), ("orco_brutal", 5, 5, 2), ("ogro", 5, 6, 1),
        ("medusa", 4, 4, 1), ("senor_del_caos", 6, 4, 3), ("dragon_pequeno", 6, 5, 2),
        ("minotauro", 5, 4, 2), ("quimera", 5, 6, 3), ("arana_gigante", 5, 3, 2),
    ])
    def test_estadisticas_de_los_jefes(self, juego, id, nivel, vida, ataques):
        p = juego.bestiario[id]
        assert (p.nivel, p.vida, p.ataques) == (nivel, vida, ataques)

    def test_el_ogro_pega_por_dos(self, juego):
        assert juego.bestiario["ogro"].dano == 2

    def test_el_dragon_deja_tres_tiradas_de_tesoro_con_mas_uno(self, juego):
        t = juego.bestiario["dragon_pequeno"].tesoro
        assert (t.tiradas, t.modificador) == (3, 1)

    def test_los_bichos_no_dan_experiencia(self, juego):
        assert all(not p.xp for p in juego.bestiario.de_tipo("bicho"))

    def test_los_jefes_y_extranos_si_la_dan_salvo_los_gremlins(self, juego):
        sin_xp = [p.id for p in juego.bestiario.perfiles.values()
                  if p.es_jefe and not p.xp]
        assert sin_xp == ["gremlins_invisibles"]

    def test_esqueletos_y_momias_nunca_prueban_moral(self, juego):
        for id in ("esqueletos", "zombies", "momia"):
            assert not juego.bestiario[id].moral.prueba, id

    def test_el_grupo_de_goblins_tiene_moral_a_menos_uno(self, juego):
        assert juego.bestiario["goblins_grupo"].moral.modificador == -1

    def test_a_los_gremlins_no_se_les_puede_combatir(self, juego):
        assert not juego.bestiario["gremlins_invisibles"].combate


class TestReglasQueImponenLosMonstruos:
    def mago(self, juego, nivel=3):
        return juego.crear_personaje("M", "mago", RandomSource(0), nivel=nivel,
                                     equipo_inicial=[])

    def test_los_murcielagos_estorban_los_hechizos(self, juego):
        m = self.mago(juego)
        amenaza = juego.bestiario["murcielagos_vampiro"].amenaza()
        r = juego.tirar("hechizo", m, ScriptedRandom([4]), amenaza=amenaza)
        assert r.bonificacion == 3 - 1   # nivel de mago menos los chillidos

    def test_la_bola_de_fuego_va_a_mas_dos_contra_momias(self, juego):
        m = self.mago(juego)
        momia = juego.bestiario["momia"].amenaza()
        normal = juego.tirar("hechizo", m, ScriptedRandom([3]), amenaza=momia)
        fuego = juego.tirar("hechizo", m, ScriptedRandom([3]), amenaza=momia,
                            etiquetas={"bola_de_fuego"})
        assert normal.bonificacion == 3 and fuego.bonificacion == 5

    def test_las_flechas_van_a_menos_uno_contra_esqueletos(self, juego):
        arquero = juego.crear_personaje("A", "guerrero", RandomSource(0), nivel=2,
                                        equipo_inicial=["arco"])
        esq = juego.bestiario["esqueletos"].amenaza()
        r = juego.atacar(arquero, esq, ScriptedRandom([3]))
        assert r.bonificacion == 2 - 1

    def test_la_carga_del_minotauro_solo_afecta_al_primer_turno(self, juego):
        g = juego.crear_personaje("G", "guerrero", RandomSource(0))
        mino = juego.bestiario["minotauro"].amenaza()
        despues = juego.defender(g, mino, ScriptedRandom([3]))
        primero = juego.defender(g, mino, ScriptedRandom([3]),
                                 etiquetas={"primer_turno"})
        assert despues.bonificacion == 2 and primero.bonificacion == 1

    def test_la_plaga_del_hierro_anula_la_armadura_pesada_no_el_escudo(self, juego):
        g = juego.crear_personaje("G", "guerrero", RandomSource(0),
                                  equipo_inicial=["armadura_pesada", "escudo"])
        plaga = juego.bestiario["plaga_del_hierro"].amenaza()
        assert juego.defender(g, plaga, ScriptedRandom([3])).bonificacion == 1


class TestGeneracionDeEncuentros:
    def test_instanciar_respeta_la_tirada_ya_hecha(self, juego):
        # Encadenar y luego instanciar no debe volver a tirar la tabla.
        r = juego.tablas.tirar("bichos", RandomSource(3), encadenar=False)
        esperado = r.entrada.datos["monstruo"]
        enc = juego.encuentro_desde(r, RandomSource(3))
        assert enc.perfil.id == esperado

    def test_la_entrada_doble_de_esbirros_elige_una_de_las_dos(self, juego):
        r = juego.tablas["esbirros"].buscar(1)
        assert r.datos["monstruo"] == ["esqueletos", "zombies"]
        salidos = set()
        for semilla in range(30):
            enc = juego.encuentro_desde(
                juego.tablas.tirar("esbirros", ScriptedRandom([1]), encadenar=False),
                RandomSource(semilla),
            )
            salidos.add(enc.perfil.id)
        assert salidos == {"esqueletos", "zombies"}

    def test_entrada_sin_monstruo_da_error_claro(self, juego):
        r = juego.tablas.tirar("tesoros", ScriptedRandom([1]), encadenar=False)
        with pytest.raises(Exception, match="no nombra ningun monstruo"):
            juego.encuentro_desde(r, RandomSource(0))


class TestMoral:
    def test_con_tres_o_menos_huyen(self, juego):
        enc = juego.bestiario["goblins"].generar(RandomSource(1))
        assert juego.moral(enc, ScriptedRandom([3])) is False and enc.huido

    def test_con_cuatro_o_mas_aguantan(self, juego):
        enc = juego.bestiario["goblins"].generar(RandomSource(1))
        assert juego.moral(enc, ScriptedRandom([4])) is True and not enc.huido

    def test_el_modificador_de_moral_cuenta(self, juego):
        # El grupo de goblins tiene moral -1: un 4 se queda en 3 y huyen.
        enc = juego.bestiario["goblins_grupo"].generar(RandomSource(1))
        assert juego.moral(enc, ScriptedRandom([4])) is False

    def test_quien_nunca_prueba_moral_devuelve_none(self, juego):
        enc = juego.bestiario["esqueletos"].generar(RandomSource(1))
        assert juego.moral(enc, ScriptedRandom([1])) is None and not enc.huido


class TestHabilidades:
    def test_los_seis_hechizos_estan(self, juego):
        seis = {"bendicion", "bola_de_fuego", "rayo", "dormir", "escapada", "proteger"}
        assert seis <= set(juego.habilidades.catalogo)

    def test_la_bendicion_la_lanzan_magos_elfos_y_clerigos(self, juego):
        b = juego.habilidades["bendicion"]
        assert all(b.puede_usarla(c) for c in ("mago", "elfo", "clerigo"))
        assert not b.puede_usarla("guerrero")

    def test_solo_magos_y_elfos_lanzan_bola_de_fuego(self, juego):
        f = juego.habilidades["bola_de_fuego"]
        assert f.puede_usarla("mago") and not f.puede_usarla("clerigo")

    def test_escapada_se_lanza_en_lugar_de_defender(self, juego):
        e = juego.habilidades["escapada"]
        assert e.en_momento("defensa") and e.en_momento("turno") and e.automatica

    def test_todas_las_habilidades_tienen_su_efecto_implementado(self, juego):
        assert juego.habilidades.sin_implementar() == []
