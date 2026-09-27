"""Tests del bucle de combate."""

from __future__ import annotations

import pytest

from runa.core.decisions import DecisorGuion, DecisorPorDefecto
from runa.core.events import Registro
from runa.core.rng import RandomSource
from runa.games.cco.combate import Combate, Situacion
from runa.games.cco.juego import Juego
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


@pytest.fixture
def grupo(juego):
    g = juego.crear_grupo(
        [("Brakk", "guerrero"), ("Sela", "clerigo"),
         ("Nim", "picaro"), ("Orin", "mago")],
        RandomSource(1),
    )
    juego.preparar_hechizos(g.por_nombre("Orin"), ["bola_de_fuego", "rayo", "dormir"])
    return g


def combate(juego, grupo, monstruo, rng, *, guion=None, sit=None, cantidad=None, vida=None):
    enc = juego.bestiario[monstruo].generar(RandomSource(0))
    if cantidad is not None:
        enc.cantidad = enc.cantidad_inicial = cantidad
    if vida is not None:
        enc.vida = enc.vida_inicial = vida
    reg = Registro()
    c = Combate(
        juego, grupo, enc, rng,
        decisor=DecisorGuion(guion or {}), registro=reg,
        situacion=sit if sit is not None else Situacion(),
    )
    return c, reg


# --------------------------------------------------------------------------- #
# Reacciones
# --------------------------------------------------------------------------- #


class TestReacciones:
    def test_atacar_de_inmediato_evita_la_tirada_de_reaccion(self, juego, grupo):
        c, reg = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=5),
                         guion={"abordaje": "atacar_ya"})
        c.resolver()
        assert "reaccion" not in reg.tipos
        assert c.reaccion == "lucha"

    def test_huir_por_reaccion_no_deja_saqueo(self, juego, grupo):
        # Ratas: 1-3 huyen. Huir por reaccion es lo unico que quita el botin.
        c, _ = combate(juego, grupo, "ratas", ScriptedRandom([1], relleno=1),
                       guion={"abordaje": "esperar"})
        r = c.resolver()
        assert r.desenlace == "evitado" and r.reaccion == "huir" and not r.botin

    def test_huir_si_superados_se_queda_si_no_le_superan(self, juego, grupo):
        # 6 ciempies contra 4 personajes: no les superan, asi que luchan.
        c, reg = combate(juego, grupo, "ciempies_gigantes",
                         ScriptedRandom([2], relleno=5), cantidad=6,
                         guion={"abordaje": "esperar", "salir_del_combate": "luchar"})
        c.resolver()
        assert c.reaccion == "lucha"
        assert any("se quedan a luchar" in e.texto for e in reg)

    def test_huir_si_superados_huye_si_le_superan(self, juego, grupo):
        c, _ = combate(juego, grupo, "ciempies_gigantes",
                       ScriptedRandom([2], relleno=1), cantidad=2,
                       guion={"abordaje": "esperar"})
        r = c.resolver()
        assert r.desenlace == "evitado" and not r.botin


class TestSoborno:
    def test_pagar_evita_el_combate_y_cuesta_el_oro(self, juego, grupo):
        for p in grupo:
            p.oro = 50
        # Hobgoblins: 2-3 soborno, 10 oro por cabeza. Con 3 son 30.
        c, _ = combate(juego, grupo, "hobgoblins", ScriptedRandom([2], relleno=1),
                       cantidad=3, guion={"abordaje": "esperar", "soborno": "pagar"})
        r = c.resolver()
        assert r.desenlace == "evitado" and not r.botin
        assert grupo.oro == 200 - 30

    def test_negarse_lleva_al_combate(self, juego, grupo):
        for p in grupo:
            p.oro = 50
        c, _ = combate(juego, grupo, "hobgoblins", ScriptedRandom([2], relleno=5),
                       cantidad=3, guion={"abordaje": "esperar", "soborno": "luchar",
                                          "salir_del_combate": "luchar"})
        c.resolver()
        assert c.reaccion == "lucha" and grupo.oro == 200

    def test_sin_oro_suficiente_no_se_ofrece_pagar(self, juego, grupo):
        for p in grupo:
            p.oro = 1
        c, reg = combate(juego, grupo, "hobgoblins", ScriptedRandom([2], relleno=5),
                         cantidad=3, guion={"abordaje": "esperar",
                                            "salir_del_combate": "luchar"})
        c.resolver()
        assert any("no puede pagar" in e.texto for e in reg)

    def test_dos_enanos_impiden_sobornar(self, juego):
        # "un grupo con 2 o mas enanos no puede sobornar monstruos"
        g = juego.crear_grupo([("A", "enano"), ("B", "enano"), ("C", "guerrero")],
                              RandomSource(1))
        for p in g:
            p.oro = 100
        c, reg = combate(juego, g, "hobgoblins", ScriptedRandom([2], relleno=5),
                         cantidad=3, guion={"abordaje": "esperar",
                                            "salir_del_combate": "luchar"})
        c.resolver()
        assert any("impensable" in e.texto for e in reg)
        assert c.reaccion == "lucha" and g.oro == 300


