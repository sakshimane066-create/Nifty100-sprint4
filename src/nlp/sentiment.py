"""Polarity scoring of pro/con text. Uses NLTK VADER when available, else a tiny finance lexicon (no download needed)."""
from __future__ import annotations

import re

_POS = {"good", "healthy", "strong", "high", "growth", "delivered", "debt", "free", "improving", "consistent", "above", "excellent", "efficient", "compounding", "positive"}
_NEG = {"low", "poor", "weak", "negative", "decline", "declined", "stressed", "risk", "high leverage", "below", "concern", "accrual", "distress", "loss", "falling", "burn"}
_analyzer = None
_tried = False


def _vader():
    global _analyzer, _tried
    if not _tried:
        _tried = True
        try:
            from nltk.sentiment import SentimentIntensityAnalyzer

            _analyzer = SentimentIntensityAnalyzer()
        except Exception:  # NLTK missing or lexicon not downloaded
            _analyzer = None
    return _analyzer


def score(text: str) -> float:
    """Compound polarity in [-1, 1]."""
    if not isinstance(text, str) or not text.strip():
        return 0.0
    if (a := _vader()) is not None:
        return float(a.polarity_scores(text)["compound"])
    words = re.findall(r"[a-z]+", text.lower())
    pos, neg = sum(w in _POS for w in words), sum(w in _NEG for w in words)
    return 0.0 if pos + neg == 0 else round((pos - neg) / (pos + neg), 3)


def engine_name() -> str:
    """Which backend is active ('nltk-vader' or 'fallback-lexicon')."""
    return "nltk-vader" if _vader() is not None else "fallback-lexicon"
