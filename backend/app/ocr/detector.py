"""Book title extraction from cover photos using PaddleOCR."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paddleocr import PaddleOCR

_ocr: PaddleOCR | None = None

# Common non-title words on book covers
_NOISE_WORDS = frozenset(
    {
        "by",
        "the",
        "a",
        "an",
        "and",
        "of",
        "new",
        "edition",
        "bestseller",
        "bestselling",
        "novel",
        "volume",
        "series",
        "book",
        "author",
        "foreword",
        "introduction",
        "revised",
        "updated",
        "international",
        "award",
        "winner",
        "nyt",
        "times",
    }
)


@dataclass(frozen=True)
class TextBlock:
    text: str
    confidence: float
    height: float
    top: float


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        # PaddleOCR 3.x — show_log and use_angle_cls were removed
        _ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
    return _ocr


def _poly_bounds(poly: Any) -> tuple[float, float, float]:
    """Return height, top, and width from a polygon."""
    points = list(poly)
    ys = [float(point[1]) for point in points]
    xs = [float(point[0]) for point in points]
    height = max(ys) - min(ys)
    top = min(ys)
    width = max(xs) - min(xs)
    return height, top, width


def _parse_predict_result(result: list[Any]) -> list[TextBlock]:
    blocks: list[TextBlock] = []

    for page in result:
        payload = page.json if hasattr(page, "json") else page
        if not isinstance(payload, dict):
            continue

        data = payload.get("res", payload)
        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        polys = data.get("rec_polys") or data.get("dt_polys") or []

        for text, score, poly in zip(texts, scores, polys, strict=False):
            if not text or not str(text).strip():
                continue

            confidence = float(score)
            if confidence < 0.5:
                continue

            height, top, width = _poly_bounds(poly)
            cleaned = str(text).strip()
            if len(cleaned) < 2 or width < 20:
                continue

            blocks.append(
                TextBlock(
                    text=cleaned,
                    confidence=confidence,
                    height=height,
                    top=top,
                )
            )

    return blocks


def _parse_legacy_result(result: list) -> list[TextBlock]:
    """PaddleOCR 2.x result format."""
    blocks: list[TextBlock] = []
    if not result or not result[0]:
        return blocks

    for line in result[0]:
        box, (text, confidence) = line
        if confidence < 0.5 or not text.strip():
            continue

        height, top, width = _poly_bounds(box)
        cleaned = text.strip()
        if len(cleaned) < 2 or width < 20:
            continue

        blocks.append(
            TextBlock(
                text=cleaned,
                confidence=float(confidence),
                height=height,
                top=top,
            )
        )

    return blocks


def _run_ocr(ocr: PaddleOCR, image_path: Path) -> list[TextBlock]:
    if hasattr(ocr, "predict"):
        return _parse_predict_result(ocr.predict(str(image_path)))

    # PaddleOCR 2.x fallback
    return _parse_legacy_result(ocr.ocr(str(image_path), cls=True))


def _score_title_candidate(block: TextBlock, image_height: float) -> float:
    words = re.findall(r"[A-Za-z]+", block.text.lower())
    if not words:
        return 0.0

    noise_ratio = sum(1 for w in words if w in _NOISE_WORDS) / len(words)
    if noise_ratio > 0.6:
        return 0.0

    size_score = block.height / max(image_height, 1) * 4.0
    position_score = max(0.0, 1.0 - (block.top / max(image_height * 0.6, 1)))
    confidence_score = block.confidence
    length_penalty = 0.0 if len(block.text) > 80 else 0.2

    return size_score + position_score + confidence_score + length_penalty


def _dedupe_titles(titles: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for title in titles:
        key = re.sub(r"\s+", " ", title.lower().strip())
        if key and key not in seen:
            seen.add(key)
            unique.append(title.strip())
    return unique


def extract_titles(image_path: Path) -> list[str]:
    """Extract likely book titles from a cover photo."""
    from PIL import Image

    with Image.open(image_path) as img:
        image_height = float(img.height)

    ocr = _get_ocr()
    blocks = _run_ocr(ocr, image_path)

    if not blocks:
        return []

    scored = [
        (block.text, _score_title_candidate(block, image_height))
        for block in blocks
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    candidates = [text for text, score in scored if score > 0.8][:3]

    if len(blocks) >= 2:
        top_blocks = sorted(blocks, key=lambda b: b.top)[:3]
        combined = " ".join(b.text for b in top_blocks[:2])
        if len(combined) > 4:
            candidates.append(combined)

    return _dedupe_titles(candidates)
