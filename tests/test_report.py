import csv
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.catalog import CSV_FIELDS as CATALOG_FIELDS
from pipeline.catalog import catalog_csv_rows
from pipeline.gate1 import (
    GATE_KEYS,
    collect_gate1,
    gate1_csv_rows,
    normalize_verdict,
    parse_render_log,
)
from pipeline.report import write_csv, write_json

# Verbatim shapes from the real runs collected into docs/gate1/.
LOG_CAPPED = """Blender 4.5.3 LTS (hash 67807e1800cc built 2025-09-09 01:38:15)
CHAOSIM_MAX_FRAMES=180: truncating frame_end 360 -> 180
Engine=CYCLES frames=1-180 res%=50 fps=30
Render complete: /home/runner/work/chaosim/chaosim/outputs/renders/ring_escape_5rings.mp4
"""

LOG_STAGED = """Blender 4.5.3 LTS (hash 67807e1800cc built 2025-09-09 01:38:15)
CHAOSIM_MAX_FRAMES=180: truncating frame_end 720 -> 180
Engine=CYCLES frames=1-180 res%=50 fps=30
CHAOSIM_MAX_FRAMES=180: stage_duration_sec -> 1.500s x 4 stages
Staged frame_end override -> 180
Render complete: /home/runner/work/chaosim/chaosim/outputs/renders/paper_to_cloth.mp4
"""

LOG_UNCAPPED = "Engine=CYCLES frames=1-600 res%=100 fps=60\n"


class ParseRenderLogTests(unittest.TestCase):
    def test_capped_non_staged_render(self):
        got = parse_render_log(LOG_CAPPED)

        self.assertEqual(got["engine"], "CYCLES")
        self.assertEqual(got["frames"], 180)
        self.assertEqual(got["full_frames"], 360)
        self.assertEqual((got["width"], got["height"]), (540, 960))
        self.assertEqual(got["duration_sec"], 6.0)
        self.assertFalse(got["staged"])

    def test_staged_render_records_stage_math(self):
        got = parse_render_log(LOG_STAGED)

        self.assertTrue(got["staged"])
        self.assertEqual(got["stages"], 4)
        self.assertEqual(got["stage_duration_sec"], 1.5)
        self.assertEqual(got["full_frames"], 720)

    def test_uncapped_render_has_no_full_frames(self):
        got = parse_render_log(LOG_UNCAPPED)

        self.assertIsNone(got["full_frames"])
        self.assertEqual((got["width"], got["height"]), (1080, 1920))
        self.assertEqual(got["frames"], 600)

    def test_log_without_sentinel_yields_nothing(self):
        """A stubbed or failed render has no Engine= line; do not invent metrics."""
        got = parse_render_log("Blender quit\n")

        self.assertEqual(got, {})


class NormalizeVerdictTests(unittest.TestCase):
    def test_missing_entry_becomes_pending_with_nothing_decided(self):
        got = normalize_verdict(None)

        self.assertEqual(got["verdict"], "pending")
        self.assertEqual(got["gate_undecided"], len(GATE_KEYS))
        self.assertEqual(got["gate_passed"], 0)

    def test_unknown_verdict_falls_back_to_pending(self):
        got = normalize_verdict({"verdict": "looks-good-to-me"})

        self.assertEqual(got["verdict"], "pending")

    def test_gate_counts_split_true_false_and_null(self):
        got = normalize_verdict({
            "verdict": "hold",
            "gate": {"framing": True, "look": True, "sim": False, "hook": None},
        })

        self.assertEqual(got["verdict"], "hold")
        self.assertEqual(got["gate_passed"], 2)
        self.assertEqual(got["gate_failed"], 1)
        # hook was null and duration was absent entirely.
        self.assertEqual(got["gate_undecided"], 2)

    def test_non_boolean_gate_value_is_treated_as_undecided(self):
        got = normalize_verdict({"gate": {"framing": "yes"}})

        self.assertIsNone(got["gate"]["framing"])


