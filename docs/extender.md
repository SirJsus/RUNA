# Extender

Lo que no cabe en datos va aquí. Son pocos casos, y todos entran por los mismos
dos sitios: `hooks/efectos.py` y `hooks/monstruos.py`.

La frontera es sencilla:

> **Datos** si la regla es "suma tanto cuando pase tal cosa".
> **Código** si hay que contar, elegir objetivos o encadenar efectos.

---

## Añadir un hechizo o un poder

Dos pasos: declararlo en `hechizos.yaml` y escribir su efecto.

### 1. Declararlo

```yaml
muro_de_hielo:
  nombre: Muro de Hielo
  tipo: hechizo              # hechizo | poder | objeto
  tirada: hechizo            # tipo de tirada; "" si es automático
  momentos: [turno]          # turno | defensa | libre | fuera_de_combate
  objetivo: monstruo         # monstruo | aliado | uno_mismo | grupo | ninguno
  gasta: hechizos            # el recurso que consume
  usable_por: [mago, elfo]   # vacío = cualquiera
  efecto: muro_de_hielo      # el nombre del gancho
  notas: Bloquea a los monstruos durante un turno.
```

### 2. Escribir el efecto

En `hooks/efectos.py`, dentro de `registrar(juego)`:

```python
@habilidades.registrar("muro_de_hielo")
def muro_de_hielo(personaje, combate, habilidad, primer_turno=False, **kw):
    r = lanzar(combate, personaje, habilidad, primer_turno)
    if r is None:                       # la acción estaba prohibida
        return None
    personaje.gastar(habilidad.gasta)
    if r.exito:
        combate.marcas["monstruos_bloqueados"] = True
        combate.reg.anotar("hechizo", f"{personaje.nombre} levanta un muro de hielo.")
    return r
```

Lo que tienes a mano:

| Objeto | Para qué |
|---|---|
| `combate.enc` | El encuentro: `.cantidad`, `.vida`, `.nivel`, `.perfil` |
| `combate.herir_monstruo(n, por=..., por_hechizo=True)` | Aplicar daño |
| `combate.vivos` | Los personajes que siguen en pie |
| `combate.reg.anotar(tipo, texto)` | Dejarlo escrito en la crónica |
| `combate.rng` | El azar de la partida (nunca uses `random` directamente) |
| `combate.marcas` | Un diccionario para notas que duran el combate |
| `combate.decisor` | Preguntarle algo al jugador |
| `juego.estado("protegido")` | Colgar una condición del catálogo |

Si tu efecto necesita preguntar:

```python
from runa.core.decisions import Opcion, Pregunta

objetivo = combate.decisor.elegir(Pregunta.crear(
    "a_quien_protejo", "¿A quién cubre el muro?",
    [Opcion(p.nombre, p.nombre, f"{p.vida}/{p.vida_max} Vida")
     for p in combate.vivos],
))
```

**La primera opción es la recomendada**: `DecisorPorDefecto` siempre la toma, así
que de ese orden depende que el modo `--auto` haga algo sensato.

`Juego.validar()` avisa si un hechizo declara un efecto que nadie ha registrado,
así que no puedes olvidarte de la segunda mitad.

---

## Añadir una regla propia de un monstruo

En `hooks/monstruos.py`. Hay seis momentos:

| Momento | Firma | Cuándo |
|---|---|---|
| `antes` | `(combate, enc)` | Una vez, al empezar el combate |
| `turno` | `(combate, enc) -> bool` | Su turno. `True` sustituye sus ataques |
| `al_herir` | `(combate, enc, personaje) -> bool` | Antes de aplicar daño. `True` lo sustituye |
| `tras_herir` | `(combate, enc, personaje)` | Después del daño: venenos, contagios |
| `al_morir` | `(combate, enc)` | Al ser derrotado de verdad |
| `tras_hechizo` | `(combate, enc, muertos)` | Cuando un hechizo le hace bajas |

