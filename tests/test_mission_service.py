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

    assert service._ordered_for_team(team, missions) == missions


def test_ordered_for_team_rotates_but_keeps_final_mission_last():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2), DummyMission(4, 3)]
    team = DummyTeam(starting_mission_id=3)

    ordered = service._ordered_for_team(team, missions)

    assert [m.id for m in ordered] == [3, 1, 2, 4]
    assert ordered[-1].id == 4  # the highest-order_index (final/vault) mission never moves


def test_ordered_for_team_falls_back_when_starting_mission_not_found():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1)]
    team = DummyTeam(starting_mission_id=999)

    assert service._ordered_for_team(team, missions) == missions


def test_current_mission_for_honors_rotation():
    service = MissionService()
    missions = [DummyMission(1, 0), DummyMission(2, 1), DummyMission(3, 2)]
    team = DummyTeam(starting_mission_id=2)

    mission, team_mission = service.current_mission_for(team, missions)

    assert mission.id == 2
    assert team_mission is None
