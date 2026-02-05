"""
HTML Fridge Sheet Translator for CareMap.

Translates generated English fridge sheet HTML pages into target languages
(Bengali by default) for Ayahs and caregivers who cannot read English.

Safety design:
- Preserves medication names verbatim (safety-critical)
- Preserves dose information verbatim
- Preserves HTML structure, CSS, and print layout
- Preserves emojis and visual badges

Uses lxml for DOM parsing and NLLBTranslator for text translation.
"""

import re
from typing import Optional, Callable

from lxml import html as lxml_html

from .translation import NLLBTranslator, LANGUAGE_CODES


# Map NLLB language codes → HTML lang attributes
HTML_LANG_CODES = {
    "ben_Beng": "bn",
    "hin_Deva": "hi",
    "spa_Latn": "es",
    "por_Latn": "pt",
    "zho_Hant": "zh-Hant",
    "zho_Hans": "zh-Hans",
    "tam_Taml": "ta",
    "tel_Telu": "te",
    "mar_Deva": "mr",
}

# Font families for non-Latin scripts
LANGUAGE_FONT_FAMILIES = {
    "ben_Beng": "'Noto Sans Bengali', 'Hind Siliguri', 'Kohinoor Bangla'",
    "hin_Deva": "'Noto Sans Devanagari', 'Hind', 'Kohinoor Devanagari'",
    "tam_Taml": "'Noto Sans Tamil', 'Hind Madurai'",
    "tel_Telu": "'Noto Sans Telugu', 'Hind Guntur'",
    "mar_Deva": "'Noto Sans Devanagari', 'Hind'",
    "zho_Hant": "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei'",
    "zho_Hans": "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei'",
}

# CSS classes whose text must stay in English (safety-critical)
PRESERVE_CLASSES = frozenset({"med-name", "med-dose", "medgemma-badge"})

# Tags whose content is not visible text
SKIP_TAGS = frozenset({"style", "script", "meta", "link"})


def _has_preserve_class(element) -> bool:
    classes = set((element.get("class") or "").split())
    return bool(PRESERVE_CLASSES & classes)


def _ancestor_preserved(element) -> bool:
    parent = element.getparent()
    while parent is not None:
        if _has_preserve_class(parent):
            return True
        parent = parent.getparent()
    return False


def _is_translatable(text: str) -> bool:
    """Return True if text contains English words worth translating."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if len(stripped) <= 1:
        return False
    if not re.search(r"[a-zA-Z]", stripped):
        return False
    return True


def _translate_preserving_whitespace(
    text: str,
    translator: NLLBTranslator,
    target_lang: str,
) -> str:
    if not _is_translatable(text):
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    core = text.strip()
    translated = translator.translate_to(core, target_lang)
    return leading + translated + trailing


def translate_fridge_sheet_html(
    html_content: str,
    translator: NLLBTranslator,
    target_lang: str = "ben_Beng",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    Translate a generated fridge sheet HTML page to a target language.

    Args:
        html_content: Complete HTML string of a fridge sheet page.
        translator: Initialized NLLBTranslator instance.
        target_lang: NLLB language code (default: ``"ben_Beng"``).
        progress_callback: Optional ``callback(current, total, message)``.

    Returns:
        Translated HTML string with preserved structure and safety fields.
    """
    doc = lxml_html.document_fromstring(html_content)

    # Set HTML lang attribute
    lang_code = HTML_LANG_CODES.get(target_lang, "en")
    doc.set("lang", lang_code)

    # Inject font CSS for non-Latin scripts
    font_family = LANGUAGE_FONT_FAMILIES.get(target_lang, "")
    if font_family:
        font_css = (
            f"\n/* CareMap translated: {lang_code} */\n"
            f"body, td, th, div, span, p, h1, h2, h3, h4 {{\n"
            f"    font-family: {font_family}, -apple-system, BlinkMacSystemFont, "
            f"'Segoe UI', Roboto, sans-serif;\n}}\n"
        )
        for style_elem in doc.findall(".//style"):
            style_elem.text = (style_elem.text or "") + font_css
            break

    body = doc.find(".//body")
    if body is None:
        return html_content

    # Collect all translatable text nodes
    nodes = []
    for elem in body.iter():
        if elem.tag in SKIP_TAGS:
            continue
        if _has_preserve_class(elem) or _ancestor_preserved(elem):
            continue
        if _is_translatable(elem.text):
            nodes.append(("text", elem))
        if _is_translatable(elem.tail):
            nodes.append(("tail", elem))

    total = len(nodes)
    for i, (attr, elem) in enumerate(nodes):
        if progress_callback and (i % 5 == 0 or i == total - 1):
            progress_callback(i + 1, total, f"Translating ({i + 1}/{total})")
        original = getattr(elem, attr)
        translated = _translate_preserving_whitespace(original, translator, target_lang)
        setattr(elem, attr, translated)

    result = lxml_html.tostring(doc, encoding="unicode")
    if not result.strip().lower().startswith("<!doctype"):
        result = "<!DOCTYPE html>\n" + result

    return result


def translate_html_file(
    input_path: str,
    output_path: str,
    translator: NLLBTranslator,
    target_lang: str = "ben_Beng",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    Convenience wrapper: read an HTML file, translate it, save the result.

    Returns:
        The translated HTML string.
    """
    with open(input_path, encoding="utf-8") as f:
        html_content = f.read()

    translated = translate_fridge_sheet_html(
        html_content, translator, target_lang, progress_callback
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(translated)

    return translated
