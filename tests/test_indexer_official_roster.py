import datetime
from types import SimpleNamespace


def _person(name, person_type="official"):
    return SimpleNamespace(id=1, ocd_id="ocd", name=name, person_type=person_type)


def _membership(person, start_date=None, end_date=None):
    return SimpleNamespace(person=person, start_date=start_date, end_date=end_date)


def test_indexer_filters_officials_by_meeting_date_when_term_dates_exist():
    """
    If term dates exist, we should prefer the roster active on the meeting date.
    """
    meeting_date = datetime.date(2022, 9, 20)

    old = _membership(_person("Old Member"), start_date=datetime.date(2020, 1, 1), end_date=datetime.date(2022, 1, 1))
    active = _membership(_person("Active Member"), start_date=datetime.date(2022, 1, 2), end_date=None)
    mentioned = _membership(_person("Mentioned Name", person_type="mentioned"), start_date=datetime.date(2022, 1, 2), end_date=None)

    org = SimpleNamespace(memberships=[old, active, mentioned])

    from pipeline.indexer import _select_official_memberships_for_event

    chosen = _select_official_memberships_for_event(org, meeting_date)
    names = [m.person.name for m in chosen]

    assert names == ["Active Member"]


def test_indexer_falls_back_to_undated_officials_when_no_term_dates_are_present():
    """
    If we have no term dates at all, don't return an empty roster; show undated official memberships.
    """
    meeting_date = datetime.date(2022, 9, 20)

    undated_a = _membership(_person("Undated A"))
    undated_b = _membership(_person("Undated B"))
    org = SimpleNamespace(memberships=[undated_a, undated_b])

    from pipeline.indexer import _select_official_memberships_for_event

    chosen = _select_official_memberships_for_event(org, meeting_date)
    names = [m.person.name for m in chosen]

    assert names == ["Undated A", "Undated B"]
