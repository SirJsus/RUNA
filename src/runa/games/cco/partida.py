"""Estado de una partida: el grupo, la mazmorra y todo lo que hay que recordar.

Se guarda y se carga en JSON. Lo que se guarda son referencias (id de clase, id
de objeto, id de estado) y no reglas: al cargar, las reglas se releen de los
YAML, de modo que un arreglo del reglamento alcanza a las partidas ya empezadas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from runa.core.entities import Grupo
from runa.core.events import Registro
from runa.core.mapa import Mapa
from runa.core.rejilla import Rejilla
from runa.core.rng import RandomSource

VERSION = 1


@dataclass
class Aventura:
    """Lo que dura una sola incursion en la mazmorra."""

    jefes_vistos: int = 0                 # cuenta para la tirada de jefe final
    jefe_final_encontrado: bool = False
    jefe_final_derrotado: bool = False
    encuentros_esbirros: int = 0          # 10 dan una tirada de XP a -1
    gastados: list[str] = field(default_factory=list)   # fuente, curandero, alquimista...
    misiones: list[dict[str, Any]] = field(default_factory=list)
    terminada: bool = False

    def gastar(self, id: str) -> bool:
        """Marca algo de una sola vez por aventura. False si ya estaba gastado."""
        if id in self.gastados:
            return False
        self.gastados.append(id)
        return True

    def a_dict(self) -> dict[str, Any]:
        return {
            "jefes_vistos": self.jefes_vistos,
            "jefe_final_encontrado": self.jefe_final_encontrado,
            "jefe_final_derrotado": self.jefe_final_derrotado,
            "encuentros_esbirros": self.encuentros_esbirros,
            "gastados": self.gastados,
            "misiones": self.misiones,
            "terminada": self.terminada,
        }

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "Aventura":
        return cls(
            jefes_vistos=int(datos.get("jefes_vistos", 0)),
            jefe_final_encontrado=bool(datos.get("jefe_final_encontrado")),
            jefe_final_derrotado=bool(datos.get("jefe_final_derrotado")),
            encuentros_esbirros=int(datos.get("encuentros_esbirros", 0)),
            gastados=list(datos.get("gastados") or []),
            misiones=list(datos.get("misiones") or []),
            terminada=bool(datos.get("terminada")),
        )


@dataclass
class Campana:
    """Lo que sobrevive de una aventura a la siguiente."""

    aventuras_jugadas: int = 0
    recompensas_gastadas: list[str] = field(default_factory=list)
    pistas: dict[str, int] = field(default_factory=dict)      # personaje -> pistas
    ultimo_en_subir: str = ""                                 # no dos veces seguidas

    def a_dict(self) -> dict[str, Any]:
        return {
            "aventuras_jugadas": self.aventuras_jugadas,
            "recompensas_gastadas": self.recompensas_gastadas,
            "pistas": self.pistas,
            "ultimo_en_subir": self.ultimo_en_subir,
        }

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "Campana":
        return cls(
            aventuras_jugadas=int(datos.get("aventuras_jugadas", 0)),
            recompensas_gastadas=list(datos.get("recompensas_gastadas") or []),
            pistas=dict(datos.get("pistas") or {}),
            ultimo_en_subir=str(datos.get("ultimo_en_subir", "")),
        )


class Partida:
    def __init__(
        self,
        juego: Any,
        grupo: Grupo,
        *,
        semilla: int | None = None,
        mapa: Mapa | None = None,
        registro: Registro | None = None,
        aventura: Aventura | None = None,
        campana: Campana | None = None,
        nombre: str = "",
        rejilla: bool = True,
    ) -> None:
        self.juego = juego
        self.grupo = grupo
        self.rng = RandomSource(semilla)
        # Con rejilla el programa dibuja la mazmorra; sin ella, la dibujas tu.
        self.mapa = mapa if mapa is not None else Mapa(Rejilla() if rejilla else None)
        self.registro = registro if registro is not None else Registro()
        self.aventura = aventura if aventura is not None else Aventura()
        self.campana = campana if campana is not None else Campana()
        self.nombre = nombre or f"partida-{self.rng.seed}"
        self.xp_pendientes: int = 0

    # -- estado -------------------------------------------------------------- #

    @property
    def viva(self) -> bool:
        return bool(self.grupo.vivos) and not self.aventura.terminada

    def anotar(self, tipo: str, texto: str, **datos: Any):
        return self.registro.anotar(tipo, texto, **datos)

    def resumen(self) -> str:
        a = self.aventura
        return (
            f"{self.nombre} | semilla {self.rng.seed} | "
            f"salas {len(self.mapa)} | jefes vistos {a.jefes_vistos} | "
            f"esbirros {a.encuentros_esbirros}/10 | oro {self.grupo.oro} | "
            f"XP pendientes {self.xp_pendientes}"
        )

    # -- persistencia --------------------------------------------------------- #

    def a_dict(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "juego": "cuatro-contra-la-oscuridad",
            "nombre": self.nombre,
            "guardada": datetime.now().isoformat(timespec="seconds"),
            "semilla": self.rng.seed,
            "tiradas": self.rng.count,
            "grupo": self.grupo.a_dict(),
            "mapa": self.mapa.a_dict(),
            "rejilla": self.mapa.rejilla is not None,
            "aventura": self.aventura.a_dict(),
            "campana": self.campana.a_dict(),
            "xp_pendientes": self.xp_pendientes,
            "cronica": [
                {"tipo": e.tipo, "texto": e.texto} for e in self.registro
            ],
        }

    def guardar(self, ruta: Path | str) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(self.a_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return ruta

    @classmethod
    def cargar(cls, ruta: Path | str, juego: Any) -> "Partida":
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cls.desde_dict(datos, juego)

    @classmethod
    def desde_dict(cls, datos: dict[str, Any], juego: Any) -> "Partida":
        version = int(datos.get("version", 0))
        if version > VERSION:
            raise ValueError(
                f"la partida es de la version {version} y este programa entiende "
                f"hasta la {VERSION}: actualiza antes de cargarla"
            )
        registro = Registro()
        for evento in datos.get("cronica") or []:
            registro.anotar(evento.get("tipo", "nota"), evento.get("texto", ""))

        mapa = Mapa.desde_dict(datos.get("mapa") or {})
        if datos.get("rejilla", False):
            mapa.rejilla = Rejilla().reconstruir(mapa, juego.planos)
        partida = cls(
            juego,
            juego.grupo_desde_dict(datos["grupo"]),
            semilla=int(datos.get("semilla", 0)),
            mapa=mapa,
            registro=registro,
            aventura=Aventura.desde_dict(datos.get("aventura") or {}),
            campana=Campana.desde_dict(datos.get("campana") or {}),
            nombre=datos.get("nombre", ""),
        )
        partida.xp_pendientes = int(datos.get("xp_pendientes", 0))
        # Se rebobina el azar hasta donde estaba, para que continuar una partida
        # guardada de la misma semilla de exactamente lo mismo que no cortarla.
        for _ in range(int(datos.get("tiradas", 0))):
            partida.rng.die(6)
        return partida
