"""The ComfyUI backend: concept -> jobs -> events.

These cover the parts that decide what gets sent and when a sound lands. The
subprocess boundary itself is not exercised here — that needs a running
ComfyUI — but everything that shapes the request is pure and testable.
"""

import unittest

from pipeline.catalog import scan_recipe, validate_concept
from pipeline.renderer import concept_source
from pipeline.sfx_events import cue_sheet_events, normalize_event, snap_to_onsets
from simulators.comfyui import resolve_overrides
from simulators.comfyui.recipes import generative_shots, look_assets


def codes(findings):
    return [f["code"] for f in findings]


def recipes(names=("generative_shots", "look_assets")):
    """The recipe scan shape, as collect_catalog would build it."""
    return {
        "generative_shots": {"name": "generative_shots",
                             "hooks": {"build_jobs": True, "apply_assets": False},
                             "keys": {"shots", "resolution", "seed", "recipe", "max_shots"},
                             "asset_recipe": False},
        "look_assets": {"name": "look_assets",
                        "hooks": {"build_jobs": True, "apply_assets": True},
                        "keys": {"assets", "seed", "recipe", "asset_size"},
                        "asset_recipe": True},
    } if names else {}


class SourceTests(unittest.TestCase):
    def test_missing_source_means_blender(self):
        self.assertEqual(concept_source({"slug": "s"}), "blender")

    def test_unknown_source_raises(self):
        with self.assertRaises(ValueError):
            concept_source({"slug": "s", "source": "houdini"})


class OverrideMappingTests(unittest.TestCase):
    def test_logical_names_become_node_addressed_inputs(self):
        out = resolve_overrides("08_video/keyframe_then_video.json",
                                {"prompt": "move", "duration": 5})

        self.assertEqual(out, {"10.prompt": "move", "10.duration": 5})

    def test_unknown_input_raises_rather_than_silently_using_the_template_default(self):
        with self.assertRaises(KeyError):
            resolve_overrides("08_video/keyframe_then_video.json", {"promt": "typo"})

    def test_none_values_are_dropped_so_the_workflow_default_stands(self):
        out = resolve_overrides("08_video/wan_image_to_video.json",
                                {"prompt": "x", "seed": None})

        self.assertEqual(out, {"10.prompt": "x"})


class GenerativeShotsTests(unittest.TestCase):
    def test_duration_is_quantized_to_what_the_model_accepts(self):
        self.assertEqual(generative_shots.quantize_duration(6), 5)
        self.assertEqual(generative_shots.quantize_duration(12), 10)
        self.assertEqual(generative_shots.quantize_duration(99), 15)

    def test_unparseable_duration_falls_back_to_the_default(self):
        self.assertEqual(generative_shots.quantize_duration(None), 5)

    def test_each_shot_gets_its_own_seed_so_shots_do_not_repeat(self):
        concept = {"slug": "s", "comfyui": {"seed": 10, "shots": [{"prompt": "a"}, {"prompt": "b"}]}}

        seeds = [s["seed"] for s in generative_shots.plan_shots(concept)]

        self.assertEqual(seeds, [11, 12])

    def test_a_shot_asking_for_audio_uses_the_workflow_that_saves_the_track(self):
        concept = {"slug": "s", "comfyui": {"shots": [{"prompt": "a", "generate_audio": True}]}}

        job = generative_shots.build_jobs(concept)[0]

        self.assertEqual(job["workflow"], "08_video/video_with_audio.json")
        self.assertIn("audio_prefix", job["inputs"])

    def test_max_shots_caps_the_cut_list(self):
        concept = {"slug": "s", "comfyui": {"max_shots": 1,
                                            "shots": [{"prompt": "a"}, {"prompt": "b"}]}}

        self.assertEqual(len(generative_shots.build_jobs(concept)), 1)

    def test_the_settings_ceiling_wins_over_a_concept_asking_for_more(self):
        concept = {"slug": "s", "comfyui": {"max_shots": 5,
                                            "shots": [{"prompt": str(i)} for i in range(5)]}}

        jobs = generative_shots.build_jobs(concept, None, {"comfyui": {"max_shots": 2}})

        self.assertEqual(len(jobs), 2)

    def test_a_concept_may_go_under_the_ceiling(self):
        concept = {"slug": "s", "comfyui": {"max_shots": 1,
                                            "shots": [{"prompt": str(i)} for i in range(5)]}}

        jobs = generative_shots.build_jobs(concept, None, {"comfyui": {"max_shots": 4}})

        self.assertEqual(len(jobs), 1)

    def test_settings_supply_the_cheap_defaults(self):
        concept = {"slug": "s", "comfyui": {"shots": [{"prompt": "a"}]}}

        shot = generative_shots.plan_shots(
            concept, {"comfyui": {"resolution": "720P", "shot_duration_sec": 10}})[0]

        self.assertEqual(shot["resolution"], "720P")
        self.assertEqual(shot["duration"], 10)


