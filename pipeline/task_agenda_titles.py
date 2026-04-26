import re


def _dedupe_titles_preserve_order(values):
    """
    Deduplicate extracted title candidates without reordering them.
    """
    seen = set()
    out = []
    for v in values or []:
        key = (v or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _extract_agenda_titles_from_text(text: str, max_titles: int = 3):
    """
    Best-effort agenda title extraction from raw/flattened extracted text.

    Why this exists:
    Some "agenda" PDFs are tiny, header-heavy, or flattened into a single line.
    In those cases, an LLM summary often degenerates into boilerplate or headings.
    This heuristic keeps the output deterministic and city-agnostic.
    """
    if not text:
        return []

    # Page markers are useful for deep linking, but they make regex parsing noisier.
    value = re.sub(r"\[PAGE\s+\d+\]", "\n", text, flags=re.IGNORECASE)
    # Normalize runs of spaces/tabs without deleting letters.
    value = re.sub(r"[ \t]+", " ", value)

    titles = []

    def _looks_like_attendance_or_access_info(line: str) -> bool:
        """
        Skip "how to attend" boilerplate.

        Why:
        Many agendas include numbered participation instructions (email/phone/webinar).
        Those are not agenda *items* and should not drive summaries.
        """
        v = (line or "").strip().lower()
        if not v:
            return True
        needles = [
            "teleconference",
            "public participation",
            "email comments",
            "e-mail comments",
            "email address",
            "enter an email",
            "enter your email",
            "register",
            "webinar",
            "zoom",
            "webex",
            "teams",
            "passcode",
            "phone",
            "dial",
            "raise hand",
            "unmute",
            "mute",
            "last four digits",
            "time allotted",
            "limit your remarks",
            "browser",
            "microsoft edge",
            "internet explorer",
            "safari",
            "firefox",
            "chrome",
            "ada",
            "accommodation",
            "accessibility",
        ]
        return any(n in v for n in needles)

    # 1) Prefer true line-based numbering when available.
    for m in re.finditer(r"(?m)^\s*\d+\.\s+(.+?)\s*$", value):
        title = (m.group(1) or "").strip()
        if not title or len(title) < 10:
            continue
        if _looks_like_attendance_or_access_info(title):
            continue
        titles.append(title)
        if len(titles) >= max_titles:
            break

    # 2) Fallback: split by inline numbering when extraction collapsed line breaks.
    if len(titles) < max_titles:
        parts = re.split(r"\b(\d{1,2})\.\s+", value)
        # parts: [prefix, num, rest, num, rest, ...]
        for i in range(1, len(parts), 2):
            rest = (parts[i + 1] if i + 1 < len(parts) else "").strip()
            if not rest:
                continue
            candidate = rest.split("\n", 1)[0].strip()
            candidate = candidate[:160].strip()
            if len(candidate) < 10:
                continue
            if _looks_like_attendance_or_access_info(candidate):
                continue
            titles.append(candidate)
            if len(titles) >= max_titles:
                break

    return _dedupe_titles_preserve_order(titles)[:max_titles]
