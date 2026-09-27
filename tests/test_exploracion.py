"""Tests del bucle de exploracion y de los ganchos de monstruo."""

from __future__ import annotations

import pytest

from runa.core.decisions import DecisorGuion, DecisorPorDefecto
from runa.core.rng import RandomSource
from runa.games.cco.combate import Combate, Situacion
from runa.games.cco.exploracion import Exploracion
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Partida
from tests.test_dice import ScriptedRandom


@pytest.fixture(scope="module")
def juego():
    return Juego()


def montar(juego, semilla=1, guion=None, clases=None, rejilla=False):
    clases = clases or [("Brakk", "guerrero"), ("Sela", "clerigo"),
                        ("Nim", "picaro"), ("Orin", "mago")]
    grupo = juego.crear_grupo(clases, RandomSource(semilla))
    if any(c == "mago" for _, c in clases):
        juego.preparar_hechizos(grupo.por_nombre("Orin"),
                                ["bola_de_fuego", "rayo", "proteger"])
    p = Partida(juego, grupo, semilla=semilla, rejilla=rejilla)
    return p, Exploracion(p, DecisorGuion(guion or {}))


class TestConstruccionEnGrafo:
    """Sin rejilla: el jugador dibuja y solo dice la forma."""

    def test_entrar_crea_la_sala_de_entrada(self, juego):
        p, ex = montar(juego, guion={"plano_tipo": "habitacion", "plano_salidas": 3})
        sala = ex.entrar()
        assert sala.tipo == "entrada" and sala.salidas == 3 and sala.resuelta
        assert p.mapa.actual == sala.id

    def test_abrir_genera_y_conecta_una_sala(self, juego):
        p, ex = montar(juego, guion={"plano_tipo": "corredor", "plano_salidas": 2,
                                     "accion_sala": "buscar"})
        ex.entrar()
        origen = p.mapa.actual
        nueva = ex.abrir(0)
        assert nueva.es_corredor and nueva.plano
        assert p.mapa.actual == nueva.id
        assert origen in nueva.conexiones.values()

    def test_el_corredor_se_vacia_cuando_la_entrada_lo_dice(self, juego):
        p, ex = montar(juego)
        sala = p.mapa.crear("corredor", salidas=2)
        # La entrada 4 dice "si es corredor, vacio".
        ex.rng = ScriptedRandom([2, 2], relleno=3)
        ex.resolver_sala(sala)
        assert "corredor" in sala.contenido and sala.limpia


class TestExperiencia:
    def test_hay_que_superar_el_nivel_no_igualarlo(self, juego):
        p, ex = montar(juego, guion={"xp_personaje": "Brakk"})
        brakk = p.grupo.por_nombre("Brakk")
        p.xp_pendientes = 1
        ex.rng = ScriptedRandom([1])            # 1 no supera el nivel 1
        assert ex.resolver_xp() is False and brakk.nivel == 1
        p.xp_pendientes = 1
        ex.rng = ScriptedRandom([2])            # 2 si lo supera
        assert ex.resolver_xp() is True and brakk.nivel == 2

    def test_no_sube_el_mismo_dos_veces_seguidas(self, juego):
        p, ex = montar(juego)
        p.campana.ultimo_en_subir = "Brakk"
        p.xp_pendientes = 1
        ex.rng = ScriptedRandom([5])
        ex.decisor = DecisorPorDefecto()
        ex.resolver_xp()
        assert p.grupo.por_nombre("Brakk").nivel == 1
        assert p.campana.ultimo_en_subir != "Brakk"

    def test_los_que_estan_al_maximo_no_optan(self, juego):
        p, ex = montar(juego, clases=[("Legolas", "elfo")])
        p.grupo.miembros[0].nivel = 3           # tope del elfo
        p.xp_pendientes = 1
        ex.rng = ScriptedRandom([6, 1])
        assert ex.resolver_xp() is False
        assert p.grupo.miembros[0].nivel == 3

    def test_diez_encuentros_de_esbirros_dan_una_tirada(self, juego):
        p, ex = montar(juego, guion={"xp_personaje": "Brakk"})
        p.aventura.encuentros_esbirros = 10
        ex.rng = ScriptedRandom([3])
        ex._contar_encuentros_de_esbirros()
        assert any("Diez encuentros" in e.texto for e in p.registro)


