import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.uploader import (
    SCOPES,
    _creds_from_env,
    _headless,
    build_video_body,
    get_authenticated_service,
    write_upload_record,
)

ENV_KEYS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
            "YOUTUBE_TOKEN_PATH", "YOUTUBE_CLIENT_SECRET_PATH", "CI", "GITHUB_ACTIONS")

FULL_ENV = {
    "YOUTUBE_CLIENT_ID": "cid.apps.googleusercontent.com",
    "YOUTUBE_CLIENT_SECRET": "csecret",
    "YOUTUBE_REFRESH_TOKEN": "1//rtoken",
}


def clean_env(**overrides):
    """patch.dict that clears every YouTube/CI var before applying overrides."""
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env.update(overrides)
    return mock.patch.dict(os.environ, env, clear=True)


class BuildVideoBodyTests(unittest.TestCase):
    def test_maps_concept_fields(self):
        concept = {
            "caption": "5つのリングが逃げ出す",
            "description": "カオス的な軌道",
            "hashtags": ["カオス", "物理"],
        }

        body = build_video_body(concept, "private", category_id="28")

        self.assertEqual(body["snippet"]["title"], "5つのリングが逃げ出す")
        self.assertTrue(body["snippet"]["description"].endswith("#Shorts"))
        self.assertIn("カオス的な軌道", body["snippet"]["description"])
        self.assertEqual(body["snippet"]["tags"], ["カオス", "物理", "Shorts"])
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])

    def test_title_truncated_to_youtube_limit(self):
        body = build_video_body({"caption": "あ" * 150}, category_id="28")

        self.assertEqual(len(body["snippet"]["title"]), 100)

    def test_falls_back_to_filename_stem_without_caption(self):
        body = build_video_body({}, fallback_title="ring_escape_5rings", category_id="28")

        self.assertEqual(body["snippet"]["title"], "ring_escape_5rings")
        self.assertEqual(body["snippet"]["tags"], ["Shorts"])

    def test_extra_description_is_appended(self):
        body = build_video_body({"description": "base"}, extra_description="run: http://x/1",
                                category_id="28")

        self.assertTrue(body["snippet"]["description"].endswith("run: http://x/1"))

    def test_privacy_is_passed_through(self):
        self.assertEqual(
            build_video_body({}, "unlisted", category_id="28")["status"]["privacyStatus"],
            "unlisted",
        )

    def test_category_id_comes_from_settings(self):
        # config/settings.yaml youtube.category_id was dead config before; it now
        # drives the request body instead of a hardcoded literal.
        with mock.patch("pipeline.config.load_settings",
                        return_value={"youtube": {"category_id": "24"}}):
            body = build_video_body({})

        self.assertEqual(body["snippet"]["categoryId"], "24")

    def test_category_id_defaults_when_settings_absent(self):
        with mock.patch("pipeline.config.load_settings", return_value={}):
            body = build_video_body({})

        self.assertEqual(body["snippet"]["categoryId"], "28")


class CredsFromEnvTests(unittest.TestCase):
    def test_builds_credentials_when_all_three_present(self):
        with clean_env(**FULL_ENV):
            creds = _creds_from_env()

        self.assertIsNotNone(creds)
        self.assertEqual(creds.refresh_token, "1//rtoken")
        self.assertEqual(creds.client_id, "cid.apps.googleusercontent.com")
        self.assertEqual(list(creds.scopes), SCOPES)

    def test_returns_none_when_any_var_missing(self):
        for missing in FULL_ENV:
            env = {k: v for k, v in FULL_ENV.items() if k != missing}
            with self.subTest(missing=missing), clean_env(**env):
                self.assertIsNone(_creds_from_env())

    def test_returns_none_with_empty_env(self):
        with clean_env():
            self.assertIsNone(_creds_from_env())


