"""Tablas aleatorias declarativas.

Una tabla se define en YAML y el motor no sabe de que juego es:

    contenido_habitacion:
      nombre: Contenido de la Habitacion
      dado: 2d6
      entradas:
        - rango: 2
          texto: Tesoro encontrado.
          tirar: [tesoros]
        - rango: 3-5
          texto: Vacio.

Soporta lo que el reglamento necesita:
  * modificadores a la tirada ("tesoro +1"), recortados al rango de la tabla
  * tiradas encadenadas (`tirar:`), que producen un arbol de resultados
  * entradas de una sola vez por campana (`unica: true`), que se vuelven a tirar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import yaml

from .dice import RollResult, roll
from .rng import RandomSource

MAX_REINTENTOS = 50


class TableError(ValueError):
    """Tabla mal definida o consulta imposible."""


@dataclass(frozen=True)
class TableEntry:
    minimo: int
    maximo: int
    texto: str
    datos: dict[str, Any] = field(default_factory=dict)

    def __contains__(self, valor: int) -> bool:
        return self.minimo <= valor <= self.maximo

    @property
    def unica(self) -> bool:
        """Entrada irrepetible en una campana (p.ej. las Recompensas Epicas)."""
        return bool(self.datos.get("unica"))

    @property
    def clave(self) -> str:
        """Identificador estable para recordar que ya salio."""
        return str(self.datos.get("id") or f"{self.minimo}-{self.maximo}")

    @property
    def encadena(self) -> list[str]:
        valor = self.datos.get("tirar") or []
        return [valor] if isinstance(valor, str) else list(valor)


@dataclass(frozen=True)
class TableResult:
    tabla: str
    entrada: TableEntry
    valor: int
    tirada: RollResult
    modificador: int = 0
    hijos: tuple["TableResult", ...] = ()

    @property
    def texto(self) -> str:
        return self.entrada.texto

    def recorrer(self) -> Iterator["TableResult"]:
        """Este resultado y, en profundidad, los que desencadeno."""
        yield self
        for hijo in self.hijos:
            yield from hijo.recorrer()

    def describir(self, sangria: int = 0) -> str:
        signo = f" {self.modificador:+d}" if self.modificador else ""
        lineas = [f"{'  ' * sangria}[{self.tabla} {self.valor}{signo}] {self.texto}"]
        lineas += [h.describir(sangria + 1) for h in self.hijos]
        return "\n".join(lineas)

    def __str__(self) -> str:
        return self.describir()


@dataclass
class Table:
    id: str
    nombre: str
    dado: str
    entradas: tuple[TableEntry, ...]

    @property
    def minimo(self) -> int:
        return min(e.minimo for e in self.entradas)

    @property
    def maximo(self) -> int:
        return max(e.maximo for e in self.entradas)

    def buscar(self, valor: int) -> TableEntry:
        """Localiza la entrada, recortando al rango de la tabla.

        El recorte es intencionado: los modificadores del juego ("tesoro +1")
        pueden sacar la tirada fuera de la tabla y el libro los trata como el
        extremo correspondiente.
        """
        acotado = max(self.minimo, min(self.maximo, valor))
        for entrada in self.entradas:
            if acotado in entrada:
                return entrada
        raise TableError(
            f"la tabla {self.id!r} no cubre el valor {acotado} "
            f"(rango {self.minimo}-{self.maximo}): faltan entradas"
        )

    def tirar(
        self,
        rng: RandomSource,
        *,
        modificador: int = 0,
        excluir: Iterable[str] = (),
        **variables: int,
    ) -> TableResult:
        excluidas = set(excluir)
        for _ in range(MAX_REINTENTOS):
            tirada = roll(self.dado, rng, **variables)
            valor = tirada.total + modificador
            entrada = self.buscar(valor)
            if not (entrada.unica and entrada.clave in excluidas):
                return TableResult(self.id, entrada, valor, tirada, modificador)
        raise TableError(
            f"la tabla {self.id!r} solo tiene entradas ya gastadas: "
            "no queda nada que sacar"
        )


class TableSet:
    """Coleccion de tablas capaz de resolver tiradas encadenadas."""

    def __init__(self, tablas: dict[str, Table] | None = None) -> None:
        self.tablas: dict[str, Table] = dict(tablas or {})

    def __getitem__(self, id: str) -> Table:
        try:
            return self.tablas[id]
        except KeyError:
            raise TableError(
                f"no existe la tabla {id!r} (hay: {', '.join(sorted(self.tablas))})"
            ) from None

    def __contains__(self, id: str) -> bool:
        return id in self.tablas

    def __len__(self) -> int:
        return len(self.tablas)

    def tirar(
        self,
        id: str,
        rng: RandomSource,
        *,
        modificador: int = 0,
        encadenar: bool | Callable[[TableEntry], bool] = True,
        excluir: Iterable[str] = (),
        _profundidad: int = 0,
        **variables: int,
    ) -> TableResult:
        """Tira en la tabla `id` y resuelve las tiradas que encadene.

        `encadenar` acepta un predicado sobre la entrada, no solo un booleano:
        asi el juego decide casos como "esta entrada no encadena si la sala es
        un corredor" sin que el motor tenga que saber que es un corredor.
        """
        if _profundidad > 10:
            raise TableError(f"tiradas encadenadas demasiado profundas desde {id!r}")
        resultado = self[id].tirar(
            rng, modificador=modificador, excluir=excluir, **variables
        )
        permitido = encadenar(resultado.entrada) if callable(encadenar) else encadenar
        if not permitido or not resultado.entrada.encadena:
            return resultado
        hijos = tuple(
            self.tirar(
                sub, rng, excluir=excluir, _profundidad=_profundidad + 1, **variables
            )
            for sub in resultado.entrada.encadena
        )
        return TableResult(
            resultado.tabla,
            resultado.entrada,
            resultado.valor,
            resultado.tirada,
            resultado.modificador,
            hijos,
        )

    def validar(self) -> list[str]:
        """Comprueba la coherencia del conjunto. Devuelve los problemas hallados.

        Sirve de red de seguridad al transcribir un reglamento: detecta tiradas
        encadenadas hacia tablas que aun no existen o mal escritas.
        """
        problemas: list[str] = []
        for tabla in self.tablas.values():
            for entrada in tabla.entradas:
                for destino in entrada.encadena:
                    if destino not in self.tablas:
                        problemas.append(
                            f"{tabla.id}[{entrada.minimo}-{entrada.maximo}] "
                            f"encadena a la tabla inexistente {destino!r}"
                        )
        return problemas

    # -- carga ------------------------------------------------------------- #

    @classmethod
    def desde_yaml(cls, *rutas: Path | str) -> "TableSet":
        conjunto = cls()
        for ruta in rutas:
            ruta = Path(ruta)
            archivos = sorted(ruta.glob("*.yaml")) if ruta.is_dir() else [ruta]
            for archivo in archivos:
                datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
                for id, bruto in datos.items():
                    if id in conjunto.tablas:
                        raise TableError(f"tabla duplicada {id!r} en {archivo}")
                    conjunto.tablas[id] = _tabla_desde_dict(id, bruto, archivo)
        return conjunto


_RANGO_RE = re.compile(r"^(-?\d+)(?:\s*\.\.\s*|\s*-\s*(?=-?\d))(-?\d+)$")


def _rango(valor: Any) -> tuple[int, int]:
    """Interpreta `3`, `"3"`, `"1-5"` o `"-20-0"` (limites negativos incluidos)."""
    if isinstance(valor, int):
        return valor, valor
    texto = str(valor).strip()
    if match := _RANGO_RE.match(texto):
        minimo, maximo = int(match.group(1)), int(match.group(2))
        if minimo > maximo:
            raise TableError(f"rango invertido: {texto!r}")
        return minimo, maximo
    try:
        return int(texto), int(texto)
    except ValueError:
        raise TableError(f"no entiendo el rango {texto!r}") from None


def _tabla_desde_dict(id: str, bruto: dict[str, Any], origen: Path) -> Table:
    try:
        entradas_brutas = bruto["entradas"]
        dado = bruto["dado"]
    except (KeyError, TypeError) as exc:
        raise TableError(f"la tabla {id!r} en {origen} necesita 'dado' y 'entradas'") from exc

    entradas: list[TableEntry] = []
    for cruda in entradas_brutas:
        datos = dict(cruda)
        minimo, maximo = _rango(datos.pop("rango"))
        texto = str(datos.pop("texto", "")).strip()
        entradas.append(TableEntry(minimo, maximo, texto, datos))
    entradas.sort(key=lambda e: e.minimo)

    for previa, siguiente in zip(entradas, entradas[1:]):
        if siguiente.minimo <= previa.maximo:
            raise TableError(
                f"la tabla {id!r} en {origen} solapa los rangos "
                f"{previa.minimo}-{previa.maximo} y {siguiente.minimo}-{siguiente.maximo}"
            )

    return Table(id, str(bruto.get("nombre", id)), str(dado), tuple(entradas))