class LookAssetsTests(unittest.TestCase):
    def test_assets_without_a_param_are_skipped(self):
        concept = {"slug": "s", "comfyui": {"assets": [{"prompt": "x"}]}}

        self.assertEqual(look_assets.build_jobs(concept), [])

    def test_a_missing_file_leaves_the_concepts_own_value_in_place(self):
        concept = {"slug": "s", "params": {"world_hdri": "assets/hdri/real.hdr"},
                   "comfyui": {"assets": [{"param": "world_hdri", "prompt": "sky"}]}}

        patched = look_assets.apply_assets(concept, {"world_hdri": "/does/not/exist.png"})

        self.assertEqual(patched["params"]["world_hdri"], "assets/hdri/real.hdr")

    def test_apply_assets_does_not_mutate_the_input_concept(self):
        concept = {"slug": "s", "params": {"a": 1},
                   "comfyui": {"assets": [{"param": "a", "prompt": "x"}]}}

        look_assets.apply_assets(concept, {})

        self.assertEqual(concept["params"], {"a": 1})


class CueSheetTests(unittest.TestCase):
    def test_cues_are_laid_out_on_the_concatenated_timeline(self):
        shots = [{"duration": 5, "cues": [{"t": 1.0}]},
                 {"duration": 5, "name": "two", "cues": [{"t": 2.0}]}]

        events = cue_sheet_events(shots)

        self.assertEqual([e["t"] for e in events], [1.0, 7.0])
        self.assertEqual(events[1]["object"], "two")

    def test_a_cue_past_the_end_of_its_shot_is_dropped(self):
        """A shortened shot must not fire its sound over the next one."""
        events = cue_sheet_events([{"duration": 5, "cues": [{"t": 9.0}]}])

        self.assertEqual(events, [])

    def test_unknown_cue_type_falls_back_rather_than_losing_the_sound(self):
        self.assertEqual(normalize_event({"t": 1, "type": "kaboom"})["type"], "impact")

    def test_intensity_is_clamped_and_defaulted(self):
        self.assertEqual(normalize_event({"t": 0, "intensity": 5})["intensity"], 1.0)
        self.assertEqual(normalize_event({"t": 0})["intensity"], 0.6)


class OnsetSnapTests(unittest.TestCase):
    def test_a_cue_near_an_onset_is_moved_onto_it(self):
        events = cue_sheet_events([{"duration": 5, "cues": [{"t": 1.0}]}])

        snapped = snap_to_onsets(events, [1.2])

        self.assertEqual(snapped[0]["t"], 1.2)
        self.assertEqual(snapped[0]["source"], "onset")
        self.assertEqual(snapped[0]["cue_t"], 1.0)

    def test_a_cue_with_no_onset_nearby_keeps_its_predicted_time(self):
        events = cue_sheet_events([{"duration": 5, "cues": [{"t": 1.0}]}])

        snapped = snap_to_onsets(events, [4.0])

        self.assertEqual(snapped[0]["t"], 1.0)
        self.assertEqual(snapped[0]["source"], "cue")

    def test_no_onsets_at_all_leaves_every_cue_alone(self):
        events = cue_sheet_events([{"duration": 5, "cues": [{"t": 1.0}, {"t": 2.0}]}])

        self.assertEqual(snap_to_onsets(events, []), events)

    def test_two_cues_cannot_collapse_onto_the_same_onset(self):
        events = cue_sheet_events([{"duration": 5, "cues": [{"t": 1.0}, {"t": 1.1}]}])

        snapped = snap_to_onsets(events, [1.05])

        self.assertEqual(len({e["t"] for e in snapped}), 2)


