"""Cuatro contra la Oscuridad: carga de datos y operaciones del reglamento.

Esta es la unica capa que conoce el juego. El motor de `core/` no importa nada
de aqui; aqui se importa el motor y se le dan datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Iterable

import yaml

from runa.core.checks import (
    Amenaza,
    Check,
    CheckResult,
    ModifierRule,
    Resolutor,
    TipoTirada,
)
from runa.core.abilities import Habilidad, Habilidades
from runa.core.bestiary import Bestiario, Encuentro, PerfilMonstruo, Tesoro
from runa.core.dice import roll
from runa.core.entities import (
    ClasePersonaje,
    Estado,
    Grupo,
    Objeto,
    Personaje,
    ReglaDeJuego,
)
from runa.core.rejilla import Catalogo
from runa.core.rng import RandomSource
from runa.core.tables import TableResult, TableSet

DATOS = Path(__file__).parent / "data"


@dataclass
class Botin:
    """Lo que se saca de un saqueo, antes de repartirlo."""

    oro: int = 0
    objetos: list[Objeto] = field(default_factory=list)
    hechizos: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)

    def absorber(self, otro: "Botin") -> "Botin":
        self.oro += otro.oro
        self.objetos += otro.objetos
        self.hechizos += otro.hechizos
        self.notas += otro.notas
        return self

    @property
    def vacio(self) -> bool:
        return not (self.oro or self.objetos or self.hechizos)

    def __str__(self) -> str:
        return "; ".join(self.notas) if self.notas else "nada"

# Los clerigos prefieren armas contundentes: en la mazmorra abundan los esqueletos.
VARIANTE_POR_DEFECTO = {"clerigo": "aplastante"}


def _leer(carpeta: Path, nombre: str) -> dict[str, Any]:
    return yaml.safe_load((carpeta / nombre).read_text(encoding="utf-8")) or {}


class Juego:
    def __init__(self, datos: Path | None = None) -> None:
        # La carpeta va en la instancia, no en una global: dos Juego con datos
        # distintos deben poder convivir sin pisarse.
        self.datos = Path(datos) if datos is not None else DATOS
        _cargar = partial(_leer, self.datos)
        self.clases = {
            id: ClasePersonaje.desde_dict(id, bruto)
            for id, bruto in _cargar("clases.yaml").items()
        }
        self.catalogo = {
            id: Objeto.desde_dict(id, bruto)
            for id, bruto in _cargar("equipo.yaml").items()
        }
        reglas = _cargar("reglas.yaml")
        self.resolutor = Resolutor(
            tipos={
                id: TipoTirada.desde_dict(id, bruto)
                for id, bruto in (reglas.get("tiradas") or {}).items()
            },
            reglas_globales=[
                ModifierRule.desde_dict(r) for r in (reglas.get("modificadores") or [])
            ],
        )
        self.bestiario = Bestiario.desde_dict(_cargar("monstruos.yaml"))
        self.habilidades = Habilidades.desde_dict(_cargar("hechizos.yaml"))
        self.tablas = TableSet.desde_yaml(self.datos / "tablas")
        self.planos = Catalogo.desde_yaml(self.datos / "planos.yaml")
        self.odios: dict[str, str] = dict(reglas.get("odios") or {})
        self.estados = {
            id: Estado.desde_dict(id, bruto)
            for id, bruto in _cargar("estados.yaml").items()
        }

        from runa.games.cco.hooks import efectos, monstruos
        efectos.registrar(self)
        self.ganchos = monstruos.registrar(self)

    # -- creacion ---------------------------------------------------------- #

    def objeto(self, id: str, variante: str = "") -> Objeto:
        try:
            objeto = self.catalogo[id]
        except KeyError:
            raise ReglaDeJuego(f"no existe el objeto {id!r} en el catalogo") from None
        return objeto.con_variante(variante) if variante and objeto.variantes else objeto

    def crear_personaje(
        self,
        nombre: str,
        clase_id: str,
        rng: RandomSource,
        *,
        nivel: int = 1,
        variante_arma: str = "",
        equipo_inicial: Iterable[str] | None = None,
    ) -> Personaje:
        try:
            clase = self.clases[clase_id]
        except KeyError:
            raise ReglaDeJuego(
                f"no existe la clase {clase_id!r} "
                f"(hay: {', '.join(sorted(self.clases))})"
            ) from None
        if clase.nivel_maximo is not None and nivel > clase.nivel_maximo:
            raise ReglaDeJuego(
                f"un {clase.nombre} no pasa del nivel {clase.nivel_maximo}"
            )

        personaje = Personaje(nombre=nombre, clase=clase, nivel=nivel)
        personaje.oro = roll(clase.riqueza_inicial, rng).total
        variante = variante_arma or VARIANTE_POR_DEFECTO.get(clase_id, "cortante")

        lleva_arma = False
        for id in equipo_inicial if equipo_inicial is not None else clase.equipo_inicial:
            objeto = self.objeto(id, variante)
            # Se puede llevar mas de un arma, pero solo se empuna una (FAQ del elfo).
            equipar = objeto.equipable and not (objeto.tipo == "arma" and lleva_arma)
            personaje.anadir(objeto, equipar=equipar)
            lleva_arma = lleva_arma or (objeto.tipo == "arma" and equipar)
        return personaje

    def crear_grupo(
        self, composicion: Iterable[tuple[str, str]], rng: RandomSource
    ) -> Grupo:
        """`composicion` es una lista de (nombre, clase). El orden es el de marcha."""
        grupo = Grupo([self.crear_personaje(n, c, rng) for n, c in composicion])
        if not grupo.miembros:
            raise ReglaDeJuego("el grupo necesita al menos un personaje")
        return grupo

    def estado(self, id: str) -> Estado:
        """Crea una condicion del catalogo, lista para colgar de un personaje."""
        try:
            plantilla = self.estados[id]
        except KeyError:
            raise ReglaDeJuego(
                f"no existe el estado {id!r} "
                f"(hay: {', '.join(sorted(self.estados))})"
            ) from None
        return Estado(plantilla.id, plantilla.texto, plantilla.reglas,
                      plantilla.etiquetas, plantilla.dura)

    # -- persistencia -------------------------------------------------------- #

    def objeto_desde_dict(self, datos: dict[str, Any]) -> Objeto:
        base = self.catalogo.get(datos["id"])
        if base is None:
            raise ReglaDeJuego(
                f"la partida guardada usa el objeto {datos['id']!r}, "
                "que ya no esta en el catalogo"
            )
        return base.copia(
            etiquetas=frozenset(datos.get("etiquetas") or base.etiquetas),
            variantes=(),
            usos=int(datos.get("usos", base.usos)),
            equipado=bool(datos.get("equipado")),
        )

    def personaje_desde_dict(self, datos: dict[str, Any]) -> Personaje:
        clase = self.clases.get(datos["clase"])
        if clase is None:
            raise ReglaDeJuego(f"clase desconocida {datos['clase']!r} en la partida guardada")
        personaje = Personaje(
            nombre=datos["nombre"], clase=clase, nivel=int(datos["nivel"]),
            vida_max=int(datos["vida_max"]), vida=int(datos["vida"]),
            oro=int(datos.get("oro", 0)),
            equipo=[self.objeto_desde_dict(o) for o in datos.get("equipo") or []],
            estados=[self.estado(e["id"]) for e in datos.get("estados") or []],
            recursos=dict(datos.get("recursos") or {}),
            preparados=list(datos.get("preparados") or []),
            muerto=bool(datos.get("muerto")),
        )
        return personaje

    def grupo_desde_dict(self, datos: dict[str, Any]) -> Grupo:
        return Grupo([self.personaje_desde_dict(p) for p in datos.get("miembros") or []])

    # -- habilidades -------------------------------------------------------- #

    def hechizos_preparados(self, personaje: Personaje) -> list[str]:
        return list(personaje.preparados)

    def preparar_hechizos(self, personaje: Personaje, hechizos: Iterable[str]) -> None:
        """Fija los hechizos del personaje antes de la aventura.

        Se pueden repetir copias del mismo hechizo, como permite el reglamento;
        el limite es el recurso `hechizos` de su clase.
        """
        elegidos = list(hechizos)
        limite = personaje.recursos.get("hechizos", 0)
        if not limite:
            raise ReglaDeJuego(f"un {personaje.clase.nombre} no prepara hechizos")
        if len(elegidos) > limite:
            raise ReglaDeJuego(
                f"{personaje.nombre} solo puede preparar {limite} hechizos, "
                f"no {len(elegidos)}"
            )
        for id in elegidos:
            habilidad = self.habilidades[id]
            if not habilidad.puede_usarla(personaje.clase.id):
                raise ReglaDeJuego(
                    f"un {personaje.clase.nombre} no puede lanzar {habilidad.nombre}"
                )
        personaje.preparados = elegidos

    def usar_habilidad(self, id: str, personaje: Personaje, combate, **kw) -> Any:
        habilidad = self.habilidades[id]
        if not habilidad.puede_usarla(personaje.clase.id):
            raise ReglaDeJuego(
                f"un {personaje.clase.nombre} no puede usar {habilidad.nombre}"
            )
        efecto = self.habilidades.efectos.get(habilidad.efecto)
        if efecto is None:
            raise ReglaDeJuego(
                f"el efecto {habilidad.efecto!r} de {habilidad.nombre} "
                "no tiene implementacion registrada"
            )
        resultado = efecto(personaje, combate, habilidad, **kw)
        # Un hechizo preparado se consume al lanzarlo.
        if habilidad.gasta == "hechizos" and id in personaje.preparados:
            personaje.preparados.remove(id)
        return resultado

    # -- tesoros ------------------------------------------------------------ #

    def resolver_tesoro(self, resultado: TableResult, rng: RandomSource) -> "Botin":
        """Convierte una tirada de la tabla de tesoros en oro y objetos."""
        botin = Botin()
        for nodo in resultado.recorrer():
            datos = nodo.entrada.datos

            if (expr := datos.get("oro")) is not None:
                tirada = roll(str(expr), rng)
                botin.oro += tirada.total
                botin.notas.append(f"{tirada.total} piezas de oro ({tirada.detail})")

            id_objeto = datos.get("objeto")
            if id_objeto and id_objeto in self.catalogo:
                objeto = self.catalogo[id_objeto]
                if (expr := datos.get("valor") or objeto.valor):
                    tirada = roll(str(expr), rng)
                    objeto = objeto.copia(precio=tirada.total)
                    botin.notas.append(
                        f"{objeto.nombre} por valor de {tirada.total} ({tirada.detail})"
                    )
                else:
                    botin.notas.append(objeto.nombre)
                botin.objetos.append(objeto)
            elif id_objeto:
                botin.notas.append(f"objeto sin catalogar: {id_objeto}")

            if hechizo := datos.get("hechizo"):
                botin.hechizos.append(hechizo)
                nombre = self.habilidades[hechizo].nombre
                # El pergamino se nombra por su hechizo en vez de anunciarlo aparte.
                if botin.objetos and "pergamino" in botin.objetos[-1].etiquetas:
                    pergamino = botin.objetos[-1]
                    botin.objetos[-1] = pergamino.copia(nombre=f"Pergamino de {nombre}")
                    botin.notas[-1] = botin.objetos[-1].nombre
                else:
                    botin.notas.append(f"pergamino de {nombre}")

            # El arma magica concreta sale de una tirada encadenada.
            if (base := datos.get("base")) and base in self.catalogo:
                arma = self.catalogo[base]
                if variante := datos.get("variante"):
                    arma = arma.con_variante(variante)
                arma = arma.copia(
                    nombre=f"{arma.nombre} magica",
                    etiquetas=arma.etiquetas | {"magico"},
                    reglas=arma.reglas + self.catalogo["arma_magica"].reglas,
                )
                botin.objetos = [o for o in botin.objetos if o.id != "arma_magica"]
                botin.objetos.append(arma)
                botin.notas.append(arma.nombre)
        return botin

    def saquear(
        self,
        tesoro: "Tesoro",
        rng: RandomSource,
        extra: int = 0,
        sin_objetos_magicos: str = "",
    ) -> "Botin":
        """Tira el tesoro de un encuentro: una tirada por encuentro, no por monstruo."""
        total = Botin()
        for _ in range(tesoro.tiradas):
            resultado = self.tablas.tirar(
                "tesoros", rng, modificador=tesoro.modificador + extra
            )
            total.absorber(self.resolver_tesoro(resultado, rng))
        if sin_objetos_magicos:
            # Los orcos no guardan magia: lo que seria un objeto magico es oro.
            magicos = [o for o in total.objetos if "magico" in o.etiquetas]
            for objeto in magicos:
                total.objetos.remove(objeto)
                tirada = roll(sin_objetos_magicos, rng)
                total.oro += tirada.total
                total.notas.append(
                    f"en vez de {objeto.nombre}, {tirada.total} de oro ({tirada.detail})"
                )
            if total.hechizos:
                for _ in list(total.hechizos):
                    total.hechizos.pop()
                    tirada = roll(sin_objetos_magicos, rng)
                    total.oro += tirada.total
                    total.notas.append(f"en vez de un pergamino, {tirada.total} de oro")
        return total

    # -- monstruos --------------------------------------------------------- #

    def encuentro_desde(self, resultado: TableResult, rng: RandomSource) -> Encuentro:
        """Monta el encuentro que describe una tirada YA hecha.

        Va separado de `generar_monstruos` a proposito: cuando la tirada llega
        encadenada desde el contenido de la habitacion, volver a tirar la tabla
        daria un monstruo distinto del que salio.
        """
        ids = resultado.entrada.datos.get("monstruo")
        if not ids:
            raise ReglaDeJuego(
                f"la entrada {resultado.valor} de {resultado.tabla!r} "
                "no nombra ningun monstruo"
            )
        if isinstance(ids, str):
            ids = [ids]
        # "d6+2 esqueletos o d6 zombies (50% de probabilidad)"
        elegido = rng.choice(ids) if len(ids) > 1 else ids[0]
        return self.bestiario[elegido].generar(rng)

    def generar_monstruos(self, tabla: str, rng: RandomSource) -> Encuentro:
        """Tira en una tabla de aparicion y monta el encuentro que salga."""
        return self.encuentro_desde(self.tablas.tirar(tabla, rng, encadenar=False), rng)

    def reaccion(self, encuentro: Encuentro, rng: RandomSource):
        """Tira en la tabla de Reacciones del monstruo. Una sola vez por grupo."""
        tabla = encuentro.perfil.reacciones
        if not tabla:
            return None
        return self.tablas.tirar(tabla, rng, encadenar=False)

    def moral(self, encuentro: Encuentro, rng: RandomSource) -> bool | None:
        """Tira moral. True = aguanta, False = huye, None = no la prueba nunca."""
        moral = encuentro.perfil.moral
        if not moral.prueba:
            return None
        tirada = roll("d6", rng).total + moral.modificador
        aguanta = tirada >= 4     # "3 o menos y huyen"
        if not aguanta:
            encuentro.huir()
        return aguanta

    # -- tiradas ----------------------------------------------------------- #

    def amenaza(
        self,
        nombre: str,
        nivel: int,
        etiquetas: Iterable[str] = (),
        reglas: Iterable[ModifierRule] = (),
    ) -> Amenaza:
        return Amenaza.crear(nombre, nivel, etiquetas, reglas)

    def tirar(
        self,
        tipo: str,
        personaje: Personaje,
        rng: RandomSource,
        *,
        amenaza: Amenaza | None = None,
        dificultad: int | None = None,
        etiquetas: Iterable[str] = (),
        ventaja: int = 1,
    ) -> CheckResult:
        if dificultad is None:
            if amenaza is None:
                raise ReglaDeJuego("una tirada necesita amenaza o dificultad")
            dificultad = amenaza.nivel
        check = Check(
            tipo=tipo,
            actor=personaje,
            dificultad=dificultad,
            amenaza=amenaza,
            etiquetas=set(etiquetas),
            ventaja=ventaja,
        )
        return self.resolutor.resolver(check, rng)

    def atacar(
        self,
        personaje: Personaje,
        objetivo: Amenaza,
        rng: RandomSource,
        *,
        etiquetas: Iterable[str] = (),
        ventaja: int = 1,
    ) -> CheckResult:
        return self.tirar(
            "ataque", personaje, rng, amenaza=objetivo,
            etiquetas=etiquetas, ventaja=ventaja,
        )

    def defender(
        self,
        personaje: Personaje,
        atacante: Amenaza,
        rng: RandomSource,
        *,
        etiquetas: Iterable[str] = (),
    ) -> CheckResult:
        return self.tirar(
            "defensa", personaje, rng, amenaza=atacante, etiquetas=etiquetas
        )

    # -- comprobacion de integridad ---------------------------------------- #

    def combatir(
        self,
        grupo: Grupo,
        encuentro: Encuentro,
        rng: RandomSource,
        *,
        decisor,
        registro=None,
        situacion=None,
    ):
        from runa.games.cco.combate import Combate

        return Combate(
            self, grupo, encuentro, rng,
            decisor=decisor, registro=registro, situacion=situacion,
        ).resolver()

    def validar(self) -> list[str]:
        """Todo lo que falta o no cuadra en los datos. Vacio = datos coherentes."""
        problemas = list(self.tablas.validar())
        for tabla in self.tablas.tablas.values():
            for entrada in tabla.entradas:
                donde = f"{tabla.id}[{entrada.minimo}-{entrada.maximo}]"
                ids = entrada.datos.get("monstruo") or []
                for id in [ids] if isinstance(ids, str) else ids:
                    if id not in self.bestiario:
                        problemas.append(f"{donde}: monstruo {id!r} no esta en el bestiario")
                for clave, catalogo, nombre in (
                    ("hechizo", self.habilidades, "las habilidades"),
                    ("objeto", self.catalogo, "el catalogo"),
                    ("base", self.catalogo, "el catalogo"),
                ):
                    id = entrada.datos.get(clave)
                    if id and id not in catalogo:
                        problemas.append(f"{donde}: {clave} {id!r} no esta en {nombre}")
        for perfil in self.bestiario.perfiles.values():
            if perfil.reacciones and perfil.reacciones not in self.tablas:
                problemas.append(
                    f"monstruo {perfil.id!r}: tabla de reacciones "
                    f"{perfil.reacciones!r} inexistente"
                )
        for habilidad in self.habilidades.catalogo.values():
            for clase in habilidad.usable_por:
                if clase not in self.clases:
                    problemas.append(
                        f"habilidad {habilidad.id!r}: clase {clase!r} inexistente"
                    )
        problemas += [
            f"la habilidad con efecto {e!r} no tiene implementacion registrada"
            for e in self.habilidades.sin_implementar()
        ]
        for etiqueta, clase in self.odios.items():
            if clase not in self.clases:
                problemas.append(f"odio {etiqueta!r}: clase {clase!r} inexistente")
        faltan = [f"{a}{b}" for a in range(1, 7) for b in range(1, 7)
                  if f"{a}{b}" not in self.planos.planos]
        if faltan:
            problemas.append(f"faltan losetas d66: {', '.join(faltan)}")
        faltan = [str(n) for n in range(1, 7) if str(n) not in self.planos.entradas]
        if faltan:
            problemas.append(f"faltan salas de entrada: {', '.join(faltan)}")
        for clase in self.clases.values():
            for id in clase.equipo_inicial:
                if id not in self.catalogo:
                    problemas.append(
                        f"clase {clase.id!r}: equipo inicial {id!r} no esta en el catalogo"
                    )
            # Se crea de verdad, en vez de reimplementar aqui el reparto de
            # equipo: asi el validador no puede desviarse de la creacion real.
            personaje = self.crear_personaje("_", clase.id, RandomSource(0))
            problemas += [f"clase {clase.id!r}: {x}" for x in personaje.problemas_de_equipo()]
        return problemas
