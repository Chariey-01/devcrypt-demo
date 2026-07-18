from app.services.mission_service import MissionService


class DummyMission:
    def __init__(self, id, order_index):
        self.id = id
        self.order_index = order_index


class DummyTeam:
    def __init__(self, starting_mission_id=None):
        self.starting_mission_id = starting_mission_id
        self.team_missions = []


def test_ordered_for_team_defaults_to_original_order_when_no_starting_booth():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2)]
    team = DummyTeam()

    assert service.ordered_for_team(team, missions) == missions


def test_ordered_for_team_rotates_fully_no_mission_excluded():
    # Full circular rotation, matching the physical-booth event: a team starting at booth 3
    # of 4 visits 3,4,1,2 — every booth participates, none is pinned last regardless of
    # starting position (the old behavior this replaces always kept the highest-order_index
    # mission last for every team, which doesn't fit an event where any booth can be a
    # team's starting point).
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2), DummyMission(4, 3)]
    team = DummyTeam(starting_mission_id=3)

    ordered = service.ordered_for_team(team, missions)

    assert [m.id for m in ordered] == [3, 4, 1, 2]


def test_ordered_for_team_rotation_starting_at_the_last_booth():
    # The specific case that was previously broken: assigning the highest-order_index mission
    # as a team's starting booth used to silently fail (fall back to unrotated order) because
    # the old lookup excluded it from the rotatable set entirely.
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2), DummyMission(4, 3)]
    team = DummyTeam(starting_mission_id=4)

    ordered = service.ordered_for_team(team, missions)

    assert [m.id for m in ordered] == [4, 1, 2, 3]


def test_ordered_for_team_every_team_visits_every_booth_exactly_once():
    # Six teams, each starting at a different booth (the actual event's opening layout) —
    # confirms every team's route is a full permutation of all 6 booths, no duplicates, no
    # omissions, matching "every team must visit every booth exactly once."
    service = MissionService()
    missions = [DummyMission(i, i - 1) for i in range(1, 7)]

    for start in range(1, 7):
        team = DummyTeam(starting_mission_id=start)
        ordered = service.ordered_for_team(team, missions)
        assert sorted(m.id for m in ordered) == [1, 2, 3, 4, 5, 6]
        assert len(ordered) == 6
        assert ordered[0].id == start


def test_ordered_for_team_falls_back_when_starting_mission_not_found():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1)]
    team = DummyTeam(starting_mission_id=999)

    assert service.ordered_for_team(team, missions) == missions


def test_current_mission_for_honors_rotation():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2)]
    team = DummyTeam(starting_mission_id=2)

    mission, team_mission = service.current_mission_for(team, missions)

    assert mission.id == 2
    assert team_mission is None
