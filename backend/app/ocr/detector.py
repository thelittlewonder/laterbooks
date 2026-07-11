"""Google Cloud Vision OCR for book cover photos."""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

NOISE_WORDS = frozenset(
    {
        "by",
        "a",
        "an",
        "the",
        "novel",
        "edition",
        "bestseller",
        "best",
        "seller",
        "paperback",
        "hardcover",
        "modern",
        "classics",
        "classic",
        "penguin",
        "signed",
        "copy",
        "oprah",
        "club",
        "pick",
        "shortlisted",
        "longlisted",
        "prize",
        "fiction",
        "booker",
        "times",
        "sunday",
        "york",
        "new",
    }
)

MAX_IMAGE_SIDE = 2000
MIN_HEIGHT_RATIO = 0.38
GROUP_GAP = 28
VISION_URL = "https://vision.googleapis.com/v1/images:annotate"


@dataclass(frozen=True)
class TextBox:
    text: str
    y0: float
    y1: float
    height: float
    area: float


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("|", " ")).strip()


def _letter_count(text: str) -> int:
    return len(re.findall(r"[a-zA-ZÀ-ÿ]", text))


def _is_garbage(text: str) -> bool:
    if _letter_count(text) < 5:
        return True
    compact = text.replace(" ", "")
    if _letter_count(compact) / max(len(compact), 1) < 0.55:
        return True
    weird = len(re.findall(r"[^a-zA-ZÀ-ÿ0-9\s'?!-]", text))
    if weird / max(len(compact), 1) > 0.2:
        return True
    return False


def _is_likely_title(text: str) -> bool:
    if len(text) < 3 or len(text) > 120 or _is_garbage(text):
        return False
    words = [word.lower() for word in text.split()]
    if not words:
        return False
    noise = sum(1 for word in words if word in NOISE_WORDS)
    return noise / len(words) <= 0.6


def _encode_image(path: Path) -> str:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    width, height = image.size
    scale = min(1.0, MAX_IMAGE_SIDE / max(width, height))
    if scale < 1.0:
        image = image.resize(
            (int(width * scale), int(height * scale)),
            Image.Resampling.LANCZOS,
        )

    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _vertices_to_box(vertices: list[dict]) -> tuple[float, float, float, float]:
    xs = [vertex.get("x", 0) for vertex in vertices]
    ys = [vertex.get("y", 0) for vertex in vertices]
    return min(xs), min(ys), max(xs), max(ys)


def _parse_vision_boxes(annotation: dict) -> list[TextBox]:
    boxes: list[TextBox] = []
    full = annotation.get("fullTextAnnotation") or {}

    for page in full.get("pages", []):
        for block in page.get("blocks", []):
            for paragraph in block.get("paragraphs", []):
                words = [
                    _clean("".join(symbol.get("text", "") for symbol in word.get("symbols", [])))
                    for word in paragraph.get("words", [])
                ]
                text = _clean(" ".join(word for word in words if word))
                if not text:
                    continue

                vertices = paragraph.get("boundingBox", {}).get("vertices", [])
                if not vertices:
                    continue

                x0, y0, x1, y1 = _vertices_to_box(vertices)
                height = y1 - y0
                width = x1 - x0
                boxes.append(
                    TextBox(
                        text=text,
                        y0=y0,
                        y1=y1,
                        height=height,
                        area=width * height,
                    )
                )

    if boxes:
        return boxes

    # Fallback: line-level annotations
    for item in annotation.get("textAnnotations", [])[1:]:
        text = _clean(item.get("description", ""))
        vertices = item.get("boundingPoly", {}).get("vertices", [])
        if not text or not vertices:
            continue
        x0, y0, x1, y1 = _vertices_to_box(vertices)
        height = y1 - y0
        width = x1 - x0
        boxes.append(
            TextBox(text=text, y0=y0, y1=y1, height=height, area=width * height)
        )

    return boxes


def _prominent_boxes(boxes: list[TextBox]) -> list[TextBox]:
    if not boxes:
        return boxes
    max_height = max(box.height for box in boxes)
    return [box for box in boxes if box.height / max_height >= MIN_HEIGHT_RATIO]


def _group_boxes(boxes: list[TextBox]) -> list[list[TextBox]]:
    ordered = sorted(boxes, key=lambda box: (box.y0, box.text))
    groups: list[list[TextBox]] = []
    for box in ordered:
        if not groups or box.y0 - groups[-1][-1].y1 > GROUP_GAP:
            groups.append([box])
        else:
            groups[-1].append(box)
    return groups


def _merge_group(group: list[TextBox]) -> str:
    return " ".join(box.text for box in sorted(group, key=lambda box: box.y0) if box.text)


