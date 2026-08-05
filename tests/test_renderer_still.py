"""Tests for still / branding output selection in the renderer."""

from pathlib import Path
from unittest import TestCase, mock

from pipeline import renderer


class RenderConceptStillTests(TestCase):
    def test_still_param_writes_png(self):
        concept = {
            "slug": "branding_channel",
            "title": "Chaos Sim",
            "scene_script": "branding_assets",
            "duration_sec": 1,
            "params": {"still": True, "shot": "channel", "resolution": [640, 360]},
        }
        with mock.patch.object(renderer, "blender_available", return_value=False):
            with mock.patch.object(renderer, "_stub_still", return_value=Path("out.png")) as stub:
                out = renderer.render_concept(concept, Path("c.yaml"), Path("/tmp/out"))
        stub.assert_called_once()
        self.assertEqual(out.suffix, ".png")
        self.assertEqual(stub.call_args.args[1].name, "branding_channel.png")

    def test_normal_concept_writes_mp4(self):
        concept = {
            "slug": "sample_001",
            "title": "Pendulum",
            "scene_script": "double_pendulum",
            "duration_sec": 10,
            "params": {},
        }
        with mock.patch.object(renderer, "blender_available", return_value=False):
            with mock.patch.object(renderer, "_stub_render", return_value=Path("out.mp4")) as stub:
                out = renderer.render_concept(concept, Path("c.yaml"), Path("/tmp/out"))
        stub.assert_called_once()
        self.assertEqual(out.suffix, ".mp4")