class CollectGate1Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _sheet(self, slug, log=LOG_CAPPED, events=0):
        (self.dir / f"{slug}_contact.png").write_bytes(b"\x89PNG stub")
        (self.dir / f"{slug}_render.log").write_text(log, encoding="utf-8")
        (self.dir / f"{slug}_events.json").write_text(
            json.dumps({"events": [{"frame": 1}] * events}), encoding="utf-8")

    def test_collects_metrics_and_verdict_together(self):
        self._sheet("alpha", events=3)

        rec = collect_gate1(self.dir, {"alpha": {"verdict": "pass"}})

        entry = rec["entries"][0]
        self.assertEqual(entry["slug"], "alpha")
        self.assertEqual(entry["verdict"], "pass")
        self.assertEqual(entry["render"]["frames"], 180)
        self.assertEqual(entry["sfx_events"], 3)
        self.assertEqual(entry["contact_sheet"], "alpha_contact.png")

    def test_sheet_without_a_verdict_is_pending(self):
        self._sheet("alpha")

        rec = collect_gate1(self.dir, {})

        self.assertEqual(rec["entries"][0]["verdict"], "pending")
        self.assertEqual(rec["totals"]["verdict_pending"], 1)

    def test_verdict_without_a_sheet_is_still_listed(self):
        """A parked concept should not vanish just because it was never rendered."""
        rec = collect_gate1(self.dir, {"never_rendered": {"verdict": "fail"}})

        self.assertEqual([e["slug"] for e in rec["entries"]], ["never_rendered"])
        self.assertIsNone(rec["entries"][0]["contact_sheet"])
        self.assertIsNone(rec["entries"][0]["render"])
        self.assertEqual(rec["totals"]["with_contact_sheet"], 0)

    def test_totals_tally_every_verdict(self):
        self._sheet("a")
        self._sheet("b")

        rec = collect_gate1(self.dir, {"a": {"verdict": "pass"}, "b": {"verdict": "fail"}})

        self.assertEqual(rec["totals"]["concepts"], 2)
        self.assertEqual(rec["totals"]["verdict_pass"], 1)
        self.assertEqual(rec["totals"]["verdict_fail"], 1)


class CsvRowTests(unittest.TestCase):
    def test_gate1_rows_flatten_the_five_checks_into_columns(self):
        rec = {
            "gate_keys": list(GATE_KEYS),
            "entries": [{
                "slug": "a", "contact_sheet": "a.png", "contact_bytes": 1,
                "render": {"engine": "CYCLES", "width": 540, "height": 960, "fps": 30,
                           "frames": 180, "full_frames": 360, "duration_sec": 6.0,
                           "staged": False, "stages": None, "stage_duration_sec": None},
                "sfx_events": 0,
                **normalize_verdict({"verdict": "fail",
                                     "gate": {"framing": False, "look": True}}),
            }],
            "totals": {},
        }

        row = gate1_csv_rows(rec)[0]

        self.assertEqual(row["gate_framing"], 0)
        self.assertEqual(row["gate_look"], 1)
        self.assertEqual(row["gate_sim"], "")
        self.assertEqual(row["full_frames"], 360)

    def test_gate1_row_for_a_concept_with_no_render_leaves_metrics_blank(self):
        rec = {"gate_keys": list(GATE_KEYS), "totals": {}, "entries": [{
            "slug": "a", "contact_sheet": None, "contact_bytes": None,
            "render": None, "sfx_events": None, **normalize_verdict(None),
        }]}

        row = gate1_csv_rows(rec)[0]

        self.assertEqual(row["frames"], "")
        self.assertEqual(row["sfx_events"], "")
        self.assertEqual(row["verdict"], "pending")

    def test_catalog_rows_have_one_row_per_concept(self):
        ctx = {"entries": [
            {"slug": "a", "title": "A", "scene": "s", "duration_sec": 6, "preset": "preview",
             "staged": False, "params_declared": 5, "params_live": 3, "errors": 0,
             "warnings": 1, "findings": [{"code": "dead-params"}], "has_gate1": True,
             "path": "concepts/a.yaml"},
        ]}

        rows = catalog_csv_rows(ctx)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["params_dead"], 2)
        self.assertEqual(rows[0]["finding_codes"], "dead-params")
        self.assertEqual(rows[0]["has_gate1"], 1)
        self.assertEqual(set(rows[0]), set(CATALOG_FIELDS))


class WriteHelperTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_csv_is_written_with_a_bom_so_excel_reads_japanese(self):
        path = write_csv(self.dir / "sub" / "t.csv",
                         [{"slug": "a", "title": "面数で変わる布"}], ["slug", "title"])

        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        with path.open(encoding="utf-8-sig", newline="") as fh:
            self.assertEqual(list(csv.DictReader(fh))[0]["title"], "面数で変わる布")

    def test_json_keeps_japanese_unescaped(self):
        path = write_json(self.dir / "sub" / "t.json", {"title": "面数"})

        self.assertIn("面数", path.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["title"], "面数")


if __name__ == "__main__":
    unittest.main()
