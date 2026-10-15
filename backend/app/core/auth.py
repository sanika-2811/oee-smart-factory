"""HTTP Basic authentication for write operations (FR-10 / NFR-S1). Single-tenant, env-seeded users.

Read endpoints stay open. The SPA sends ``X-Requested-With: fetch`` so a 401 does not trigger the
browser's native password prompt; Swagger UI (/docs) still gets the standard challenge.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic = HTTPBasic(auto_error=False)

# --- brute-force protection: 5 failed logins per client+username within 60 s -> locked for 60 s
_FAILS: dict[str, deque] = defaultdict(deque)
MAX_FAILS, WINDOW_S = 5, 60.0

# --- role permissions. Reading is open to everyone; writing needs a login, and some writes need a role.
OPERATE = {"floor_manager", "maintenance_engineer", "system_administrator"}     # alarms, maintenance, feedback
CONTROL = {"floor_manager", "system_administrator"}                             # simulator, What-If, limits, ML outage
ROLE_LABEL = {"floor_manager": "Floor Manager", "maintenance_engineer": "Maintenance Engineer",
              "production_analyst": "Production Analyst", "system_administrator": "System Administrator"}


def _throttle_key(request: Request, username: str) -> str:
    return f"{request.client.host if request.client else '?'}|{username}"


def _check_locked(key: str) -> None:
    q = _FAILS[key]
    now = time.time()
    while q and now - q[0] > WINDOW_S:
        q.popleft()
    if len(q) >= MAX_FAILS:
        wait = int(WINDOW_S - (now - q[0])) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed sign-in attempts. Please wait {wait} seconds and try again.",
                            headers={"Retry-After": str(wait)})
_ITER = 60_000


@dataclass(frozen=True)
class User:
    username: str
    role: str


class UserStore:
    def __init__(self, spec: str):
        self._users: dict[str, tuple[bytes, bytes, str]] = {}
        for item in filter(None, (s.strip() for s in spec.split(","))):
            parts = item.split(":")
            if len(parts) < 2:
                continue
            name, pw = parts[0], parts[1]
            role = parts[2] if len(parts) > 2 else "operator"
            salt = secrets.token_bytes(16)
            self._users[name] = (salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _ITER), role)

    def verify(self, username: str, password: str) -> User | None:
        rec = self._users.get(username)
        # always run the KDF so unknown users and wrong passwords take the same time
        salt, expected, role = rec or (b"\0" * 16, b"\0" * 32, "")
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
        if rec and hmac.compare_digest(got, expected):
            return User(username, role)
        return None

    def export(self) -> list[dict]:
        return [{"username": u, "role": r, "password_hash": f"pbkdf2_sha256${_ITER}${s.hex()}${h.hex()}"}
                for u, (s, h, r) in self._users.items()]

    def __len__(self) -> int:
        return len(self._users)


def require_user(request: Request, creds: HTTPBasicCredentials | None = Depends(_basic)) -> User:
    store: UserStore = request.app.state.users
    key = _throttle_key(request, creds.username) if creds else ""
    if creds:
        _check_locked(key)
    user = store.verify(creds.username, creds.password) if creds else None
    if creds and user is None:
        _FAILS[key].append(time.time())
    elif creds and user is not None:
        _FAILS.pop(key, None)
    if user is None:
        headers = {} if request.headers.get("x-requested-with") else {"WWW-Authenticate": 'Basic realm="OEE Dashboard"'}
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Please sign in with a valid username and password to make changes.", headers=headers)
    return user


def require_roles(*allowed: str):
    """Dependency factory: signed-in user whose role is in ``allowed`` (else 403 with a plain-language hint)."""
    allowed_set = set(allowed)

    def dep(user: User = Depends(require_user)) -> User:
        if user.role not in allowed_set:
            names = " or ".join(ROLE_LABEL.get(r, r) for r in sorted(allowed_set))
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Your role ({ROLE_LABEL.get(user.role, user.role)}) cannot do this. Ask a {names}.")
        return user

    return dep
