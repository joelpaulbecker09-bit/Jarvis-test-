"""
Zeichnung des Partikel-Orbs auf einer Tkinter-Zeichenfläche.

Der Orb besteht aus:
    - einem weichen Halo aus mehreren transparent wirkenden Ringen
    - der rotierenden Partikelkugel
    - dem Schriftzug "JARVIS" in der Mitte

Die Farbe richtet sich nach dem aktuellen Zustand von JARVIS.
"""

import tkinter as tk
from typing import Optional

from src.core.state import AssistantState
from src.ui.particles import ParticleSphere
from src.ui.states import blend, style_for, to_hex

HALO_RINGS = 6
BACKGROUND_RGB = (5, 7, 10)


class OrbRenderer:
    """Zeichnet den Orb wiederholt neu auf ein Canvas."""

    def __init__(
        self,
        canvas: tk.Canvas,
        particle_count: int = 420,
        radius: float = 130.0,
    ):
        self.canvas = canvas
        self.sphere = ParticleSphere(count=particle_count, radius=radius)
        self.state = AssistantState.IDLE
        self.audio_level = 0.0
        self.title = "JARVIS"
        self._smoothed_level = 0.0

    def set_state(self, state: AssistantState) -> None:
        self.state = state

    def set_audio_level(self, level: float) -> None:
        self.audio_level = max(0.0, min(1.0, level))

    def render(self, delta: float) -> None:
        """Aktualisiert die Physik und zeichnet ein Bild."""
        style = style_for(self.state)

        # Pegel weich nachziehen, damit die Kugel nicht zuckt
        self._smoothed_level += (self.audio_level - self._smoothed_level) * 0.25

        self.sphere.update(
            delta=delta,
            audio_level=self._smoothed_level,
            pulse=style.pulse,
            rotation=style.rotation,
        )

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        center_x = width / 2
        center_y = height / 2

        self.canvas.delete("orb")

        self._draw_halo(center_x, center_y, style.glow)

        for point in self.sphere.project(center_x, center_y):
            color = to_hex(blend((10, 16, 26), style.color, point.brightness))
            size = max(0.6, point.size * (0.6 + 0.4 * point.brightness))

            self.canvas.create_oval(
                point.x - size,
                point.y - size,
                point.x + size,
                point.y + size,
                fill=color,
                outline="",
                tags="orb",
            )

        self.canvas.create_text(
            center_x,
            center_y,
            text=self.title,
            fill=to_hex(blend(style.color, (255, 255, 255), 0.75)),
            font=("Helvetica", 20, "bold"),
            tags="orb",
        )

    def _draw_halo(self, center_x: float, center_y: float, glow) -> None:
        base_radius = self.sphere.radius * self.sphere.scale

        for ring in range(HALO_RINGS, 0, -1):
            factor = ring / HALO_RINGS
            radius = base_radius * (1.0 + factor * 0.55)
            color = to_hex(blend(BACKGROUND_RGB, glow, (1.0 - factor) * 0.5))

            self.canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                fill=color,
                outline="",
                tags="orb",
            )


def make_orb(
    canvas: tk.Canvas,
    particle_count: Optional[int] = None,
    radius: Optional[float] = None,
) -> OrbRenderer:
    return OrbRenderer(
        canvas=canvas,
        particle_count=particle_count or 420,
        radius=radius or 130.0,
    )