# --------------------------------------------------------------------------- #
# Reparto de ataques
# --------------------------------------------------------------------------- #


class TestRepartoDeAtaques:
    def test_igual_numero_todos_reciben_uno(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=4)
        assert len(c.repartir_ataques(4)) == 4
        assert {p.nombre for p in c.repartir_ataques(4)} == {"Brakk", "Sela", "Nim", "Orin"}

    def test_menos_monstruos_el_jugador_elige_quien_se_libra(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=2,
                       guion={"a_salvo": ["Orin", "Nim"]})
        objetivos = [p.nombre for p in c.repartir_ataques(2)]
        assert sorted(objetivos) == ["Brakk", "Sela"]

    def test_mas_monstruos_todos_uno_y_los_extra_al_odiado(self, juego):
        # Los goblins odian a los enanos: los ataques sobrantes van a por el.
        g = juego.crear_grupo([("Brakk", "guerrero"), ("Thrunn", "enano")],
                              RandomSource(1))
        c, _ = combate(juego, g, "goblins", RandomSource(1), cantidad=4)
        objetivos = [p.nombre for p in c.repartir_ataques(4)]
        assert objetivos.count("Thrunn") == 3 and objetivos.count("Brakk") == 1

    def test_en_pasillo_atacan_dos_a_los_dos_de_cabeza(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=8,
                       sit=Situacion(corredor=True))
        objetivos = [p.nombre for p in c.repartir_ataques(8)]
        assert objetivos == ["Brakk", "Sela"]

    def test_los_errantes_en_pasillo_caen_sobre_la_retaguardia(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=8,
                       sit=Situacion(corredor=True, errante=True))
        assert [p.nombre for p in c.repartir_ataques(8)] == ["Nim", "Orin"]

    def test_a_un_solo_personaje_en_pasillo_le_atacan_dos(self, juego):
        g = juego.crear_grupo([("Solo", "guerrero")], RandomSource(1))
        c, _ = combate(juego, g, "goblins", RandomSource(1), cantidad=5,
                       sit=Situacion(corredor=True))
        assert [p.nombre for p in c.repartir_ataques(5)] == ["Solo", "Solo"]

    def test_un_jefe_reparte_sus_propios_ataques(self, juego, grupo):
        # El Senor del Caos tiene 3 ataques, no 1 por punto de Vida.
        c, _ = combate(juego, grupo, "senor_del_caos", RandomSource(1),
                       guion={"a_salvo": ["Orin"]})
        assert c._numero_de_ataques() == 3


# --------------------------------------------------------------------------- #
# Desarrollo del combate
# --------------------------------------------------------------------------- #


