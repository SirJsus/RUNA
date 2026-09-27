# Referencia rápida

Chuleta de las piezas principales. Para el porqué, [Arquitectura](arquitectura.md).

## Empezar a usar el motor desde Python

```python
from runa.core.decisions import DecisorPorDefecto
from runa.core.rng import RandomSource
from runa.games.cco.exploracion import Exploracion
from runa.games.cco.juego import Juego
from runa.games.cco.partida import Partida

juego = Juego()                                    # carga todos los YAML
# juego = Juego(datos="otra/carpeta")             # o un reglamento a medida
grupo = juego.crear_grupo(
    [("Brakk", "guerrero"), ("Sela", "clerigo"),
     ("Nim", "picaro"), ("Orin", "mago")],
    RandomSource(42),
)
juego.preparar_hechizos(grupo.por_nombre("Orin"),
                        ["bola_de_fuego", "rayo", "dormir"])

partida = Partida(juego, grupo, semilla=42)      # rejilla=False: sin dibujo
Exploracion(partida, DecisorPorDefecto()).jugar()

print(partida.registro.cronica())
partida.guardar("partidas/mia.json")
```

## `core/dice` — dados

```python
from runa.core.dice import roll
from runa.core.rng import RandomSource

rng = RandomSource(42)                             # sin semilla, aleatoria
r = roll("d6+1/2N", rng, explode=True, N=5)
r.total     # 6
r.detail    # "d6[4] + 1/2N(5->2)"
str(r)      # "d6+1/2N = d6[4] + 1/2N(5->2) = 6"
```

## `core/tables` — tablas

```python
from runa.core.tables import TableSet

tablas = TableSet.desde_yaml("ruta/a/tablas")
tablas.validar()                                   # referencias rotas

r = tablas.tirar("tesoros", rng, modificador=+1)
r.texto                                            # el resultado
r.describir()                                      # el árbol de tiradas encadenadas
list(r.recorrer())                                 # este resultado y sus hijos

# Cortar el encadenado con un predicado sobre la entrada
tablas.tirar("contenido_habitacion", rng,
             encadenar=lambda e: not e.datos.get("si_corredor"))
```

## `core/checks` — tiradas

```python
r = juego.atacar(personaje, amenaza, rng, etiquetas={"superados_en_numero"})
r = juego.defender(personaje, amenaza, rng, etiquetas={"sorpresa"})
r = juego.tirar("salvacion", personaje, rng, amenaza=veneno)
r = juego.tirar("experiencia", personaje, rng, dificultad=personaje.nivel)

r.exito           # True / False
r.total           # el resultado con modificadores
r.bonificacion    # solo la suma de modificadores
r.modificadores   # tupla de (valor, fuente)
r.describir()     # la traza legible
```

Una acción prohibida lanza `AccionProhibida`. Para consultarlo antes:
`juego.resolutor.prohibiciones(check)` devuelve los motivos.

## `core/entities` — personajes

```python
p.vivo, p.herido, p.muerto
p.herir(2); p.curar(3)
p.subir_nivel(); p.bajar_nivel()
p.gastar("suerte")                  # lanza si no queda
p.arma                              # el arma equipada
p.anadir(objeto, equipar=True)
p.problemas_de_equipo()             # lista de incumplimientos, no lanza
p.reglas(); p.etiquetas_activas()   # lo que ve el resolutor
p.estados; p.estado("maldito"); p.limpiar_estados("combate")

grupo.vivos; grupo.oro
grupo.por_nombre("Brakk"); grupo.con_clase("enano")
grupo.reordenar(["Nim", "Brakk", ...])   # el orden es el de marcha
```

## `core/bestiary` — monstruos

```python
perfil = juego.bestiario["trolls"]
enc = perfil.generar(rng)           # tira cuántos salen

enc.nombre, enc.cantidad, enc.vida
enc.nivel                           # ya rebajado si el jefe va a media Vida
enc.vivo, enc.bajo_de_moral
enc.herir(2); enc.huir()
enc.amenaza                         # lo que se pasa a una tirada
```

## `core/decisions` — preguntar

```python
from runa.core.decisions import DecisorGuion, DecisorPorDefecto, Opcion, Pregunta

decisor.elegir(Pregunta.crear("mi_id", "¿Qué haces?", [
    Opcion("atacar", "Atacar", "con la espada"),    # la primera es la recomendada
    Opcion("huir", "Huir"),
]))

DecisorGuion({"accion": ["atacar", "huir"],         # lista: se consume en orden
              "objetivo": "goblins",                # valor suelto: siempre igual
              "xp_personaje": lambda p: p.valores[-1]})   # o una función
```

Ids de decisión que ya existen, por si guionizas una partida:

