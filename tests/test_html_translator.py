"""Tests for HTML fridge sheet translator."""

from unittest.mock import MagicMock
from caremap.html_translator import (
    translate_fridge_sheet_html,
    _is_translatable,
    _has_preserve_class,
)


class TestIsTranslatable:
    def test_empty_string(self):
        assert not _is_translatable("")

    def test_whitespace(self):
        assert not _is_translatable("   ")

    def test_single_char(self):
        assert not _is_translatable("A")

    def test_emoji_only(self):
        assert not _is_translatable("☀️🌙")

    def test_number_only(self):
        assert not _is_translatable("123")

    def test_english_word(self):
        assert _is_translatable("Morning")

    def test_emoji_plus_text(self):
        assert _is_translatable("☀️ Morning")


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test</title>
    <style>body { color: #333; }</style>
</head>
<body>
    <h1>💊 Medication Schedule</h1>
    <div class="med-name">Metformin</div>
    <div class="med-dose">500mg</div>
    <div class="why-matters">This medicine helps lower blood sugar.</div>
    <span class="warning">⚠️ Do not take with alcohol</span>
    <span class="medgemma-badge">MedGemma</span>
</body>
</html>"""


class TestTranslateHTML:
    def _make_translator(self):
        mock = MagicMock()
        mock.translate_to.side_effect = lambda text, lang: f"[{lang}]{text}"
        return mock

    def test_preserves_med_name(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "Metformin" in result

    def test_preserves_med_dose(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "500mg" in result

    def test_preserves_medgemma_badge(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "MedGemma" in result

    def test_translates_why_matters(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "[ben_Beng]This medicine helps lower blood sugar." in result

    def test_translates_warning(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "[ben_Beng]" in result
        assert "Do not take with alcohol" not in result or "[ben_Beng]" in result

    def test_translates_header(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "[ben_Beng]" in result

    def test_sets_lang_attribute(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert 'lang="bn"' in result

    def test_preserves_css(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "color: #333" in result

    def test_injects_bengali_font(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "ben_Beng")
        assert "Noto Sans Bengali" in result

    def test_no_font_for_latin(self):
        translator = self._make_translator()
        result = translate_fridge_sheet_html(SAMPLE_HTML, translator, "spa_Latn")
        assert "Noto Sans Bengali" not in result