class TestTrampas:
    def nodo_trampa(self, juego, valor):
        return juego.tablas.tirar("trampas", ScriptedRandom([valor]), encadenar=False)

    def test_el_bloque_de_piedra_va_al_ultimo_de_la_marcha(self, juego):
        p, ex = montar(juego)
        ex.rng = ScriptedRandom([1], relleno=1)   # salvacion fallida
        ex.decisor = DecisorGuion({"desarmar_trampa": ""})
        ex.resolver_trampa(self.nodo_trampa(juego, 6))
        assert p.grupo.por_nombre("Orin").vida == 2      # el ultimo

    def test_la_trampilla_va_al_primero(self, juego):
        p, ex = montar(juego)
        ex.rng = ScriptedRandom([1], relleno=1)
        ex.decisor = DecisorGuion({"desarmar_trampa": ""})
        ex.resolver_trampa(self.nodo_trampa(juego, 3))
        assert p.grupo.por_nombre("Brakk").vida == 6

    def test_el_gas_alcanza_a_todo_el_grupo(self, juego):
        p, ex = montar(juego)
        ex.rng = ScriptedRandom([1], relleno=1)
        ex.decisor = DecisorGuion({"desarmar_trampa": ""})
        ex.resolver_trampa(self.nodo_trampa(juego, 2))
        assert all(x.herido for x in p.grupo.vivos)

    def test_un_picaro_puede_desarmarla(self, juego):
        p, ex = montar(juego)
        ex.rng = ScriptedRandom([5], relleno=1)   # el picaro acierta
        ex.decisor = DecisorGuion({"desarmar_trampa": "Nim"})
        ex.resolver_trampa(self.nodo_trampa(juego, 2))
        assert not any(x.herido for x in p.grupo.vivos)


class TestRepartoDeBotin:
    def test_el_enano_siempre_recibe_al_menos_una_moneda(self, juego):
        from runa.games.cco.juego import Botin
        p, ex = montar(juego, clases=[("A", "guerrero"), ("B", "guerrero"),
                                      ("Thrunn", "enano")])
        for x in p.grupo:
            x.oro = 0
        ex._repartir(Botin(oro=1, notas=["1 de oro"]))
        assert p.grupo.por_nombre("Thrunn").oro == 1

    def test_el_oro_se_reparte_entre_los_vivos(self, juego):
        from runa.games.cco.juego import Botin
        p, ex = montar(juego)
        for x in p.grupo:
            x.oro = 0
        p.grupo.por_nombre("Orin").herir(99)
        ex._repartir(Botin(oro=9, notas=["9 de oro"]))
        assert p.grupo.oro == 9
        assert p.grupo.por_nombre("Orin").oro == 0

    def test_al_barbaro_no_se_le_ofrece_un_objeto_magico(self, juego):
        from runa.games.cco.juego import Botin
        p, ex = montar(juego, clases=[("Krom", "barbaro"), ("Sela", "clerigo")])
        candidatos = []

        class Espia(DecisorGuion):
            def elegir(self, pregunta):
                if pregunta.id == "asignar_tesoro":
                    candidatos.extend(pregunta.valores)
                return super().elegir(pregunta)

        ex.decisor = Espia({})
        ex._repartir(Botin(objetos=[juego.objeto("pocion_curacion")], notas=["pocion"]))
        assert candidatos == ["Sela"]


class TestBusqueda:
    def test_solo_se_puede_buscar_una_vez(self, juego):
        p, ex = montar(juego)
        sala = p.mapa.crear("habitacion", salidas=2)
        ex.rng = ScriptedRandom([3], relleno=3)
        ex.buscar()
        assert sala.buscada
        ex.buscar()
        assert any("ya se registro" in e.texto for e in p.registro)

    def test_en_pasillo_se_busca_a_menos_uno(self, juego):
        p, ex = montar(juego)
        p.mapa.crear("corredor", salidas=2)
        # Un 2 en corredor queda en 1: monstruos errantes.
        ex.rng = ScriptedRandom([2], relleno=1)
        ex.decisor = DecisorGuion({"salir_del_combate": "luchar"})
        ex.buscar()
        assert any("errantes" in e.tipo for e in p.registro)

    def test_tres_pistas_dan_un_secreto_y_una_tirada_de_xp(self, juego):
        p, ex = montar(juego, guion={"pista": "Nim", "xp_personaje": "Nim"})
        p.campana.pistas["Nim"] = 2
        ex.rng = ScriptedRandom([5], relleno=5)
        ex._pista()
        assert any("gran secreto" in e.texto for e in p.registro)
        assert p.campana.pistas["Nim"] == 0


