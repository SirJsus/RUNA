"""El bucle de combate de Cuatro contra la Oscuridad.

Escrito una sola vez para los dos modos de juego: cada decision del jugador sale
por el puerto `Decisor`, asi que la CLI (modo arbitro) y un futuro agente
automatico usan este mismo codigo sin tocarlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runa.core.bestiary import Encuentro
from runa.core.checks import AccionProhibida, CheckResult
from runa.core.decisions import Decisor, Opcion, Pregunta
from runa.core.entities import Grupo, Personaje
from runa.core.events import Registro
from runa.core.rng import RandomSource

# Reacciones que este bucle sabe resolver por si mismo. El resto (misiones,
# acertijos, desafios magicos) las devuelve al flujo de exploracion.
RESUELVE = frozenset({
    "lucha", "lucha_hasta_muerte", "huir", "huir_si_superados", "soborno", "durmiendo",
})


@dataclass
class Situacion:
    """Donde y como ocurre el combate."""

    corredor: bool = False
    errante: bool = False      # monstruos errantes: sorprenden y pegan primero
    puerta: bool = True        # sin puerta que cerrar no hay retirada posible


@dataclass
class ResultadoCombate:
    desenlace: str             # victoria | derrota | huida | retirada | evitado | pendiente
    rondas: int = 0
    reaccion: str = ""
    botin: bool = True         # si el grupo tiene derecho a tirar tesoro
    xp: bool = False
    detalle: str = ""
    # Cosas que deja pendientes para el flujo de exploracion: refuerzos que
    # aparecen, pistas encontradas...
    sucesos: list[str] = field(default_factory=list)
    refuerzos: list[str] = field(default_factory=list)

    @property
    def terminado(self) -> bool:
        return self.desenlace != "pendiente"


class Combate:
    def __init__(
        self,
        juego: Any,
        grupo: Grupo,
        encuentro: Encuentro,
        rng: RandomSource,
        *,
        decisor: Decisor,
        registro: Registro | None = None,
        situacion: Situacion | None = None,
    ) -> None:
        self.juego = juego
        self.grupo = grupo
        self.enc = encuentro
        self.rng = rng
        self.decisor = decisor
        # `or` no sirve: un Registro vacio es falsy por su __len__.
        self.reg = registro if registro is not None else Registro()
        self.sit = situacion if situacion is not None else Situacion()
        self.ronda = 0
        self.reaccion = ""
        self.moral_probada = False
        self._odios: dict[str, str] = juego.odios
        self.sucesos: list[str] = []
        self.refuerzos: list[str] = []
        self.marcas: dict[str, Any] = {}     # notas que dejan los ganchos

    # -- utilidades -------------------------------------------------------- #

    @property
    def vivos(self) -> list[Personaje]:
        # Quien se marcho con Escapada no cuenta hasta que acabe el combate.
        return [p for p in self.grupo.vivos if not p.fuera_de_combate]

    @property
    def monstruos_restantes(self) -> int:
        if not self.enc.vivo:
            return 0
        return self.enc.cantidad if self.enc.perfil.es_esbirro else 1

    def _etiquetas_base(self, primer_turno: bool = False) -> set[str]:
        etiquetas: set[str] = set()
        if primer_turno:
            etiquetas.add("primer_turno")
        if self.sit.corredor:
            etiquetas.add("corredor")
        return etiquetas

    def _anotar_tirada(self, tipo: str, r: CheckResult) -> None:
        self.reg.anotar(tipo, r.describir(), tirada=r)

    def _ofrecer_suerte(
        self, personaje: Personaje, r: CheckResult, rehacer
    ) -> CheckResult:
        """La Suerte del halfling: repetir una tirada de Ataque o Defensa fallida.

        No es una accion de turno, sino una oportunidad que aparece justo
        despues de fallar. La repeticion es definitiva aunque salga peor.
        """
        if r.exito or personaje.recursos.get("suerte", 0) <= 0:
            return r
        if personaje.clase.id != "halfling":
            return r

        gastar = Opcion(True, "Gastar un punto de Suerte", "la repeticion es definitiva")
        no = Opcion(False, f"Aceptar el resultado ({r.total} vs {r.dificultad})")
        # La opcion recomendada va primera: gastar si la vida esta en juego.
        en_peligro = r.tipo == "defensa" and personaje.vida <= self.enc.perfil.dano
        opciones = [gastar, no] if en_peligro else [no, gastar]

        if not self.decisor.elegir(Pregunta.crear(
            "suerte",
            f"{personaje.nombre} falla su {r.tipo} "
            f"(le quedan {personaje.recursos['suerte']} de Suerte).",
            opciones, personaje=personaje, tirada=r,
        )):
            return r

        personaje.gastar("suerte")
        nueva = rehacer()
        self.reg.anotar(
            "suerte",
            f"{personaje.nombre} gasta un punto de Suerte y repite: "
            f"{nueva.total} vs {nueva.dificultad} -> "
            + ("EXITO" if nueva.exito else "FALLO"),
        )
        return nueva

    # -- reaccion ---------------------------------------------------------- #

    def _reaccion_inicial(self) -> ResultadoCombate | None:
        """Devuelve un resultado si el combate no llega a empezar."""
        if self.sit.errante:
            self.reaccion = "lucha"
            self.reg.anotar(
                "sorpresa",
                f"{self.enc} caen sobre el grupo por sorpresa y atacan primero.",
            )
            return None

        eleccion = self.decisor.elegir(Pregunta.crear(
            "abordaje",
            f"Aparecen {self.enc}. ¿Que hace el grupo?",
            [
                Opcion("esperar", "Ver que hacen", "tira su tabla de Reacciones"),
                Opcion("atacar_ya", "Atacar de inmediato", "el grupo actua primero"),
            ],
            encuentro=self.enc,
        ))
        if eleccion == "atacar_ya":
            self.reaccion = "lucha"
            self.reg.anotar("abordaje", "El grupo ataca de inmediato.")
            self._monstruos_primero = False
            return None

        resultado = self.juego.reaccion(self.enc, self.rng)
        if resultado is None:
            self.reaccion = "lucha"
            return None
        self.reaccion = str(resultado.entrada.datos.get("reaccion", "lucha"))
        self.reg.anotar("reaccion", f"Reaccion: {resultado.texto}", reaccion=self.reaccion)
        return self._aplicar_reaccion(resultado.entrada.datos)

    def _aplicar_reaccion(self, datos: dict[str, Any]) -> ResultadoCombate | None:
        if self.reaccion not in RESUELVE:
            return ResultadoCombate(
                "pendiente", reaccion=self.reaccion, botin=False,
                detalle="esta reaccion la resuelve el flujo de exploracion",
            )

        if self.reaccion == "huir_si_superados":
            if self.monstruos_restantes < len(self.vivos):
                self.reaccion = "huir"
            else:
                self.reaccion = "lucha"
                self.reg.anotar("reaccion", "No los superan en numero: se quedan a luchar.")

        if self.reaccion == "huir":
            self.enc.huir()
            self.reg.anotar("huida_monstruos", f"{self.enc.nombre} da media vuelta y huye.")
            # Huir por reaccion no deja saqueo; huir por moral si.
            return ResultadoCombate("evitado", reaccion="huir", botin=False)

        if self.reaccion == "soborno":
            return self._soborno(datos)

        if self.reaccion == "durmiendo":
            self.reg.anotar("sorpresa", f"{self.enc.nombre} duerme: el primer ataque va a +2.")
            self._monstruos_primero = False
        return None

    def _soborno(self, datos: dict[str, Any]) -> ResultadoCombate | None:
        from runa.core.dice import roll

        if len(self.grupo.con_clase("enano")) >= 2:
            self.reg.anotar(
                "soborno",
                "Con dos o mas enanos en el grupo, sobornar es impensable: se lucha.",
            )
            self.reaccion = "lucha"
            return None

        if (por_monstruo := datos.get("oro_por_monstruo")) is not None:
            cantidad = roll(str(por_monstruo), self.rng).total * self.monstruos_restantes
        elif (fijo := datos.get("oro")) is not None:
            cantidad = roll(str(fijo), self.rng).total
        else:
            cantidad = max(int(datos.get("oro_minimo", 0)), self.grupo.oro)

        puede = self.grupo.oro >= cantidad
        opciones = [Opcion("luchar", "Negarse y luchar")]
        if puede:
            opciones.insert(0, Opcion("pagar", f"Pagar {cantidad} de oro"))
        eleccion = self.decisor.elegir(Pregunta.crear(
            "soborno",
            f"{self.enc.nombre} pide {cantidad} piezas de oro "
            f"(el grupo tiene {self.grupo.oro}).",
            opciones, cantidad=cantidad, puede_pagar=puede,
        ))
        if eleccion == "pagar":
            self._cobrar(cantidad)
            self.reg.anotar("soborno", f"El grupo paga {cantidad} de oro y evita el combate.")
            return ResultadoCombate("evitado", reaccion="soborno", botin=False)
        self.reg.anotar("soborno", "El grupo se niega a pagar." if puede
                        else "El grupo no puede pagar.")
        self.reaccion = "lucha"
        return None

    def _cobrar(self, cantidad: int) -> None:
        """Reparte el pago entre los personajes, empezando por el mas rico."""
        for personaje in sorted(self.grupo.miembros, key=lambda p: -p.oro):
            if cantidad <= 0:
                break
            pagado = min(personaje.oro, cantidad)
            personaje.oro -= pagado
            cantidad -= pagado

    # -- turnos ------------------------------------------------------------ #

    def _acciones_de(self, personaje: Personaje) -> list[Opcion]:
        opciones = [Opcion("atacar", "Atacar", personaje.arma.nombre if personaje.arma else "sin arma")]
        preparados = self.juego.hechizos_preparados(personaje)
        for habilidad in self.juego.habilidades.para(personaje.clase.id, "turno"):
            if habilidad.gasta and personaje.recursos.get(habilidad.gasta, 0) <= 0:
                continue
            if habilidad.gasta == "hechizos" and habilidad.id not in preparados:
                continue
            opciones.append(Opcion(f"habilidad:{habilidad.id}", habilidad.nombre,
                                   f"gasta {habilidad.gasta}" if habilidad.gasta else ""))
        opciones.append(Opcion("nada", "No hacer nada"))
        return opciones

    def _turno_grupo(self, primer_turno: bool) -> None:
        for personaje in list(self.vivos):
            if not self.enc.vivo:
                return
            eleccion = self.decisor.elegir(Pregunta.crear(
                "accion",
                f"Turno de {personaje.nombre} ({personaje.vida}/{personaje.vida_max} Vida) "
                f"contra {self.enc}.",
                self._acciones_de(personaje),
                personaje=personaje, encuentro=self.enc,
            ))
            if eleccion == "nada":
                self.reg.anotar("accion", f"{personaje.nombre} se mantiene a la espera.")
            elif eleccion == "atacar":
                self._atacar(personaje, primer_turno)
            else:
                self.juego.usar_habilidad(
                    eleccion.split(":", 1)[1], personaje, self, primer_turno=primer_turno
                )

    def etiquetas_de_ataque(self, primer_turno: bool = False) -> set[str]:
        etiquetas = self._etiquetas_base(primer_turno)
        if (
            self.enc.perfil.es_esbirro
            and len(self.vivos) > self.monstruos_restantes
        ):
            etiquetas.add("superados_en_numero")
        if primer_turno and self.reaccion == "durmiendo":
            etiquetas.add("monstruo_dormido")
        return etiquetas

    def _atacar(self, personaje: Personaje, primer_turno: bool, ventaja: int = 1) -> CheckResult | None:
        try:
            r = self.juego.atacar(
                personaje, self.enc.amenaza, self.rng,
                etiquetas=self.etiquetas_de_ataque(primer_turno), ventaja=ventaja,
            )
        except AccionProhibida as e:
            self.reg.anotar("prohibido", f"{personaje.nombre} no puede atacar: {e.motivos[0]}")
            return None
        self._anotar_tirada("ataque", r)
        r = self._ofrecer_suerte(personaje, r, lambda: self.juego.atacar(
            personaje, self.enc.amenaza, self.rng,
            etiquetas=self.etiquetas_de_ataque(primer_turno), ventaja=ventaja,
        ))
        if r.exito:
            heridas = 2 if (ventaja > 1 and self.enc.perfil.es_jefe) else 1
            self.herir_monstruo(heridas, por=personaje.nombre)
        return r

    def herir_monstruo(self, heridas: int, por: str = "", por_hechizo: bool = False) -> int:
        aplicadas = self.enc.herir(heridas)
        if self.enc.perfil.es_esbirro:
            texto = f"Caen {aplicadas} {self.enc.nombre.lower()}; quedan {self.enc.cantidad}."
        else:
            texto = (f"{self.enc.nombre} pierde {aplicadas} de Vida "
                     f"(le quedan {self.enc.vida}).")
        self.reg.anotar("dano", (f"{por}: " if por else "") + texto)
        if por_hechizo and aplicadas:
            self._gancho("tras_hechizo", aplicadas)
        return aplicadas

    # -- moral ------------------------------------------------------------- #

    def _comprobar_moral(self) -> None:
        if self.moral_probada or self.reaccion == "lucha_hasta_muerte":
            return
        if not self.enc.vivo or not self.enc.bajo_de_moral:
            return
        aguanta = self.juego.moral(self.enc, self.rng)
        if aguanta is None:
            return
        self.moral_probada = True
        self.reg.anotar(
            "moral",
            f"{self.enc.nombre} aguanta la moral." if aguanta
            else f"{self.enc.nombre} rompe filas y huye.",
        )

    # -- turno de los monstruos -------------------------------------------- #

    def _numero_de_ataques(self) -> int:
        if not self.enc.vivo:
            return 0
        if self.enc.perfil.es_esbirro:
            return self.enc.cantidad
        return max(1, self.enc.perfil.ataques)

    def _odiados(self) -> list[Personaje]:
        clases = {
            self._odios[e] for e in self.enc.perfil.etiquetas if e in self._odios
        }
        return [p for p in self.vivos if p.clase.id in clases]

    def repartir_ataques(self, n: int, prioridad: str = "normal") -> list[Personaje]:
        """Decide a quien golpea cada ataque, segun las reglas de la pagina 63."""
        vivos = self.vivos
        if not vivos or n <= 0:
            return []

        if self.sit.corredor:
            # En un pasillo atacan dos monstruos como maximo. Los errantes caen
            # sobre la retaguardia; el resto, sobre los dos de cabeza.
            frente = (vivos[-2:] if self.sit.errante else vivos[:2])
            if len(vivos) == 1:
                return [vivos[0]] * min(2, n)     # a uno solo le llueven dos
            return frente[: min(2, n)]

        if n < len(vivos):
            # Cada monstruo ataca a uno distinto y el jugador elige quien se libra.
            candidatos = list(vivos)
            while len(candidatos) > n:
                a_salvo = self.decisor.elegir(Pregunta.crear(
                    "a_salvo",
                    f"Hay {n} ataques para {len(candidatos)} personajes. "
                    "¿Quien se queda fuera?",
                    [Opcion(p.nombre, p.nombre, f"{p.vida}/{p.vida_max} Vida")
                     for p in candidatos],
                ))
                candidatos = [p for p in candidatos if p.nombre != a_salvo]
            return candidatos

        objetivos = list(vivos)                    # todos reciben uno
        sobrantes = n - len(vivos)
        if sobrantes <= 0:
            return objetivos

        if prioridad == "heridos":                 # al huir, primero los mas tocados
            cola = sorted(vivos, key=lambda p: (p.vida - p.vida_max, p.nombre))
        else:                                      # los ataques extra van al odiado
            cola = self._odiados() or self.rng.shuffled(vivos)
        for i in range(sobrantes):
            objetivos.append(cola[i % len(cola)])
        return objetivos

    def _gancho(self, punto: str, *args) -> Any:
        gancho = getattr(self.juego.ganchos, punto).get(self.enc.perfil.id)
        return gancho(self, self.enc, *args) if gancho is not None else None

    def _gancho_antes(self) -> None:
        self._gancho("antes")

    def _turno_monstruos(
        self, etiquetas: set[str] | None = None, prioridad: str = "normal",
        maximo: int | None = None,
    ) -> None:
        # Regeneraciones y alientos ocurren antes que los ataques normales, y
        # el aliento puede sustituirlos por completo.
        gancho = self.juego.ganchos.turno.get(self.enc.perfil.id)
        if gancho is not None and gancho(self, self.enc):
            return
        n = self._numero_de_ataques()
        if maximo is not None:
            n = min(n, maximo)
        objetivos = self.repartir_ataques(n, prioridad)
        if not objetivos:
            return
        self.reg.anotar(
            "turno_monstruos",
            f"{self.enc.nombre} ataca a " + ", ".join(p.nombre for p in objetivos),
        )
        etiquetas = set(etiquetas or self._etiquetas_base())
        if self.sit.errante and self.ronda <= 1:
            etiquetas.add("sorpresa")              # el escudo no cuenta
        if self.ronda <= 1:
            etiquetas.add("primer_turno")

        for personaje in objetivos:
            if not personaje.vivo:
                continue
            r = self.juego.defender(personaje, self.enc.amenaza, self.rng,
                                    etiquetas=etiquetas)
            self._anotar_tirada("defensa", r)
            r = self._ofrecer_suerte(personaje, r, lambda p=personaje: self.juego.defender(
                p, self.enc.amenaza, self.rng, etiquetas=etiquetas,
            ))
            if not r.exito:
                # Algunos monstruos no hacen dano: la Plaga del Hierro roba.
                if not self._gancho("al_herir", personaje):
                    heridas = personaje.herir(self.enc.perfil.dano)
                    if personaje.vivo:
                        self.reg.anotar(
                            "herida",
                            f"{personaje.nombre} recibe {heridas} herida(s) "
                            f"({personaje.vida}/{personaje.vida_max} Vida).",
                        )
                    else:
                        # La muerte de un personaje merece su propia linea.
                        self.reg.anotar(
                            "muerte",
                            f"{personaje.nombre} cae y no vuelve a levantarse.",
                        )
                self._gancho("tras_herir", personaje)

    # -- salir del combate -------------------------------------------------- #

    def _salida(self) -> ResultadoCombate | None:
        if motivo := self.marcas.get("sin_salida"):
            self.reg.anotar("atrapados", f"No hay escapatoria: {motivo}.")
            return None
        opciones = [Opcion("luchar", "Seguir luchando")]
        if self.sit.puerta:
            opciones.append(Opcion("retirada", "Retirarse", "+1 a la Defensa, un golpe"))
        opciones.append(Opcion("huida", "Huir", "sin escudo, un golpe por monstruo"))
        eleccion = self.decisor.elegir(Pregunta.crear(
            "salir_del_combate",
            f"Ronda {self.ronda}. {self.enc} frente a "
            + ", ".join(f"{p.nombre} {p.vida}/{p.vida_max}" for p in self.vivos),
            opciones, encuentro=self.enc,
        ))
        if eleccion == "luchar":
            return None
        if eleccion == "retirada":
            self.reg.anotar("retirada", "El grupo se retira y cierra la puerta.")
            self._turno_monstruos(etiquetas={"retirada"}, maximo=len(self.vivos))
            return ResultadoCombate("retirada", self.ronda, self.reaccion, botin=False)
        self.reg.anotar("huida", "El grupo huye.")
        self._turno_monstruos(etiquetas={"huida"}, prioridad="heridos")
        return ResultadoCombate("huida", self.ronda, self.reaccion, botin=False)

    # -- bucle -------------------------------------------------------------- #

    def _cerrar(self, resultado: ResultadoCombate) -> ResultadoCombate:
        for personaje in self.grupo.miembros:
            personaje.limpiar_estados("combate")
        return resultado

    def _fin(self) -> ResultadoCombate | None:
        if not self.vivos:
            self.reg.anotar("derrota", "El grupo ha caido.")
            return ResultadoCombate("derrota", self.ronda, self.reaccion, botin=False)
        if not self.enc.vivo:
            huyeron = self.enc.huido
            self.reg.anotar(
                "victoria",
                f"{self.enc.nombre} huye del combate." if huyeron
                else f"{self.enc.nombre} ha sido derrotado.",
            )
            # FAQ: "un monstruo que huye cuenta como derrotado, y por lo tanto
            # cuenta para propositos de XP". Tambien se tira su tesoro. Los
            # errantes dan XP pero nunca llevan tesoro encima.
            if not huyeron:
                self._gancho("al_morir")
            return ResultadoCombate(
                "victoria", self.ronda, self.reaccion,
                botin=not self.sit.errante,
                xp=self.enc.perfil.xp,
                sucesos=list(self.sucesos),
                refuerzos=list(self.refuerzos),
            )
        return None

    def resolver(self, limite_rondas: int = 50) -> ResultadoCombate:
        self._monstruos_primero = True
        self.reg.anotar("combate_inicio", f"Combate contra {self.enc}.")

        if (resultado := self._reaccion_inicial()) is not None:
            return self._cerrar(resultado)
        self._gancho_antes()
        if (resultado := self._fin()) is not None:
            return self._cerrar(resultado)

        while self.ronda < limite_rondas:
            self.ronda += 1
            primer_turno = self.ronda == 1

            if primer_turno and self._monstruos_primero:
                self._disparo_de_arcos()
                if (resultado := self._fin()) is not None:
                    return self._cerrar(resultado)
                self._turno_monstruos()
                if (resultado := self._fin()) is not None:
                    return self._cerrar(resultado)

            if not primer_turno or not self._monstruos_primero:
                if (resultado := self._salida()) is not None:
                    return self._cerrar(resultado)

            self._turno_grupo(primer_turno)
            if (resultado := self._fin()) is not None:
                return self._cerrar(resultado)

            self._comprobar_moral()
            if (resultado := self._fin()) is not None:
                return self._cerrar(resultado)

            if not (primer_turno and self._monstruos_primero):
                self._turno_monstruos()
                if (resultado := self._fin()) is not None:
                    return self._cerrar(resultado)

        self.reg.anotar("tablas", "El combate se alarga sin desenlace.")
        return self._cerrar(ResultadoCombate("pendiente", self.ronda, self.reaccion, botin=False,
                                detalle="se alcanzo el limite de rondas"))

    def _disparo_de_arcos(self) -> None:
        """El arco dispara antes que los monstruos, aunque estos vayan primero."""
        arqueros = [p for p in self.vivos
                    if p.arma and "a_distancia" in p.arma.etiquetas]
        for arquero in arqueros:
            if not self.enc.vivo:
                return
            self.reg.anotar("arco", f"{arquero.nombre} dispara antes del choque.")
            self._atacar(arquero, primer_turno=True)