class TestDesarrollo:
    def test_los_errantes_sorprenden_y_pegan_primero(self, juego, grupo):
        c, reg = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=5),
                         cantidad=2, sit=Situacion(errante=True),
                         guion={"salir_del_combate": "luchar"})
        c.resolver()
        assert reg.tipos[1] == "sorpresa"
        assert reg.tipos.index("turno_monstruos") < reg.tipos.index("ataque")

    def test_el_arco_dispara_antes_que_los_monstruos(self, juego):
        g = juego.crear_grupo([("Arq", "guerrero")], RandomSource(1))
        g.miembros[0].equipo.clear()
        g.miembros[0].anadir(juego.objeto("arco"), equipar=True)
        c, reg = combate(juego, g, "goblins", ScriptedRandom([], relleno=5),
                         cantidad=1, sit=Situacion(errante=True))
        c.resolver()
        assert reg.tipos[2] == "arco"

    def test_huir_por_moral_si_deja_saqueo(self, juego, grupo):
        # A diferencia de huir por reaccion: "tira por el tesoro incluso si huyen".
        c, reg = combate(juego, grupo, "goblins", RandomSource(1), cantidad=4)
        c.herir_monstruo(3)                       # quedan 1 de 4: rompen filas
        c.rng = ScriptedRandom([3])               # 3 o menos y huyen
        c._comprobar_moral()
        r = c._fin()
        assert c.enc.huido
        assert r.desenlace == "victoria" and r.botin is True
        # FAQ: "un monstruo que huye cuenta como derrotado" tambien para la XP.
        assert r.xp

    def test_un_jefe_errante_da_xp_pero_no_tesoro(self, juego, grupo):
        # FAQ: "puedes imaginar que dejaron el tesoro a salvo en su guarida",
        # pero si dan derecho a tirada de experiencia.
        c, _ = combate(juego, grupo, "ogro", ScriptedRandom([], relleno=5), vida=1,
                       sit=Situacion(errante=True),
                       guion={"salir_del_combate": "luchar"})
        r = c.resolver()
        assert r.desenlace == "victoria" and r.xp and not r.botin

    def test_no_se_gasta_curacion_si_nadie_esta_herido(self, juego, grupo):
        c, reg = combate(juego, grupo, "goblins", RandomSource(1), cantidad=2)
        sela = grupo.por_nombre("Sela")
        juego.usar_habilidad("curacion", sela, c)
        assert sela.recursos["curacion"] == 3
        assert any("Nadie esta herido" in e.texto for e in reg)

    def test_los_errantes_nunca_dejan_tesoro(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=5),
                       cantidad=1, sit=Situacion(errante=True),
                       guion={"salir_del_combate": "luchar"})
        assert c.resolver().botin is False

    def test_el_jefe_pierde_un_nivel_a_media_vida(self, juego, grupo):
        c, _ = combate(juego, grupo, "ogro", RandomSource(5), vida=6)
        assert c.enc.amenaza.nivel == 5
        c.herir_monstruo(4)
        assert c.enc.amenaza.nivel == 4

    def test_si_cae_todo_el_grupo_es_derrota(self, juego, grupo):
        for p in grupo:
            p.vida = 1
        # Defensas siempre a 1 (fallo natural), ataques del grupo siempre a 1.
        c, _ = combate(juego, grupo, "orcos", ScriptedRandom([], relleno=1),
                       cantidad=8, guion={"abordaje": "atacar_ya",
                                          "salir_del_combate": "luchar"})
        r = c.resolver()
        assert r.desenlace == "derrota" and not r.botin and not grupo.vivos


class TestSalirDelCombate:
    def test_la_retirada_da_mas_uno_a_la_defensa(self, juego, grupo):
        c, reg = combate(juego, grupo, "esqueletos", ScriptedRandom([], relleno=3),
                         cantidad=10, guion={"abordaje": "atacar_ya",
                                             "salir_del_combate": ["luchar", "retirada"]})
        r = c.resolver()
        assert r.desenlace == "retirada" and not r.botin
        defensas = [e for e in reg.de_tipo("defensa") if "retirada ordenada" in e.texto]
        assert defensas

    def test_sin_puerta_no_se_puede_retirar(self, juego, grupo):
        c, _ = combate(juego, grupo, "esqueletos", ScriptedRandom([], relleno=3),
                       cantidad=10, sit=Situacion(puerta=False),
                       guion={"abordaje": "atacar_ya"})
        opciones = None

        class Espia(DecisorGuion):
            def elegir(self, pregunta):
                nonlocal opciones
                if pregunta.id == "salir_del_combate":
                    opciones = pregunta.valores
                return super().elegir(pregunta)

        c.decisor = Espia({"abordaje": "atacar_ya", "salir_del_combate": "luchar"})
        c.resolver()
        assert opciones is not None and "retirada" not in opciones

    def test_al_huir_el_escudo_no_protege(self, juego, grupo):
        c, reg = combate(juego, grupo, "esqueletos", ScriptedRandom([], relleno=3),
                         cantidad=10, guion={"abordaje": "atacar_ya",
                                             "salir_del_combate": ["luchar", "huida"]})
        r = c.resolver()
        assert r.desenlace == "huida"
        defensas = reg.de_tipo("defensa")
        de_huida = [e for e in defensas if "Brakk" in e.texto][-1]
        assert "escudo" not in de_huida.texto


