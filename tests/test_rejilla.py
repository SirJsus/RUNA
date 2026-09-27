"""Tests del dibujo de la mazmorra en rejilla."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from runa.core.rejilla import (
    Catalogo, Colocacion, Plano, Rejilla, RejillaError, Salida,
)

CATALOGO = "src/runa/games/cco/data/planos.yaml"


@pytest.fixture(scope="module")
def catalogo():
    return Catalogo.desde_yaml(CATALOGO)


def plano(forma, salidas=(), aberturas=(), tipo="habitacion", id="X"):
    return Plano.desde_dict(id, {"forma": forma, "tipo": tipo,
                                 "salidas": list(salidas),
                                 "aberturas": list(aberturas)})


class TestLectura:
    def test_la_forma_se_lee_en_celdas(self):
        p = plano("##\n.#\n")
        assert p.celdas == {(0, 0), (1, 0), (1, 1)}
        assert (p.ancho, p.alto) == (2, 2)

    def test_la_silueta_se_redibuja_igual_que_en_el_yaml(self):
        forma = "###\n.#.\n###"
        assert plano(forma + "\n").dibujo() == forma

    def test_las_aberturas_son_salidas_sin_puerta(self):
        p = plano("#\n", salidas=["0,0,N"], aberturas=["0,0,S"])
        assert [s.puerta for s in p.salidas] == [True, False]

    def test_una_loseta_sin_suelo_se_rechaza(self):
        with pytest.raises(RejillaError, match="ninguna celda"):
            plano("...\n")

    def test_una_salida_fuera_del_suelo_se_rechaza(self):
        with pytest.raises(RejillaError, match="no es una celda de suelo"):
            plano("#\n", salidas=["5,5,N"])

    def test_un_lado_invalido_se_rechaza(self):
        with pytest.raises(RejillaError, match="N, S, E u O"):
            plano("#\n", salidas=["0,0,Z"])


class TestGiro:
    def test_gira_en_sentido_horario(self):
        # La columna de la izquierda pasa a ser la fila de arriba, del reves.
        #   #.        ##
        #   ##   ->   #.
        assert plano("#.\n##\n").girar(1).dibujo() == "##\n#."

    def test_las_salidas_giran_con_la_loseta(self):
        p = plano("#\n", salidas=["0,0,N"])
        assert [s.lado for s in p.girar(1).salidas] == ["E"]
        assert [s.lado for s in p.girar(2).salidas] == ["S"]
        assert [s.lado for s in p.girar(3).salidas] == ["O"]

    def test_cuatro_giros_vuelven_al_original(self, catalogo):
        for p in catalogo.planos.values():
            assert p.girar(4).celdas == p.celdas, p.id
            assert p.girar(4).salidas == p.salidas, p.id

    def test_girar_cambia_ancho_por_alto(self):
        p = plano("###\n###\n")
        assert (p.ancho, p.alto) == (3, 2)
        assert (p.girar(1).ancho, p.girar(1).alto) == (2, 3)


class TestColocacion:
    def sala_suelta(self, r, id=1, origen=(5, 5)):
        r.colocar_primera(id, plano("##\n##\n", salidas=["1,1,S"]), origen=origen)

    def test_encaja_contra_una_salida(self):
        r = Rejilla(12, 12)
        self.sala_suelta(r)
        celda, salida = r.salidas_libres(1)[0]
        assert (celda, salida.lado) == ((6, 6), "S")
        opciones = r.colocaciones(plano("#\n", salidas=["0,0,N"]), celda, "S")
        assert len(opciones) == 1 and opciones[0].origen == (6, 7)

    def test_la_loseta_se_gira_para_que_encaje(self):
        # Una salida al sur sirve para entrar desde el norte: se gira media vuelta.
        r = Rejilla(12, 12)
        self.sala_suelta(r)
        celda, _ = r.salidas_libres(1)[0]
        opciones = r.colocaciones(plano("#\n", salidas=["0,0,S"]), celda, "S")
        assert len(opciones) == 1 and opciones[0].giros == 2

    def test_los_giros_de_una_cruz_cuentan_como_distintos(self, catalogo):
        """Misma silueta, pero las puertas quedan en otros lados."""
        r = Rejilla(20, 20)
        self.sala_suelta(r, origen=(8, 8))
        celda, salida = r.salidas_libres(1)[0]
        opciones = r.colocaciones(catalogo["24"], celda, salida.lado)
        assert len(opciones) > 1
        assert len({o.origen for o in opciones}) < len(opciones)   # misma huella
        lados = {frozenset(s.lado for s in o.plano.salidas) for o in opciones}
        assert len(lados) > 1                                      # otras salidas

    def test_un_cuadrado_girado_no_se_cuenta_dos_veces(self):
        r = Rejilla(12, 12)
        self.sala_suelta(r)
        celda, salida = r.salidas_libres(1)[0]
        # Un cuadrado con una sola puerta al norte: los cuatro giros que la
        # dejan al norte darian el mismo dibujo, asi que solo hay una opcion.
        cuadrado = plano("##\n##\n", salidas=["0,0,N"])
        assert len(r.colocaciones(cuadrado, celda, salida.lado)) == 1

    def test_no_encaja_donde_ya_hay_algo(self):
        r = Rejilla(12, 12)
        self.sala_suelta(r)
        celda, salida = r.salidas_libres(1)[0]
        r.colocar(2, r.colocaciones(plano("#\n", salidas=["0,0,N"]), celda, "S")[0])
        assert r.colocaciones(plano("#\n", salidas=["0,0,N"]), celda, "S") == []

    def test_no_encaja_fuera_de_la_hoja(self):
        r = Rejilla(4, 4)
        r.colocar_primera(1, plano("#\n", salidas=["0,0,S"]), origen=(0, 3))
        assert r.salidas_libres(1) == []          # la puerta da al borde

    def test_las_celdas_quedan_ocupadas(self):
        r = Rejilla(12, 12)
        self.sala_suelta(r)
        assert r.sala_en((5, 5)) == 1 and r.libre((7, 7))
        assert not r.libre((5, 5))


class TestRecorte:
    def test_una_loseta_que_no_cabe_se_corta(self):
        # "Si la tirada crea una estancia que no cabe, corta la habitacion."
        r = Rejilla(6, 6)
        r.colocar_primera(1, plano("##\n##\n", salidas=["0,1,S"]), origen=(0, 3))
        celda, salida = r.salidas_libres(1)[0]
        grande = plano("###\n###\n###\n", salidas=["1,0,N"])
        assert r.colocaciones(grande, celda, salida.lado) == []
        recorte = r.recorte(grande, celda, salida.lado)
        pieza = r.colocar(2, recorte, recortar=True)
        assert pieza.recortada and len(pieza.celdas) < 9

    def test_una_loseta_recortada_es_un_callejon_sin_salida(self):
        r = Rejilla(6, 6)
        r.colocar_primera(1, plano("##\n##\n", salidas=["0,1,S"]), origen=(0, 3))
        celda, salida = r.salidas_libres(1)[0]
        grande = plano("###\n###\n###\n", salidas=["1,0,N", "2,2,E"])
        r.colocar(2, r.recorte(grande, celda, salida.lado), recortar=True)
        assert r.salidas_libres(2) == []

    def test_sin_recortar_se_niega_a_colocar_lo_que_no_cabe(self):
        r = Rejilla(6, 6)
        r.colocar_primera(1, plano("##\n##\n", salidas=["0,1,S"]), origen=(0, 3))
        celda, salida = r.salidas_libres(1)[0]
        grande = plano("###\n###\n###\n", salidas=["1,0,N"])
        with pytest.raises(RejillaError, match="no cabe entera"):
            r.colocar(2, r.recorte(grande, celda, salida.lado))


class TestDibujo:
    def montar(self):
        r = Rejilla(12, 12)
        r.colocar_primera(1, plano("##\n##\n", salidas=["1,1,S"]), origen=(4, 4))
        celda, salida = r.salidas_libres(1)[0]
        opcion = r.colocaciones(plano("##\n", salidas=["0,0,N"]), celda, "S")[0]
        r.colocar(2, opcion)
        vecina = (celda[0], celda[1] + 1)
        return r, {frozenset((celda, vecina))}

    def test_sin_salas_lo_dice(self):
        assert "aun no tiene" in Rejilla().ascii()

    def test_dibuja_muros_y_numeros(self):
        r, puertas = self.montar()
        dibujo = r.ascii(puertas)
        assert "|" in dibujo and "--" in dibujo
        assert " 1" in dibujo and " 2" in dibujo

    def test_una_puerta_abre_el_muro(self):
        r, puertas = self.montar()
        con = r.ascii(puertas).count("--")
        sin = r.ascii().count("--")
        assert con < sin          # la puerta quita un tramo de muro

    def test_marca_las_salidas_por_explorar(self):
        r = Rejilla(12, 12)
        r.colocar_primera(1, plano("##\n", salidas=["0,0,N", "1,0,S"]), origen=(4, 4))
        assert r.ascii().count("**") == 2

    def test_dice_donde_esta_el_grupo(self):
        r, puertas = self.montar()
        assert "esta en la sala 2" in r.ascii(puertas, actual=2)

    def test_el_svg_es_xml_valido(self):
        r, puertas = self.montar()
        raiz = ET.fromstring(r.svg(puertas, actual=1))
        assert raiz.tag.endswith("svg")
        etiquetas = [e.tag.split("}")[-1] for e in raiz.iter()]
        assert "rect" in etiquetas and "line" in etiquetas and "text" in etiquetas

    def test_el_svg_vacio_no_da_nada(self):
        assert Rejilla().svg() == ""


class TestCatalogoDelJuego:
    def test_estan_las_36_losetas_y_las_6_entradas(self, catalogo):
        assert len(catalogo.planos) == 36 and len(catalogo.entradas) == 6
        for a in range(1, 7):
            for b in range(1, 7):
                assert f"{a}{b}" in catalogo.planos

    def test_toda_loseta_tiene_al_menos_una_salida(self, catalogo):
        sin_salida = [p.id for p in catalogo.planos.values() if not p.salidas]
        assert sin_salida == []

    def test_los_corredores_miden_una_celda_de_ancho(self, catalogo):
        """"Cualquier habitacion que tenga solo un cuadrado de ancho es un corredor"."""
        for p in catalogo.planos.values():
            if not p.es_corredor:
                continue
            filas = {y: sum(1 for x, yy in p.celdas if yy == y) for _, y in p.celdas}
            columnas = {x: sum(1 for xx, y in p.celdas if xx == x) for x, _ in p.celdas}
            assert min(filas.values()) == 1 or min(columnas.values()) == 1, p.id

    def test_loseta_inexistente(self, catalogo):
        with pytest.raises(RejillaError, match="99"):
            catalogo["99"]

    def test_entrada_inexistente(self, catalogo):
        with pytest.raises(RejillaError, match="sala de entrada"):
            catalogo.entrada("9")