class HeadlessDetectionTests(unittest.TestCase):
    """`CI=false` is a real convention; it must not be read as "CI is set, so true"."""

    def test_truthy_spellings_are_headless(self):
        for var in ("CI", "GITHUB_ACTIONS"):
            for value in ("1", "true", "TRUE", "yes"):
                with self.subTest(var=var, value=value), clean_env(**{var: value}):
                    self.assertTrue(_headless())

    def test_falsy_spellings_are_not_headless(self):
        for value in ("false", "0", "no", ""):
            with self.subTest(value=value), clean_env(CI=value):
                self.assertFalse(_headless())

    def test_unset_is_not_headless(self):
        with clean_env():
            self.assertFalse(_headless())

    def test_ci_false_still_reaches_the_browser_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "client_secret.json"
            secret.write_text("{}", encoding="utf-8")
            env = {"CI": "false", "YOUTUBE_TOKEN_PATH": str(Path(tmp) / "token.pickle"),
                   "YOUTUBE_CLIENT_SECRET_PATH": str(secret)}
            with clean_env(**env), \
                 mock.patch("pipeline.uploader.build"), \
                 mock.patch("pipeline.uploader.pickle"), \
                 mock.patch("pipeline.uploader.InstalledAppFlow") as flow:
                get_authenticated_service()

        flow.from_client_secrets_file.assert_called_once()


class HeadlessGuardTests(unittest.TestCase):
    def test_ci_without_secrets_fails_before_opening_a_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"CI": "true", "YOUTUBE_TOKEN_PATH": str(Path(tmp) / "token.pickle")}
            with clean_env(**env), \
                 mock.patch("pipeline.uploader.InstalledAppFlow") as flow:
                with self.assertRaises(RuntimeError) as ctx:
                    get_authenticated_service()

        flow.from_client_secrets_file.assert_not_called()
        self.assertIn("YOUTUBE_CLIENT_ID", str(ctx.exception))

    def test_env_credentials_skip_the_token_cache_entirely(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "token.pickle"
            env = dict(FULL_ENV, CI="true", YOUTUBE_TOKEN_PATH=str(cache))
            with clean_env(**env), \
                 mock.patch("pipeline.uploader._refresh", side_effect=lambda c: c), \
                 mock.patch("pipeline.uploader.build") as build, \
                 mock.patch("pipeline.uploader.InstalledAppFlow") as flow:
                get_authenticated_service()

            self.assertFalse(cache.exists())
        flow.from_client_secrets_file.assert_not_called()
        build.assert_called_once()
        self.assertEqual(build.call_args[0], ("youtube", "v3"))


class UploadRecordTests(unittest.TestCase):
    def test_writes_receipt_json(self):
        result = {"video_id": "abc123", "url": "https://youtube.com/shorts/abc123",
                  "privacy": "private", "title": "T", "tags": ["Shorts"],
                  "thumbnail_set": False}

        with tempfile.TemporaryDirectory() as tmp:
            path = write_upload_record(Path(tmp) / "uploads", "ring_escape_5rings", result,
                                       source_video="outputs/renders/ring_escape_5rings.mp4",
                                       run_url="https://github.com/o/r/actions/runs/1")
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(path.name, "ring_escape_5rings.json")
        self.assertEqual(payload["slug"], "ring_escape_5rings")
        self.assertEqual(payload["video_id"], "abc123")
        self.assertEqual(payload["run_url"], "https://github.com/o/r/actions/runs/1")
        self.assertIn("uploaded_at", payload)

    def test_explicit_slug_names_the_file(self):
        # upload.yml pins this so it reads back the receipt it just named.
        with tempfile.TemporaryDirectory() as tmp:
            path = write_upload_record(Path(tmp), "pinned_slug", {"video_id": "x"})

        self.assertEqual(path.name, "pinned_slug.json")

    def test_drops_none_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_upload_record(Path(tmp), "s", {"video_id": "x"},
                                       run_url=None, concept_path=None)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertNotIn("run_url", payload)
        self.assertNotIn("concept_path", payload)


if __name__ == "__main__":
    unittest.main()