def _score_group(group: list[TextBox], text: str) -> float:
    total_area = sum(box.area for box in group)
    avg_height = sum(box.height for box in group) / len(group)
    max_height = max(box.height for box in group)
    word_count = len(text.split())

    score = total_area * 2.5 + avg_height * 14 + max_height * 6
    score += min(len(text), 70)
    if 2 <= word_count <= 12:
        score += 25
    return score


def _pick_primary_title(boxes: list[TextBox]) -> str | None:
    scoped = _prominent_boxes(boxes) or boxes
    ranked: list[tuple[float, str]] = []

    for group in _group_boxes(scoped):
        text = _merge_group(group)
        if _is_likely_title(text):
            ranked.append((_score_group(group, text), text))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def _vision_auth_mode() -> str:
    if settings.google_vision_credentials_json.strip():
        return "service_account"
    if settings.google_vision_api_key.strip():
        return "api_key"
    return "none"


@lru_cache(maxsize=1)
def _vision_enabled() -> bool:
    return _vision_auth_mode() != "none"


def _access_token() -> str | None:
    raw = settings.google_vision_credentials_json.strip()
    if not raw:
        return None

    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(Request())
    return credentials.token


def _vision_error_message(status: int, body: str) -> str:
    try:
        detail = json.loads(body).get("error", {})
        message = detail.get("message") or body
        reason = (detail.get("details") or [{}])[0].get("reason", "")
        if reason:
            return f"Vision API failed ({status}): {message} [{reason}]"
        return f"Vision API failed ({status}): {message}"
    except (json.JSONDecodeError, IndexError, AttributeError):
        return f"Vision API failed ({status}): {body[:300]}"


def _call_vision(image_b64: str) -> dict:
    payload = json.dumps(
        {
            "requests": [
                {
                    "image": {"content": image_b64},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }
    ).encode("utf-8")

    token = _access_token()
    api_key = settings.google_vision_api_key.strip()

    if token:
        url = VISION_URL
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    elif api_key:
        url = f"{VISION_URL}?key={api_key}"
        headers = {"Content-Type": "application/json"}
    else:
        raise RuntimeError(
            "Set GOOGLE_VISION_API_KEY or GOOGLE_VISION_CREDENTIALS_JSON on Render."
        )

    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("Vision API error %s: %s", exc.code, body)
        raise RuntimeError(_vision_error_message(exc.code, body)) from exc


def diagnose_vision() -> dict[str, str | bool]:
    """Check Vision credentials without exposing secrets."""
    mode = _vision_auth_mode()
    result: dict[str, str | bool] = {"auth_mode": mode, "token_ok": False, "vision_ok": False}

    if mode != "service_account":
        result["error"] = "GOOGLE_VISION_CREDENTIALS_JSON is not set"
        return result

    raw = settings.google_vision_credentials_json.strip()
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        result["error"] = f"Invalid JSON in GOOGLE_VISION_CREDENTIALS_JSON: {exc}"
        return result

    result["project_id"] = info.get("project_id", "")
    result["client_email"] = info.get("client_email", "")

    try:
        _access_token()
        result["token_ok"] = True
    except Exception as exc:
        result["error"] = f"Token refresh failed: {exc}"
        return result

    # Tiny 1x1 white JPEG — enough to verify API access.
    tiny_jpeg = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
        "Hh0gJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIy"
        "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAB"
        "AAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA"
        "/9oADAMBAAIQAxAAAAGfAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAQUCf//EABQRAQAA"
        "AAAAAAAAAAAAAAAAAAD/2gAIAQMBAT8Bf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8B"
        "f//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEABj8Cf//Z"
    )

    try:
        _call_vision(tiny_jpeg)
        result["vision_ok"] = True
    except RuntimeError as exc:
        result["error"] = str(exc)
    except Exception as exc:
        result["error"] = f"Vision probe failed: {exc}"

    return result


def extract_titles(image_path: Path) -> list[str]:
    """Return one best-guess title for a cover photo."""
    if not _vision_enabled():
        raise RuntimeError(
            "Vision OCR not configured. Set GOOGLE_VISION_API_KEY or "
            "GOOGLE_VISION_CREDENTIALS_JSON."
        )

    image_b64 = _encode_image(image_path)
    response = _call_vision(image_b64)
    responses = response.get("responses", [])
    if not responses:
        return []

    annotation = responses[0]
    if annotation.get("error"):
        message = annotation["error"].get("message", "Vision API error")
        raise RuntimeError(message)

    title = _pick_primary_title(_parse_vision_boxes(annotation))
    return [title] if title else []
