# Jugar

## Instalar

Necesitas Python 3.11 o más nuevo.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Empezar una partida

```bash
.venv/bin/runa
```

El programa te lleva de la mano: formar el grupo, preparar hechizos, comprar
equipo y bajar a la mazmorra.

### Las opciones

| Orden | Qué hace |
|---|---|
| `runa` | Partida nueva |
| `runa partidas/mia.json` | Continuar una partida guardada |
| `runa --semilla 42` | Fijar el azar: la misma semilla da la misma partida |
| `runa --nombre cripta` | Nombrar la partida (si no, se llama `partida-<semilla>`) |
| `runa --aventuras 3` | Encadenar hasta 3 incursiones con el mismo grupo |
| `runa --grafo` | No dibujar el mapa: lo llevas tú en papel |
| `runa --losetas` | Ver las losetas d66 (o una sola: `--losetas 32`) |
| `runa --auto` | Que la juegue el programa solo, sin preguntarte |
| `runa --sin-guardar` | No escribir ningún archivo |
| `runa --sin-cronica` | Guardar la partida pero no la crónica en Markdown |
| `runa partida.json --exportar cronica.md` | Reconstruir la crónica de una partida vieja |

## Cómo se responde

Cada pregunta muestra una lista numerada. Escribe el número y pulsa Enter.

```
Turno de Brakk (7/7 Vida) contra 6x Goblins (nivel 3).
  1) Atacar  (Arma de mano)
  2) No hacer nada
  > [1-2]
```

**Pulsar Enter sin escribir nada elige la primera opción**, que siempre es la
recomendada. Eso permite jugar rápido dando solo a Enter cuando la decisión es
obvia. `Ctrl+C` corta la partida (lo guardado hasta la última sala se conserva).

## Quién hace qué

El programa es un **árbitro**, no un jugador. Reparto de tareas:

**Lo hace el programa**
- Tira todos los dados, con la regla explosiva del seis
- Aplica todos los modificadores (nivel, clase, arma, armadura, situación, monstruo)
- Lleva la Vida, el oro, los hechizos preparados, la Suerte, las Bendiciones
- Genera el contenido de las salas, los monstruos, los tesoros y las trampas
- Lleva la moral de los monstruos y su tabla de reacciones
- Cuenta los encuentros para la experiencia y tira para subir de nivel
- Guarda la partida y escribe la crónica

**Lo decides tú**
- Qué clases forma el grupo y en qué orden de marcha
- Qué hechizos prepara cada lanzador y qué equipo compra cada uno
- Si atacas de inmediato o esperas a ver qué hace el monstruo
- A quién atacas, qué hechizo lanzas, a quién curas
- Si pagas un soborno, te retiras o huyes
- Si gastas un punto de Suerte para repetir una tirada fallida
- Qué puerta cruzas, si registras una sala y cuándo sales de la mazmorra
- Quién intenta subir de nivel

## El mapa

Hay dos modos, y se juega igual con los dos.

### Con dibujo (por defecto)

El programa conoce la silueta de las 36 losetas d66, las encaja en una hoja de
20×28 cuadros y te enseña la mazmorra antes de cada decisión:

```
+--+  +
|     |
+  +  +
|     |
+--+  +
   | 1|
   +  +
   |  |
   +--+
```

`--` y `|` son muros, un hueco es un paso entre salas y `*` una salida que aún
no has cruzado. El número es el de la sala.

Solo te pregunta cuando una loseta encaja de más de una forma:

```
El plano 31 encaja de 2 formas. ¿Cual dibujas?
  1) sin girar, entrando por su lado S en (9, 16)  (2 salidas)
  2) girada 180°, entrando por su lado S en (9, 16)  (2 salidas)
```

Si una loseta no cabe, se recorta y queda como callejón sin salida, tal y como
manda el libro. Y sigue tirando su contenido.

### Solo grafo (`--grafo`)

No dibuja nada: llevas tú el mapa en papel y el programa solo te pregunta qué
forma tiene la sala que acabas de dibujar.

```
Al otro lado hay el plano 42.
  1) Habitacion  (2 o mas cuadrados de ancho)
  2) Corredor  (un solo cuadrado de ancho)
¿Cuantas salidas tiene?
  1) 1   2) 2   3) 3   4) 4
```

Es más rápido de llevar y deja el dibujo a tu gusto. La distinción entre sala y
corredor importa en los dos modos: los corredores están vacíos más a menudo y en
ellos solo pueden atacarte dos monstruos a la vez.

### Sobre las losetas

Las siluetas están transcritas **a ojo** de los dibujos a mano del libro. Las
proporciones y el número de salidas son fieles, pero alguna forma retorcida es
aproximada. `runa --losetas` te las enseña todas para que las compares con tu
PDF, y corregir una es editar su bloque `forma` en `planos.yaml` — está
explicado en [Tocar las reglas](datos.md#corregir-una-loseta).

## Guardado

La partida se guarda sola **después de cada sala**, en `partidas/<nombre>.json`.
No hay que hacer nada. Al terminar se escriben además `partidas/<nombre>.md` con
la crónica y `partidas/<nombre>-plano.svg` con el mapa dibujado.

Continuar una partida guardada da exactamente lo mismo que no haberla cortado:
el azar se rebobina hasta donde estaba.

## La crónica

Todo lo que pasa queda registrado y al final se convierte en un documento
legible. Las tiradas van dentro de bloques plegables: están, pero no estorban.

```markdown
### 🚪 Sala 2: habitacion (plano 55)

Tesoro protegido por una trampa.

Un dardo (nivel 2) ataca a un personaje al azar.

<details><summary>Tiradas</summary>

Desarmar trampa de Nim contra Trampa (nivel 2)
  d6[4]  +1 nivel de picaro  = 5 vs 2 -> EXITO

</details>

Nim desarma la trampa.

> 💰 Botin: Pergamino de Escapada
```

Se destacan el botín, las muertes, las subidas de nivel, las pistas y el jefe
final. Y como la crónica se guarda dentro del `.json`, puedes regenerarla meses
después con `--exportar`.

## El modo automático

`runa --auto` juega solo tomando siempre la primera opción, que por convenio es
la recomendada. No es una inteligencia artificial: es un jugador muy simple.
Sirve para tres cosas:

- Ver una partida entera de ejemplo sin teclear nada
- Probar cambios en el reglamento a lo bruto (¿sigue siendo jugable?)
- Comprobar que nada se rompe tras tocar el código

## Si algo va mal

| Síntoma | Qué mirar |
|---|---|
| No arranca y salen errores de datos | Algún `.yaml` está mal. El programa los lista y termina |
| Una partida guardada no carga | Puede ser de una versión posterior, o usar un objeto que ya no existe. El mensaje lo dice |
| Quieres repetir una partida idéntica | Anota la semilla que sale en el resumen y úsala con `--semilla` |
| Los colores molestan | `NO_COLOR=1 runa`, o redirige la salida a un archivo |
