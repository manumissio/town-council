import html
import os
import re


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_text_lines_from_html(raw_html):
    # Remove script/style blocks first so we do not index JS/CSS text.
    cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw_html)
    cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)

    # Turn layout tags into line breaks, then strip all other tags.
    cleaned = re.sub(r"(?i)</?(?:br|p|li|td|tr|div|h[1-6])[^>]*>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)

    lines = [_normalize(line) for line in cleaned.splitlines()]
    return [line for line in lines if line]


def parse_eagenda_items_from_html(raw_html):
    """
    Parse likely agenda items from Berkeley-style eAgenda HTML text.

    This parser is intentionally conservative: it only accepts lines with a
    clear section/item marker so we do not pull random prose into results.
    """
    items = []
    seen_titles = set()
    lines = _extract_text_lines_from_html(raw_html)

    marker_pattern = re.compile(
        r"(?i)^(?:agenda\s*)?(?:item|section)?\s*"
        r"(\d{1,2}(?:\.\d+)*|[A-Z]|[IVXLCM]+)"
        r"[\)\.\-:]\s+(.{6,220})$"
    )

    for line in lines:
        match = marker_pattern.match(line)
        if not match:
            continue

        marker = _normalize(match.group(1))
        title = _normalize(match.group(2))
        title_key = title.lower()

        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        items.append({
            "order": len(items) + 1,
            "title": title,
            "description": f"eAgenda section {marker}",
            "classification": "Agenda Item",
            "result": "",
            "page_number": None,
        })

        # Defensive cap so malformed HTML does not flood rows.
        if len(items) >= 40:
            break

    return items


def parse_eagenda_items_from_file(file_path):
    """
    Read an HTML eAgenda file and return parsed agenda items.
    """
    if not file_path or not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_html = f.read()
    except OSError:
        return []

    return parse_eagenda_items_from_html(raw_html)


def merge_ai_with_eagenda(ai_items, eagenda_items):
    """
    Merge strategy:
    - If eAgenda parsed at least 3 items, treat it as authoritative.
    - Otherwise, keep AI items and append non-duplicate eAgenda items.
    """
    ai_items = ai_items or []
    eagenda_items = eagenda_items or []

    if len(eagenda_items) >= 3:
        return eagenda_items

    merged = []
    seen_titles = set()

    for item in ai_items:
        title = _normalize(item.get("title"))
        if not title:
            continue
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        merged.append(item)

    for item in eagenda_items:
        title = _normalize(item.get("title"))
        if not title:
            continue
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        merged.append(item)

    return merged