```python
@ganchos.registrar("turno", "basilisco")
def mirada_del_basilisco(combate, encuentro) -> bool:
    """Con 1-2 petrifica en vez de morder."""
    if roll("d6", combate.rng).total > 2:
        return False                      # que ataque normalmente
    amenaza = juego.amenaza("Mirada del basilisco", 5, ["mirada"])
    for personaje in list(combate.vivos):
        r = juego.tirar("salvacion", personaje, combate.rng, amenaza=amenaza)
        combate.reg.anotar("salvacion", r.describir(), tirada=r)
        if not r.exito:
            personaje.estados.append(juego.estado("petrificado"))
    return True                           # sustituye a sus ataques
```

Ejemplos reales que ya están escritos, por si buscas uno parecido al tuyo:

| Quieres... | Mira |
|---|---|
| Daño extra tras ser herido | los venenos de ciempiés, araña y hongos |
| Robar en vez de herir | `al_herir` de la Plaga del Hierro |
| Sustituir los ataques | el aliento del dragón y de la quimera |
| Resucitar monstruos | la regeneración de los trolls |
| Convertir a una víctima | el contagio de la momia |
| Algo al empezar la batalla | la mirada de la medusa, los poderes del Señor del Caos |
| Cambiar la reacción | los trolls ante un enano |
| Bloquear la huida | la telaraña de la araña gigante |

---

## Añadir un tipo de contenido de sala

Todo lo que puede haber en una habitación se despacha en
`exploracion.py`, en `_despachar()`, mirando de qué tabla vino el resultado.
Añadir un tipo nuevo es añadir una rama ahí y un método que lo resuelva.

---

## Un juego nuevo

**Antes de nada: no intentes hacer el motor universal.** Sin un segundo juego
delante, cualquier abstracción estará mal apuntada. La forma de proceder es
construir el segundo juego usando lo que ya sirve, y **extraer después** lo que
resulte de verdad común.

### Qué deberías poder reutilizar tal cual

Todo `core/`: dados, tablas, tiradas con modificadores, entidades, bestiario,
habilidades, registro de eventos, decisor, mapa y crónica. Son piezas que no
mencionan Cuatro contra la Oscuridad por ninguna parte.

### Qué tendrás que escribir

```
games/tu_juego/
  data/       el reglamento nuevo en YAML
  juego.py    ensamblar los datos y exponer las operaciones
  <bucles>.py el flujo propio del juego
  hooks/      lo que no quepa en datos
```

### Cómo empezar

0. **Para experimentar sin tocar nada**, `Juego(datos=<carpeta>)` carga otra
   carpeta de datos. Cada instancia lleva la suya, así que puedes comparar dos
   variantes del reglamento en el mismo proceso.
1. **Copia la forma de `games/cco/juego.py`.** Es el molde: carga los YAML,
   construye el `Resolutor` con los tipos de tirada del nuevo juego, y expone
   `crear_personaje`, `tirar`, `atacar`, `validar`.
2. **Traduce el reglamento a `reglas.yaml` primero.** Los tipos de tirada y sus
   comparaciones. Eso te dirá enseguida si el motor de tiradas te sirve.
3. **Escribe `validar()` desde el principio.** Transcribir un reglamento genera
   erratas, y que el programa te las liste ahorra horas.
4. **Escribe los ejemplos del libro como tests.** Si el manual trae combates
   resueltos, son la mejor prueba de que lo has entendido bien.
5. **Deja los bucles para el final.** Lo específico de cada juego es el flujo;
   lo compartido son las tiradas y las tablas.

### Señales de que el motor se te queda corto

Si te ves haciendo esto, para y piénsalo:

- **Añadir un `if` con el nombre de un juego dentro de `core/`.** Nunca. Ese caso
  se resuelve con un parámetro o un gancho.
- **Necesitas un tipo de dado o una notación que no existe.** Eso sí va en
  `core/dice.py`: es genuinamente genérico.
- **Tu juego no compara contra un número objetivo** (usa reservas de dados,
  éxitos contados, cartas). Entonces `checks.py` no te vale y toca escribir un
  resolutor hermano. Las demás piezas te siguen sirviendo.
