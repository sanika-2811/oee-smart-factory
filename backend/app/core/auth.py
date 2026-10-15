"""HTTP Basic authentication for write operations (FR-10 / NFR-S1). Single-tenant, env-seeded users.

Read endpoints stay open. The SPA sends ``X-Requested-With: fetch`` so a 401 does not trigger the
browser's native password prompt; Swagger UI (/docs) still gets the standard challenge.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic = HTTPBasic(auto_error=False)
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
    user = store.verify(creds.username, creds.password) if creds else None
    if user is None:
        headers = {} if request.headers.get("x-requested-with") else {"WWW-Authenticate": 'Basic realm="OEE Dashboard"'}
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Please sign in with a valid username and password to make changes.", headers=headers)
    return user
