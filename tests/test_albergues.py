from datetime import date

import pytest

from src.actas import albergues, policies, service as actas, tesoreria
from src.errors import ConflictError, InvalidInputError, NotFoundError
from src.kraal import service as kraal


@pytest.fixture
def outing(conn):
    ronda = kraal.create_ronda(conn, "2026", "2026-09-01")
    event = actas.add_calendar_event(conn, ronda, "2027-03-20", "Spring camp", end_date="2027-03-22")
    return ronda, event


def test_default_deadline_is_lead_days_before_the_outing(conn, outing, monkeypatch):
    monkeypatch.setenv("BOOKING_LEAD_DAYS", "90")
    _, event = outing
    assert albergues.plan_booking(conn, event) == "2026-12-20"          # 90 days before 2027-03-20


def test_planning_tells_the_whole_kraal(conn, outing, notifier):
    ronda, event = outing
    albergues.plan_booking(conn, event, "2027-01-15", notifier)
    assert notifier.sent[0]["topic"] == f"ronda.{ronda}.all"
    assert notifier.sent[0]["body"] == "Book before 2027-01-15."


@pytest.mark.parametrize("book_by", ["2027-03-20", "2027-04-01", "not-a-date"])
def test_deadline_must_be_a_date_before_the_outing(conn, outing, book_by):
    _, event = outing
    with pytest.raises(InvalidInputError):
        albergues.plan_booking(conn, event, book_by)


def test_cannot_plan_twice_or_plan_an_unknown_outing(conn, outing):
    _, event = outing
    albergues.plan_booking(conn, event, "2027-01-15")
    with pytest.raises(ConflictError):
        albergues.plan_booking(conn, event, "2027-01-20")
    with pytest.raises(NotFoundError):
        albergues.plan_booking(conn, 999)


def test_mark_booked_links_the_payment_and_cannot_repeat(conn, outing, notifier):
    ronda, event = outing
    albergues.plan_booking(conn, event, "2027-01-15")
    budget = tesoreria.create_budget(conn, ronda, "Albergues", 50000)
    paid = tesoreria.submit_request(conn, budget, "Guías", "Albergue Cercedilla", 30000, policies.RejectOverBudget())
    albergues.mark_booked(conn, event, "Albergue Cercedilla", paid.request_id, notifier)
    row = albergues.list_bookings(conn, ronda, today=date(2027, 1, 1))[0]
    assert (row["status"], row["venue"], row["request_id"]) == ("booked", "Albergue Cercedilla", paid.request_id)
    assert notifier.sent[0]["title"] == "Albergue booked for Spring camp: Albergue Cercedilla"
    with pytest.raises(ConflictError):
        albergues.mark_booked(conn, event, "Another place")


def test_mark_booked_needs_a_plan_a_venue_and_a_real_request(conn, outing):
    _, event = outing
    with pytest.raises(ConflictError):
        albergues.mark_booked(conn, event, "Somewhere")                 # not planned yet
    with pytest.raises(NotFoundError):
        albergues.mark_booked(conn, 999, "Somewhere")
    albergues.plan_booking(conn, event, "2027-01-15")
    with pytest.raises(InvalidInputError):
        albergues.mark_booked(conn, event, "   ")
    with pytest.raises(NotFoundError):
        albergues.mark_booked(conn, event, "Somewhere", request_id=999)

def test_list_shows_days_left_and_urgency(conn, outing, monkeypatch):
    monkeypatch.setenv("BOOKING_REMIND_DAYS", "14")
    ronda, event = outing
    albergues.plan_booking(conn, event, "2027-01-15")
    far = albergues.list_bookings(conn, ronda, today=date(2026, 12, 1))[0]
    near = albergues.list_bookings(conn, ronda, today=date(2027, 1, 5))[0]
    assert (far["days_left"], far["urgent"]) == (45, False)
    assert (near["days_left"], near["urgent"]) == (10, True)


def test_reminders_only_when_close_once_per_day_and_not_after_booking(conn, outing, notifier, monkeypatch):
    monkeypatch.setenv("BOOKING_REMIND_DAYS", "14")
    _, event = outing
    albergues.plan_booking(conn, event, "2027-01-15")
    assert albergues.send_reminders(conn, notifier, today=date(2026, 12, 1)) == 0      # too early
    assert albergues.send_reminders(conn, notifier, today=date(2027, 1, 5)) == 1       # 10 days left
    assert albergues.send_reminders(conn, notifier, today=date(2027, 1, 5)) == 0       # already reminded today
    assert albergues.send_reminders(conn, notifier, today=date(2027, 1, 20)) == 1      # overdue, new day
    assert "5 days OVERDUE" in notifier.sent[-1]["body"]
    albergues.mark_booked(conn, event, "Albergue Cercedilla")
    assert albergues.send_reminders(conn, notifier, today=date(2027, 1, 21)) == 0      # booked: stop