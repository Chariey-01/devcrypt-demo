import base64
import hashlib
import hmac


def _hmac(key, message):
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).digest()


class FinalFlagService:
    """Server-only reconstruction of the event's one final flag.

    Deliberately independent of CipherService's per-team decorative fragment codes (the
    cryptogram board) — those are shown to players and must never leak real key material. This
    derives its master key purely from EVENT_SALT (a server-only secret) and a fixed set of
    Mission ids (public, which is fine — HMAC security depends on the key being secret, not the
    message). It only ever runs after the caller has independently verified, server-side, that
    the requesting team has actually passed every one of those missions — see missions.py's
    /missions/final-flag route, which never trusts anything the client claims about its own
    progress.

    No new dependency: HMAC-keyed keystream + XOR is a correct, standard stream-cipher
    construction (HMAC as the PRF, equivalent to counter-mode). The usual XOR-cipher pitfall —
    reusing a keystream across multiple different plaintexts — doesn't apply here, because there
    is exactly one plaintext (this event's flag) ever encrypted under this key.
    """

    def __init__(self, event_salt, ciphertext_b64):
        self.event_salt = event_salt
        self.ciphertext = base64.b64decode(ciphertext_b64) if ciphertext_b64 else None

    def mission_share(self, mission_id):
        return _hmac(self.event_salt, f"vault-key:{mission_id}")

    def master_key(self, mission_ids):
        # Sorted by id (immutable once a Mission row is created), not order_index — order_index
        # can be changed later by a Game Master reordering booths, which would silently shift
        # the derived key and break decryption of an already-generated ciphertext.
        combined = b"".join(self.mission_share(mid) for mid in sorted(mission_ids))
        return _hmac(self.event_salt, combined)

    def _keystream(self, key, length):
        out = b""
        counter = 0
        while len(out) < length:
            out += _hmac(key, str(counter))
            counter += 1
        return out[:length]

    def encrypt(self, plaintext, mission_ids):
        """Setup-time only (scripts/derive_final_flag.py) — never called at request time."""
        key = self.master_key(mission_ids)
        keystream = self._keystream(key, len(plaintext.encode("utf-8")))
        ciphertext = bytes(c ^ k for c, k in zip(plaintext.encode("utf-8"), keystream))
        return base64.b64encode(ciphertext).decode("ascii")

    def reconstruct(self, mission_ids):
        """Request-time reconstruction. Returns None if no ciphertext is configured at all
        (e.g. local dev before an operator has run derive_final_flag.py) — the caller decides
        how to present that, never fabricates a fallback flag value."""
        if self.ciphertext is None:
            return None
        key = self.master_key(mission_ids)
        keystream = self._keystream(key, len(self.ciphertext))
        plaintext = bytes(c ^ k for c, k in zip(self.ciphertext, keystream))
        return plaintext.decode("utf-8", errors="replace")
