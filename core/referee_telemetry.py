from __future__ import annotations

import re


_CONTAINER_KEYS = (
    "opponent_positions",
    "konumBilgileri",
    "konum_bilgileri",
    "rakip_iha_konumlari",
    "rakipIhaKonumlari",
    "opponents",
    "rakipler",
    "vehicles",
    "aircraft",
    "results",
    "items",
    "records",
    "data",
    "telemetry",
    "samples",
    "positions",
    "track",
)
_LATITUDE_KEYS = ("iha_enlem", "ihaEnlem", "enlem", "lat", "latitude")
_LONGITUDE_KEYS = ("iha_boylam", "ihaBoylam", "boylam", "lon", "lng", "longitude")
_IDENTITY_KEYS = (
    "takim_numarasi",
    "takimNumarasi",
    "takimNo",
    "team",
    "team_id",
    "vehicle_id",
    "id",
)


def extract_opponent_positions(payload) -> list[dict]:
    """Flatten referee telemetry wrappers without imposing an aircraft limit."""
    positions: list[dict] = []

    def walk(value, inherited_team=None, depth: int = 0):
        if value is None or depth > 10:
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item, inherited_team, depth + 1)
            return
        if not isinstance(value, dict):
            return

        local_team = _identity(value)
        if local_team is None:
            local_team = inherited_team

        if _looks_like_position(value):
            position = dict(value)
            if local_team is not None and _identity(position) is None:
                position["takim_numarasi"] = local_team
            positions.append(position)
            return

        for key in _CONTAINER_KEYS:
            nested = value.get(key)
            if not isinstance(nested, (dict, list, tuple)):
                continue
            before = len(positions)
            walk(nested, local_team, depth + 1)
            if len(positions) > before:
                return

        for key, nested in value.items():
            if not isinstance(nested, (dict, list, tuple)):
                continue
            team_hint = _team_from_mapping_key(key)
            walk(nested, team_hint if team_hint is not None else local_team, depth + 1)

    walk(payload)
    return positions


def _looks_like_position(value: dict) -> bool:
    return any(key in value for key in _LATITUDE_KEYS) and any(
        key in value for key in _LONGITUDE_KEYS
    )


def _identity(value: dict):
    for key in _IDENTITY_KEYS:
        identity = value.get(key)
        if identity is not None and str(identity).strip():
            return identity
    return None


def _team_from_mapping_key(key):
    text = str(key or "").strip()
    if not text:
        return None
    if text.isdigit():
        return text
    match = re.fullmatch(r"(?:takim|team|rakip|siha|iha)[-_ ]*(.+)", text, re.IGNORECASE)
    return match.group(1) if match else None
