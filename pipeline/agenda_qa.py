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
from typing import Any, Callable, Dict, Iterable, List, Optional

from pipeline.lexicon import is_agenda_boilerplate_title, is_name_like_title


_RE_VOTE_LINE = re.compile(r"(?im)^\s*vote\s*:\s*(.+?)\s*$")
_RE_PAGE_MARKER = re.compile(r"(?i)\[page\s+(\d+)\]")
_RE_INLINE_PAGE = re.compile(r"(?im)^.*\bpage\s+(\d+)\s*$")


def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


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
    return is_name_like_title(title)


def _title_looks_like_boilerplate(title: str) -> bool:
    title = _norm(title)
    return is_agenda_boilerplate_title(title)


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
    """Score agenda items with generic QA signals."""
    th = thresholds or QAThresholds()
    normalized_items = _normalized_agenda_items(items)
    metrics = _qa_metrics(normalized_items, catalog_text)
    flags, severity = _qa_flags_and_severity(metrics, th)
    return QAResult(
        catalog_id=catalog_id,
        city=city,
        meeting_date=meeting_date,
        severity=severity,
        flags=flags,
        metrics=_qa_metrics_payload(metrics),
    )


def _normalized_agenda_items(items: Iterable[Any]) -> List[Dict[str, Any]]:
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
    return normalized_items


def _qa_metrics(normalized_items: List[Dict[str, Any]], catalog_text: str) -> Dict[str, Any]:
    non_empty_titles = _non_empty_titles(normalized_items)
    pages = _page_values(normalized_items)
    boilerplate_count, boilerplate_rate = _title_signal_count_and_rate(non_empty_titles, _title_looks_like_boilerplate)
    name_like_count, name_like_rate = _title_signal_count_and_rate(non_empty_titles, _title_looks_like_person_name)
    return {
        "item_count": len(normalized_items),
        "non_empty_title_count": len(non_empty_titles),
        "boilerplate_count": boilerplate_count,
        "boilerplate_rate": boilerplate_rate,
        "name_like_count": name_like_count,
        "name_like_rate": name_like_rate,
        "page_count": len(pages),
        "page_one_count": sum(1 for page in pages if page == 1),
        "missing_page_count": _missing_page_count(normalized_items),
        "raw_vote_lines": _count_vote_lines(catalog_text or ""),
        "extracted_vote_count": _extracted_vote_count(normalized_items),
        "max_page_in_raw": _max_page_in_text(catalog_text or ""),
    }


def _title_signal_count_and_rate(titles: List[str], predicate: Callable[[str], bool]) -> tuple[int, float]:
    signal_count = sum(1 for title in titles if predicate(title))
    return signal_count, (signal_count / len(titles)) if titles else 0.0


def _non_empty_titles(normalized_items: List[Dict[str, Any]]) -> List[str]:
    return [title for title in (_norm(item.get("title")) for item in normalized_items) if title]


def _page_values(normalized_items: List[Dict[str, Any]]) -> List[Any]:
    return [item.get("page_number") for item in normalized_items if item.get("page_number") not in (None, 0)]


def _missing_page_count(normalized_items: List[Dict[str, Any]]) -> int:
    return sum(1 for item in normalized_items if item.get("page_number") in (None, 0))


def _extracted_vote_count(normalized_items: List[Dict[str, Any]]) -> int:
    return sum(1 for item in normalized_items if _norm(item.get("result")))


def _qa_flags_and_severity(metrics: Dict[str, Any], thresholds: QAThresholds) -> tuple[List[str], int]:
    flags: List[str] = []
    item_count = int(metrics["item_count"])
    severity = _item_count_severity(flags, item_count, thresholds)
    severity += _rate_severity(
        flags,
        "high_boilerplate_rate",
        float(metrics["boilerplate_rate"]),
        thresholds.suspect_boilerplate_rate,
        item_count,
        severe_penalty=30,
        proportional_penalty=25,
    )
    severity += _rate_severity(
        flags,
        "high_name_like_rate",
        float(metrics["name_like_rate"]),
        thresholds.suspect_name_rate,
        item_count,
        severe_penalty=20,
        proportional_penalty=15,
    )
    severity += _page_number_severity(flags, metrics, thresholds)
    severity += _vote_severity(flags, metrics)
    return flags, max(0, min(100, severity))


def _item_count_severity(flags: List[str], item_count: int, thresholds: QAThresholds) -> int:
    severity = 0
    if item_count == 0:
        flags.append("no_items")
        severity += 10
    if item_count >= thresholds.suspect_item_count_high:
        flags.append("high_item_count")
        severity += 20
        severity += min(20, item_count - thresholds.suspect_item_count_high)
    return severity


def _rate_severity(
    flags: List[str],
    flag_name: str,
    rate: float,
    threshold: float,
    item_count: int,
    *,
    severe_penalty: int,
    proportional_penalty: int,
) -> int:
    if rate >= threshold and item_count >= 3:
        flags.append(flag_name)
        return severe_penalty
    return int(rate * proportional_penalty)


def _page_number_severity(flags: List[str], metrics: Dict[str, Any], thresholds: QAThresholds) -> int:
    page_one_rate = _page_one_rate(metrics)
    if int(metrics["page_count"]) > 0 and page_one_rate >= thresholds.suspect_page_one_rate and metrics["max_page_in_raw"] >= 2:
        flags.append("page_numbers_suspect")
        return 15
    return 0


def _vote_severity(flags: List[str], metrics: Dict[str, Any]) -> int:
    if metrics["raw_vote_lines"] >= 1 and metrics["extracted_vote_count"] == 0:
        flags.append("votes_missed")
        return 20
    return 0


def _page_one_rate(metrics: Dict[str, Any]) -> float:
    page_count = int(metrics["page_count"])
    if page_count == 0:
        return 0.0
    return int(metrics["page_one_count"]) / page_count


def _qa_metrics_payload(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_count": metrics["item_count"],
        "boilerplate_count": metrics["boilerplate_count"],
        "boilerplate_rate": round(float(metrics["boilerplate_rate"]), 4),
        "name_like_count": metrics["name_like_count"],
        "name_like_rate": round(float(metrics["name_like_rate"]), 4),
        "missing_page_count": metrics["missing_page_count"],
        "page_one_rate": round(_page_one_rate(metrics), 4),
        "raw_vote_lines": metrics["raw_vote_lines"],
        "extracted_vote_count": metrics["extracted_vote_count"],
        "max_page_in_raw": metrics["max_page_in_raw"],
    }


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
