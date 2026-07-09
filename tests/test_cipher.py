from types import SimpleNamespace

from app.services.cipher_service import CipherService


def test_cipher_accepts_case_insensitive_match():
    service = CipherService()

    assert service.solve("DevCrypt", "devcrypt") is True
    assert service.solve("wrong", "devcrypt") is False


def test_encode_decode_are_inverses():
    service = CipherService()

    encoded = service.encode("DEPLOY", 5)
    assert encoded != "DEPLOY"
    assert service.decode(encoded, 5) == "DEPLOY"


def test_shift_is_distinct_per_mission_order_index():
    service = CipherService()
    missions = [SimpleNamespace(order_index=i) for i in range(1, 7)]

    shifts = {service.shift_for(m) for m in missions}
    assert len(shifts) == 6


def test_board_for_mission_reveals_only_requested_indices():
    service = CipherService()
    mission = SimpleNamespace(order_index=1, cipher_word="DEPLOY")

    board = service.board_for_mission(mission, revealed_indices={0, 2})
    encoded = service.encode("DEPLOY", service.shift_for(mission))

    assert board[0] == "D"
    assert board[2] == "P"
    assert board[1] == encoded[1]


def test_generate_fragment_is_deterministic_and_salt_sensitive():
    service = CipherService()

    a = service.generate_fragment(1, 1, "salt-one")
    b = service.generate_fragment(1, 1, "salt-one")
    c = service.generate_fragment(1, 1, "salt-two")

    assert a == b
    assert a != c
    assert ":" in a
