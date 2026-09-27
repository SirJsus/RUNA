"""El bucle de exploracion: entrar, generar salas, resolver lo que hay y salir.

Como el combate, se escribe una sola vez: todas las elecciones salen por el
puerto `Decisor`, asi que vale para el modo arbitro y para el automatico.

Sobre el mapa hay dos modos, y se juega igual con los dos:

  * **con rejilla** (por defecto): el programa conoce la silueta de cada loseta
    d66, la encaja en la hoja y dibuja la mazmorra. Solo pregunta cuando una
    loseta cabe de varias formas.
  * **solo grafo**: no dibuja nada y te pregunta la forma de la sala que estas
    dibujando tu en papel. Mas rapido de llevar.
"""

from __future__ import annotations

from typing import Any

from runa.core.bestiary import Encuentro, Tesoro
from runa.core.checks import AccionProhibida
from runa.core.decisions import Decisor, Opcion, Pregunta
from runa.core.dice import roll
from runa.core.entities import Personaje
from runa.core.mapa import Sala
from runa.games.cco.combate import Situacion

# Tablas de las que sale un monstruo listo para pelear.
TABLAS_MONSTRUO = frozenset({"bichos", "esbirros", "jefes", "monstruos_extranos"})


class Exploracion:
    def __init__(self, partida: Any, decisor: Decisor) -> None:
        self.p = partida
        self.juego = partida.juego
        self.decisor = decisor

    # -- atajos ------------------------------------------------------------- #

    @property
    def rng(self):
        # Se lee de la partida, no se copia: si la partida cambia de fuente de
        # azar (al cargarla, por ejemplo), aqui no puede quedarse una vieja.
        return self.p.rng

    @rng.setter
    def rng(self, fuente) -> None:
        self.p.rng = fuente

    @property
    def mapa(self):
        return self.p.mapa

    @property
    def grupo(self):
        return self.p.grupo

    @property
    def sala(self) -> Sala:
        return self.mapa.sala_actual

    def anotar(self, tipo: str, texto: str, **datos):
        return self.p.anotar(tipo, texto, **datos)

    def preguntar(self, id: str, texto: str, opciones, **ctx):
        return self.decisor.elegir(Pregunta.crear(id, texto, opciones, **ctx))

    # -- construccion de la mazmorra ---------------------------------------- #

    @property
    def rejilla(self):
        return self.mapa.rejilla

    def _preguntar_forma(self, titulo: str) -> tuple[str, int]:
        """Modo solo grafo: el jugador dibuja, el arbitro solo necesita la forma."""
        tipo = self.preguntar("plano_tipo", titulo, [
            Opcion("habitacion", "Habitacion", "2 o mas cuadrados de ancho"),
            Opcion("corredor", "Corredor", "un solo cuadrado de ancho"),
        ])
        salidas = self.preguntar(
            "plano_salidas", "¿Cuantas salidas tiene?",
            [Opcion(n, str(n)) for n in (1, 2, 3, 4)],
        )
        return tipo, int(salidas)

    def entrar(self) -> Sala:
        tirada = self.juego.tablas.tirar("sala_entrada", self.rng)
        plano_id = str(tirada.valor)
        if self.rejilla is None:
            tipo, salidas = self._preguntar_forma(
                f"Sala de entrada: plano {plano_id}. ¿Que forma tiene?"
            )
            sala = self.mapa.crear("entrada", salidas=salidas, plano=plano_id)
        else:
            plano = self.juego.planos.entrada(plano_id)
            sala = self.mapa.crear("entrada", salidas=len(plano.salidas),
                                   plano=plano_id, origen=(0, 0))
            # "Dibuja esta entrada en el centro del borde inferior de la hoja."
            pieza = self.rejilla.colocar_primera(sala.id, plano)
            sala.origen = pieza.origen
        sala.contenido = "Entrada de la mazmorra."
        sala.resuelta = True
        self.anotar("entrada", f"Sala {sala.id}: entrada (plano {plano_id})")
        return sala

    def abrir(self, salida: int, secreta: bool = False) -> Sala:
        """Cruza una puerta sin explorar: genera la sala nueva y la conecta."""
        plano_id = str(roll("d66", self.rng).total)
        if self.rejilla is None:
            return self._abrir_en_grafo(salida, plano_id, secreta)
        return self._abrir_en_rejilla(salida, plano_id, secreta)

    def _abrir_en_grafo(self, salida: int, plano_id: str, secreta: bool) -> Sala:
        origen = self.sala
        tipo, salidas = self._preguntar_forma(f"Al otro lado hay el plano {plano_id}.")
        nueva = self.mapa.crear(tipo, salidas=salidas, plano=plano_id, secreta=secreta)
        self.mapa.conectar(origen.id, salida, nueva.id)
        self.mapa.mover(nueva.id)
        self.anotar("sala", f"Sala {nueva.id}: {tipo} (plano {plano_id})")
        return nueva

    def _abrir_en_rejilla(self, indice: int, plano_id: str, secreta: bool) -> Sala:
        origen = self.sala
        libres = self.rejilla.salidas_libres(origen.id)
        celda, salida = libres[indice]
        plano = self.juego.planos[plano_id]

        opciones = self.rejilla.colocaciones(plano, celda, salida.lado)
        recortada = False
        if len(opciones) > 1:
            elegida = opciones[self._elegir_colocacion(plano_id, opciones)]
        elif opciones:
            elegida = opciones[0]
        else:
            # "Si la tirada crea una estancia que no cabe, corta la habitacion."
            elegida = self.rejilla.recorte(plano, celda, salida.lado)
            recortada = True
            if elegida is None:
                self.anotar("sala", f"El plano {plano_id} no cabe: la puerta esta tapiada.")
                origen.salidas = max(1, origen.salidas)
                self.rejilla.ocupadas.setdefault(
                    (celda[0] + salida.vector[0], celda[1] + salida.vector[1]), origen.id
                )
                return origen

        nueva = self.mapa.crear(plano.tipo, salidas=len(elegida.plano.salidas),
                                plano=plano_id, secreta=secreta,
                                origen=elegida.origen, giros=elegida.giros,
                                recortada=recortada)
        pieza = self.rejilla.colocar(nueva.id, elegida, recortar=recortada)
        nueva.recortada = pieza.recortada
        nueva.salidas = max(1, len(pieza.salidas_mundo()))
        self.mapa.conectar(origen.id, origen.salidas_libres[0], nueva.id)
        self.mapa.mover(nueva.id)

        detalle = f"Sala {nueva.id}: {plano.tipo} (plano {plano_id})"
        if elegida.giros:
            detalle += f", {90 * elegida.giros}°"
        if pieza.recortada:
            detalle += " — no cupo entera: callejon sin salida"
        self.anotar("sala", detalle)
        return nueva

    def _elegir_colocacion(self, plano_id: str, opciones) -> int:
        """La unica pregunta que la rejilla necesita: como encaja la loseta."""
        return self.preguntar(
            "colocacion",
            f"El plano {plano_id} encaja de {len(opciones)} formas. ¿Cual dibujas?",
            [Opcion(i, o.descripcion(), f"{len(o.plano.salidas)} salidas")
             for i, o in enumerate(opciones)],
        )


    # -- contenido de la sala ----------------------------------------------- #

    def resolver_sala(self, sala: Sala | None = None) -> None:
        sala = sala or self.sala
        if sala.resuelta:
            return
        sala.resuelta = True
        # "Si es un corredor, vacio" solo corta las entradas que lo dicen.
        encadenar = lambda entrada: not (sala.es_corredor and entrada.datos.get("si_corredor"))
        resultado = self.juego.tablas.tirar(
            "contenido_habitacion", self.rng, encadenar=encadenar
        )
        sala.contenido = resultado.texto
        self.anotar("contenido", resultado.texto)

        if sala.es_corredor and resultado.entrada.datos.get("si_corredor"):
            sala.contenido = "Vacio (corredor)."
            self.anotar("contenido", "Es un corredor: esta vacio.")
            return

        for nodo in resultado.recorrer():
            self._despachar(nodo, sala)

    def _despachar(self, nodo, sala: Sala) -> None:
        datos = nodo.entrada.datos
        if nodo.tabla in TABLAS_MONSTRUO:
            self._encuentro(nodo, sala)
        elif nodo.tabla == "tesoros":
            self._tesoro_suelto(nodo)
        elif nodo.tabla == "trampas":
            self.resolver_trampa(nodo)
        elif nodo.tabla == "caracteristicas_especiales":
            self._caracteristica(datos, nodo.texto)
        elif nodo.tabla in ("eventos_especiales",):
            self._evento(datos, nodo.texto)
        elif datos.get("jefe_fijo"):
            perfil = self.juego.bestiario[datos["jefe_fijo"]]
            self._pelear(perfil.generar(self.rng), sala, es_jefe=True)

    # -- encuentros ---------------------------------------------------------- #

    def _encuentro(self, nodo, sala: Sala, errante: bool = False) -> None:
        encuentro = self.juego.encuentro_desde(nodo, self.rng)
        es_jefe = encuentro.perfil.es_jefe
        if es_jefe and not errante:
            self._comprobar_jefe_final(encuentro)
        self._pelear(encuentro, sala, es_jefe=es_jefe, errante=errante)

    def _comprobar_jefe_final(self, encuentro: Encuentro) -> None:
        """d6 + 1 por cada jefe ya visto; con 6+ o mazmorra completa, es el final."""
        av = self.p.aventura
        av.jefes_vistos += 1
        if av.jefe_final_encontrado:
            return
        tirada = roll("d6", self.rng)
        total = tirada.total + (av.jefes_vistos - 1)
        if total >= 6 or self.mapa.completo:
            av.jefe_final_encontrado = True
            self.anotar(
                "jefe_final",
                f"¡{encuentro.nombre} es el JEFE FINAL! ({tirada.detail} "
                f"+{av.jefes_vistos - 1} = {total}).",
            )

    def _pelear(self, encuentro: Encuentro, sala: Sala, *, es_jefe: bool,
                errante: bool = False) -> None:
        sala.limpia = False
        situacion = Situacion(
            corredor=sala.es_corredor, errante=errante,
            puerta=not sala.es_corredor,
        )
        # El enano huele el oro antes de decidir si ataca.
        self._olfato_de_enano(encuentro)

        resultado = self.juego.combatir(
            self.grupo, encuentro, self.rng, decisor=self.decisor,
            registro=self.p.registro, situacion=situacion,
        )
        if encuentro.perfil.es_esbirro and resultado.desenlace == "victoria":
            self.p.aventura.encuentros_esbirros += 1

        if resultado.desenlace in ("victoria", "evitado"):
            sala.limpia = True
        if resultado.desenlace == "victoria":
            if resultado.botin:
                self._repartir(self.juego.saquear(
                    encuentro.perfil.tesoro, self.rng,
                    sin_objetos_magicos=encuentro.perfil.sin_objetos_magicos,
                ))
            if resultado.xp:
                self.conceder_xp("derrotar a " + encuentro.nombre)
            if es_jefe and self.p.aventura.jefe_final_encontrado and encuentro.perfil.es_jefe:
                self.p.aventura.jefe_final_derrotado = True
        self._contar_encuentros_de_esbirros()

        for suceso in resultado.sucesos:
            if suceso == "pista" and self.grupo.vivos:
                self._pista()
        # Las momias que se levantan de los caidos se combaten a continuacion.
        for id in resultado.refuerzos:
            if not self.grupo.vivos:
                break
            self.anotar("refuerzos", f"Se alza {self.juego.bestiario[id].nombre}.")
            self._pelear(self.juego.bestiario[id].generar(self.rng), sala,
                         es_jefe=self.juego.bestiario[id].es_jefe)

    def _olfato_de_enano(self, encuentro: Encuentro) -> None:
        for enano in self.grupo.con_clase("enano"):
            if not enano.vivo:
                continue
            tirada = roll("d6", self.rng)
            if tirada.total + enano.nivel >= 6:
                t = encuentro.perfil.tesoro
                self.anotar(
                    "olfato",
                    f"{enano.nombre} huele el tesoro de {encuentro.nombre}: "
                    + (f"{t.tiradas} tirada(s) con {t.modificador:+d}" if t
                       else "no lleva nada"),
                )
            return

    def _contar_encuentros_de_esbirros(self) -> None:
        av = self.p.aventura
        if av.encuentros_esbirros and av.encuentros_esbirros % 10 == 0:
            self.anotar("xp", "Diez encuentros contra esbirros superados.")
            self.conceder_xp("sobrevivir a diez encuentros con esbirros", modificador=-1)

    # -- tesoros y reparto ---------------------------------------------------- #

    def _tesoro_suelto(self, nodo) -> None:
        self._repartir(self.juego.resolver_tesoro(nodo, self.rng))

    def _repartir(self, botin) -> None:
        vivos = list(self.grupo.vivos)
        if not vivos:
            self.anotar("botin", "No queda nadie para recoger el botin.")
            return
        if botin.vacio:
            self.anotar("botin", "No hay tesoro.")
            return
        if botin.oro and not botin.objetos:
            pass                     # el reparto de oro ya lo cuenta debajo
        else:
            self.anotar("botin", f"Botin: {botin}")
        if botin.oro:
            # Los enanos siempre reciben al menos una moneda del reparto.
            reparto = self._repartir_oro(botin.oro, vivos)
            self.anotar("botin", "Oro: " + ", ".join(
                f"{p.nombre} +{o}" for p, o in reparto if o))
        for objeto in botin.objetos:
            candidatos = [p for p in vivos if p.clase.permite_objeto(objeto)] or vivos
            elegido = self.preguntar(
                "asignar_tesoro", f"¿Quien se lleva {objeto.nombre}?",
                [Opcion(p.nombre, p.nombre, f"{p.oro} oro") for p in candidatos],
                objeto=objeto,
            )
            personaje = self.grupo.por_nombre(elegido)
            personaje.anadir(objeto)
            self.anotar("botin", f"{personaje.nombre} se queda {objeto.nombre}.")


    def _repartir_oro(self, oro: int, vivos: list[Personaje]) -> list[tuple[Personaje, int]]:
        reparto = {p.nombre: 0 for p in vivos}
        restante = oro
        for enano in [p for p in vivos if p.clase.id == "enano"]:
            if restante <= 0:
                break
            reparto[enano.nombre] += 1
            restante -= 1
        base, resto = divmod(restante, len(vivos))
        for i, p in enumerate(vivos):
            reparto[p.nombre] += base + (1 if i < resto else 0)
        for p in vivos:
            p.oro += reparto[p.nombre]
        return [(p, reparto[p.nombre]) for p in vivos]

    # -- trampas -------------------------------------------------------------- #

    def resolver_trampa(self, nodo) -> None:
        datos = nodo.entrada.datos
        nivel = int(datos.get("nivel", 3))
        amenaza = self.juego.amenaza("Trampa", nivel, ["trampa"])
        self.anotar("trampa", nodo.texto)

        if self._desarmar(amenaza):
            return
        for victima in self._victimas_de_trampa(datos):
            r = self.juego.tirar("salvacion", victima, self.rng, amenaza=amenaza)
            self.anotar("salvacion", r.describir(), tirada=r)
            if not r.exito:
                victima.herir(1)
                self.anotar("herida", f"{victima.nombre} pierde 1 Vida "
                                      f"({victima.vida}/{victima.vida_max}).")

    def _desarmar(self, amenaza) -> bool:
        picaros = [p for p in self.grupo.vivos if p.clase.id == "picaro"]
        if not picaros:
            return False
        opciones = [Opcion(p.nombre, f"{p.nombre} intenta desarmarla") for p in picaros]
        opciones.append(Opcion("", "Nadie la toca"))
        elegido = self.preguntar(
            "desarmar_trampa", f"Trampa de nivel {amenaza.nivel}. ¿Quien la desarma?",
            opciones,
        )
        if not elegido:
            return False
        picaro = self.grupo.por_nombre(elegido)
        try:
            r = self.juego.tirar("desarmar_trampa", picaro, self.rng, amenaza=amenaza)
        except AccionProhibida as e:
            self.anotar("prohibido", f"{picaro.nombre} no puede: {e.motivos[0]}")
            return False
        self.anotar("desarmar", r.describir(), tirada=r)
        if r.exito:
            self.anotar("trampa", f"{picaro.nombre} desarma la trampa.")
            return True
        return False

    def _victimas_de_trampa(self, datos: dict) -> list[Personaje]:
        vivos = self.grupo.vivos
        if not vivos:
            return []
        objetivo = datos.get("objetivo", "aleatorio")
        cuantos = int(datos.get("objetivos", 1))
        if objetivo == "todos":
            return vivos
        if objetivo == "primero":
            return vivos[:1]
        if objetivo == "ultimo":
            return vivos[-1:]
        return self.rng.shuffled(vivos)[:cuantos]

    # -- caracteristicas y eventos -------------------------------------------- #

    def _caracteristica(self, datos: dict, texto: str) -> None:
        id = datos.get("id", "")
        self.anotar("caracteristica", texto)
        if id == "fuente":
            if not self.p.aventura.gastar("fuente"):
                self.anotar("caracteristica", "Ya bebieron de una fuente: no hace nada.")
                return
            for p in self.grupo.vivos:
                if p.curar(1):
                    self.anotar("curacion", f"{p.nombre} recupera 1 Vida en la fuente.")
        elif id == "templo_bendito":
            elegido = self.preguntar(
                "templo", "¿Quien recibe la bendicion del templo?",
                [Opcion(p.nombre, p.nombre) for p in self.grupo.vivos],
            )
            self.grupo.por_nombre(elegido).estados.append(self.juego.estado("bendecido"))
            self.anotar("caracteristica", f"{elegido} queda bendecido (+1 contra no muertos).")
        elif id == "altar_maldito":
            victima = self.rng.choice(self.grupo.vivos)
            victima.estados.append(self.juego.estado("maldito"))
            self.anotar("caracteristica", f"{victima.nombre} queda maldito (-1 a la Defensa).")
        else:
            # Armeria, estatua y puzzle piden decisiones que resuelve el jugador.
            self.anotar("pendiente", f"A resolver por el jugador: {texto}")

    def _evento(self, datos: dict, texto: str) -> None:
        id = datos.get("id", "")
        unico = bool(datos.get("unica_por_aventura"))
        if unico and not self.p.aventura.gastar(id):
            self.anotar("evento", f"{texto[:40]}... ya habia ocurrido: no se repite.")
            return
        self.anotar("evento", texto)
        if id == "fantasma":
            amenaza = self.juego.amenaza("Miedo", 4, ["miedo"])
            for p in self.grupo.vivos:
                r = self.juego.tirar("salvacion", p, self.rng, amenaza=amenaza)
                self.anotar("salvacion", r.describir(), tirada=r)
                if not r.exito:
                    p.herir(1)
                    self.anotar("herida", f"{p.nombre} pierde 1 Vida de puro terror.")
        elif id == "curandero":
            self._curandero()
        elif id not in ("monstruos_errantes", "trampa"):
            self.anotar("pendiente", f"A resolver por el jugador: {texto}")

    def _curandero(self) -> None:
        heridos = [p for p in self.grupo.vivos if p.herido]
        while heridos and self.grupo.oro >= 10:
            elegido = self.preguntar(
                "curandero", "El curandero cobra 10 de oro por punto de Vida. ¿A quien?",
                [Opcion(p.nombre, p.nombre, f"{p.vida}/{p.vida_max}") for p in heridos]
                + [Opcion("", "Basta")],
            )
            if not elegido:
                return
            personaje = self.grupo.por_nombre(elegido)
            if personaje.oro < 10:
                self.anotar("curandero", f"{personaje.nombre} no tiene 10 de oro.")
                return
            personaje.oro -= 10
            personaje.curar(1)
            self.anotar("curandero", f"{personaje.nombre} paga 10 y recupera 1 Vida.")
            heridos = [p for p in self.grupo.vivos if p.herido]

    # -- busqueda -------------------------------------------------------------- #

    def buscar(self) -> None:
        sala = self.sala
        if sala.buscada:
            self.anotar("busqueda", f"La sala {sala.id} ya se registro.")
            return
        sala.buscada = True
        modificador = -1 if sala.es_corredor else 0
        resultado = self.juego.tablas.tirar(
            "busqueda_habitacion_vacia", self.rng, modificador=modificador,
            encadenar=False,
        )
        self.anotar("busqueda", f"Registran la sala {sala.id}: {resultado.texto}")
        if resultado.valor <= 1:
            self._monstruos_errantes()
        elif resultado.valor >= 5:
            self._hallazgo(sala)

    def _hallazgo(self, sala: Sala) -> None:
        eleccion = self.preguntar("buscar_hallazgo", "El registro da fruto. ¿Que es?", [
            Opcion("tesoro", "Tesoro oculto", "3d6 x 3d6 de oro, con complicacion"),
            Opcion("puerta", "Puerta secreta", "una sala mas, y quiza una salida"),
            Opcion("pista", "Una pista", "tres pistas dan un secreto y una tirada de XP"),
        ])
        if eleccion == "tesoro":
            self._tesoro_oculto(sala)
        elif eleccion == "puerta":
            sala.salidas += 1
            self.anotar("secreto", f"Puerta secreta en la sala {sala.id}.")
            atajo = roll("d6", self.rng)
            if atajo.total == 6:
                sala.anotar("atajo seguro fuera de la mazmorra")
                self.anotar("secreto", "¡La puerta esconde un atajo seguro al exterior!")
        else:
            self._pista()

    def _tesoro_oculto(self, sala: Sala) -> None:
        complicacion = self.juego.tablas.tirar(
            "complicacion_tesoro_oculto", self.rng, encadenar=False
        )
        self.anotar("secreto", f"Complicacion: {complicacion.texto}")
        if complicacion.valor <= 2:
            self._monstruos_errantes()
        elif complicacion.entrada.datos.get("trampa_nivel_igual_a_la_tirada"):
            amenaza = self.juego.amenaza("Trampa del tesoro", complicacion.valor, ["trampa"])
            if not self._desarmar(amenaza):
                victima = self.rng.choice(self.grupo.vivos)
                r = self.juego.tirar("salvacion", victima, self.rng, amenaza=amenaza)
                self.anotar("salvacion", r.describir(), tirada=r)
                if not r.exito:
                    heridas = 2 if r.tirada.dice[0].rolls[0] == 1 else 1
                    victima.herir(heridas)
                    self.anotar("herida", f"{victima.nombre} pierde {heridas} Vida.")
        else:
            self._fantasma_guardian()

        if not self.grupo.vivos:
            return          # la complicacion se llevo al grupo por delante
        oro = roll("3d6x3d6", self.rng)
        if sala.secreta:
            oro_total = oro.total * 2      # tras una puerta secreta, el oro se dobla
            self.anotar("botin", f"Oro doblado por venir de una sala secreta.")
        else:
            oro_total = oro.total
        from runa.games.cco.juego import Botin
        self._repartir(Botin(oro=oro_total, notas=[f"{oro_total} de oro oculto ({oro.detail})"]))

    def _fantasma_guardian(self) -> None:
        nivel = roll("d3+1", self.rng).total
        amenaza = self.juego.amenaza("Fantasma guardian", nivel, ["no_muerto", "fantasma"])
        clerigos = [p for p in self.grupo.vivos if p.clase.id == "clerigo"]
        if clerigos:
            r = self.juego.tirar("hechizo", clerigos[0], self.rng, amenaza=amenaza)
            self.anotar("fantasma", r.describir(), tirada=r)
            if r.exito:
                self.anotar("fantasma", f"{clerigos[0].nombre} disipa al fantasma.")
                return
        for p in self.grupo.vivos:
            p.herir(1)
        self.anotar("fantasma", "El fantasma se cobra 1 Vida de cada personaje y desaparece.")

    def _pista(self) -> None:
        elegido = self.preguntar(
            "pista", "¿Quien encuentra la pista?",
            [Opcion(p.nombre, p.nombre,
                    f"{self.p.campana.pistas.get(p.nombre, 0)} pistas")
             for p in self.grupo.vivos],
        )
        pistas = self.p.campana.pistas.get(elegido, 0) + 1
        self.p.campana.pistas[elegido] = pistas
        self.anotar("pista", f"{elegido} encuentra una pista ({pistas} de 3).")
        if pistas >= 3:
            self.p.campana.pistas[elegido] = 0
            self.anotar("pista", f"¡{elegido} descubre un gran secreto!")
            self.conceder_xp(f"el gran secreto de {elegido}", solo=elegido)

    def _monstruos_errantes(self) -> None:
        self.anotar("errantes", "¡Monstruos errantes!")
        # "Si sale un Dragon, vuelve a tirar": los dragones no vagan.
        for _ in range(20):
            nodo = self.juego.tablas.tirar("monstruo_errante", self.rng)
            hoja = [n for n in nodo.recorrer() if n.tabla in TABLAS_MONSTRUO]
            if not hoja:
                return
            ids = hoja[-1].entrada.datos.get("monstruo") or []
            ids = [ids] if isinstance(ids, str) else ids
            if all(self.juego.bestiario[i].errante for i in ids):
                self._encuentro(hoja[-1], self.sala, errante=True)
                return

    # -- experiencia ------------------------------------------------------------ #

    def conceder_xp(self, motivo: str, modificador: int = 0, solo: str = "") -> None:
        self.p.xp_pendientes += 1
        self.anotar("xp", f"Tirada de experiencia por {motivo}.")
        self.resolver_xp(modificador=modificador, solo=solo)

    def resolver_xp(self, modificador: int = 0, solo: str = "") -> bool:
        if self.p.xp_pendientes <= 0:
            return False
        ultimo = self.p.campana.ultimo_en_subir
        candidatos = [
            p for p in self.grupo.vivos
            if (not solo or p.nombre == solo)
            and p.nombre != ultimo                    # no dos veces seguidas
            and (p.clase.nivel_maximo is None or p.nivel < p.clase.nivel_maximo)
        ]
        if not candidatos:
            self.anotar("xp", "Nadie puede aprovechar la tirada de experiencia.")
            self.p.xp_pendientes -= 1
            return False

        elegido = self.preguntar(
            "xp_personaje", "¿Quien intenta subir de nivel?",
            [Opcion(p.nombre, p.nombre, f"{p.clase.nombre} nivel {p.nivel}")
             for p in candidatos],
        )
        personaje = self.grupo.por_nombre(elegido)
        self.p.xp_pendientes -= 1
        # Hay que SUPERAR el nivel actual; los esbirros restan 1.
        r = self.juego.tirar("experiencia", personaje, self.rng,
                             dificultad=personaje.nivel)
        total = r.total + modificador
        self.anotar("xp", f"{personaje.nombre}: {r.tirada.detail}"
                          + (f" {modificador:+d}" if modificador else "")
                          + f" = {total} vs nivel {personaje.nivel}")
        if total > personaje.nivel:
            personaje.subir_nivel()
            self.p.campana.ultimo_en_subir = personaje.nombre
            self.anotar("xp", f"¡{personaje.nombre} sube a nivel {personaje.nivel}!")
            return True
        self.anotar("xp", f"{personaje.nombre} no aprende nada esta vez.")
        return False

    # -- turno de exploracion ---------------------------------------------------- #

    def queda_algo_por_hacer(self) -> bool:
        """¿Sigue habiendo puertas sin cruzar o salas sin registrar?"""
        return any(self.mapa.salidas_libres(s.id) or (not s.buscada and s.limpia)
                   for s in self.mapa)

    def opciones_de_sala(self) -> list[Opcion]:
        """Las opciones van de mas a menos util: la primera es la recomendada.

        Ese orden no es cosmetico: `DecisorPorDefecto` siempre toma la primera,
        asi que de el depende que el modo automatico avance en vez de dar
        vueltas entre dos salas.
        """
        sala = self.sala
        explorar, aqui, moverse, salir = [], [], [], []

        for i, libre in enumerate(self.mapa.salidas_libres(sala.id)):
            if self.rejilla is None:
                etiqueta = f"Cruzar la salida {libre + 1}"
                valor = f"abrir:{libre}"
            else:
                celda, salida = libre
                rumbo = {"N": "al norte", "S": "al sur",
                         "E": "al este", "O": "al oeste"}[salida.lado]
                puerta = "puerta" if salida.puerta else "paso abierto"
                etiqueta = f"Cruzar la {puerta} {rumbo}"
                valor = f"abrir:{i}"
            explorar.append(Opcion(valor, etiqueta, "sala nueva"))
        if not sala.buscada and sala.limpia:
            aqui.append(Opcion("buscar", "Registrar la sala",
                               "puede atraer monstruos"))
        for destino in sorted(set(sala.conexiones.values())):
            otra = self.mapa[destino]
            pistas = []
            if not otra.limpia:
                pistas.append("con monstruos")
            if not otra.sin_salida:
                pistas.append("tiene salidas sin cruzar")
            if not otra.buscada and otra.limpia:
                pistas.append("sin registrar")
            moverse.append(Opcion(f"ir:{destino}", f"Ir a la sala {destino}",
                                  ", ".join(pistas)))
        # Las salas con algo pendiente van antes que los callejones sin salida.
        moverse.sort(key=lambda o: not o.detalle)

        entrada = self.mapa.entrada
        if entrada is not None and entrada.id != sala.id:
            camino = self.mapa.camino_a_la_entrada()
            if len(camino) > 2:
                salir.append(Opcion("a_la_entrada", "Volver a la entrada",
                                    f"{len(camino) - 1} salas de camino"))
        if sala.tipo == "entrada":
            salir.append(Opcion("salir", "Salir de la mazmorra",
                                "termina la aventura"))

        if self.queda_algo_por_hacer():
            return [*explorar, *aqui, *moverse, *salir]
        # No queda nada: lo sensato es marcharse con el botin.
        return [*salir, *explorar, *aqui, *moverse]

    def plano_actual(self) -> str:
        """El dibujo de la mazmorra, o cadena vacia si se juega solo con grafo."""
        if self.rejilla is None:
            return ""
        return self.rejilla.ascii(self.mapa.puertas(), actual=self.mapa.actual)

    def turno(self) -> bool:
        """Un turno de exploracion. Devuelve False cuando la aventura acaba."""
        if not self.p.viva:
            return False
        self.resolver_sala()
        if not self.grupo.vivos:
            self.p.aventura.terminada = True
            self.anotar("fin", "El grupo ha caido en la mazmorra.")
            return False

        opciones = self.opciones_de_sala()
        if not opciones:
            self.anotar("fin", "No queda a donde ir.")
            self.p.aventura.terminada = True
            return False

        eleccion = self.preguntar(
            "accion_sala",
            f"{self.sala}\nGrupo: " + ", ".join(
                f"{p.nombre} {p.vida}/{p.vida_max}" for p in self.grupo.vivos),
            opciones,
            plano=self.plano_actual(),
        )
        if eleccion == "salir":
            self.p.aventura.terminada = True
            self.anotar("fin", "El grupo sale de la mazmorra.")
            return False
        if eleccion == "a_la_entrada":
            camino = self.mapa.camino_a_la_entrada()
            for paso in camino[1:]:
                self.mapa.mover(paso)
            self.anotar("movimiento",
                        f"El grupo desanda {len(camino) - 1} salas hasta la entrada.")
        elif eleccion == "buscar":
            self.buscar()
        elif eleccion.startswith("abrir:"):
            self.abrir(int(eleccion.split(":", 1)[1]))
        elif eleccion.startswith("ir:"):
            self.mapa.mover(int(eleccion.split(":", 1)[1]))
            self.anotar("movimiento", f"El grupo vuelve a la sala {self.mapa.actual}.")
        return True

    def jugar(self, limite: int = 200) -> None:
        if not self.mapa.salas:
            self.entrar()
        turnos = 0
        while turnos < limite and self.turno():
            turnos += 1
        self.p.campana.aventuras_jugadas += 1
        self.p.aventura.terminada = True
