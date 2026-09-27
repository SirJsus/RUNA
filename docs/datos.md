# Tocar las reglas sin programar

Casi todo el juego son datos. Están en `src/runa/games/cco/data/` y se editan
con un editor de texto.

```
data/
  clases.yaml       las 8 clases de personaje
  equipo.yaml       el catálogo de objetos
  monstruos.yaml    el bestiario (25 criaturas)
  hechizos.yaml     hechizos y poderes de clase
  estados.yaml      condiciones (maldito, petrificado, protegido...)
  reglas.yaml       cómo se resuelve cada tipo de tirada, y las reglas globales
  planos.yaml       las 36 losetas d66 y las 6 salas de entrada
  tablas/
    mazmorra.yaml     contenido de sala, trampas, tesoros, eventos
    monstruos.yaml    qué monstruo sale en cada tirada
    reacciones.yaml   la tabla de reacciones de cada monstruo
    tesoros.yaml      hechizos aleatorios y tesoros mágicos
    exploracion.yaml  búsqueda, misiones, recompensas épicas
```

**Después de editar, comprueba siempre que los datos cuadran:**

```bash
.venv/bin/python -c "
from runa.games.cco.juego import Juego
print(Juego().validar() or 'todo correcto')"
```

Eso detecta tablas que apuntan a monstruos inexistentes, equipo inicial que no
está en el catálogo, clases con equipo que no pueden usar, y demás.

Si prefieres probar cambios sin tocar los datos originales, copia la carpeta y
cárgala aparte: `Juego(datos="mi/copia")`. Cada instancia lleva la suya.

---

## La pieza que se repite: una regla

Aparece en clases, objetos, monstruos y estados. Hace dos cosas según se rellene
`suma` o `prohibe`.

```yaml
# Modificar una tirada
- en: ataque              # tipo de tirada; se puede poner una lista
  suma: nivel             # un número, `nivel` o `medio_nivel`
  si: [aplastante, esqueleto]     # exige TODAS estas etiquetas
  si_alguno: [troll, ogro]        # exige AL MENOS UNA
  si_no: [a_distancia]            # exige NINGUNA
  texto: lo que saldrá en la traza

# Vetar una acción
- prohibe: hechizo        # o una lista de tipos
  si: [dos_manos]
  texto: no se puede lanzar con las dos manos ocupadas
```

Los tres filtros son opcionales y se combinan. Si omites `en`, la regla aplica a
cualquier tirada.

**Tipos de tirada disponibles:** `ataque`, `defensa`, `hechizo`, `salvacion`,
`puzzle`, `desarmar_trampa`, `moral`, `experiencia`, `resurreccion`.

### De dónde salen las etiquetas

Una tirada junta las etiquetas de tres sitios. Puedes usar cualquiera de ellas
en `si` / `si_alguno` / `si_no`:

| Fuente | Ejemplos |
|---|---|
| El personaje | su clase (`picaro`, `enano`), sus estados (`maldito`) y las que declare |
| Su equipo equipado | la `categoria` (`dos_manos`, `arco`) y sus `etiquetas` (`aplastante`) |
| La amenaza | su id (`trolls`) y sus `etiquetas` (`no_muerto`, `goblin`) |
| La situación | `superados_en_numero`, `sorpresa`, `primer_turno`, `huida`, `retirada`, `corredor` |

---

## Notación de dados

Se usa en cualquier sitio donde haya una cantidad: Vida, riqueza, cuántos
monstruos, cuánto oro.

| Escribes | Significa |
|---|---|
| `d6`, `2d6`, `d3` | Tiradas normales |
| `2d6+1`, `d6-1` | Con sumas y restas |
| `d6xd6`, `3d6x15` | Multiplicaciones |
| `d66` | Dos dados: el primero decenas, el segundo unidades (11 a 66) |
| `N` | El nivel del personaje |
| `1/2N` o `N/2` | Medio nivel, redondeando hacia abajo |
| `6+N` | Fórmulas sin azar, como la Vida de una clase |

---

## Recetas

### Añadir una clase

En `clases.yaml`:

```yaml
paladin:
  nombre: Paladin
  vida: 5+N                    # Vida = 5 + nivel
  riqueza_inicial: 2d6         # oro con el que empieza
  nivel_maximo: 5              # opcional; sin esto, sin tope
  etiquetas: [lanzador]        # opcionales, para que otras reglas las usen
  reglas:
    - {en: ataque, suma: nivel, texto: nivel de paladin}
    - {en: ataque, suma: 1, si: [no_muerto], texto: paladin contra no muertos}
  permite:
    armaduras: [ligera, pesada]
    escudo: true
    armas: [ligera, mano, dos_manos]
    objetos_magicos: true      # por defecto true
  equipo_inicial: [armadura_pesada, escudo, arma_mano]
  recursos: {bendicion: 1}     # se reponen entre aventuras; admiten fórmulas
  notas: Lo que no cabe en reglas, para que salga en la ficha
```

### Añadir un objeto

En `equipo.yaml`:

```yaml
lanza_larga:
  nombre: Lanza larga
  tipo: arma                   # arma, armadura, escudo, luz, util,
                               # consumible, magico, tesoro, servicio
  categoria: dos_manos         # lo que las clases permiten o no
  precio: 18
  manos: 2
  variantes: [cortante]        # el jugador elige una al comprarlo
  usos: 0                      # cargas, para objetos mágicos
  etiquetas: [alcance]
  reglas:
    - {en: ataque, suma: 1, si_no: [torpe_con_armas], texto: lanza larga}
  notas: Ataca primero en el primer turno.
```

