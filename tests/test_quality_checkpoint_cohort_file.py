from pathlib import Path


def test_quality_checkpoint_cohort_file_is_pinned():
    path = Path("experiments/gemma4_quality_checkpoint_cohort_v1.txt")
    values = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            values.append(line)
    assert values == ["3", "609", "933"]
