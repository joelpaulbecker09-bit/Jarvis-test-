"""
Partikel-Orb

Physik und Projektion der Partikelkugel. Bewusst ohne Zeichenbefehle und
ohne Tkinter, damit die Bewegung getrennt vom Rendering testbar ist.

Die Partikel sitzen gleichmäßig verteilt auf einer Kugel (Fibonacci-
Verteilung), rotieren um die Y-Achse und atmen mit einer Sinuswelle. Der
Mikrofonpegel verstärkt den Ausschlag, wodurch die Kugel auf die Stimme
reagiert.
"""

import math
import random
from dataclasses import dataclass
from typing import List

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


@dataclass
class Particle:
    """Ein Punkt auf der Kugeloberfläche."""

    x: float
    y: float
    z: float
    speed: float
    phase: float
    size: float


@dataclass(frozen=True)
class ProjectedParticle:
    """Auf die Bildfläche projizierter Punkt."""

    x: float
    y: float
    depth: float
    size: float

    @property
    def brightness(self) -> float:
        """Vordere Partikel leuchten stärker als hintere (0.25 bis 1.0)."""
        return 0.25 + 0.75 * ((self.depth + 1.0) / 2.0)


class ParticleSphere:
    """
    Rotierende Partikelkugel.

    Verwendung:

        sphere = ParticleSphere(count=420, radius=130)
        sphere.update(delta=0.033, audio_level=0.4, pulse=0.16, rotation=0.01)
        points = sphere.project(center_x=400, center_y=300)
    """

    def __init__(self, count: int = 420, radius: float = 130.0, seed: int = 7):
        self.count = max(1, count)
        self.radius = radius
        self.angle = 0.0
        self.time = 0.0
        self.scale = 1.0

        generator = random.Random(seed)
        self.particles: List[Particle] = []

        for index in range(self.count):
            # Fibonacci-Kugel: gleichmäßige Verteilung ohne Pole-Häufung
            y = 1.0 - (index / max(1, self.count - 1)) * 2.0
            ring = math.sqrt(max(0.0, 1.0 - y * y))
            theta = GOLDEN_ANGLE * index

            self.particles.append(
                Particle(
                    x=math.cos(theta) * ring,
                    y=y,
                    z=math.sin(theta) * ring,
                    speed=generator.uniform(0.6, 1.6),
                    phase=generator.uniform(0.0, math.tau),
                    size=generator.uniform(1.2, 3.0),
                )
            )

    def update(
        self,
        delta: float,
        audio_level: float = 0.0,
        pulse: float = 0.05,
        rotation: float = 0.004,
    ) -> None:
        """Bewegt die Kugel einen Zeitschritt weiter."""
        delta = max(0.0, min(0.2, delta))
        self.time += delta
        self.angle = (self.angle + rotation * delta * 60.0) % math.tau

        breathing = math.sin(self.time * 1.6) * pulse
        reaction = max(0.0, min(1.0, audio_level)) * 0.35

        self.scale = 1.0 + breathing + reaction

    def project(
        self,
        center_x: float,
        center_y: float,
        perspective: float = 420.0,
    ) -> List[ProjectedParticle]:
        """Projiziert alle Partikel auf die Zeichenfläche (hinten zuerst)."""
        cosine = math.cos(self.angle)
        sine = math.sin(self.angle)
        points: List[ProjectedParticle] = []

        for particle in self.particles:
            wobble = 1.0 + 0.05 * math.sin(self.time * particle.speed + particle.phase)
            radius = self.radius * self.scale * wobble

            x = particle.x * radius
            y = particle.y * radius
            z = particle.z * radius

            rotated_x = x * cosine - z * sine
            rotated_z = x * sine + z * cosine

            factor = perspective / (perspective + rotated_z)

            points.append(
                ProjectedParticle(
                    x=center_x + rotated_x * factor,
                    y=center_y + y * factor,
                    depth=rotated_z / max(1e-6, radius),
                    size=particle.size * factor,
                )
            )

        points.sort(key=lambda point: point.depth)
        return points
