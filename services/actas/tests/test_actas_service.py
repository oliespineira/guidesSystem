import pytest
from app.actas import service
from app.errors import InvalidInputError, NotFoundError


def make_ronda(conn, kraal):
    return kraal.create_ronda(conn, "Ronda Solar 11", "2026-09-01")


def test_create_meeting_rejects_blank_title(conn, kraal):
    ronda = make_ronda(conn, kraal)
    with pytest.raises(InvalidInputError):
        service.create_meeting(conn, ronda, "2026-09-01", "   ")


def test_create_meeting_unknown_ronda_is_not_found(conn, kraal):
    with pytest.raises(NotFoundError):
        service.create_meeting(conn, 999, "2026-09-01", "Meeting Title")


@pytest.mark.parametrize("bad_date", ["invalid-date", "2026-02-30"])
def test_create_meeting_rejects_invalid_date(conn, kraal, bad_date):
    ronda = make_ronda(conn, kraal)
    with pytest.raises(InvalidInputError):
        service.create_meeting(conn, ronda, bad_date, "Meeting Title")


def test_calendar_event_end_before_start_is_rejected(conn, kraal):
    ronda = make_ronda(conn, kraal)
    with pytest.raises(service.InvalidDateRangeError):
        service.add_calendar_event(conn, ronda, "2026-09-10", "Camp", end_date="2026-09-05")


def test_calendar_event_same_day_is_allowed(conn, kraal):
    ronda = make_ronda(conn, kraal)
    event_id = service.add_calendar_event(conn, ronda, "2026-09-10", "Camp", end_date="2026-09-10")
    assert isinstance(event_id, int)


def test_agenda_positions_auto_increment(conn, kraal):
    ronda = make_ronda(conn, kraal)
    meeting = service.create_meeting(conn, ronda, "2026-09-10", "Kickoff")
    for title in ("A", "B", "C"):
        service.add_agenda_item(conn, meeting, title)
    positions = [i["position"] for i in service.meeting_summary(conn, meeting)["agenda"]]
    assert positions == [0, 1, 2]


def test_meeting_summary_nests_decisions_under_the_right_item(conn, kraal):
    ronda = make_ronda(conn, kraal)
    meeting = service.create_meeting(conn, ronda, "2026-09-10", "Kickoff")
    budget = service.add_agenda_item(conn, meeting, "Budget")
    service.add_agenda_item(conn, meeting, "Camp")
    service.record_decision(conn, budget, "Approve budget", "5-0")

    agenda = service.meeting_summary(conn, meeting)["agenda"]
    assert agenda[0]["decisions"][0]["description"] == "Approve budget"
    assert agenda[1]["decisions"] == []


def test_meeting_summary_unknown_meeting_is_not_found(conn, kraal):
    with pytest.raises(NotFoundError):
        service.meeting_summary(conn, 999)
