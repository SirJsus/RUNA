"""Fuente de aleatoriedad reproducible.

Todo el azar del juego pasa por aqui. Al fijar una semilla, una partida entera
se puede repetir de forma identica: sirve para tests, para depurar y para
rejugar una aventura tal cual ocurrio.
"""

from __future__ import annotations

import random
import secrets


class RandomSource:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = secrets.randbelow(2**32) if seed is None else seed
        self._rnd = random.Random(self.seed)
        self.count = 0

    def die(self, faces: int) -> int:
        """Lanza un dado de `faces` caras."""
        if faces < 2:
            raise ValueError(f"un dado necesita al menos 2 caras, no {faces}")
        self.count += 1
        return self._rnd.randint(1, faces)

    def choice(self, items):
        self.count += 1
        return self._rnd.choice(list(items))

    def shuffled(self, items):
        pool = list(items)
        self.count += 1
        self._rnd.shuffle(pool)
        return pool

    def __repr__(self) -> str:
        return f"RandomSource(seed={self.seed}, tiradas={self.count})"
