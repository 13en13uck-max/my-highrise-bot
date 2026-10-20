from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BotStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = {
            "roles": {},
            "warnings": {},
            "known_users": {},
            "teleports": {},
            "owner_id": None,
            "owner_set": False,
            "usernames": {},
            "nicknames": {},
            "notes": {},
            "sessions": {},
            "actions": {},
            "user_stats": {},
            "command_logs": [],
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
                    self.data["owner_set"] = bool(
                        loaded.get("owner_set", loaded.get("owner_id"))
                    )
            except (json.JSONDecodeError, OSError):
                self._save()
        for key, default in (
            ("roles", {}),
            ("warnings", {}),
            ("known_users", {}),
            ("teleports", {}),
            ("usernames", {}),
            ("nicknames", {}),
            ("notes", {}),
            ("sessions", {}),
            ("actions", {}),
            ("user_stats", {}),
            ("command_logs", []),
        ):
            if not isinstance(self.data.get(key), type(default)):
                self.data[key] = default
        if isinstance(self.data["known_users"], list):
            self.data["known_users"] = {
                user_id: self.data["sessions"].get(user_id, {}).get("first_joined_at")
                or self.data["sessions"].get(user_id, {}).get("last_joined_at")
                for user_id in self.data["known_users"]
            }
        if not isinstance(self.data.get("owner_set"), bool):
            self.data["owner_set"] = bool(self.data.get("owner_id"))
        for user_id, history in self.data["actions"].items():
            stats = self.data["user_stats"].setdefault(
                user_id, self._empty_user_stats()
            )
            for command, counter in (
                ("!ban", "bans"),
                ("!kick", "kicks"),
                ("!mute", "mutes"),
                ("!warn", "warns"),
            ):
                if counter not in stats:
                    stats[counter] = sum(
                        entry.get("command") == command for entry in history
                    )
        for user_id, session in self.data["sessions"].items():
            stats = self.data["user_stats"].setdefault(
                user_id, self._empty_user_stats()
            )
            stats.setdefault("total_time_in_room", session.get("total_seconds", 0))

    def _save(self) -> None:
        temporary_path = self.path.with_name(self.path.name + ".tmp")
        temporary_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(self.path)

    def register_user(self, user_id: str, username: str) -> tuple[bool, str]:
        known_users = self.data["known_users"]
        returning = user_id in known_users
        self.data["roles"].setdefault(user_id, "guest")
        self.data["usernames"][user_id] = username
        if not known_users.get(user_id):
            known_users[user_id] = datetime.now(timezone.utc).isoformat()
        session = self.data["sessions"].setdefault(user_id, {})
        if not session.get("first_joined_at"):
            session["first_joined_at"] = known_users[user_id]
        role = self.data["roles"][user_id]
        self._save()
        return returning, role

    def role_for(self, user_id: str) -> str:
        return self.data["roles"].get(user_id, "guest")

    def nickname_for(self, user_id: str) -> str | None:
        nickname = self.data["nicknames"].get(user_id)
        return nickname if isinstance(nickname, str) else None

    def set_nickname(self, user_id: str, nickname: str) -> None:
        self.data["nicknames"][user_id] = nickname
        self._save()

    def note_for(self, user_id: str) -> str | None:
        note = self.data["notes"].get(user_id)
        return note if isinstance(note, str) else None

    def set_note(self, user_id: str, note: str) -> None:
        self.data["notes"][user_id] = note
        self._save()

    def set_role(self, user_id: str, username: str, role: str) -> None:
        self.data["roles"][user_id] = role
        self.data["usernames"][user_id] = username
        self._save()

    def get_owner_id(self) -> str | None:
        return self.data.get("owner_id") if self.data.get("owner_set") else None

    def set_owner_once(self, user_id: str, username: str) -> bool:
        if self.data.get("owner_set"):
            return False
        self.data["owner_id"] = user_id
        self.data["owner_set"] = True
        self.data["roles"][user_id] = "owner"
        self.data["usernames"][user_id] = username
        if user_id not in self.data["known_users"]:
            self.data["known_users"][user_id] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def user_id_for_username(self, username: str) -> str | None:
        requested = username.lstrip("@").casefold()
        return next(
            (
                user_id
                for user_id, saved_name in self.data["usernames"].items()
                if saved_name.casefold() == requested
            ),
            None,
        )

    def start_session(
        self, user_id: str, username: str, joined_at: datetime | None = None
    ) -> None:
        self.data["usernames"][user_id] = username
        session = self.data["sessions"].setdefault(
            user_id,
            {"current_joined_at": None, "total_seconds": 0, "visits": 0},
        )
        session.setdefault("current_joined_at", None)
        session.setdefault("total_seconds", 0)
        session.setdefault("visits", 0)
        if session.get("current_joined_at"):
            return
        now = joined_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        timestamp = now.astimezone(timezone.utc).isoformat()
        session["current_joined_at"] = timestamp
        if not session.get("first_joined_at"):
            session["first_joined_at"] = self.data["known_users"].get(user_id) or timestamp
        session["last_joined_at"] = timestamp
        session["visits"] += 1
        self._save()

    def finish_session(
        self, user_id: str, departed_at: datetime | None = None
    ) -> int:
        session = self.data["sessions"].get(user_id)
        if not session or not session.get("current_joined_at"):
            return 0
        joined_at = datetime.fromisoformat(session["current_joined_at"])
        now = departed_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        duration = max(0, int((now - joined_at).total_seconds()))
        session["total_seconds"] = session.get("total_seconds", 0) + duration
        session["last_session_seconds"] = duration
        session["last_left_at"] = now.astimezone(timezone.utc).isoformat()
        session["current_joined_at"] = None
        stats = self.data["user_stats"].setdefault(user_id, self._empty_user_stats())
        stats["total_time_in_room"] = stats.get("total_time_in_room", 0) + duration
        self._save()
        return duration

    def session_stats(self, user_id: str) -> dict[str, Any]:
        session = self.data["sessions"].get(user_id, {})
        current_seconds = 0
        current_joined_at = session.get("current_joined_at")
        if current_joined_at:
            joined_at = datetime.fromisoformat(current_joined_at)
            current_seconds = max(
                0, int((datetime.now(timezone.utc) - joined_at).total_seconds())
            )
        return {
            "joined_at": self.data["known_users"].get(user_id)
            or session.get("first_joined_at"),
            "current_seconds": current_seconds,
            "total_seconds": self.data["user_stats"]
            .get(user_id, {})
            .get("total_time_in_room", session.get("total_seconds", 0))
            + current_seconds,
            "visits": session.get("visits", 0),
        }

    @staticmethod
    def _empty_user_stats() -> dict[str, int]:
        return {
            "bans": 0,
            "kicks": 0,
            "mutes": 0,
            "warns": 0,
            "total_time_in_room": 0,
        }

    def user_stats_for(self, user_id: str) -> dict[str, int]:
        stats = self._empty_user_stats()
        stats.update(self.data["user_stats"].get(user_id, {}))
        return stats

    def record_action(
        self,
        user_id: str,
        command: str,
        duration_seconds: int,
        reason: str,
        timestamp: str,
    ) -> None:
        history = self.data["actions"].setdefault(user_id, [])
        history.append(
            {
                "timestamp": timestamp,
                "command": command,
                "duration_seconds": duration_seconds,
                "reason": reason,
            }
        )
        counter_key = {
            "!ban": "bans",
            "!kick": "kicks",
            "!mute": "mutes",
            "!warn": "warns",
        }.get(command)
        if counter_key:
            stats = self.data["user_stats"].setdefault(
                user_id, self._empty_user_stats()
            )
            stats[counter_key] = stats.get(counter_key, 0) + 1
        self._save()

    def actions_for(self, user_id: str) -> list[dict[str, Any]]:
        return list(self.data["actions"].get(user_id, []))

    def append_command_log(self, entry: dict[str, Any]) -> None:
        self.data["command_logs"].append(entry)
        del self.data["command_logs"][:-100]
        self._save()

    def recent_command_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self.data["command_logs"][-limit:])

    def staff_user_ids(self) -> list[str]:
        from bot_helpers import ROLE_RANK

        return [
            user_id
            for user_id, role in self.data["roles"].items()
            if ROLE_RANK.get(role, -1) >= ROLE_RANK["mod2"]
        ]

    def warnings_for(self, user_id: str) -> list[int]:
        return list(self.data["warnings"].get(user_id, []))

    def add_warning(self, user_id: str, warning_number: int) -> str:
        warnings = self.data["warnings"].setdefault(user_id, [])
        if len(warnings) >= 3:
            return "maximum"
        if warning_number in warnings:
            return "duplicate"
        warnings.append(warning_number)
        warnings.sort()
        self._save()
        return "added"

    def clear_warnings(self, user_id: str) -> int:
        warnings = self.data["warnings"].pop(user_id, [])
        if warnings:
            self._save()
        return len(warnings)

    def teleport_exists(self, name: str) -> bool:
        return name.casefold() in {key.casefold() for key in self.data["teleports"]}

    def save_teleport(
        self, name: str, x: float, y: float, z: float, facing: str, min_role: str
    ) -> None:
        self.data["teleports"][name] = {
            "x": x,
            "y": y,
            "z": z,
            "facing": facing,
            "min_role": min_role,
        }
        self._save()

    def get_teleport(self, name: str) -> dict[str, Any] | None:
        for saved_name, location in self.data["teleports"].items():
            if saved_name.casefold() == name.casefold():
                return location
        return None

    def remove_teleport(self, name: str) -> bool:
        saved_name = next(
            (key for key in self.data["teleports"] if key.casefold() == name.casefold()),
            None,
        )
        if saved_name is None:
            return False
        del self.data["teleports"][saved_name]
        self._save()
        return True

    def remove_all_teleports(self) -> list[str]:
        names = list(self.data["teleports"])
        if names:
            self.data["teleports"].clear()
            self._save()
        return names