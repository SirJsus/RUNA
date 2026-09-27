"""Dibujo de la mazmorra sobre una cuadricula.

Es una capa **encima** del grafo de salas, no un sustituto: el grafo sigue
diciendo que conecta con que, y esto le anade geometria (que forma tiene cada
loseta, donde cae en la hoja y hacia donde miran sus puertas).

El motor no sabe que losetas existen: el catalogo llega desde los datos del
juego.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

# Un lado y hacia donde apunta. La y crece hacia abajo, como en la hoja.
LADOS: dict[str, tuple[int, int]] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "O": (-1, 0)}
OPUESTO = {"N": "S", "S": "N", "E": "O", "O": "E"}
_AL_GIRAR = {"N": "E", "E": "S", "S": "O", "O": "N"}   # un cuarto en sentido horario

# La hoja que recomienda el reglamento.
ANCHO_HOJA, ALTO_HOJA = 20, 28

Celda = tuple[int, int]


class RejillaError(ValueError):
    """Loseta mal definida o imposible de colocar."""


@dataclass(frozen=True)
class Salida:
    celda: Celda
    lado: str
    puerta: bool = True

    @property
    def vector(self) -> Celda:
        return LADOS[self.lado]

    def __str__(self) -> str:
        return f"{self.celda[0]},{self.celda[1]},{self.lado}"

    @classmethod
    def desde_texto(cls, texto: str, puerta: bool = True) -> "Salida":
        try:
            x, y, lado = (t.strip() for t in texto.split(","))
            if lado.upper() not in LADOS:
                raise ValueError
            return cls((int(x), int(y)), lado.upper(), puerta)
        except ValueError:
            raise RejillaError(
                f"salida {texto!r} mal escrita: se espera \"x,y,lado\" "
                "con lado N, S, E u O"
            ) from None


@dataclass(frozen=True)
class Plano:
    """Una loseta: su silueta en celdas y por donde se sale de ella."""

    id: str
    tipo: str = "habitacion"
    celdas: frozenset[Celda] = frozenset()
    salidas: tuple[Salida, ...] = ()
    notas: str = ""
    giros: int = 0                  # cuartos de vuelta ya aplicados

    @property
    def ancho(self) -> int:
        return max((x for x, _ in self.celdas), default=-1) + 1

    @property
    def alto(self) -> int:
        return max((y for _, y in self.celdas), default=-1) + 1

    def girar(self, cuartos: int = 1) -> "Plano":
        """Gira la loseta en cuartos de vuelta, en sentido horario."""
        cuartos %= 4
        if cuartos == 0 or not self.celdas:
            return self
        plano = self
        for _ in range(cuartos):
            alto = plano.alto
            plano = Plano(
                id=plano.id, tipo=plano.tipo,
                celdas=frozenset((alto - 1 - y, x) for x, y in plano.celdas),
                salidas=tuple(
                    Salida((alto - 1 - s.celda[1], s.celda[0]),
                           _AL_GIRAR[s.lado], s.puerta)
                    for s in plano.salidas
                ),
                notas=plano.notas, giros=(plano.giros + 1) % 4,
            )
        return plano

    @property
    def es_corredor(self) -> bool:
        return self.tipo == "corredor"

    def dibujo(self) -> str:
        """La silueta en el mismo formato del YAML, para cotejar una transcripcion."""
        return "\n".join(
            "".join("#" if (x, y) in self.celdas else "." for x in range(self.ancho))
            for y in range(self.alto)
        )

    @classmethod
    def desde_dict(cls, id: str, bruto: dict[str, Any]) -> "Plano":
        forma = str(bruto.get("forma") or "")
        celdas = {
            (x, y)
            for y, fila in enumerate(forma.rstrip("\n").split("\n"))
            for x, c in enumerate(fila)
            if c == "#"
        }
        if not celdas:
            raise RejillaError(f"la loseta {id!r} no tiene ninguna celda de suelo")
        salidas = [Salida.desde_texto(t, True) for t in bruto.get("salidas") or []]
        salidas += [Salida.desde_texto(t, False) for t in bruto.get("aberturas") or []]
        for s in salidas:
            if s.celda not in celdas:
                raise RejillaError(
                    f"la loseta {id!r} tiene una salida en {s.celda}, "
                    "que no es una celda de suelo"
                )
        return cls(id=id, tipo=str(bruto.get("tipo", "habitacion")),
                   celdas=frozenset(celdas), salidas=tuple(salidas),
                   notas=str(bruto.get("notas", "")))


class Catalogo:
    """Las losetas de un juego, cargadas de su YAML."""

    def __init__(self, planos: dict[str, Plano] | None = None,
                 entradas: dict[str, Plano] | None = None) -> None:
        self.planos = dict(planos or {})
        self.entradas = dict(entradas or {})

    def __getitem__(self, id: str) -> Plano:
        id = str(id)
        if id in self.planos:
            return self.planos[id]
        if id in self.entradas:
            return self.entradas[id]
        raise RejillaError(f"no existe la loseta {id!r}")

    def __contains__(self, id: str) -> bool:
        return str(id) in self.planos or str(id) in self.entradas

    def __len__(self) -> int:
        return len(self.planos) + len(self.entradas)

    def entrada(self, id: str) -> Plano:
        try:
            return self.entradas[str(id)]
        except KeyError:
            raise RejillaError(f"no existe la sala de entrada {id!r}") from None

    @classmethod
    def desde_yaml(cls, ruta: Path | str) -> "Catalogo":
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
        return cls(
            planos={k: Plano.desde_dict(k, v)
                    for k, v in (datos.get("habitaciones") or {}).items()},
            entradas={k: Plano.desde_dict(k, v)
                      for k, v in (datos.get("entradas") or {}).items()},
        )


@dataclass
class Pieza:
    """Una loseta ya colocada en la hoja."""

    sala: int
    plano: Plano
    origen: Celda
    celdas: frozenset[Celda] = frozenset()
    recortada: bool = False

    def __post_init__(self) -> None:
        if not self.celdas:
            self.celdas = frozenset(self.mundo(c) for c in self.plano.celdas)

    def mundo(self, celda: Celda) -> Celda:
        return (self.origen[0] + celda[0], self.origen[1] + celda[1])

    def salidas_mundo(self) -> list[tuple[Celda, Salida]]:
        """Las salidas que sobrevivieron al recorte, en coordenadas de hoja."""
        return [(self.mundo(s.celda), s) for s in self.plano.salidas
                if self.mundo(s.celda) in self.celdas]


@dataclass(frozen=True)
class Colocacion:
    """Una forma concreta de encajar una loseta contra una salida."""

    plano: Plano                # ya girado
    origen: Celda
    salida: Salida              # la salida del plano que hace de entrada
    giros: int

    @property
    def celdas(self) -> set[Celda]:
        return {(self.origen[0] + x, self.origen[1] + y) for x, y in self.plano.celdas}

    def descripcion(self) -> str:
        vueltas = {0: "sin girar", 1: "girada 90°", 2: "girada 180°", 3: "girada 270°"}
        return (f"{vueltas[self.giros]}, entrando por su lado "
                f"{self.salida.lado} en ({self.origen[0]}, {self.origen[1]})")


class Rejilla:
    """La hoja de papel: qué celda ocupa cada sala."""

    def __init__(self, ancho: int = ANCHO_HOJA, alto: int = ALTO_HOJA) -> None:
        self.ancho = ancho
        self.alto = alto
        self.piezas: dict[int, Pieza] = {}
        self.ocupadas: dict[Celda, int] = {}

    # -- consulta ------------------------------------------------------------ #

    def dentro(self, celda: Celda) -> bool:
        x, y = celda
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def libre(self, celda: Celda) -> bool:
        return self.dentro(celda) and celda not in self.ocupadas

    def sala_en(self, celda: Celda) -> int | None:
        return self.ocupadas.get(celda)

    def __len__(self) -> int:
        return len(self.piezas)

    def __iter__(self) -> Iterator[Pieza]:
        return iter(self.piezas.values())

    @property
    def usado(self) -> tuple[int, int, int, int] | None:
        """El rectangulo que ocupa lo dibujado: (x0, y0, x1, y1)."""
        if not self.ocupadas:
            return None
        xs = [x for x, _ in self.ocupadas]
        ys = [y for _, y in self.ocupadas]
        return min(xs), min(ys), max(xs), max(ys)

    # -- colocacion ----------------------------------------------------------- #

    def colocaciones(
        self, plano: Plano, desde: Celda, lado: str
    ) -> list[Colocacion]:
        """Todas las formas de encajar `plano` saliendo de `desde` hacia `lado`.

        La loseta nueva tiene que tener una salida en el lado contrario, y caer
        justo en la celda de al lado.
        """
        destino = (desde[0] + LADOS[lado][0], desde[1] + LADOS[lado][1])
        entra_por = OPUESTO[lado]
        encontradas: list[Colocacion] = []
        vistas: set[tuple] = set()
        for giros in range(4):
            girado = plano.girar(giros)
            for salida in girado.salidas:
                if salida.lado != entra_por:
                    continue
                origen = (destino[0] - salida.celda[0], destino[1] - salida.celda[1])
                huella = frozenset((origen[0] + x, origen[1] + y)
                                   for x, y in girado.celdas)
                # Dos giros solo repiten si dejan la misma silueta Y las mismas
                # puertas: un cuadrado girado es el mismo dibujo, pero una cruz
                # girada tiene las salidas en otros lados.
                puertas = frozenset(
                    (origen[0] + s.celda[0], origen[1] + s.celda[1], s.lado)
                    for s in girado.salidas
                )
                if (origen, huella, puertas) in vistas:
                    continue
                vistas.add((origen, huella, puertas))
                if all(self.libre(c) for c in huella):
                    encontradas.append(Colocacion(girado, origen, salida, giros))
        return encontradas

    def recorte(self, plano: Plano, desde: Celda, lado: str) -> Colocacion | None:
        """El mejor encaje parcial cuando la loseta entera no cabe.

        "Si la tirada crea una estancia que no cabe, corta la habitacion: es un
        callejon sin salida. Todavia cuenta como sala o corredor."
        """
        destino = (desde[0] + LADOS[lado][0], desde[1] + LADOS[lado][1])
        if not self.libre(destino):
            return None
        entra_por = OPUESTO[lado]
        mejor: Colocacion | None = None
        mejores_celdas = 0
        for giros in range(4):
            girado = plano.girar(giros)
            for salida in girado.salidas:
                if salida.lado != entra_por:
                    continue
                origen = (destino[0] - salida.celda[0], destino[1] - salida.celda[1])
                cabidas = sum(
                    1 for x, y in girado.celdas
                    if self.libre((origen[0] + x, origen[1] + y))
                )
                if cabidas > mejores_celdas:
                    mejor, mejores_celdas = Colocacion(girado, origen, salida, giros), cabidas
        return mejor

    def colocar(self, sala: int, colocacion: Colocacion,
                recortar: bool = False) -> Pieza:
        celdas = {c for c in colocacion.celdas if self.libre(c)}
        completa = celdas == colocacion.celdas
        if not completa and not recortar:
            raise RejillaError(
                f"la loseta {colocacion.plano.id} no cabe entera en "
                f"{colocacion.origen}"
            )
        if not celdas:
            raise RejillaError(f"la loseta {colocacion.plano.id} no cabe en absoluto")
        pieza = Pieza(sala=sala, plano=colocacion.plano, origen=colocacion.origen,
                      celdas=frozenset(celdas), recortada=not completa)
        self.piezas[sala] = pieza
        for celda in celdas:
            self.ocupadas[celda] = sala
        return pieza

    def colocar_primera(self, sala: int, plano: Plano,
                        origen: Celda | None = None) -> Pieza:
        """La entrada: "dibuja esta entrada en el centro del borde inferior"."""
        if origen is None:
            origen = ((self.ancho - plano.ancho) // 2, self.alto - plano.alto)
        return self.colocar(sala, Colocacion(plano, origen, plano.salidas[0]
                                             if plano.salidas else
                                             Salida((0, 0), "N"), 0))

    def reconstruir(self, salas: Iterable[Any], catalogo: "Catalogo") -> "Rejilla":
        """Rehace la hoja a partir de las salas guardadas.

        No se guarda la rejilla: se guarda, en cada sala, que loseta es, donde
        cae y cuanto gira. Replicar la colocacion en orden de id devuelve
        exactamente el mismo dibujo, y ademas un arreglo en una loseta alcanza a
        las partidas ya empezadas.
        """
        for sala in sorted(salas, key=lambda s: s.id):
            if sala.origen is None or not sala.plano:
                continue
            plano = catalogo[sala.plano].girar(sala.giros)
            entrada = plano.salidas[0] if plano.salidas else Salida((0, 0), "N")
            self.colocar(sala.id, Colocacion(plano, tuple(sala.origen), entrada,
                                             sala.giros), recortar=True)
        return self

    def salidas_libres(self, sala: int) -> list[tuple[Celda, Salida]]:
        """Salidas de una sala que no dan a otra sala ni al borde de la hoja."""
        pieza = self.piezas.get(sala)
        if pieza is None:
            return []
        if pieza.recortada:
            # "corta la habitacion: es un callejon sin salida."
            return []
        libres = []
        for celda, salida in pieza.salidas_mundo():
            vecina = (celda[0] + salida.vector[0], celda[1] + salida.vector[1])
            if self.libre(vecina):
                libres.append((celda, salida))
        return libres

    # -- dibujo --------------------------------------------------------------- #

    def _lados_de(self, celda: Celda, sala: int,
                  puertas: set[frozenset]) -> dict[str, str]:
        """Qué hay en cada lado de una celda: muro, paso o nada."""
        lados = {}
        for lado, (dx, dy) in LADOS.items():
            vecina = (celda[0] + dx, celda[1] + dy)
            otra = self.ocupadas.get(vecina)
            if otra == sala:
                lados[lado] = "nada"           # misma sala: no hay muro dentro
            elif otra is not None:
                lados[lado] = ("paso" if frozenset((celda, vecina)) in puertas
                               else "muro")
            else:
                lados[lado] = "muro"
        return lados

    def _anclas(self) -> dict[int, Celda]:
        """La celda donde se escribe el numero de cada sala: la de mas arriba."""
        anclas: dict[int, Celda] = {}
        for celda, sala in sorted(self.ocupadas.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            anclas.setdefault(sala, celda)
        return anclas

    def _pendientes(self) -> dict[tuple[Celda, str], bool]:
        return {(celda, salida.lado): salida.puerta
                for sala in self.piezas
                for celda, salida in self.salidas_libres(sala)}

    def ascii(self, puertas: Iterable[frozenset] = (), actual: int | None = None,
              margen: int = 0) -> str:
        """Dibuja la mazmorra en texto, recortada a lo que ocupa.

        Leyenda: `--` y `|` son muros, un hueco es un paso entre salas y `*` una
        salida por explorar. El numero de cada sala va en su esquina superior.
        """
        marco = self.usado
        if marco is None:
            return "(la mazmorra aun no tiene ninguna sala)"
        puertas = set(puertas)
        pendientes = self._pendientes()
        anclas = self._anclas()
        x0, y0, x1, y1 = marco
        x0, y0 = max(0, x0 - margen), max(0, y0 - margen)
        x1, y1 = min(self.ancho - 1, x1 + margen), min(self.alto - 1, y1 + margen)

        cols, filas = 3 * (x1 - x0 + 1) + 1, 2 * (y1 - y0 + 1) + 1
        lienzo = [[" "] * cols for _ in range(filas)]

        def escribir(fila: int, col: int, texto: str) -> None:
            for i, c in enumerate(texto):
                if 0 <= fila < filas and 0 <= col + i < cols:
                    lienzo[fila][col + i] = c

        for (cx, cy), sala in self.ocupadas.items():
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            f, c = 2 * (cy - y0) + 1, 3 * (cx - x0) + 1
            lados = self._lados_de((cx, cy), sala, puertas)
            for esquina in ((f - 1, c - 1), (f - 1, c + 2), (f + 1, c - 1), (f + 1, c + 2)):
                escribir(*esquina, "+")
            arriba = pendientes.get(((cx, cy), "N"))
            abajo = pendientes.get(((cx, cy), "S"))
            izq = pendientes.get(((cx, cy), "O"))
            der = pendientes.get(((cx, cy), "E"))
            if lados["N"] == "muro":
                escribir(f - 1, c, "**" if arriba is not None else "--")
            if lados["S"] == "muro":
                escribir(f + 1, c, "**" if abajo is not None else "--")
            if lados["O"] == "muro":
                escribir(f, c - 1, "*" if izq is not None else "|")
            if lados["E"] == "muro":
                escribir(f, c + 2, "*" if der is not None else "|")
            if anclas.get(sala) == (cx, cy):
                marca = f"{sala:>2}"
                escribir(f, c, marca[-2:])

        dibujo = "\n".join("".join(fila).rstrip() for fila in lienzo)
        if actual is not None and actual in self.piezas:
            dibujo += f"\n\nEl grupo esta en la sala {actual}."
        return dibujo

    def svg(self, puertas: Iterable[frozenset] = (), actual: int | None = None,
            lado: int = 22, margen: int = 1) -> str:
        """El mismo mapa en SVG, para la cronica."""
        marco = self.usado
        if marco is None:
            return ""
        puertas = set(puertas)
        pendientes = self._pendientes()
        anclas = self._anclas()
        x0, y0, x1, y1 = marco
        x0, y0 = x0 - margen, y0 - margen
        x1, y1 = x1 + margen, y1 + margen
        ancho, alto = (x1 - x0 + 1) * lado, (y1 - y0 + 1) * lado

        def px(celda: Celda) -> tuple[int, int]:
            return (celda[0] - x0) * lado, (celda[1] - y0) * lado

        partes = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
            f'width="{ancho}" height="{alto}" role="img" '
            f'aria-label="Plano de la mazmorra">',
            f'<rect width="{ancho}" height="{alto}" fill="#f4f1ea"/>',
            '<g stroke="#d8d2c4" stroke-width="0.5">',
        ]
        for i in range(x1 - x0 + 2):        # la cuadricula de la hoja
            partes.append(f'<line x1="{i*lado}" y1="0" x2="{i*lado}" y2="{alto}"/>')
        for j in range(y1 - y0 + 2):
            partes.append(f'<line x1="0" y1="{j*lado}" x2="{ancho}" y2="{j*lado}"/>')
        partes.append("</g>")

        for celda, sala in sorted(self.ocupadas.items()):
            x, y = px(celda)
            relleno = "#ffffff" if sala != actual else "#fff3c4"
            partes.append(f'<rect x="{x}" y="{y}" width="{lado}" height="{lado}" '
                          f'fill="{relleno}"/>')

        partes.append('<g stroke="#2b2b2b" stroke-width="3" stroke-linecap="square">')
        for celda, sala in sorted(self.ocupadas.items()):
            x, y = px(celda)
            lados = self._lados_de(celda, sala, puertas)
            bordes = {
                "N": (x, y, x + lado, y), "S": (x, y + lado, x + lado, y + lado),
                "O": (x, y, x, y + lado), "E": (x + lado, y, x + lado, y + lado),
            }
            for lado_id, estado in lados.items():
                if estado == "muro":
                    a, b, c, d = bordes[lado_id]
                    partes.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}"/>')
        partes.append("</g>")

        # Las salidas por explorar, como el libro dibuja las puertas.
        partes.append('<g fill="#ffffff" stroke="#2b2b2b" stroke-width="2">')
        for (celda, lado_id), es_puerta in pendientes.items():
            if not es_puerta:
                continue
            x, y = px(celda)
            grosor, largo = lado // 4, lado // 2
            sitios = {
                "N": (x + (lado - largo) // 2, y - grosor // 2, largo, grosor),
                "S": (x + (lado - largo) // 2, y + lado - grosor // 2, largo, grosor),
                "O": (x - grosor // 2, y + (lado - largo) // 2, grosor, largo),
                "E": (x + lado - grosor // 2, y + (lado - largo) // 2, grosor, largo),
            }
            a, b, w, h = sitios[lado_id]
            partes.append(f'<rect x="{a}" y="{b}" width="{w}" height="{h}" rx="1"/>')
        partes.append("</g>")

        for sala, celda in sorted(anclas.items()):
            x, y = px(celda)
            partes.append(
                f'<text x="{x + lado/2}" y="{y + lado/2}" text-anchor="middle" '
                f'dominant-baseline="central" font-family="monospace" '
                f'font-size="{max(9, lado // 2)}" fill="#7a6a4f">{sala}</text>'
            )
        partes.append("</svg>")
        return "\n".join(partes)
