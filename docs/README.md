# Documentación de RUNA

*Reglas Unificadas, Narración y Azar.*

Toda la documentación del proyecto, en orden de menos a más técnica.
Cada documento se puede leer suelto.

| Documento | Para qué sirve | Para quién |
|---|---|---|
| [Jugar](jugar.md) | Instalar, empezar una partida y entender qué te pregunta | Si solo quieres jugar |
| [El reglamento](reglamento.md) | Qué automatiza, qué decisiones se tomaron sobre el libro y qué te toca a ti | Si quieres saber si el programa juega "bien" |
| [Tocar las reglas](datos.md) | Cambiar clases, monstruos, tablas y objetos editando YAML, sin programar | Si quieres ajustar el juego |
| [Arquitectura](arquitectura.md) | Cómo está construido y por qué | Si vas a tocar el código |
| [Extender](extender.md) | Añadir hechizos, reglas de monstruo o un juego nuevo | Si vas a programar |
| [Referencia](referencia.md) | Chuleta de las piezas principales | Para consultar al vuelo |

## Por dónde empezar

- **Nunca lo has ejecutado** → [Jugar](jugar.md).
- **Quieres cambiar algo del juego** → [Tocar las reglas](datos.md). La mayoría
  de cosas se cambian editando un `.yaml`, sin escribir código.
- **Vas a programar** → [Arquitectura](arquitectura.md) primero, que explica las
  cuatro ideas en las que se apoya todo lo demás.

## El reglamento original

En esta misma carpeta están `Cuatro contra la Oscuridad.md` y su `.pdf`: es el
libro de reglas del que se transcribió todo. Cuando la documentación cita una
página, se refiere a ese PDF.
