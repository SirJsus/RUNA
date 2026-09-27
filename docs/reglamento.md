# El reglamento

Qué está automatizado, qué decisiones hubo que tomar sobre el libro y qué sigue
siendo cosa tuya. Las páginas citadas son las del PDF de esta misma carpeta.

## Qué está implementado

| Parte del libro | Estado |
|---|---|
| Códigos de dados y regla explosiva del seis (p. 7) | Completo |
| Las 8 clases, con todos sus rasgos condicionales (p. 10-17) | Completo |
| Catálogo de equipo, aplastante contra cortante (p. 18-23) | Completo |
| Ataque, defensa, secuaces contra jefes, moral (p. 24-26) | Completo |
| Tabla de reacciones de cada monstruo (p. 28-30) | Completo |
| Generación de salas y su contenido (p. 31-41) | Completo |
| Bestiario entero: 25 criaturas con sus reglas propias | Completo |
| Los seis hechizos y los poderes de clase (p. 58-59) | Completo |
| Encuentros, orden de marcha, quién es atacado (p. 60-64) | Completo |
| Retirada y huida (p. 65) | Completo |
| Saqueo y reparto (p. 66-67) | Completo |
| Búsqueda, puertas secretas, tesoros ocultos, pistas (p. 68-71) | Completo |
| Trampas y cerraduras (p. 72-74) | Completo |
| Experiencia, subir de nivel, nivel máximo (p. 55-57) | Completo |
| Héroes caídos y resurrección (p. 55-56) | Completo |
| Misiones y recompensas épicas (p. 49-50) | Completo |
| Compra y venta de equipo entre aventuras | Completo |
| Dibujo de la mazmorra en rejilla d66 (p. 32-37) | Completo (o en papel, con `--grafo`) |
| Hoja de 20×28 y recorte de las salas que no caben (p. 51) | Completo |

## Lo que decides tú

Tres cosas del libro piden un criterio que no tiene sentido automatizar, así que
salen marcadas en la crónica con 📌 y las resuelves tú:

- **La armería** (característica especial 3): cambiar armas dentro de lo que
  permite cada clase.
- **La estatua** (característica 5): tocarla o no, y lo que salga de ahí.
- **La caja-puzzle** (característica 6): intentar resolverla o dejarla.

---

## Discrepancias del libro

Transcribir el reglamento sacó a la luz cosas que no cuadran. Ninguna se
resolvió en silencio.

### La tabla de monstruos errantes aparece dos veces, con valores distintos

| Dónde | Qué dice |
|---|---|
| Sección propia (p. 68) | `1-2` bichos, `3-4` esbirros, `5` extraños, `6` jefe |
| Eventos Especiales, entrada 2 (p. 98) | `1-3` bichos, `4` esbirros, `5` extraños, `6` jefe |

**Qué se hizo:** conservar las dos. `monstruo_errante` es la regla general y
`monstruo_errante_evento` la que usa esa entrada concreta. Cada sitio usa la
suya. Si prefieres unificarlas, es cambiar una línea en
`tablas/mazmorra.yaml`.

### Las reacciones del minotauro tienen un hueco

El libro salta de `3-4 lucha` a `6 lucha hasta la muerte` y deja el **5** sin
asignar.

**Qué se hizo:** extenderlo a `3-5 lucha`, que es lo que hacen las demás tablas
de esa misma página. Va marcado en el YAML con `enmienda: hueco en el original`.
Y hay un test que comprueba que *todas* las tablas de reacciones cubren el d6
entero, para que no se cuele otro hueco.

---

## Reglas fáciles de pasar por alto

Estas no son erratas del libro: son detalles que el texto dice claramente pero
que es fácil aplicar mal. Todos están implementados y con test.

### El ataque iguala, la defensa supera

El ataque acierta con **`total >= nivel`**. La defensa solo salva con
**`total > nivel`** — hay que superarlo, no igualarlo. Además, un **1 natural
siempre falla** y un **6 natural siempre salva**, pase lo que pase con los
modificadores. "Natural" es la primera cara del dado: una explosión no lo anula.

### La tirada de experiencia también hay que superarla

"Si el resultado es **más alto** que el nivel actual". Un 3 no sube a un
personaje de nivel 3. Y no puede intentarlo el mismo personaje dos veces
seguidas.

### La resurrección va al revés que todo lo demás

Se logra sacando **igual o inferior** al nivel del personaje. A los veteranos les
cuesta menos volver. Es la única tirada del juego con esa comparación.

### El nivel del jefe baja de inmediato

En cuanto pierde más de la mitad de su Vida, el jefe pierde un nivel — y el libro
subraya que ocurre **inmediatamente**, no al final del turno. Eso hace que sea
más fácil golpearle y esquivarle a partir de ese momento.

### Huir cuenta como ser derrotado

El FAQ es explícito: *"un monstruo que huye cuenta como derrotado, y por lo tanto
cuenta para propósitos de XP"*. También se tira su tesoro.

Pero hay una distinción fina: si huye por su **tabla de reacciones**, antes de
pelear, no hay saqueo ni experiencia (nunca llegaste a enfrentarte a él). Si huye
por **moral**, en mitad del combate, sí cuenta.

### Los monstruos errantes dan experiencia pero no tesoro

*"Puedes imaginar que dejaron el tesoro a salvo en su guarida"*. Y el dragón
nunca sale como monstruo errante: si sale en la tabla, se vuelve a tirar.

### El escudo no siempre protege

No cuenta al huir de un combate ni cuando unos monstruos errantes sorprenden al
grupo.

### Un mago sí puede coger un arma a dos manos

El FAQ lo permite, pero le cuenta como **arma ligera** (-1 al ataque) y le impide
lanzar hechizos mientras la lleve. Al pícaro le impide desarmar trampas.

### El nivel máximo depende de la especie

Humanos 5, enanos 4, elfos y halflings 3.

---

## Simplificaciones conscientes

### La momia que convierte a sus víctimas

El libro dice que quien muere a manos de una momia se levanta como otra momia y
hay que combatirla **en el mismo encuentro**. Aquí el bucle de combate maneja un
encuentro a la vez, así que la nueva momia se pelea **justo después**, de forma
consecutiva.

Es algo más fácil para el grupo, porque no acumula ataques en el mismo turno. Si
te importa, se arregla haciendo que `Combate` acepte varios encuentros a la vez;
es un cambio acotado, pero toca el reparto de ataques.

### Las siluetas de las losetas están transcritas a ojo

Las 36 losetas d66 y las 6 salas de entrada son dibujos a mano sobre papel
cuadriculado, con formas irregulares y dos que son círculos. Están transcritas
mirándolas: **las proporciones y el número de salidas son fieles, pero alguna
silueta retorcida es aproximada**, y los dos círculos se dibujan como celdas.

`runa --losetas` las enseña todas para compararlas con el PDF, y corregir una es
editar su bloque `forma`. Cómo, en [Tocar las reglas](datos.md#corregir-una-loseta).

Si prefieres dibujar tú el mapa en papel, `runa --grafo` no dibuja nada y solo te
pregunta la forma de cada sala.

### Volver sobre tus pasos no tira monstruos errantes

El libro dice que al reentrar en una sala ya visitada se tira un d6 y con un 1
aparecen monstruos errantes (p. 52). Eso no está implementado: moverse entre
salas conocidas es gratis.
