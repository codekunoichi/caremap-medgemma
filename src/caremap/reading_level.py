"""
Reading level analysis for CareMap fridge sheet output.

Uses Flesch-Kincaid Grade Level to validate that MedGemma output
is accessible to non-medical caregivers (target: 6th grade or below).
"""

import re
from dataclasses import dataclass

try:
    import textstat
except ImportError:
    textstat = None


@dataclass
class ReadingLevelResult:
    """Results from reading level analysis."""
    text_source: str
    flesch_kincaid_grade: float
    flesch_reading_ease: float
    word_count: int
    sentence_count: int
    meets_target: bool
    target_grade: float = 6.0


def strip_html_tags(html: str) -> str:
    """Remove HTML tags and extract visible text."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#x[0-9a-fA-F]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def analyze_reading_level(
    text: str,
    source_label: str = "unknown",
    target_grade: float = 6.0,
    is_html: bool = False,
) -> ReadingLevelResult:
    """
    Analyze the reading level of text using Flesch-Kincaid Grade Level.

    Args:
        text: The text to analyze (plain text or HTML).
        source_label: Label for reporting (e.g., "Amma Medications Page").
        target_grade: Target grade level (default 6.0).
        is_html: If True, strip HTML tags before analysis.

    Returns:
        ReadingLevelResult with grade level and pass/fail.
    """
    if textstat is None:
        raise ImportError("textstat is required: pip install textstat")

    if is_html:
        text = strip_html_tags(text)

    grade = textstat.flesch_kincaid_grade(text)
    ease = textstat.flesch_reading_ease(text)
    words = textstat.lexicon_count(text)
    sentences = textstat.sentence_count(text)

    return ReadingLevelResult(
        text_source=source_label,
        flesch_kincaid_grade=round(grade, 1),
        flesch_reading_ease=round(ease, 1),
        word_count=words,
        sentence_count=sentences,
        meets_target=grade <= target_grade,
        target_grade=target_grade,
    )