`grupo` · `clase` · `hechizo` · `comprar` · `variante` — creación
`plano_tipo` · `plano_salidas` · `accion_sala` — exploración
`abordaje` · `accion` · `salir_del_combate` · `a_salvo` · `soborno` · `suerte` — combate
`proteger` · `bendicion` · `curacion` — efectos de hechizo
`desarmar_trampa` · `buscar_hallazgo` · `asignar_tesoro` · `pista` · `templo` · `curandero` · `xp_personaje` — sala
`vender` · `resucitar` · `reemplazo` · `curar` · `seguir` — intermedio

## `core/mapa` — la mazmorra

```python
sala = mapa.crear("habitacion", salidas=3, plano="42")
mapa.conectar(origen.id, salida, destino.id)       # puertas de doble sentido
mapa.mover(destino.id)

sala.es_corredor, sala.salidas_libres, sala.sin_salida
sala.limpia, sala.buscada, sala.secreta
mapa.completo                                      # ni una puerta sin cruzar
mapa.camino_a_la_entrada()                         # ruta más corta
```

## `core/rejilla` — el dibujo

```python
from runa.core.rejilla import Catalogo, Rejilla

catalogo = juego.planos                    # las 36 losetas + 6 entradas
plano = catalogo["32"]
plano.tipo, plano.ancho, plano.alto, plano.celdas, plano.salidas
print(plano.dibujo())                      # la silueta, como en el YAML
plano.girar(1)                             # un cuarto de vuelta en horario

rejilla = partida.mapa.rejilla             # None si se juega solo con grafo
rejilla.colocar_primera(1, catalogo.entrada("4"))
celda, salida = rejilla.salidas_libres(1)[0]

opciones = rejilla.colocaciones(plano, celda, salida.lado)   # encajes enteros
opciones[0].descripcion()                  # "girada 90°, entrando por su lado S..."
rejilla.colocar(2, opciones[0])

recorte = rejilla.recorte(plano, celda, salida.lado)         # si no cabe entera
rejilla.colocar(2, recorte, recortar=True)                   # callejón sin salida

print(rejilla.ascii(partida.mapa.puertas(), actual=partida.mapa.actual))
open("plano.svg", "w").write(rejilla.svg(partida.mapa.puertas()))
```

El mapa combina las dos capas:

```python
partida.mapa.salidas_libres(sala_id)   # con rejilla, salidas concretas
partida.mapa.puertas()                 # pares de celdas que comunican salas
partida.mapa.completo                  # ni una puerta sin cruzar
```

## `core/events` y la crónica

```python
registro.anotar("botin", "25 de oro")
registro.de_tipo("victoria", "derrota")
registro.tipos                                     # la secuencia, útil en tests
registro.cronica()                                 # texto plano
registro.al_anotar = lambda e: print(e.texto)      # narrar en vivo

from runa.games.cco import cronica
cronica.escribir(partida)                          # el documento Markdown entero
```

## `games/cco/juego` — la fachada

```python
juego.clases, juego.catalogo, juego.bestiario, juego.habilidades
juego.tablas, juego.estados, juego.odios, juego.resolutor, juego.ganchos

juego.crear_personaje("Brakk", "guerrero", rng, nivel=2, variante_arma="aplastante")
juego.crear_grupo([(nombre, clase), ...], rng)
juego.preparar_hechizos(personaje, ["rayo", "rayo", "proteger"])
juego.usar_habilidad("bola_de_fuego", personaje, combate)

juego.generar_monstruos("esbirros", rng)           # tira e instancia
juego.encuentro_desde(resultado_de_tabla, rng)     # instancia una tirada ya hecha
juego.reaccion(encuentro, rng); juego.moral(encuentro, rng)
juego.saquear(perfil.tesoro, rng)

juego.combatir(grupo, encuentro, rng, decisor=..., situacion=...)
juego.validar()                                    # [] si los datos cuadran
```

## Partida

```python
partida.guardar("partidas/mia.json")
partida = Partida.cargar("partidas/mia.json", juego)

partida.grupo, partida.mapa, partida.registro, partida.rng
partida.aventura        # jefes vistos, encuentros, lo gastado esta incursión
partida.campana         # aventuras jugadas, pistas, quién subió la última vez
partida.resumen()
```

## Tests

```bash
.venv/bin/python -m pytest              # los 341
.venv/bin/python -m pytest -k dados     # por nombre
.venv/bin/python -m pytest -x -q        # parar en el primer fallo
```

`tests/test_dice.py` define `ScriptedRandom`, que devuelve una secuencia fija de
dados. Es lo que hace exactos los demás tests:

```python
from tests.test_dice import ScriptedRandom

ScriptedRandom([5, 3])              # saca 5, luego 3, luego revienta
ScriptedRandom([5], relleno=3)      # saca 5 y luego siempre 3
```

**El relleno no puede ser la cara máxima**: con la regla explosiva activa, eso no
termina nunca. (El motor tiene un tope de seguridad que lo convierte en error en
vez de un cuelgue.)