# --------------------------------------------------------------------------- #
# Efectos de hechizos y poderes
# --------------------------------------------------------------------------- #


class TestEfectos:
    def mago(self, juego, grupo):
        return grupo.por_nombre("Orin")

    def test_la_bola_de_fuego_mata_tirada_menos_nivel(self, juego, grupo):
        # Ejemplo del libro: mago nivel 1, tirada 5+1=6, goblins nivel 3 -> 3 muertos.
        c, _ = combate(juego, grupo, "goblins", ScriptedRandom([5], relleno=1),
                       cantidad=8)
        juego.usar_habilidad("bola_de_fuego", self.mago(juego, grupo), c)
        assert c.enc.cantidad == 5

    def test_la_bola_de_fuego_mata_al_menos_a_uno(self, juego, grupo):
        c, _ = combate(juego, grupo, "trolls", ScriptedRandom([1], relleno=1),
                       cantidad=3)
        # Tirada 1+1=2 contra nivel 5: falla, no muere nadie.
        juego.usar_habilidad("bola_de_fuego", self.mago(juego, grupo), c)
        assert c.enc.cantidad == 3

    def test_el_rayo_hace_dos_heridas_a_un_jefe(self, juego, grupo):
        c, _ = combate(juego, grupo, "ogro", ScriptedRandom([6, 1], relleno=1), vida=6)
        juego.usar_habilidad("rayo", self.mago(juego, grupo), c)
        assert c.enc.vida == 4

    def test_dormir_derrota_a_un_jefe_entero(self, juego, grupo):
        c, reg = combate(juego, grupo, "ogro", ScriptedRandom([6, 1], relleno=1), vida=6)
        juego.usar_habilidad("dormir", self.mago(juego, grupo), c)
        assert not c.enc.vivo
        assert any("puede ser atado" in e.texto for e in reg)

    def test_dormir_no_afecta_a_los_muertos_vivientes(self, juego, grupo):
        c, reg = combate(juego, grupo, "esqueletos", ScriptedRandom([], relleno=5),
                         cantidad=5)
        juego.usar_habilidad("dormir", self.mago(juego, grupo), c)
        assert c.enc.cantidad == 5
        assert any("no afecta a los muertos vivientes" in e.texto for e in reg)

    def test_proteger_da_mas_uno_a_la_defensa_del_elegido(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=2)
        c.decisor = DecisorGuion({"proteger": "Brakk"})
        juego.usar_habilidad("proteger", self.mago(juego, grupo), c)
        brakk = grupo.por_nombre("Brakk")
        assert brakk.estado("protegido") is not None
        r = juego.defender(brakk, c.enc.amenaza, ScriptedRandom([3]))
        assert r.bonificacion == 1 + 1 + 1     # armadura, escudo, hechizo

    def test_escapada_saca_al_mago_del_combate(self, juego, grupo):
        c, _ = combate(juego, grupo, "goblins", RandomSource(1), cantidad=2)
        orin = self.mago(juego, grupo)
        juego.usar_habilidad("escapada", orin, c)
        assert orin.fuera_de_combate
        assert orin not in c.vivos and orin in grupo.vivos

    def test_los_efectos_de_combate_se_caen_al_terminar(self, juego, grupo):
        elige_proteger = lambda p: ("habilidad:proteger" if "habilidad:proteger"
                                    in p.valores else "atacar")
        c, _ = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=5),
                       cantidad=1, guion={"abordaje": "atacar_ya",
                                          "accion": elige_proteger,
                                          "proteger": "Brakk"})
        c.resolver()
        assert grupo.por_nombre("Brakk").estado("protegido") is None

    def test_la_curacion_sana_d6_mas_nivel(self, juego, grupo):
        sela = grupo.por_nombre("Sela")
        brakk = grupo.por_nombre("Brakk")
        brakk.herir(5)
        c, _ = combate(juego, grupo, "goblins", ScriptedRandom([4], relleno=1),
                       cantidad=2)
        c.decisor = DecisorGuion({"curacion": "Brakk"})
        juego.usar_habilidad("curacion", sela, c)
        assert brakk.vida == 2 + 5 and sela.recursos["curacion"] == 2

    def test_el_ataque_de_ira_tira_tres_veces_y_hiere_por_dos(self, juego):
        g = juego.crear_grupo([("Krom", "barbaro")], RandomSource(1))
        c, _ = combate(juego, g, "ogro", ScriptedRandom([1, 5, 2], relleno=1), vida=6)
        juego.usar_habilidad("ataque_de_ira", g.miembros[0], c)
        assert c.enc.vida == 4                    # dos heridas de golpe
        assert g.miembros[0].recursos["ira"] == 0

    def test_un_hechizo_preparado_se_gasta_al_lanzarlo(self, juego, grupo):
        orin = self.mago(juego, grupo)
        c, _ = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=5),
                       cantidad=5)
        assert "rayo" in orin.preparados
        juego.usar_habilidad("rayo", orin, c)
        assert "rayo" not in orin.preparados


