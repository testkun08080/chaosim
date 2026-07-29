import ast
import unittest

from pipeline.catalog import (
    _param_keys,
    build_catalog,
    validate_concept,
)


def scene(name="demo", hooks=("setup_scene", "run_simulation"), params=()):
    return {
        "name": name,
        "hooks": {h: h in hooks for h in
                  ("setup_scene", "run_simulation", "render_staged", "collect_impact_events")},
        "params": set(params),
        "staged": "render_staged" in hooks,
        "emits_events": "collect_impact_events" in hooks,
    }


def codes(findings):
    return [f["code"] for f in findings]


class ParamKeyScanTests(unittest.TestCase):
    def test_collects_literal_params_get_keys(self):
        src = 'def setup_scene(params):\n    a = params.get("alpha")\n    b = params.get("beta", 3)\n'

        keys = _param_keys(ast.parse(src))

        self.assertEqual(keys, {"alpha", "beta"})

    def test_ignores_get_on_other_objects(self):
        src = 'def setup_scene(params):\n    x = settings.get("alpha")\n    y = params.get("beta")\n'

        keys = _param_keys(ast.parse(src))

        self.assertEqual(keys, {"beta"})

    def test_ignores_non_literal_keys(self):
        src = 'def setup_scene(params):\n    for k in names:\n        v = params.get(k)\n'

        keys = _param_keys(ast.parse(src))

        self.assertEqual(keys, set())


class ValidateConceptTests(unittest.TestCase):
    def test_clean_concept_has_no_findings(self):
        concept = {"title": "T", "slug": "ok_one", "scene_script": "demo",
                   "duration_sec": 6, "render_preset": "preview",
                   "params": {"alpha": 1}}

        findings = validate_concept(concept, {"demo": scene(params=["alpha"])}, set())

        self.assertEqual(findings, [])

    def test_missing_scene_script_is_an_error(self):
        concept = {"title": "T", "slug": "s", "scene_script": "nope", "duration_sec": 6}

        findings = validate_concept(concept, {}, set())

        self.assertIn("missing-scene", codes(findings))
        self.assertEqual(findings[0]["level"], "error")

    def test_blocked_concept_downgrades_missing_scene_to_warning(self):
        concept = {"title": "T", "slug": "s", "scene_script": "nope",
                   "duration_sec": 6, "status": "blocked"}

        findings = validate_concept(concept, {}, set())

        levels = {f["code"]: f["level"] for f in findings}
        self.assertEqual(levels["missing-scene"], "warn")
        self.assertEqual(levels["blocked"], "warn")

    def test_params_not_read_by_the_scene_are_reported(self):
        concept = {"title": "T", "slug": "s", "scene_script": "demo", "duration_sec": 6,
                   "params": {"alpha": 1, "ghost": 2}}

        findings = validate_concept(concept, {"demo": scene(params=["alpha"])}, set())

        dead = [f for f in findings if f["code"] == "dead-params"]
        self.assertEqual(len(dead), 1)
        self.assertIn("ghost", dead[0]["message"])
        self.assertNotIn("alpha", dead[0]["message"])

    def test_params_consumed_by_the_runner_are_not_dead(self):
        """face_counts is read by runner.py, not by the scene — still live config."""
        concept = {"title": "T", "slug": "s", "scene_script": "demo", "duration_sec": 6,
                   "params": {"face_counts": [16, 64]}}

        findings = validate_concept(concept, {"demo": scene()}, {"face_counts"})

        self.assertNotIn("dead-params", codes(findings))

    def test_missing_required_field_is_an_error(self):
        concept = {"slug": "s", "scene_script": "demo", "duration_sec": 6}

        findings = validate_concept(concept, {"demo": scene()}, set())

        self.assertIn("missing-field", codes(findings))

    def test_slug_unusable_as_artifact_name_is_an_error(self):
        concept = {"title": "T", "slug": "bad slug/x", "scene_script": "demo", "duration_sec": 6}

        findings = validate_concept(concept, {"demo": scene()}, set())

        self.assertIn("bad-slug", codes(findings))

    def test_unknown_render_preset_is_an_error(self):
        concept = {"title": "T", "slug": "s", "scene_script": "demo",
                   "duration_sec": 6, "render_preset": "insane"}

        findings = validate_concept(concept, {"demo": scene()}, set())

        self.assertIn("bad-preset", codes(findings))

    def test_scene_without_any_entrypoint_is_an_error(self):
        concept = {"title": "T", "slug": "s", "scene_script": "demo", "duration_sec": 6}

        findings = validate_concept(concept, {"demo": scene(hooks=())}, set())

        self.assertIn("no-entrypoint", codes(findings))

    def test_staged_scene_needs_no_setup_scene(self):
        concept = {"title": "T", "slug": "s", "scene_script": "demo", "duration_sec": 6}

        findings = validate_concept(concept, {"demo": scene(hooks=("render_staged",))}, set())

        self.assertNotIn("no-entrypoint", codes(findings))


class BuildCatalogTests(unittest.TestCase):
    def test_totals_exclude_unresolvable_scenes_from_the_params_ratio(self):
        scenes = {"demo": scene(params=["alpha"])}
        concepts = [
            ("concepts/a.yaml", {"title": "A", "slug": "a", "scene_script": "demo",
                                 "duration_sec": 6, "params": {"alpha": 1, "ghost": 2}}),
            ("concepts/b.yaml", {"title": "B", "slug": "b", "scene_script": "gone",
                                 "duration_sec": 6, "status": "blocked",
                                 "params": {"x": 1, "y": 2, "z": 3}}),
        ]

        ctx = build_catalog(concepts, scenes, set())

        self.assertEqual(ctx["totals"]["params_declared"], 2)
        self.assertEqual(ctx["totals"]["params_live"], 1)
        self.assertEqual(ctx["totals"]["params_dead"], 1)
        self.assertEqual(ctx["totals"]["params_unverifiable"], 3)

    def test_entries_are_sorted_worst_first(self):
        scenes = {"demo": scene()}
        concepts = [
            ("concepts/clean.yaml", {"title": "C", "slug": "clean", "scene_script": "demo",
                                     "duration_sec": 6}),
            ("concepts/broken.yaml", {"title": "B", "slug": "broken", "scene_script": "gone",
                                      "duration_sec": 6}),
        ]

        ctx = build_catalog(concepts, scenes, set())

        self.assertEqual([e["slug"] for e in ctx["entries"]], ["broken", "clean"])

    def test_scene_usage_lists_every_concept_using_it(self):
        scenes = {"demo": scene()}
        concepts = [
            ("concepts/one.yaml", {"title": "1", "slug": "one", "scene_script": "demo",
                                   "duration_sec": 6}),
            ("concepts/two.yaml", {"title": "2", "slug": "two", "scene_script": "demo",
                                   "duration_sec": 6}),
        ]

        ctx = build_catalog(concepts, scenes, set())

        self.assertEqual(ctx["scenes"][0]["used_by"], ["one", "two"])

    def test_gate1_slugs_are_flagged(self):
        scenes = {"demo": scene()}
        concepts = [("concepts/a.yaml", {"title": "A", "slug": "a", "scene_script": "demo",
                                         "duration_sec": 6})]

        ctx = build_catalog(concepts, scenes, set(), frozenset({"a"}))

        self.assertTrue(ctx["entries"][0]["has_gate1"])


if __name__ == "__main__":
    unittest.main()
