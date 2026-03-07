"""User model and role definitions."""

from enum import Enum
from dataclasses import dataclass


class Role(str, Enum):
    admin = "admin"
    attorney = "attorney"
    paralegal = "paralegal"


@dataclass
class User:
    username: str
    hashed_password: str
    role: Role
    full_name: str = ""


# In-memory user store for development.
# In production, replace with a database lookup.
_USERS: dict[str, User] = {
    "admin": User(
        username="admin",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        role=Role.admin,
        full_name="System Administrator",
    ),
    "attorney1": User(
        username="attorney1",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        role=Role.attorney,
        full_name="Jane Smith, Esq.",
    ),
    "paralegal1": User(
        username="paralegal1",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        role=Role.paralegal,
        full_name="Bob Johnson",
    ),
}


def get_user(username: str) -> User | None:
    return _USERS.get(username)
