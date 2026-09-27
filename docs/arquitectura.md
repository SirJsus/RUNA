# Arquitectura

## La idea de fondo

Cuatro contra la Oscuridad es, mecánicamente, muy uniforme. Casi todo lo que
ocurre en la mesa es la misma operación:

> tirar un d6, sumarle un montón de modificadores condicionales,
> y comparar con un número objetivo

Eso vale para atacar, defender, salvar contra veneno, resolver acertijos, probar
moral, desarmar trampas y subir de nivel. Lo demás son **tablas aleatorias** y un
**bucle de exploración**.

De ahí sale la decisión que gobierna todo el proyecto: si el motor resuelve bien
"tirada con modificadores" y "tabla aleatoria", el 80% del juego son **datos**, no
código. Y esas dos piezas son justo las que reutilizará cualquier otro juego
solitario de dados.

## Las capas

```
src/runa/
  core/       el motor. No sabe que existe ningún juego concreto
  games/cco/  Cuatro contra la Oscuridad: datos + los pocos ganchos que hacen falta
  apps/cli/   la terminal
```

Tres reglas de la casa, y de ellas depende que la modularidad sea real:

1. **`core/` nunca importa de `games/`.**
2. **Las reglas de un juego nunca se escriben dentro de `core/`.**
3. **Los textos viven en los datos.** Adaptar otro juego es escribir YAML.

### `core/` — el motor

| Módulo | Qué resuelve |
|---|---|
| `rng.py` | Azar reproducible por semilla. Todo el azar pasa por aquí |
| `dice.py` | Notación de dados (`2d6+1`, `d6xd6`, `d66`, `d6+N`), regla explosiva y traza |
| `tables.py` | Tablas declarativas: rangos, modificadores, encadenado, entradas únicas |
| `checks.py` | La tirada con modificadores: el corazón del sistema |
| `entities.py` | Personaje, clase, objeto, estado, grupo |
| `bestiary.py` | Perfil de monstruo y encuentro (esbirros contra jefes) |
| `abilities.py` | Hechizos y poderes, con registro de ganchos para sus efectos |
| `events.py` | Registro de todo lo que pasa |
| `decisions.py` | El puerto por el que el motor pregunta al jugador |
| `mapa.py` | La mazmorra como grafo de salas |
| `rejilla.py` | La geometría: siluetas de loseta, encaje en la hoja y dibujo |
| `cronica.py` | Convierte el registro en Markdown |

### `games/cco/` — el juego

| Pieza | Qué es |
|---|---|
| `data/*.yaml` | El reglamento entero: clases, equipo, monstruos, hechizos, tablas, estados, losetas |
| `juego.py` | Ensambla los datos y expone las operaciones del reglamento |
| `combate.py` | El bucle de combate |
| `exploracion.py` | El bucle de exploración |
| `intermedio.py` | Entre aventuras: vender, resucitar, curar, descansar |
| `partida.py` | Estado de partida, guardado y carga |
| `cronica.py` | El vocabulario de la crónica |
| `hooks/efectos.py` | Efectos de hechizos y poderes |
| `hooks/monstruos.py` | Reglas propias de cada monstruo |

---

## Las cuatro ideas que sostienen todo

### 1. Toda tirada lleva su traza

Una tirada no devuelve un número: devuelve de dónde salió ese número.

```
Ataque de Nim contra Esqueleto (nivel 3)
  d6[3]
  +1 picaro atacando a esbirros superados en numero
  -1 arma ligera
  = 3 vs 3 -> EXITO
```

Esto no es cosmética. Da tres cosas a la vez: el jugador entiende por qué pasó
lo que pasó, los tests pueden afirmar sobre los modificadores concretos, y
—lo importante— adaptar otro juego consiste en aportar modificadores nuevos, no
un motor nuevo.

### 2. Azar con semilla

Todo el azar sale de un `RandomSource` con semilla. Dos partidas con la misma
semilla son idénticas. Sirve para depurar, para tests exactos y para que
continuar una partida guardada dé exactamente lo mismo que no haberla cortado.

### 3. Etiquetas en vez de casos especiales

Este es el mecanismo central. Una tirada arrastra un **conjunto plano de
etiquetas** que aportan tres fuentes:

| Fuente | Ejemplos |
|---|---|
| La situación | `superados_en_numero`, `sorpresa`, `primer_turno`, `huida` |
| El equipo | `dos_manos`, `aplastante`, `a_distancia`, `escudo` |
| La amenaza | `no_muerto`, `esqueleto`, `goblin`, `dragon` |

Y una regla declarativa dice qué etiquetas exige:

```yaml
- en: ataque
  suma: 1
  si: [aplastante, esqueleto]
  texto: arma aplastante contra esqueletos
```

El motor no sabe qué es un arma ni qué es un esqueleto: solo comprueba
conjuntos. Con eso salen, sin una sola línea de código especial, el pícaro que
solo suma nivel contra esbirros superados en número, el clérigo con medio nivel
salvo contra no muertos, el enano que no suma con arco y el elfo +1 contra orcos.

Una regla también puede **vetar** una acción en vez de modificarla:

```yaml
- prohibe: hechizo
  si: [dos_manos]
  texto: no se puede lanzar con las dos manos ocupadas
```

