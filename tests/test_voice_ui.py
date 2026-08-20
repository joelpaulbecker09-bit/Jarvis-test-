"""Tests für Sprachschicht (Wake Word, Pegel) und Partikel-Physik."""

import math
import unittest

from src.core.state import AssistantState
from src.ui.particles import ParticleSphere
from src.ui.states import blend, style_for, to_hex
from src.voice.audio import level_of
from src.voice.wake_word import WakeWordDetector


class TestWakeWord(unittest.TestCase):
    def setUp(self):
        self.detector = WakeWordDetector()

    def test_detects_and_strips_wake_word(self):
        match = self.detector.detect("Jarvis, wie spät ist es?")

        self.assertTrue(match.detected)
        self.assertEqual(match.command, "wie spät ist es?")

    def test_tolerates_recognition_errors(self):
        self.assertTrue(self.detector.detect("Jervis mach das Licht an").detected)

    def test_ignores_other_sentences(self):
        self.assertFalse(self.detector.detect("Wie geht es dir").detected)

    def test_hey_jarvis(self):
        match = self.detector.detect("Hey Jarvis starte den Browser")

        self.assertTrue(match.detected)
        self.assertEqual(match.command, "starte den Browser")


class TestAudioLevel(unittest.TestCase):
    def test_silence_is_zero(self):
        self.assertEqual(level_of(b"\x00\x00" * 100), 0.0)

    def test_loud_signal_is_higher_than_quiet(self):
        quiet = level_of((1000).to_bytes(2, "little", signed=True) * 100)
        loud = level_of((20000).to_bytes(2, "little", signed=True) * 100)

        self.assertGreater(loud, quiet)
        self.assertLessEqual(loud, 1.0)


class TestParticleSphere(unittest.TestCase):
    def test_particles_sit_on_unit_sphere(self):
        sphere = ParticleSphere(count=200, radius=100)

        for particle in sphere.particles:
            radius = math.sqrt(particle.x ** 2 + particle.y ** 2 + particle.z ** 2)
            self.assertAlmostEqual(radius, 1.0, places=6)

    def test_audio_level_expands_sphere(self):
        quiet = ParticleSphere(count=50)
        loud = ParticleSphere(count=50)

        quiet.update(delta=0.033, audio_level=0.0)
        loud.update(delta=0.033, audio_level=1.0)

        self.assertGreater(loud.scale, quiet.scale)

    def test_projection_is_sorted_back_to_front(self):
        sphere = ParticleSphere(count=80)
        sphere.update(delta=0.033)

        points = sphere.project(center_x=400, center_y=300)
        depths = [point.depth for point in points]

        self.assertEqual(depths, sorted(depths))
        self.assertEqual(len(points), 80)

    def test_rotation_advances(self):
        sphere = ParticleSphere(count=10)
        sphere.update(delta=0.033, rotation=0.02)

        self.assertGreater(sphere.angle, 0.0)


class TestStateStyles(unittest.TestCase):
    def test_every_state_has_a_style(self):
        for state in AssistantState:
            self.assertTrue(style_for(state).label)

    def test_colors_are_hex(self):
        self.assertEqual(to_hex((5, 7, 10)), "#05070a")
        self.assertEqual(blend((0, 0, 0), (100, 100, 100), 0.5), (50, 50, 50))


if __name__ == "__main__":
    unittest.main()