class ComfyuiCatalogTests(unittest.TestCase):
    def base(self, **over):
        concept = {"title": "T", "slug": "s", "duration_sec": 15, "source": "comfyui",
                   "comfyui": {"recipe": "generative_shots",
                               "shots": [{"prompt": "it moves", "duration": 5,
                                          "cues": [{"t": 1.0, "type": "impact"}]}]}}
        concept.update(over)
        return concept

    def test_a_comfyui_concept_needs_no_scene_script(self):
        self.assertEqual(validate_concept(self.base(), {}, set(), recipes()), [])

    def test_a_blender_concept_still_needs_one(self):
        findings = validate_concept({"title": "T", "slug": "s", "duration_sec": 6},
                                    {}, set(), recipes())

        self.assertIn("missing-field", codes(findings))

    def test_an_unregistered_recipe_is_an_error(self):
        concept = self.base()
        concept["comfyui"]["recipe"] = "nope"

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("missing-recipe", codes(findings))

    def test_hybrid_needs_a_recipe_that_can_apply_assets(self):
        concept = {"title": "T", "slug": "s", "duration_sec": 6, "source": "hybrid",
                   "scene_script": "demo",
                   "comfyui": {"recipe": "generative_shots", "assets": [{"param": "x"}]}}

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("not-an-asset-recipe", codes(findings))

    def test_a_comfyui_concept_with_no_cues_is_flagged_as_silent(self):
        concept = self.base()
        concept["comfyui"]["shots"][0]["cues"] = []

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("no-cues", codes(findings))

    def test_a_duration_the_model_will_refuse_is_flagged(self):
        concept = self.base()
        concept["comfyui"]["shots"][0]["duration"] = 7

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("bad-shot-duration", codes(findings))

    def test_a_cue_past_the_end_of_its_shot_is_flagged(self):
        concept = self.base()
        concept["comfyui"]["shots"][0]["cues"] = [{"t": 9.0, "type": "impact"}]

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("cue-out-of-shot", codes(findings))

    def test_comfyui_keys_no_recipe_reads_are_reported(self):
        concept = self.base()
        concept["comfyui"]["ghost"] = 1

        findings = validate_concept(concept, {}, set(), recipes())

        dead = [f for f in findings if f["code"] == "dead-comfyui-keys"]
        self.assertEqual(len(dead), 1)
        self.assertIn("ghost", dead[0]["message"])

    def test_a_blender_concept_carrying_a_comfyui_block_is_warned_about(self):
        concept = {"title": "T", "slug": "s", "duration_sec": 6, "scene_script": "demo",
                   "comfyui": {"recipe": "generative_shots"}}

        findings = validate_concept(concept, {}, set(), recipes())

        self.assertIn("unused-comfyui", codes(findings))


class RecipeScanTests(unittest.TestCase):
    """The scan must agree with the real recipes, or the catalog lies."""

    def test_generative_shots_builds_jobs_but_is_not_an_asset_recipe(self):
        info = scan_recipe(__import__("pathlib").Path(generative_shots.__file__))

        self.assertTrue(info["hooks"]["build_jobs"])
        self.assertFalse(info["asset_recipe"])

    def test_look_assets_is_an_asset_recipe(self):
        info = scan_recipe(__import__("pathlib").Path(look_assets.__file__))

        self.assertTrue(info["asset_recipe"])


if __name__ == "__main__":
    unittest.main()
