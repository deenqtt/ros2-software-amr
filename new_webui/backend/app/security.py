"""
Password hashing and session tokens.

Standard library only. ``hashlib.scrypt`` is a memory-hard password hash, the
same family the OWASP cheat sheet recommends, and using it avoids a native
dependency (bcrypt, argon2-cffi) in a container that otherwise has none.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# OWASP's minimum for scrypt: N=2^17 is ~128 MiB per hash. 2^15 keeps a login
# well under a tenth of a second on the small PCs these servers run on, which
# matters more here than on a public site: the attacker has to be on the plant
# network, and repeated failures are throttled (see api/auth.py).
_N = 2**15
_R = 8
_P = 1
_KEY_BYTES = 32
_SALT_BYTES = 16
# scrypt needs 128 * N * r bytes; the default cap (32 MiB) is exactly that, so
# leave headroom rather than fail on an interpreter that counts differently.
_MAXMEM = 64 * 1024 * 1024

# Ten characters: long enough that guessing through the sign-in throttle is
# hopeless, short enough for a touchscreen in gloves. A short sentence is the
# easy way past it. Applies to every password set from now on; one set under
# the old minimum of eight still signs in, and is replaced at the next change.
PASSWORD_MIN = 10
PASSWORD_MAX = 128

# The commonest passwords that are long enough to pass the minimum, the ones a
# guesser tries first (from the published breach-corpus top lists), plus the
# obvious ones for this product. Not a full breach check, which would need a
# large list or a network lookup; just the handful no password should be.
_COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "123456789a",
        "0123456789",
        "0987654321",
        "1111111111",
        "1q2w3e4r5t",
        "1qaz2wsx3edc",
        "qwertyuiop",
        "qwerty1234",
        "qwerty12345",
        "qwerty123456",
        "asdfghjkl1",
        "asdfghjkl;",
        "zxcvbnm123",
        "password12",
        "password123",
        "password1234",
        "password!1",
        "passw0rd123",
        "p@ssw0rd123",
        "iloveyou12",
        "letmein123",
        "welcome123",
        "welcome1234",
        "abc1234567",
        "abcdefghij",
        "abcd123456",
        "admin12345",
        "admin123456",
        "administrator",
        "superadmin",
        "superadmin1",
        "changeme123",
        "change-me-at-first-sign-in",
        "football123",
        "sunshine123",
        "princess123",
        "trustno1234",
        "operator123",
        "robot12345",
    }
)


def password_problem(password: str, username: str | None = None) -> str | None:
    """
    Why this password may not be set, in words for the person typing it, or None.

    The one policy for every place a password is chosen: a new account, an admin
    reset, a change of your own, the command-line admin and the bootstrap
    account. Never applied at sign-in, so nobody is locked out by a rule that
    arrived after their password did.
    """
    if len(password) < PASSWORD_MIN:
        return f"Use at least {PASSWORD_MIN} characters"
    if len(password) > PASSWORD_MAX:
        return f"Use at most {PASSWORD_MAX} characters"
    folded = password.casefold()
    if username and folded.strip() == username.strip().casefold():
        return "Choose a password that is not your username"
    if len(set(folded)) == 1:
        return "Choose a password that is not one character repeated"
    if folded in _COMMON_PASSWORDS:
        return "That password is one of the first a guesser tries; choose another"
    return None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str) -> str:
    """Return ``scrypt$N$r$p$salt$key``, parameters first so they can change later."""
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, maxmem=_MAXMEM, dklen=_KEY_BYTES
    )
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check. A malformed stored hash is a mismatch, never an error."""
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(key)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the username does not exist, so "no such user" and
# "wrong password" take the same time and cannot be told apart by a stopwatch.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def new_session_token() -> str:
    """256 random bits. Goes to the browser; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    SHA-256, unsalted on purpose.

    The token is already 256 random bits, so there is nothing to guess and no
    reason for a slow hash — and the lookup has to find the row by this value.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()
