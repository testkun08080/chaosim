import unittest

from pipeline.thumbnail import resolve_thumbnail_config


class ThumbnailConfigTests(unittest.TestCase):
    def test_portrait_video_uses_vertical_cover(self):
        concept = {"title": "Short", "thumbnail": {"style": "bold_headline"}}
        template = {
            "resolution": [1080, 1920],
            "thumbnail": {"size": [1280, 720]},
        }

        config = resolve_thumbnail_config(concept, template)

        self.assertEqual(config["style"], "vertical_cover")
        self.assertEqual(config["size"], [1080, 1920])

    def test_landscape_video_uses_youtube_thumbnail(self):
        concept = {"title": "Landscape", "thumbnail": {"style": "vertical_cover"}}
        template = {"resolution": [1920, 1080]}

        config = resolve_thumbnail_config(concept, template)

        self.assertEqual(config["style"], "bold_headline")
        self.assertEqual(config["size"], [1280, 720])

    def test_custom_matching_profile_is_preserved(self):
        concept = {
            "title": "Custom",
            "thumbnail": {"style": "custom_portrait", "size": [720, 1280]},
        }
        template = {"resolution": [1080, 1920]}

        config = resolve_thumbnail_config(concept, template)

        self.assertEqual(config["style"], "custom_portrait")
        self.assertEqual(config["size"], [720, 1280])


if __name__ == "__main__":
    unittest.main()
