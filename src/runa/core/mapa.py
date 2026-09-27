"""La mazmorra como grafo de salas.

El grafo es la verdad sobre **que conecta con que**: una sala sabe cuantas
salidas tiene y a donde lleva cada una. La geometria —que forma dibuja la
loseta y donde cae en la hoja— es una capa opcional encima, en `rejilla.py`.

Se puede jugar con las dos o solo con el grafo, que es mas rapido de llevar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from .rejilla import Celda, Rejilla


class MapaError(ValueError):
    """Movimiento o conexion imposible."""


@dataclass
class Sala:
    id: int
    tipo: str = "habitacion"          # entrada | habitacion | corredor
    plano: str = ""                   # tirada d66, para el dibujo futuro
    salidas: int = 1                  # puertas o aberturas que tiene
    conexiones: dict[int, int] = field(default_factory=dict)  # salida -> id de sala
    contenido: str = ""
    resuelta: bool = False            # ya se sabe que hay dentro
    limpia: bool = True               # sin monstruos pendientes
    buscada: bool = False             # "solo se puede buscar una vez"
    secreta: bool = False             # se llego por una puerta secreta
    notas: list[str] = field(default_factory=list)
    # Geometria, solo si se juega con rejilla.
    origen: Celda | None = None       # esquina superior izquierda en la hoja
    giros: int = 0                    # cuartos de vuelta aplicados a la loseta
    recortada: bool = False           # no cupo entera: es un callejon sin salida

    @property
    def es_corredor(self) -> bool:
        return self.tipo == "corredor"

    @property
    def salidas_libres(self) -> list[int]:
        return [i for i in range(self.salidas) if i not in self.conexiones]

    @property
    def sin_salida(self) -> bool:
        return not self.salidas_libres

    def anotar(self, texto: str) -> None:
        self.notas.append(texto)

    def describir(self, libres: int | None = None) -> str:
        marcas = []
        if not self.limpia:
            marcas.append("monstruos")
        if self.buscada:
            marcas.append("buscada")
        if self.secreta:
            marcas.append("secreta")
        if self.recortada:
            marcas.append("recortada")
        if libres is None:
            libres = len(self.salidas_libres)
        marcas.append(f"{libres} salida(s) sin explorar" if libres else "sin salidas")
        return (f"Sala {self.id} ({self.tipo}): "
                f"{self.contenido or 'sin resolver'} [{', '.join(marcas)}]")

    def __str__(self) -> str:
        return self.describir()


class Mapa:
    def __init__(self, rejilla: Rejilla | None = None) -> None:
        self.salas: dict[int, Sala] = {}
        self.actual: int = 0
        self._siguiente = 1
        # Cuando hay rejilla, ella manda sobre que salidas quedan libres.
        self.rejilla = rejilla

    # -- construccion ------------------------------------------------------- #

    def crear(self, tipo: str = "habitacion", salidas: int = 1, plano: str = "",
              secreta: bool = False, origen: Celda | None = None,
              giros: int = 0, recortada: bool = False) -> Sala:
        sala = Sala(id=self._siguiente, tipo=tipo, salidas=max(1, salidas),
                    plano=plano, secreta=secreta, origen=origen, giros=giros,
                    recortada=recortada)
        self.salas[sala.id] = sala
        self._siguiente += 1
        if len(self.salas) == 1:
            self.actual = sala.id
        return sala

    def conectar(self, origen: int, salida: int, destino: int) -> None:
        """Une dos salas por una salida concreta. Las puertas son de doble sentido."""
        a, b = self[origen], self[destino]
        if salida in a.conexiones:
            raise MapaError(f"la salida {salida} de la sala {origen} ya lleva a otro sitio")
        libres = b.salidas_libres
        if not libres:
            raise MapaError(f"la sala {destino} no tiene salidas libres para conectar")
        a.conexiones[salida] = destino
        b.conexiones[libres[0]] = origen

    # -- consulta ----------------------------------------------------------- #

    def __getitem__(self, id: int) -> Sala:
        try:
            return self.salas[id]
        except KeyError:
            raise MapaError(f"no existe la sala {id}") from None

    def __len__(self) -> int:
        return len(self.salas)

    def __iter__(self) -> Iterator[Sala]:
        return iter(self.salas.values())

    @property
    def sala_actual(self) -> Sala:
        return self[self.actual]

    @property
    def entrada(self) -> Sala | None:
        return next((s for s in self if s.tipo == "entrada"), None)

    @property
    def completo(self) -> bool:
        """No queda ninguna puerta sin explorar en toda la mazmorra."""
        if self.rejilla is not None:
            return not any(self.rejilla.salidas_libres(s.id) for s in self)
        return all(s.sin_salida for s in self)

    def salidas_libres(self, id: int | None = None) -> list:
        """Las salidas sin explorar de una sala.

        Con rejilla son salidas concretas (celda y lado); sin ella, solo
        indices de puerta.
        """
        sala = self[self.actual if id is None else id]
        if self.rejilla is not None:
            return self.rejilla.salidas_libres(sala.id)
        return sala.salidas_libres

    def puertas(self) -> set[frozenset]:
        """Los pares de celdas contiguas que comunican dos salas conectadas."""
        if self.rejilla is None:
            return set()
        from .rejilla import LADOS
        pares = set()
        for sala in self:
            vecinas = set(sala.conexiones.values())
            for celda, salida in self.rejilla.piezas.get(sala.id, None) \
                    and self.rejilla.piezas[sala.id].salidas_mundo() or []:
                dx, dy = LADOS[salida.lado]
                contigua = (celda[0] + dx, celda[1] + dy)
                if self.rejilla.sala_en(contigua) in vecinas:
                    pares.add(frozenset((celda, contigua)))
        return pares

    def vecinas(self, id: int | None = None) -> list[Sala]:
        sala = self[self.actual if id is None else id]
        return [self[d] for d in sala.conexiones.values()]

    def mover(self, destino: int) -> Sala:
        if destino not in self.salas:
            raise MapaError(f"no existe la sala {destino}")
        if destino not in self.sala_actual.conexiones.values():
            raise MapaError(
                f"la sala {destino} no conecta con la sala {self.actual}"
            )
        self.actual = destino
        return self.sala_actual

    def camino_a_la_entrada(self) -> list[int]:
        """Ruta mas corta hasta la entrada, para salir de la mazmorra."""
        entrada = self.entrada
        if entrada is None:
            return []
        pendientes = [[self.actual]]
        vistas = {self.actual}
        while pendientes:
            camino = pendientes.pop(0)
            if camino[-1] == entrada.id:
                return camino
            for vecina in self[camino[-1]].conexiones.values():
                if vecina not in vistas:
                    vistas.add(vecina)
                    pendientes.append([*camino, vecina])
        return []

    def describir(self) -> str:
        """Con rejilla manda la geometria: puede haber puertas ya tapiadas."""
        lineas = []
        for sala in self:
            marca = ">" if sala.id == self.actual else " "
            libres = len(self.salidas_libres(sala.id))
            lineas.append(f"{marca} {sala.describir(libres)}")
        return "\n".join(lineas)

    # -- persistencia -------------------------------------------------------- #

    def a_dict(self) -> dict[str, Any]:
        return {
            "actual": self.actual,
            "siguiente": self._siguiente,
            "salas": [
                {
                    "id": s.id, "tipo": s.tipo, "plano": s.plano, "salidas": s.salidas,
                    "conexiones": {str(k): v for k, v in s.conexiones.items()},
                    "contenido": s.contenido, "resuelta": s.resuelta,
                    "limpia": s.limpia, "buscada": s.buscada, "secreta": s.secreta,
                    "notas": s.notas, "origen": list(s.origen) if s.origen else None,
                    "giros": s.giros, "recortada": s.recortada,
                }
                for s in self
            ],
        }

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "Mapa":
        mapa = cls()
        for bruto in datos.get("salas", []):
            sala = Sala(
                id=int(bruto["id"]), tipo=bruto.get("tipo", "habitacion"),
                plano=bruto.get("plano", ""), salidas=int(bruto.get("salidas", 1)),
                conexiones={int(k): int(v) for k, v in (bruto.get("conexiones") or {}).items()},
                contenido=bruto.get("contenido", ""),
                resuelta=bool(bruto.get("resuelta")), limpia=bool(bruto.get("limpia", True)),
                buscada=bool(bruto.get("buscada")), secreta=bool(bruto.get("secreta")),
                notas=list(bruto.get("notas") or []),
                origen=tuple(bruto["origen"]) if bruto.get("origen") else None,
                giros=int(bruto.get("giros", 0)),
                recortada=bool(bruto.get("recortada")),
            )
            mapa.salas[sala.id] = sala
        mapa.actual = int(datos.get("actual", 0))
        mapa._siguiente = int(datos.get("siguiente", len(mapa.salas) + 1))
        return mapa
