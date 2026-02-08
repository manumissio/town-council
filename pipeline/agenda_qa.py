"""
Agenda QA (Quality Assurance) scoring for segmented agenda items.

Why this exists:
Agenda segmentation is heuristic-heavy. We do not want correctness to depend on
manually checking every meeting or adding city-specific special cases.

Instead, this module scores stored agenda items using generic, source-agnostic
signals (boilerplate, speaker-roll names, page-number quality, missing votes).
That score can be used to:
1) produce a report of likely-bad meetings, and
2) selectively regenerate only the suspect ones.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, Iterable, List, Optional


_RE_VOTE_LINE = re.compile(r"(?im)^\s*vote\s*:\s*(.+?)\s*$")
_RE_PAGE_MARKER = re.compile(r"(?i)\[page\s+(\d+)\]")
_RE_INLINE_PAGE = re.compile(r"(?im)^.*\bpage\s+(\d+)\s*$")

# Generic boilerplate and participation/accessibility phrases.
# These are intentionally not municipality-specific.
_BOILERPLATE_PATTERNS = [
    r"\b(communication access information)\b",
    r"\b(disability[- ]related|accommodation\(s\)|auxiliary aids|interpreters?)\b",
    r"\b(brown act|executive orders?)\b",
    r"\b(public comment portion|may participate in the public comment)\b",
    r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b",
    r"\b(questions regarding this matter)\b",
    r"\b(i hereby request|in witness whereof|official seal|cause personal notice|forthwith)\b",
]


def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _has_url(s: str) -> bool:
    lowered = s.lower()
    return ("http://" in lowered) or ("https://" in lowered) or ("www." in lowered)


def _title_looks_like_person_name(title: str) -> bool:
    """
    Heuristic: speaker rolls frequently produce titles that are just names.

    We keep this conservative. It's OK to miss some names; this is QA scoring,
    not a hard filter.
    """
    title = _norm(title)
    if not title:
        return False

    # "Shona Armstrong, on behalf of ..." is effectively a speaker line.
    if "on behalf of" in title.lower():
        return True

    # Strip trailing "(2)"-style speaker-count annotations.
    title = re.sub(r"\(\d+\)$", "", title).strip()

    # Two+ capitalized tokens, optionally with a middle initial.
    return bool(
        re.fullmatch(r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+)+(?:[-'][A-Za-z]+)?", title)
    )


def _title_looks_like_boilerplate(title: str) -> bool:
    title = _norm(title)
    if not title:
        return True

    if _has_url(title):
        return True

    lowered = title.lower()
    for pat in _BOILERPLATE_PATTERNS:
        if re.search(pat, lowered):
            return True

    # Often appears as a dangling clause extracted from prose.
    if lowered.endswith(":") and len(lowered) <= 60:
        return True

    return False


def _max_page_in_text(text: str) -> int:
    """
    Best-effort page number detection in raw catalog text.
    """
    pages: List[int] = []
    for m in _RE_PAGE_MARKER.finditer(text or ""):
        try:
            pages.append(int(m.group(1)))
        except ValueError:
            continue
    for m in _RE_INLINE_PAGE.finditer(text or ""):
        try:
            pages.append(int(m.group(1)))
        except ValueError:
            continue
    return max(pages) if pages else 0


def _count_vote_lines(text: str) -> int:
    return len(_RE_VOTE_LINE.findall(text or ""))


@dataclass(frozen=True)
class QAThresholds:
    """
    Tunable thresholds for deciding whether an agenda extraction is suspect.
    """

    suspect_boilerplate_rate: float = 0.30
    suspect_name_rate: float = 0.20
    suspect_item_count_high: int = 25
    suspect_page_one_rate: float = 0.80

    # Severity threshold used by `needs_regeneration`.
    suspect_severity: int = 35


@dataclass
class QAResult:
    """
    Output of scoring a single catalog's agenda items.
    """

    catalog_id: Optional[int] = None
    city: Optional[str] = None
    meeting_date: Optional[str] = None

    severity: int = 0  # 0-100-ish, higher means more likely-bad.
    flags: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_agenda_items(
    items: Iterable[Any],
    catalog_text: str,
    *,
    thresholds: Optional[QAThresholds] = None,
    catalog_id: Optional[int] = None,
    city: Optional[str] = None,
    meeting_date: Optional[str] = None,
) -> QAResult:
    """
    Score a set of agenda items and return generic QA signals.

    `items` can be ORM objects or dicts. We look for: title, page_number, result.
    """
    th = thresholds or QAThresholds()

    normalized_items: List[Dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            normalized_items.append(item)
        else:
            normalized_items.append(
                {
                    "title": getattr(item, "title", None),
                    "page_number": getattr(item, "page_number", None),
                    "result": getattr(item, "result", None),
                }
            )

    item_count = len(normalized_items)
    titles = [_norm(i.get("title")) for i in normalized_items]
    non_empty_titles = [t for t in titles if t]

    boilerplate_count = sum(1 for t in non_empty_titles if _title_looks_like_boilerplate(t))
    name_like_count = sum(1 for t in non_empty_titles if _title_looks_like_person_name(t))

    boilerplate_rate = (boilerplate_count / len(non_empty_titles)) if non_empty_titles else 0.0
    name_rate = (name_like_count / len(non_empty_titles)) if non_empty_titles else 0.0

    pages = [
        i.get("page_number")
        for i in normalized_items
        if i.get("page_number") not in (None, 0)
    ]
    page_one_count = sum(1 for p in pages if p == 1)
    page_one_rate = (page_one_count / len(pages)) if pages else 0.0
    missing_page_count = sum(1 for i in normalized_items if i.get("page_number") in (None, 0))

    extracted_vote_count = sum(1 for i in normalized_items if _norm(i.get("result")))
    raw_vote_lines = _count_vote_lines(catalog_text or "")
    max_page_in_raw = _max_page_in_text(catalog_text or "")

    flags: List[str] = []
    severity = 0

    if item_count == 0:
        flags.append("no_items")
        # Not always wrong, but worth surfacing.
        severity += 10

    if item_count >= th.suspect_item_count_high:
        flags.append("high_item_count")
        severity += 20
        severity += min(20, item_count - th.suspect_item_count_high)

    if boilerplate_rate >= th.suspect_boilerplate_rate and item_count >= 3:
        flags.append("high_boilerplate_rate")
        severity += 30
    else:
        severity += int(boilerplate_rate * 25)

    if name_rate >= th.suspect_name_rate and item_count >= 3:
        flags.append("high_name_like_rate")
        severity += 20
    else:
        severity += int(name_rate * 15)

    if pages and page_one_rate >= th.suspect_page_one_rate and max_page_in_raw >= 2:
        flags.append("page_numbers_suspect")
        severity += 15

    if raw_vote_lines >= 1 and extracted_vote_count == 0:
        flags.append("votes_missed")
        severity += 20

    # Clamp to a friendly range.
    severity = max(0, min(100, severity))

    return QAResult(
        catalog_id=catalog_id,
        city=city,
        meeting_date=meeting_date,
        severity=severity,
        flags=flags,
        metrics={
            "item_count": item_count,
            "boilerplate_count": boilerplate_count,
            "boilerplate_rate": round(boilerplate_rate, 4),
            "name_like_count": name_like_count,
            "name_like_rate": round(name_rate, 4),
            "missing_page_count": missing_page_count,
            "page_one_rate": round(page_one_rate, 4),
            "raw_vote_lines": raw_vote_lines,
            "extracted_vote_count": extracted_vote_count,
            "max_page_in_raw": max_page_in_raw,
        },
    )


def needs_regeneration(result: QAResult, *, thresholds: Optional[QAThresholds] = None) -> bool:
    """
    Decide whether an existing cached agenda should be regenerated.
    """
    th = thresholds or QAThresholds()

    # "no_items" alone is not enough to force regeneration; some docs legitimately
    # lack an agenda section. We only regenerate if other signals also fire.
    if result.flags == ["no_items"]:
        return False

    return result.severity >= th.suspect_severity