Y una unificación que el libro ya insinúa: **un veneno de nivel 3, un acertijo
de nivel 5 y un ogro de nivel 5 son la misma pieza**, `Amenaza`. Eso elimina de
golpe tres sistemas paralelos de salvaciones.

### 4. El motor nunca decide por el jugador

Cuando hace falta una elección, el motor **pregunta** a través de un puerto
abstracto, `Decisor`:

```
Combate / Exploracion / Intermedio
            |
            v
      Decisor (abstracto)
       /      |       \
ConsolaDecisor  DecisorGuion  DecisorPorDefecto
  (jugar)        (tests)       (modo --auto)
```

Por eso el bucle de combate se escribe **una sola vez** y sirve para jugar, para
los tests (que juegan partidas enteras con decisiones prefijadas) y para el modo
automático. Y por eso un futuro agente que juegue solo no tocará el motor: solo
implementará este puerto.

Detalle que no es cosmético: **la primera opción es siempre la recomendada**.
`DecisorPorDefecto` toma siempre la primera, así que de ese orden depende que el
modo automático avance en vez de dar vueltas.

---

## El recorrido de una tirada

Vale la pena seguir un ataque de principio a fin, porque explica cómo encajan las
piezas.

```
1. combate.py  arma el contexto
   etiquetas = situación  ∪  actor (clase + equipo + estados)  ∪  amenaza

2. Resolutor.prohibiciones()
   ¿alguna regla veta esta acción?  → AccionProhibida

3. Resolutor.modificadores()
   recorre reglas del actor + de la amenaza + globales
   se queda con las que cumplen sus condiciones de etiquetas
   evalúa cuánto suma cada una (puede depender del nivel)

4. dice.roll()
   tira el dado, con la regla explosiva si el tipo de tirada la usa

5. TipoTirada.compara()
   ataque   → total >= nivel
   defensa  → total >  nivel   (hay que superarlo, no igualarlo)
   resurrección → total <= nivel   (va al revés)

6. el 1 y el 6 naturales mandan sobre el resultado modificado

7. CheckResult
   total + éxito + la lista de modificadores con su procedencia
```

El paso 5 se configura en `data/reglas.yaml`, no en el código.

## El flujo de una partida

```
CLI: crear grupo, preparar hechizos, comprar
  │
  ├─► Exploracion.turno()  ◄──────────────┐
  │     genera la sala (d66 + preguntas)  │
  │     resuelve su contenido             │
  │       ├─ monstruos ─► Combate ─► botín, experiencia
  │       ├─ tesoro, trampa, evento, característica
  │       └─ vacío
  │     tú eliges: cruzar / registrar / volver / salir
  │                                        │
  └──────────────────────────────────────┘
  │
  └─► Intermedio: vender, resucitar, reclutar, curar, comprar, descansar
        └─► otra aventura, con el mismo grupo
```

Todo lo que ocurre se anota en el `Registro`, y de ahí sale la crónica.

## El mapa: grafo y geometría, separados

El grafo (`mapa.py`) es la verdad sobre **qué conecta con qué**. La rejilla
(`rejilla.py`) es una capa **encima**, opcional, que añade **dónde cae cada cosa
en la hoja**. Se puede jugar con las dos o solo con el grafo.

```
Mapa (grafo)                 Rejilla (geometría)
  Sala 1 ──puerta── Sala 2     loseta, esquina, giro, celdas ocupadas
      │                              │
      └──── mismo id de sala ────────┘
```

Esa separación paga en tres sitios:

- **El motor de exploración no cambia** entre un modo y otro. Solo cambia de
  dónde salen las salidas libres.
- **El dibujo no se guarda.** Cada sala guarda su loseta, su esquina y su giro;
  al cargar, la rejilla se rehace colocándolas en orden. Así, corregir la
  silueta de una loseta alcanza también a las partidas ya empezadas.
- **Encajar una loseta es un problema geométrico puro**: probar los cuatro giros
  y cada una de sus puertas, y quedarse con los encajes que no pisen nada. Si
  ninguno cabe, se recorta, que es justo lo que manda el libro.

## Qué se guarda

El `.json` guarda **referencias, no reglas**: id de clase, id de objeto, id de
estado. Al cargar, las reglas se releen de los YAML.

Eso tiene una consecuencia que merece la pena: **un arreglo del reglamento
alcanza a las partidas ya empezadas**. Si corriges el modificador de un arma, la
partida que tenías a medias juega ya con la corrección.

## Cómo está probado

341 tests. Los que más valen no son los de cobertura, sino tres tipos concretos:

- **Los ejemplos del propio libro.** Los tres combates numerados de la página 25
  están como tests y se comprueban contra el resultado que imprime el libro.
- **Partidas enteras jugadas con `DecisorGuion`.** Los tests pueden guionizar
  decisiones y comprobar el desenlace y la secuencia de eventos.
- **Tests que buscan huecos en los datos**, como el que verifica que *todas* las
  tablas de reacciones cubren el d6 entero. Ese encontró un fallo del libro.

Además, `Juego.validar()` comprueba todas las referencias cruzadas entre tablas,
bestiario, catálogo y habilidades, y devuelve una lista de problemas. La CLI lo
ejecuta al arrancar y no juega si algo no cuadra.
