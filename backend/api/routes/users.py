"""User profiles API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import duckdb

from backend.db.connection import get_db


router = APIRouter(prefix="/api/users", tags=["Users"])


class UserProfile(BaseModel):
    user_id: str
    user_name: str
    role: str
    role_display: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    initials: str
    color_hue: int


@router.get("", response_model=List[UserProfile])
def get_users(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> List[UserProfile]:
    """Retrieve all operator and field personnel profiles."""
    rows = con.execute(
        """
        SELECT u.user_id, u.user_name, u.role, u.team_id, t.team_name
        FROM users u
        LEFT JOIN teams t ON u.team_id = t.team_id
        ORDER BY
            CASE
                WHEN u.user_name = 'Michael Turner' THEN 1
                WHEN u.user_name = 'Jessica Reed' THEN 2
                WHEN u.user_name = 'Tyler Hughes' THEN 3
                WHEN u.user_name = 'Jake Morales' THEN 4
                WHEN u.user_name = 'Laura Simmons' THEN 5
                ELSE 6
            END,
            u.user_name ASC
        """
    ).fetchall()

    profiles: List[UserProfile] = []
    hue_map = {
        "production_supervisor": 210,    # Blue
        "field_inspector": 145,          # Green
        "field_operator": 35,            # Amber
        "hse_officer": 0,                # Red / Crimson
        "maintenance_technician": 275,   # Purple
        "maintenance_lead": 290,         # Deep purple
    }

    for r in rows:
        uid, name, role, team_id, team_name = r
        parts = name.split()
        initials = "".join([p[0].upper() for p in parts if p])[:2]
        role_disp = role.replace("_", " ").title()

        profiles.append(
            UserProfile(
                user_id=uid,
                user_name=name,
                role=role,
                role_display=role_disp,
                team_id=team_id,
                team_name=team_name,
                initials=initials,
                color_hue=hue_map.get(role, 200),
            )
        )

    return profiles