Solo los tipos `arma`, `armadura`, `escudo` y `luz` se equipan; el resto se
lleva encima. Únicamente lo equipado aporta modificadores y etiquetas.

### Añadir un monstruo

En `monstruos.yaml`:

```yaml
gargola:
  nombre: Gargola
  tipo: extrano                # bicho | esbirro | jefe | extrano
  nivel: 5
  vida: 4                      # los esbirros siempre 1
  ataques: 2
  dano: 1
  cantidad: "1"                # cuántos salen; para esbirros, p.ej. d6+2
  etiquetas: [piedra, odia_magos]
  tesoro: "+1"                 # null | normal | "+1" | {tiradas: 2, modificador: 1}
  moral: normal                # normal | nunca | -1
  reacciones: reacciones_gargola      # id de una tabla de reacciones
  xp: true
  errante: true                # si puede salir como monstruo errante
  sin_objetos_magicos: ""      # si lleva algo, el oro que sustituye a la magia
  reglas:
    - {en: ataque, suma: -1, si: [cortante], texto: su piel de piedra}
  notas: Lo que necesite adjudicación del jugador.
```

Y su tabla de reacciones en `tablas/reacciones.yaml`:

```yaml
reacciones_gargola:
  nombre: Reacciones (gargola)
  dado: d6
  entradas:
    - {rango: 1-2, texto: Permanece inmovil., reaccion: lucha}
    - {rango: 3-6, texto: Despierta y ataca., reaccion: lucha_hasta_muerte}
```

**Las reacciones deben cubrir el d6 entero (1 a 6).** Hay un test que lo
comprueba; fue el que descubrió un hueco en el libro original.

Reacciones que el combate entiende: `lucha`, `lucha_hasta_muerte`, `huir`,
`huir_si_superados`, `soborno`, `durmiendo`, `mision`.

Por último, añádelo a una tabla de aparición en `tablas/monstruos.yaml`:

```yaml
    - {rango: 6, texto: Gargola., monstruo: gargola}
```

### Añadir o cambiar una tabla

Cualquier tabla tiene la misma forma:

```yaml
mi_tabla:
  nombre: Cómo se llama
  dado: d6                     # 2d6, d66, lo que sea
  entradas:
    - rango: 1                 # un número, "1-3", o "-20-0" para negativos
      texto: Lo que sale.
      tirar: [otra_tabla]      # encadena: tira también en esa
      unica: true              # solo puede salir una vez por campaña
      id: mi_entrada           # para recordar que ya salió
    - {rango: 2-6, texto: Otra cosa.}
```

Los rangos no pueden solaparse: el cargador lo rechaza. Los modificadores que
saquen la tirada fuera de la tabla se recortan al extremo más cercano, que es lo
que el libro hace con "tesoro +1".

### Cambiar cómo se resuelve una tirada

En `reglas.yaml`:

```yaml
tiradas:
  defensa:
    dado: d6
    comparacion: ">"       # ">=" iguala, ">" hay que superar, "<=" al revés
    explosiva: true        # regla explosiva del seis
    exito_natural: 6       # un 6 sin modificar siempre acierta
    fallo_natural: 1       # un 1 sin modificar siempre falla
```

### Añadir una regla global

También en `reglas.yaml`, en `modificadores`. Se aplican a todo el mundo:

```yaml
modificadores:
  - en: ataque
    suma: 1
    si: [aplastante, esqueleto]
    texto: arma aplastante contra esqueletos
```

### Corregir una loseta

Las siluetas de `planos.yaml` están transcritas a ojo de los dibujos a mano del
libro, así que alguna puede no cuadrar con tu PDF. Compáralas con
`runa --losetas` (o `--losetas 32` para una sola) y corrige lo que haga falta:

```yaml
"32":
  tipo: habitacion            # habitacion o corredor
  notas: Planta en forma de E invertida.
  forma: |
    .###
    .##.
    ####
  salidas: ["3,0,E", "0,2,S", "3,2,S"]
  aberturas: []               # pasos sin puerta, que el libro dibuja abiertos
```

- En `forma`, `#` es suelo y `.` es roca. La fila de arriba es `y=0` y la
  columna de la izquierda `x=0`. **No uses espacios**: romperían el bloque YAML.
- Cada salida es `"x,y,lado"`, donde el lado es `N`, `S`, `E` u `O`. La celda
  tiene que ser de suelo, y el cargador avisa si no lo es.
- Una loseta con `tipo: corredor` cuenta como pasillo a efectos de juego: se
  vacía más a menudo y solo dos monstruos pueden atacar en ella.

El motor gira las losetas solo, así que basta con dibujarlas en una orientación
cualquiera.

### Añadir una condición

En `estados.yaml`:

```yaml
envenenado:
  texto: envenenado
  dura: aventura           # combate | aventura | permanente
  reglas:
    - {en: ataque, suma: -1, texto: envenenado}
  notas: Se cura con una poción.
```

Los estados de duración `combate` se caen al acabar el combate, y los de
`aventura` al descansar en el pueblo.

---

## Lo que no se puede hacer solo con datos

Si la regla necesita **lógica** —contar, elegir objetivos, encadenar efectos—
hace falta un poco de código. Son pocos casos y están todos en `hooks/`:

- **Efectos de hechizos y poderes** (cuántos esbirros mata una bola de fuego)
- **Reglas propias de monstruo** (los trolls que regeneran, el aliento del dragón)

Cómo se escriben está en [Extender](extender.md).
