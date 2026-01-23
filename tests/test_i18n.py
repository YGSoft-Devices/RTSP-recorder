# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web-manager", "services"))

import i18n_service


class TestI18nService(unittest.TestCase):
    def setUp(self):
        i18n_service.reset_cache()

    def test_interpolation(self):
        value = i18n_service.t("i18n.sample", "fr", {"name": "Cam"})
        self.assertEqual(value, "Bonjour Cam")

    def test_fallback_to_default(self):
        value = i18n_service.t("i18n.only_fr", "en")
        self.assertEqual(value, "Seulement en français")

    def test_missing_key_returns_key(self):
        value = i18n_service.t("i18n.missing", "en")
        self.assertEqual(value, "i18n.missing")

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write("{invalid json")
            temp_path = handle.name
        try:
            data = i18n_service.load_translations_from_path(temp_path)
            self.assertEqual(data, {})
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