class TestGanchosDeMonstruo:
    def combate(self, juego, grupo, monstruo, rng, **kw):
        enc = juego.bestiario[monstruo].generar(RandomSource(0))
        for k, v in kw.items():
            setattr(enc, k, v)
        return Combate(juego, grupo, enc, rng, decisor=DecisorPorDefecto()), enc

    def test_los_trolls_se_regeneran_con_cinco_o_seis(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "trolls", ScriptedRandom([5, 2]),
                              cantidad=1, cantidad_inicial=3)
        gancho = juego.ganchos.turno["trolls"]
        gancho(c, enc)
        assert enc.cantidad == 2          # de los 2 caidos, uno se levanta

    def test_los_trolls_intactos_no_regeneran(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "trolls", ScriptedRandom([5]),
                              cantidad=3, cantidad_inicial=3)
        assert juego.ganchos.turno["trolls"](c, enc) is False
        assert enc.cantidad == 3

    def test_el_aliento_del_dragon_sustituye_a_sus_ataques(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "dragon_pequeno",
                              ScriptedRandom([1], relleno=1))
        assert juego.ganchos.turno["dragon_pequeno"](c, enc) is True
        assert all(x.herido for x in p.grupo.vivos)

    def test_con_tres_o_mas_el_dragon_muerde_en_vez_de_exhalar(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "dragon_pequeno", ScriptedRandom([4]))
        assert juego.ganchos.turno["dragon_pequeno"](c, enc) is False

    def test_medio_nivel_contra_el_aliento_del_dragon(self, juego):
        p, _ = montar(juego)
        brakk = p.grupo.por_nombre("Brakk")
        brakk.nivel = 4
        r = juego.tirar("salvacion", brakk, ScriptedRandom([3]),
                        amenaza=juego.amenaza("Aliento", 6, ["fuego"]),
                        etiquetas={"aliento_de_dragon"})
        assert r.bonificacion == 2

    def test_la_medusa_petrifica_al_empezar(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "medusa", ScriptedRandom([1], relleno=1))
        juego.ganchos.antes["medusa"](c, enc)
        assert all(x.estado("petrificado") for x in p.grupo.miembros)

    def test_el_senor_del_caos_puede_no_tener_poderes(self, juego):
        p, _ = montar(juego)
        c, enc = self.combate(juego, p.grupo, "senor_del_caos", ScriptedRandom([2]))
        juego.ganchos.antes["senor_del_caos"](c, enc)
        assert any("no tiene poderes" in e.texto for e in c.reg)


def test_el_dragon_nunca_sale_como_monstruo_errante(juego):
    """"Si sale un Dragon, vuelve a tirar": los dragones no vagan."""
    for semilla in range(40):
        p, ex = montar(juego, semilla=semilla,
                       guion={"salir_del_combate": "luchar", "abordaje": "atacar_ya"})
        p.mapa.crear("habitacion", salidas=2)
        ex._monstruos_errantes()
        assert not any("Dragon" in e.texto for e in p.registro
                       if e.tipo == "combate_inicio")


@pytest.mark.parametrize("rejilla", [False, True], ids=["grafo", "rejilla"])
def test_una_aventura_entera_no_se_rompe(juego, rejilla):
    """Humo: diez semillas jugadas de principio a fin, en los dos modos."""
    for semilla in range(10):
        grupo = juego.crear_grupo(
            [("A", "guerrero"), ("B", "clerigo"), ("C", "enano"), ("D", "mago")],
            RandomSource(semilla),
        )
        juego.preparar_hechizos(grupo.por_nombre("D"), ["bola_de_fuego", "rayo", "dormir"])
        p = Partida(juego, grupo, semilla=semilla, rejilla=rejilla)
        Exploracion(p, DecisorPorDefecto()).jugar(limite=30)
        assert len(p.mapa) >= 1
        assert p.campana.aventuras_jugadas == 1
        if rejilla:
            # Ninguna sala pisa a otra: la hoja es coherente.
            celdas = [c for pieza in p.mapa.rejilla for c in pieza.celdas]
            assert len(celdas) == len(set(celdas))
