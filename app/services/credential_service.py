import secrets

# Excludes 0/O and 1/I/L so a team reading a printed key card aloud can't confuse them.
TEAM_KEY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_team_key(length=8):
    return "".join(secrets.choice(TEAM_KEY_ALPHABET) for _ in range(length))


def generate_password():
    return secrets.token_urlsafe(18)
