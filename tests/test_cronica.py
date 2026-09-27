"""Tests de la cronica en Markdown."""

from __future__ import annotations

import pytest

from runa.core.cronica import Cronista, Estilo, escapar_celda, tabla
from runa.core.events import Registro
from runa.core.rng import RandomSource
from runa.games.cco import cronica
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Partida


class TestFormateador:
    def cronista(self):
        return Cronista({
            "sala": Estilo("seccion", "🚪", nivel=3),
            "combate": Estilo("escena", "⚔"),
            "ataque": Estilo("detalle"),
            "botin": Estilo("destacado", "💰"),
            "ruido": Estilo("omitir"),
        })

    def registro(self, *pares):
        r = Registro()
        for tipo, texto in pares:
            r.anotar(tipo, texto)
        return r

    def test_una_seccion_abre_un_encabezado(self):
        md = self.cronista().markdown(self.registro(("sala", "Sala 1")))
        assert md.startswith("### 🚪 Sala 1")

    def test_las_tiradas_van_plegadas(self):
        md = self.cronista().markdown(
            self.registro(("ataque", "d6[5] = 5"), ("nota", "Cae un goblin.")))
        assert "<details>" in md and "d6[5] = 5" in md
        # Y lo narrativo queda fuera del pliegue.
        assert md.index("</details>") < md.index("Cae un goblin.")

    def test_varias_tiradas_seguidas_van_en_un_solo_pliegue(self):
        md = self.cronista().markdown(
            self.registro(("ataque", "uno"), ("ataque", "dos"), ("ataque", "tres")))
        assert md.count("<details>") == 1

    def test_lo_destacado_se_cita(self):
        md = self.cronista().markdown(self.registro(("botin", "25 de oro")))
        assert md == "> 💰 25 de oro"

    def test_las_escenas_van_en_negrita(self):
        md = self.cronista().markdown(self.registro(("combate", "Aparecen goblins")))
        assert md == "**⚔ Aparecen goblins**"

    def test_lo_omitido_no_aparece(self):
        md = self.cronista().markdown(
            self.registro(("ruido", "El grupo vuelve a la sala 1."), ("nota", "Algo")))
        assert "vuelve a la sala" not in md and "Algo" in md

    def test_los_eventos_desconocidos_salen_como_lineas(self):
        md = self.cronista().markdown(self.registro(("sin_estilo", "Un texto")))
        assert md == "Un texto"

    def test_un_registro_vacio_no_da_nada(self):
        assert self.cronista().markdown(Registro()) == ""

    def test_formato_invalido_se_rechaza(self):
        with pytest.raises(ValueError, match="formato"):
            Estilo("inventado")


class TestTablas:
    def test_estructura(self):
        md = tabla(["A", "B"], [[1, 2], [3, 4]])
        assert md.splitlines() == ["| A | B |", "|---|---|", "| 1 | 2 |", "| 3 | 4 |"]

    def test_una_barra_en_un_nombre_no_rompe_la_tabla(self):
        assert escapar_celda("Bra|kk") == "Bra\\|kk"
        assert "Bra\\|kk" in tabla(["N"], [["Bra|kk"]])


@pytest.fixture(scope="module")
def juego():
    return Juego()


@pytest.fixture
def partida(juego):
    grupo = juego.crear_grupo(
        [("Brakk", "guerrero"), ("Orin", "mago")], RandomSource(3))
    p = Partida(juego, grupo, semilla=3, nombre="prueba")
    sala = p.mapa.crear("entrada", salidas=2, plano="4")
    sala.contenido = "Entrada de la mazmorra."
    sala.buscada = True
    p.anotar("entrada", "Sala 1: entrada (plano 4)")
    p.anotar("contenido", "Bichos y alimanas.")
    p.anotar("ataque", "Ataque de Brakk\n  d6[5]\n  = 5 vs 3 -> EXITO")
    p.anotar("dano", "Cae 1 rata.")
    p.anotar("botin", "Botin: 12 de oro")
    p.anotar("muerte", "Orin cae y no vuelve a levantarse.")
    p.anotar("fin", "El grupo sale de la mazmorra.")
    return p


class TestDocumentoCompleto:
    def test_tiene_todas_las_secciones(self, partida):
        md = cronica.escribir(partida)
        for encabezado in ("# Cronica de prueba", "## El grupo al terminar",
                           "## La cronica", "## La mazmorra recorrida", "## Resumen"):
            assert encabezado in md, encabezado

    def test_la_tabla_del_grupo_lista_a_todos(self, partida):
        md = cronica.escribir(partida)
        assert "| Brakk | Guerrero | 1 |" in md
        assert "| Orin | Mago | 1 |" in md

    def test_marca_a_los_muertos(self, partida):
        partida.grupo.por_nombre("Orin").herir(99)
        md = cronica.escribir(partida)
        assert "muerto" in md and "| Caidos | Orin |" in md

    def test_las_tiradas_estan_pero_plegadas(self, partida):
        md = cronica.escribir(partida)
        assert "<details>" in md and "d6[5]" in md

    def test_el_botin_y_la_muerte_se_destacan(self, partida):
        md = cronica.escribir(partida)
        assert "> 💰 Botin: 12 de oro" in md
        assert "> ☠ Orin cae y no vuelve a levantarse." in md

    def test_el_titulo_se_puede_cambiar(self, partida):
        assert cronica.escribir(partida, "Las minas de Moria").startswith(
            "# Las minas de Moria")

    def test_una_partida_sin_eventos_no_revienta(self, juego):
        vacia = Partida(juego, juego.crear_grupo([("A", "elfo")], RandomSource(1)),
                        semilla=1, nombre="vacia")
        md = cronica.escribir(vacia)
        assert "No paso nada digno de mencion" in md

    def test_se_puede_reconstruir_desde_una_partida_guardada(self, partida, tmp_path,
                                                             juego):
        ruta = partida.guardar(tmp_path / "p.json")
        copia = Partida.cargar(ruta, juego)
        # La cronica sobrevive al guardado, que es lo que permite exportarla luego.
        assert cronica.escribir(copia) == cronica.escribir(partida)


class TestExportacionDesdeLaCli:
    def test_exportar_escribe_el_archivo(self, tmp_path, monkeypatch, capsys):
        from runa.apps.cli.main import main
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "9", "--nombre", "cli", "--aventuras", "1"])
        capsys.readouterr()
        destino = tmp_path / "fuera.md"
        assert main(["--exportar", str(destino),
                     str(tmp_path / "partidas" / "cli.json")]) == 0
        assert destino.exists() and destino.read_text(encoding="utf-8").startswith("# ")

    def test_la_partida_escribe_su_cronica_al_terminar(self, tmp_path, monkeypatch):
        from runa.apps.cli.main import main
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "9", "--nombre", "cli", "--aventuras", "1"])
        assert (tmp_path / "partidas" / "cli.md").exists()

    def test_sin_cronica_no_escribe_el_md(self, tmp_path, monkeypatch):
        from runa.apps.cli.main import main
        monkeypatch.chdir(tmp_path)
        main(["--auto", "--semilla", "9", "--nombre", "cli", "--aventuras", "1",
              "--sin-cronica"])
        assert not (tmp_path / "partidas" / "cli.md").exists()

    def test_exportar_sin_partida_avisa(self, tmp_path, monkeypatch, capsys):
        from runa.apps.cli.main import main
        monkeypatch.chdir(tmp_path)
        assert main(["--auto", "--exportar", "x.md"]) == 1
        assert "necesita una partida guardada" in capsys.readouterr().out
