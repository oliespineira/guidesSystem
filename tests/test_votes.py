from datetime import datetime

import pytest

from src.actas import service as actas, votes
from src.errors import ConflictError, InvalidInputError, NotFoundError
from src.kraal import service as kraal

BEFORE = datetime(2026, 10, 5, 19, 0)    # while the vote is open
AFTER = datetime(2026, 10, 5, 21, 0)     # after it closes at 20:00


@pytest.fixture
def setup(conn):
    """A ronda with 4 kraal members (3 in ramas, 1 with only a role), an outsider, and one decision."""
    r = kraal.create_ronda(conn, "2026", "2026-09-01")
    guias = kraal.create_rama(conn, r, "Guías")
    members = [kraal.add_volunteer(conn, n) for n in ("Ana", "Ben", "Cai", "Dia")]
    for v in members[:3]:
        kraal.assign_to_rama(conn, guias, v)
    kraal.assign_role(conn, r, members[3], "Tesorera")
    outsider = kraal.add_volunteer(conn, "Eva")              # exists, but not in this ronda
    meeting = actas.create_meeting(conn, r, "2026-10-05", "Kickoff")
    item = actas.add_agenda_item(conn, meeting, "Material")
    decision = actas.record_decision(conn, item, "Buy 4 tents")
    votes.open_vote(conn, decision, "2026-10-05T20:00", now=datetime(2026, 10, 1))
    return {"decision": decision, "members": members, "outsider": outsider}


def test_electorate_is_everyone_in_a_rama_or_role(conn, setup):
    assert votes.tally(conn, setup["decision"])["electorate"] == 4


def test_absent_member_can_vote_before_the_meeting(conn, setup):
    ana = setup["members"][0]
    votes.cast_vote(conn, setup["decision"], ana, "yes", now=datetime(2026, 10, 2))
    assert votes.tally(conn, setup["decision"])["voters"] == [{"volunteer_id": ana, "choice": "yes"}]


def test_cannot_vote_twice(conn, setup):
    ana = setup["members"][0]
    votes.cast_vote(conn, setup["decision"], ana, "yes", now=BEFORE)
    with pytest.raises(ConflictError):
        votes.cast_vote(conn, setup["decision"], ana, "no", now=BEFORE)


def test_outsider_cannot_vote(conn, setup):
    with pytest.raises(ConflictError):
        votes.cast_vote(conn, setup["decision"], setup["outsider"], "yes", now=BEFORE)


def test_cannot_vote_after_closing_time(conn, setup):
    with pytest.raises(ConflictError):
        votes.cast_vote(conn, setup["decision"], setup["members"][0], "yes", now=AFTER)


def test_invalid_choice_is_rejected(conn, setup):
    with pytest.raises(InvalidInputError):
        votes.cast_vote(conn, setup["decision"], setup["members"][0], "maybe", now=BEFORE)


def test_cannot_close_before_closing_time(conn, setup):
    with pytest.raises(ConflictError):
        votes.close_vote(conn, setup["decision"], now=BEFORE)


def test_close_stores_result_on_the_decision_and_notifies_everyone(conn, setup, notifier):
    ana, ben, cai, _ = setup["members"]
    votes.cast_vote(conn, setup["decision"], ana, "yes", now=BEFORE)
    votes.cast_vote(conn, setup["decision"], ben, "yes", now=BEFORE)
    votes.cast_vote(conn, setup["decision"], cai, "no", now=BEFORE)
    summary = votes.close_vote(conn, setup["decision"], notifier, now=AFTER)
    assert summary.startswith("approved (2 yes, 1 no, 0 abstain, 4 in kraal")
    meeting = conn.execute("SELECT vote_result FROM decisions WHERE id = ?", (setup["decision"],)).fetchone()
    assert meeting["vote_result"] == summary
    assert notifier.sent[0]["topic"].endswith(".all") and notifier.sent[0]["body"] == summary
    with pytest.raises(ConflictError):
        votes.close_vote(conn, setup["decision"], now=AFTER)          # already closed


@pytest.mark.parametrize("yes, no, abstain, cast_passes, kraal_passes", [
    (2, 1, 0, True, False),     # 2 of 4 is not MORE than half the kraal
    (3, 1, 0, True, True),
    (1, 1, 2, False, False),    # a tie does not pass
])
def test_counting_rules(yes, no, abstain, cast_passes, kraal_passes):
    t = votes.Tally(yes, no, abstain, electorate=4)
    assert votes.MajorityOfCast().passes(t) is cast_passes
    assert votes.MajorityOfKraal().passes(t) is kraal_passes


def test_open_vote_validation(conn, setup):
    with pytest.raises(ConflictError):                                  # already open
        votes.open_vote(conn, setup["decision"], "2026-12-01T20:00", now=BEFORE)
    with pytest.raises(NotFoundError):
        votes.open_vote(conn, 999, "2026-12-01T20:00", now=BEFORE)


@pytest.mark.parametrize("closes_at, rule", [("not a date", "majority_of_cast"),
                                             ("2026-01-01T10:00", "majority_of_cast"),   # in the past
                                             ("2026-12-01T20:00", "loudest_wins")])
def test_open_vote_rejects_bad_input(conn, setup, closes_at, rule):
    item = conn.execute("SELECT agenda_item_id FROM decisions WHERE id = ?", (setup["decision"],)).fetchone()[0]
    other = actas.record_decision(conn, item, "Another decision")
    with pytest.raises(InvalidInputError):
        votes.open_vote(conn, other, closes_at, rule, now=BEFORE)


def test_votes_on_a_decision_without_an_open_vote(conn, setup):
    item = conn.execute("SELECT agenda_item_id FROM decisions WHERE id = ?", (setup["decision"],)).fetchone()[0]
    other = actas.record_decision(conn, item, "Not put to a vote")
    with pytest.raises(ConflictError):
        votes.tally(conn, other)
    with pytest.raises(NotFoundError):
        votes.tally(conn, 999)


def test_opening_a_vote_tells_the_whole_kraal(conn, setup, notifier):
    item = conn.execute("SELECT agenda_item_id FROM decisions WHERE id = ?", (setup["decision"],)).fetchone()[0]
    other = actas.record_decision(conn, item, "Change meeting day")
    votes.open_vote(conn, other, "2026-12-01T20:00", notifier=notifier, now=BEFORE)
    assert notifier.sent[0]["title"] == "Vote open: Change meeting day"
    assert "2026-12-01 20:00" in notifier.sent[0]["body"]