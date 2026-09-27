# RUNA — juegos de rol en solitario, automatizados

> **R**eglas **U**nificadas, **N**arración y **A**zar

Automatiza la parte mecánica de un juego de rol en solitario —dados, tablas,
modificadores, cuentas— para que jugar sea solo llegar y decidir.

Las tres palabras del nombre son las tres ideas del diseño: **un solo resolutor**
de tiradas que vale para cualquier juego, **una crónica** de lo que pasó, y un
**azar reproducible** por semilla.

El juego implementado es **Cuatro contra la Oscuridad**. El motor no sabe nada
de él: las reglas viven en archivos de datos.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/runa
```

## Qué hace

El programa es un **árbitro**, no un jugador. Tira todos los dados, aplica todos
los modificadores y lleva todas las cuentas. Tú decides a quién atacas, qué
hechizo lanzas y si huyes o sobornas.

Cada tirada te dice de dónde salió su resultado:

```
Ataque de Nim contra Esqueleto (nivel 3)
  d6[3]
  +1 picaro atacando a esbirros superados en numero
  -1 arma ligera
  = 3 vs 3 -> EXITO
```

Y dibuja la mazmorra mientras la exploras:

```
+--+  +
|     |
+--+  +--+--+
   | 1      |
   +  +  +  +
   |        |
   +--+--+**+
```

Guarda la partida sola después de cada sala, encadena aventuras con el mismo
grupo, y al terminar escribe la crónica de lo que pasó en Markdown, con el plano
en SVG.

## Documentación

Empieza por [`docs/`](docs/README.md). En resumen:

| | |
|---|---|
| [Jugar](docs/jugar.md) | Instalar, empezar, y qué te pregunta el programa |
| [El reglamento](docs/reglamento.md) | Qué automatiza y qué decisiones se tomaron sobre el libro |
| [Tocar las reglas](docs/datos.md) | Cambiar clases, monstruos y tablas editando YAML |
| [Arquitectura](docs/arquitectura.md) | Cómo está construido y por qué |
| [Extender](docs/extender.md) | Añadir hechizos, reglas de monstruo o un juego nuevo |
| [Referencia](docs/referencia.md) | Chuleta de las piezas principales |

## Cómo está organizado

```
src/runa/
  core/       el motor. No sabe que existe ningún juego concreto
  games/cco/  Cuatro contra la Oscuridad: datos + los pocos ganchos necesarios
  apps/cli/   la terminal
docs/         la documentación, y el reglamento original
tests/        341 tests
```

Tres reglas de la casa, y de ellas depende que la modularidad sea real:

1. `core/` nunca importa de `games/`.
2. Las reglas de un juego nunca se escriben dentro de `core/`.
3. Los textos viven en los datos: adaptar otro juego es sobre todo escribir YAML.

## Estado

Jugable y completo para Cuatro contra la Oscuridad: creación de grupo, compra de
equipo, exploración, combate, hechizos, botín, experiencia, campaña entre
aventuras, dibujo del mapa, guardado y crónica.

Las siluetas de las 36 losetas d66 están transcritas a ojo de los dibujos a mano
del libro; `runa --losetas` las enseña para cotejarlas y son fáciles de corregir.
Si prefieres dibujar tú el mapa, `runa --grafo` no dibuja nada.
