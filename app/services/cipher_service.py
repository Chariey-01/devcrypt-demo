import hashlib
import hmac
import string


class CipherService:
    ALPHABET = string.ascii_uppercase

    def solve(self, submitted_answer, expected_answer):
        return submitted_answer.strip().lower() == expected_answer.strip().lower()

    def shift_for(self, mission):
        return (mission.order_index * 3 + 1) % 26

    def _shift_word(self, word, shift):
        return "".join(
            self.ALPHABET[(self.ALPHABET.index(ch) + shift) % 26] if ch in self.ALPHABET else ch
            for ch in word.upper()
        )

    def encode(self, word, shift):
        return self._shift_word(word, shift)

    def decode(self, word, shift):
        return self._shift_word(word, -shift % 26)

    def board_for_mission(self, mission, revealed_indices):
        word = mission.cipher_word.upper()
        encoded = self.encode(word, self.shift_for(mission))
        return "".join(
            word[i] if i in revealed_indices else encoded[i] for i in range(len(word))
        )

    def revealed_indices(self, mission, team_mission):
        revealed = set()
        if not team_mission:
            return revealed
        word_len = len(mission.cipher_word)
        if word_len:
            for answer in team_mission.knowledge_answers:
                if answer.is_correct:
                    # Modulo, not a direct index — a booth's Knowledge Check question count
                    # and its cipher word length are independently configured (unlike the old
                    # removed MCQ system, which assumed they matched 1:1), so this never
                    # throws even if an Agent adds more questions than letters.
                    revealed.add(answer.question.order_index % word_len)
        if team_mission.status in ("passed", "overridden"):
            revealed.update(range(word_len))
        return revealed

    def board_state(self, team, missions):
        tm_map = {tm.mission_id: tm for tm in team.team_missions}
        board = []
        for mission in missions:
            team_mission = tm_map.get(mission.id)
            revealed = self.revealed_indices(mission, team_mission)
            board.append(
                {
                    "mission_id": mission.id,
                    "title": mission.title,
                    "tagline": mission.tagline,
                    "display": self.board_for_mission(mission, revealed),
                    "revealed": [i in revealed for i in range(len(mission.cipher_word))],
                    "complete": bool(team_mission and team_mission.status in ("passed", "overridden")),
                }
            )
        return board

    def generate_fragment(self, team_id, mission_id, event_salt):
        digest = hmac.new(
            event_salt.encode(), f"{team_id}:{mission_id}".encode(), hashlib.sha256
        ).hexdigest()
        return f"{digest[0:2].upper()}:{digest[2:4].upper()}"
