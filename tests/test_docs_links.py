from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _extract_markdown_links(text: str):
    # Capture markdown links [label](target)
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def test_readme_local_doc_links_resolve():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = _extract_markdown_links(readme)

    local_links = [
        l for l in links
        if not l.startswith("http://")
        and not l.startswith("https://")
        and not l.startswith("#")
    ]

    for link in local_links:
        path_part = link.split("#", 1)[0]
        target = (ROOT / path_part).resolve()
        assert target.exists(), f"Broken README local link: {link}"


def test_docs_files_exist_and_nonempty():
    required = [
        ROOT / "docs" / "OPERATIONS.md",
        ROOT / "docs" / "PERFORMANCE.md",
        ROOT / "docs" / "CONTRIBUTING_CITIES.md",
    ]
    for p in required:
        assert p.exists(), f"Missing docs file: {p}"
        assert p.read_text(encoding="utf-8").strip(), f"Empty docs file: {p}"
