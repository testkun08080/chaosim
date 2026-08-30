"""Sound: which file an event gets, when it fires, and how loud.

``docs/sfx-design.md`` calls sound the hardest part of this pipeline, and every
failure it lists is silent — the video still renders, it just sounds wrong. So
the checks here are about the ways that happens: the wrong file, the same file
every time, forty of them at once, or none at all.
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from pipeline.audio_assets import (
    VOLUME_CEILING,
    VOLUME_FLOOR,
    _pitch_for,
    resolve_event_cues,
    should_generate,
    thin_events,
)
from pipeline.sfx_library import (
    bucket_for,
    cache_key,
    cached_path,
    event_spec,
    required_sounds,
    resolve_event_sound,
)
from pipeline.sfx_report import build_report, max_polyphony, onset_deltas_ms

CATALOG = {
    "sfx_events": {
        "impact": {
            "variants": 2,
            "soft": {"prompt": "light knock", "duration": 0.6},
            "mid": {"prompt": "firm hit", "duration": 0.9},
            "hard": {"prompt": "heavy hit", "duration": 1.2},
        },
        "collapse": {"prompt": "debris", "duration": 2.2},
    },
}


class BucketTests(unittest.TestCase):
    def test_intensity_selects_the_variant(self):
        self.assertEqual(bucket_for(0.1), "soft")
        self.assertEqual(bucket_for(0.5), "mid")
        self.assertEqual(bucket_for(0.9), "hard")

    def test_unusable_intensity_lands_in_the_middle(self):
        self.assertEqual(bucket_for(None), "mid")


class EventSpecTests(unittest.TestCase):
    def test_a_graded_role_merges_the_bucket_over_the_shared_settings(self):
        spec = event_spec(CATALOG, "impact", 0.9)

        self.assertEqual(spec["prompt"], "heavy hit")
        self.assertEqual(spec["variants"], 2)

    def test_a_flat_role_uses_one_sound_at_every_intensity(self):
        self.assertEqual(event_spec(CATALOG, "collapse", 0.1)["bucket"], "all")
        self.assertEqual(event_spec(CATALOG, "collapse", 0.9)["bucket"], "all")

    def test_an_unknown_type_resolves_to_impact_and_takes_its_name(self):
        """Otherwise every typo caches its own copy of the same audio."""
        spec = event_spec(CATALOG, "kaboom", 0.9)

        self.assertEqual(spec["type"], "impact")
        self.assertEqual(cached_path(spec).name, cached_path(event_spec(CATALOG, "impact", 0.9)).name)

    def test_a_catalog_without_the_role_gives_up_rather_than_guessing(self):
        self.assertIsNone(event_spec({"sfx_events": {}}, "impact", 0.5))


class CacheKeyTests(unittest.TestCase):
    def test_editing_a_prompt_yields_a_new_file(self):
        a = cache_key({"prompt": "one", "duration": 1, "prompt_influence": 0.4, "loop": False})
        b = cache_key({"prompt": "two", "duration": 1, "prompt_influence": 0.4, "loop": False})

        self.assertNotEqual(a, b)

    def test_the_same_spec_always_reuses_the_same_file(self):
        spec = {"prompt": "one", "duration": 1, "prompt_influence": 0.4, "loop": False}

        self.assertEqual(cache_key(spec), cache_key(dict(spec)))

    def test_variants_are_separate_files(self):
        spec = {"prompt": "one", "duration": 1, "prompt_influence": 0.4, "loop": False}

        self.assertNotEqual(cache_key(spec, 0), cache_key(spec, 1))


class RequiredSoundsTests(unittest.TestCase):
    def test_events_sharing_a_bucket_share_one_paid_generation(self):
        events = [{"type": "collapse", "intensity": 0.9}] * 5

        sounds = required_sounds(CATALOG, events)

        self.assertEqual(len(sounds), 1)
        self.assertEqual(sounds[0]["events"], 5)

    def test_a_role_with_variants_spreads_across_them(self):
        events = [{"type": "impact", "intensity": 0.9}] * 4

        sounds = required_sounds(CATALOG, events)

        self.assertEqual(len(sounds), 2)
        self.assertEqual(sorted(s["variant"] for s in sounds), [0, 1])

    def test_a_type_the_catalog_cannot_voice_is_left_out(self):
        self.assertEqual(required_sounds({"sfx_events": {}}, [{"type": "impact"}]), [])


class ResolveEventSoundTests(unittest.TestCase):
    def test_a_shipped_library_wins_over_generation(self):
        with mock.patch("pipeline.sfx_library.library_sounds",
                        return_value=[Path("a.wav"), Path("b.wav")]):
            path, origin = resolve_event_sound(CATALOG, "impact", 0.9)

        self.assertEqual(origin, "library")
        self.assertEqual(path, Path("a.wav"))

    def test_the_library_is_round_robined_so_a_chain_is_not_one_sample(self):
        with mock.patch("pipeline.sfx_library.library_sounds",
                        return_value=[Path("a.wav"), Path("b.wav")]):
            picks = [resolve_event_sound(CATALOG, "impact", 0.9, occurrence=i)[0]
                     for i in range(3)]

        self.assertEqual(picks, [Path("a.wav"), Path("b.wav"), Path("a.wav")])

    def test_nothing_cached_and_generation_off_reports_none(self):
        with mock.patch("pipeline.sfx_library.library_sounds", return_value=[]), \
             mock.patch("pipeline.sfx_library.cached_path", return_value=Path("/nope.mp3")):
            self.assertEqual(resolve_event_sound(CATALOG, "impact", 0.9)[1], "none")


class ThinEventsTests(unittest.TestCase):
    def test_events_too_close_to_separate_are_merged(self):
        events = [{"t": 1.0, "intensity": 0.5}, {"t": 1.01, "intensity": 0.5}]

        self.assertEqual(len(thin_events(events)), 1)

    def test_the_loudest_of_a_cluster_survives_not_the_first(self):
        events = [{"t": 1.0, "intensity": 0.2}, {"t": 1.01, "intensity": 0.9}]

        self.assertEqual(thin_events(events)[0]["intensity"], 0.9)

    def test_well_separated_events_all_survive(self):
        events = [{"t": 1.0}, {"t": 2.0}, {"t": 3.0}]

        self.assertEqual(len(thin_events(events)), 3)


class CueBuildingTests(unittest.TestCase):
    def build(self, events):
        with mock.patch("pipeline.sfx_library.library_sounds",
                        return_value=[Path("hit.wav")]):
            return resolve_event_cues(events, sim_start=2.0, base_vol=0.5, catalog=CATALOG)

    def test_cues_are_offset_to_where_the_sim_starts_on_the_base_track(self):
        cues = self.build([{"t": 1.0, "type": "impact", "intensity": 0.9}])

        self.assertEqual(cues[0]["start"], 3.0)

    def test_intensity_drives_volume_between_the_floor_and_the_ceiling(self):
        quiet = self.build([{"t": 0, "type": "impact", "intensity": 0.0}])[0]
        loud = self.build([{"t": 0, "type": "impact", "intensity": 1.0}])[0]

        self.assertAlmostEqual(quiet["volume"], 0.5 * VOLUME_FLOOR, places=3)
        self.assertAlmostEqual(loud["volume"], 0.5 * VOLUME_CEILING, places=3)
        self.assertLess(quiet["volume"], loud["volume"])

    def test_consecutive_hits_are_detuned_so_a_chain_is_not_one_sample(self):
        cues = self.build([{"t": i * 0.5, "type": "impact", "intensity": 0.8}
                           for i in range(4)])

        self.assertGreater(len({c["pitch"] for c in cues}), 1)

    def test_the_detune_is_deterministic_so_a_rerender_is_the_same_video(self):
        self.assertEqual(_pitch_for(3), _pitch_for(3))
        self.assertEqual(_pitch_for(0), _pitch_for(5))

    def test_an_event_with_no_sound_anywhere_is_dropped_not_crashed(self):
        with mock.patch("pipeline.sfx_library.library_sounds", return_value=[]), \
             mock.patch("pipeline.audio_assets.resolve_sfx_path", return_value=None), \
             mock.patch("pipeline.sfx_library.cached_path", return_value=Path("/nope.mp3")):
            cues = resolve_event_cues([{"t": 1.0, "type": "impact"}], 0.0, 0.5,
                                      catalog=CATALOG)

        self.assertEqual(cues, [])


class GenerationGateTests(unittest.TestCase):
    def test_generation_is_off_by_default_when_a_sandbox_could_bill_us(self):
        with mock.patch("pipeline.comfyui.comfyui_available", return_value=True), \
             mock.patch.dict(os.environ, {"CHAOSIM_SFX_GENERATE": ""}):
            self.assertFalse(should_generate({}))

    def test_generation_is_on_when_nothing_can_be_billed(self):
        """With no sandbox the 'generated' sound is a free placeholder tone."""
        with mock.patch("pipeline.comfyui.comfyui_available", return_value=False):
            self.assertTrue(should_generate({}))

    def test_a_template_can_opt_in_explicitly(self):
        with mock.patch("pipeline.comfyui.comfyui_available", return_value=True):
            self.assertTrue(should_generate({"generate": True}))


class ReportTests(unittest.TestCase):
    def test_only_snapped_events_contribute_a_timing_error(self):
        events = [{"t": 1.2, "cue_t": 1.0}, {"t": 3.0}]

        self.assertEqual([round(d) for d in onset_deltas_ms(events)], [200])

    def test_overlapping_cues_are_counted(self):
        cues = [{"start": 1.0}, {"start": 1.1}, {"start": 1.2}, {"start": 9.0}]

        self.assertEqual(max_polyphony(cues), 3)

    def test_a_concept_whose_events_all_found_sounds_reads_fully_voiced(self):
        events = [{"t": 1.0, "type": "impact", "intensity": 0.9, "source": "onset",
                   "cue_t": 0.9}]
        cues = [{"start": 1.0, "origin": "generated", "type": "impact"}]

        report = build_report({"slug": "s", "source": "comfyui"}, events, cues, [], None)

        self.assertEqual(report["generated_ratio"], 1.0)
        self.assertEqual(report["measured_ratio"], 1.0)
        self.assertEqual(report["onset_delta_median_ms"], 100.0)
        self.assertIsNone(report["lufs"])

    def test_thinned_events_are_reported_rather_than_hidden(self):
        events = [{"t": 1.0}, {"t": 1.01}]
        cues = [{"start": 1.0, "origin": "library"}]

        self.assertEqual(build_report({"slug": "s"}, events, cues, [], None)["thinned"], 1)


if __name__ == "__main__":
    unittest.main()