class TestSuerteDelHalfling:
    def test_repite_una_defensa_fallida(self, juego):
        g = juego.crear_grupo([("Pip", "halfling")], RandomSource(1))
        pip = g.miembros[0]
        # Primera defensa: 2 (falla contra nivel 3). Repeticion: 5 (salva).
        c, reg = combate(juego, g, "goblins", ScriptedRandom([2, 5], relleno=5),
                         cantidad=1, sit=Situacion(errante=True),
                         guion={"suerte": True, "salir_del_combate": "luchar"})
        c._turno_monstruos()
        assert pip.vida == pip.vida_max
        assert pip.recursos["suerte"] == 1
        assert any("gasta un punto de Suerte" in e.texto for e in reg)

    def test_la_repeticion_es_definitiva_aunque_salga_peor(self, juego):
        g = juego.crear_grupo([("Pip", "halfling")], RandomSource(1))
        pip = g.miembros[0]
        c, _ = combate(juego, g, "goblins", ScriptedRandom([2, 1], relleno=1),
                       cantidad=1, guion={"suerte": True})
        c._turno_monstruos()
        assert pip.vida == pip.vida_max - 1

    def test_solo_la_gasta_si_el_jugador_quiere(self, juego):
        g = juego.crear_grupo([("Pip", "halfling")], RandomSource(1))
        c, _ = combate(juego, g, "goblins", ScriptedRandom([1], relleno=1),
                       cantidad=1, guion={"suerte": False})
        c._turno_monstruos()
        assert g.miembros[0].recursos["suerte"] == 2

    def test_los_demas_no_tienen_suerte_que_gastar(self, juego, grupo):
        c, reg = combate(juego, grupo, "goblins", ScriptedRandom([], relleno=1),
                         cantidad=4)
        c._turno_monstruos()
        assert "suerte" not in reg.tipos


def test_una_partida_entera_con_el_decisor_por_defecto(juego, grupo):
    """Humo: el modo automatico basico debe llegar a un desenlace sin romperse."""
    for semilla in range(20):
        g = juego.crear_grupo(
            [("A", "guerrero"), ("B", "clerigo"), ("C", "enano"), ("D", "mago")],
            RandomSource(semilla),
        )
        juego.preparar_hechizos(g.por_nombre("D"), ["bola_de_fuego", "rayo", "dormir"])
        rng = RandomSource(semilla)
        enc = juego.generar_monstruos("esbirros", rng)
        r = juego.combatir(g, enc, rng, decisor=DecisorPorDefecto())
        assert r.desenlace in {"victoria", "derrota", "huida", "retirada", "evitado"}
