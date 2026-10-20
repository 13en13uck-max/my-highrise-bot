from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import shutil
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone


def _python311_command(arguments: list[str], launcher: str) -> list[str]:
    return [launcher, "-3.11", os.path.abspath(__file__), *arguments]


if (
    __name__ == "__main__"
    and sys.argv[1:2] == ["startbot"]
    and sys.version_info[:2] != (3, 11)
):
    python_launcher = shutil.which("py")
    if python_launcher is None:
        print("Python 3.11 launcher 'py' was not found.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(
        subprocess.call(_python311_command(sys.argv[1:], python_launcher))
    )

from highrise import BaseBot, CurrencyItem, Error, Item, Position, SessionMetadata, User

from bot_emotes import EMOTE_DATA
from bot_helpers import (
    COMMAND_MIN_RANK,
    NOTE_COLORS,
    REQUIRES_ADMIN,
    REQUIRES_VIP,
    ROLE_LABEL,
    ROLE_PERMISSION_NAME,
    ROLE_RANK,
    can_assign_role,
    is_emote_free,
    normalize_role,
    resolve_emote,
    resolve_emote_duration,
    split_gold_amount,
)
from bot_store import BotStore


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("highrise-room-bot")
REFRESH_DELAY_SECONDS = 2
INTERACTION_ACTIONS = {
    "!punch": (
        "emote-fail1",
        "💥🥊 @{target} just got dropped by @{sender}! Lights out! 😵",
    ),
    "!slap": ("emote-slap", "🖐️ @{target} got slapped by @{sender}! Ouch!"),
    "!kiss": ("emote-kiss", "💋 @{sender} smooched @{target}!"),
    "!hug": ("emote-hug", "🤗 @{sender} is hugging @{target}!"),
    "!scare": ("emote-panic", "😱 @{sender} scared @{target}! They're panicking!"),
    "!faint": ("emote-fainting", "😵 @{target} fainted after seeing @{sender}!"),
    "!rofl": ("emote-rofl", "😂 @{sender} made @{target} ROFL!"),
    "!dizzy": ("emoji-dizzy", "💫 @{sender} stunned @{target}!"),
}


class Bot(BaseBot):
    def __init__(self) -> None:
        self.store = BotStore(os.getenv("BOT_DATA_PATH", "bot_data.json"))
        self.owner_id = os.getenv("BOT_OWNER_ID", "").strip() or self.store.get_owner_id() or ""
        if os.getenv("BOT_OWNER_ID", "").strip() and not self.store.data["owner_set"]:
            configured_owner = os.getenv("BOT_OWNER_ID", "").strip()
            self.store.set_owner_once(
                configured_owner,
                self.store.data["usernames"].get(configured_owner, configured_owner),
            )
        self.users: dict[str, User] = {}
        self.user_positions: dict[str, Position] = {}
        self.logs: list[dict[str, object]] = self.store.recent_command_logs()
        self.last_note_color: str | None = None
        self.loop_task: asyncio.Task[None] | None = None
        self.autotip_task: asyncio.Task[None] | None = None
        self.active_emote_loops: dict[str, asyncio.Task[None]] = {}
        self.active_emote_targets: dict[str, list[str]] = {}
        self.punch_cooldowns: dict[str, float] = {}

    def _role_for(self, user_id: str) -> str:
        if user_id and user_id == self.owner_id:
            return "owner"
        return normalize_role(self.store.role_for(user_id)) or "guest"

    def _rank_for(self, user_id: str) -> int:
        return ROLE_RANK[self._role_for(user_id)]

    @staticmethod
    def _teleport_min_rank(location: dict[str, object]) -> int:
        min_role = normalize_role(str(location.get("min_role", "guest"))) or "guest"
        return ROLE_RANK[min_role]

    async def _require_rank(self, user_id: str, minimum_rank: int) -> bool:
        if self._rank_for(user_id) >= minimum_rank:
            return True
        await self._whisper_rank_requirement(user_id, minimum_rank)
        return False

    async def _whisper_rank_requirement(
        self, user_id: str, minimum_rank: int
    ) -> None:
        required_role = next(
            (role for role, rank in ROLE_RANK.items() if rank == minimum_rank),
            "guest",
        )
        role_name = ROLE_PERMISSION_NAME[required_role]
        await self.highrise.send_whisper(
            user_id,
            f"✖️ You don't have a high enough role. You need {role_name} or higher "
            "to complete this action 🔏",
        )

    async def _refresh_room(self) -> None:
        response = await self.highrise.get_room_users()
        if not hasattr(response, "content"):
            return
        current_ids: set[str] = set()
        for room_user, position in response.content:
            current_ids.add(room_user.id)
            self.users[room_user.id] = room_user
            if isinstance(position, Position):
                self.user_positions[room_user.id] = position
        for user_id in self.users.keys() - current_ids:
            self.users.pop(user_id, None)
            self.user_positions.pop(user_id, None)

    async def _find_user(self, name: str, refresh: bool = True) -> User | None:
        if refresh:
            await self._refresh_room()
        requested = name.lstrip("@").casefold()
        return next(
            (
                room_user
                for room_user in self.users.values()
                if room_user.username.casefold() == requested
                or room_user.id.casefold() == requested
            ),
            None,
        )

    def _log(
        self,
        command: str,
        duration_seconds: int,
        reason: str,
        target_username: str,
        target_user_id: str | None = None,
    ) -> None:
        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "command": command,
            "duration_seconds": duration_seconds,
            "reason": reason,
            "target_username": target_username,
            "target_user_id": target_user_id,
        }
        self.logs.append(entry)
        del self.logs[:-100]
        self.store.append_command_log(entry)
        if target_user_id:
            self.store.record_action(
                target_user_id, command, duration_seconds, reason, timestamp
            )
            if command in {"!warn", "!kick", "!ban", "!mute"}:
                counts = self._action_counts(target_user_id)
                if command == "!warn":
                    details = f"warned {len(self.store.warnings_for(target_user_id))}/3"
                elif command == "!ban":
                    details = f"ban {duration_seconds}s, {counts['!ban']}"
                elif command == "!mute":
                    details = f"mute {duration_seconds}s, {counts['!mute']}"
                else:
                    details = f"kicked {counts['!kick']}"
                print(
                    f"\u26a0\ufe0f @{target_username}|{target_user_id} "
                    f"{target_username}({details})",
                    flush=True,
                )

    def _action_counts(self, user_id: str) -> dict[str, int]:
        stats = self.store.user_stats_for(user_id)
        return {
            "!warn": stats["warns"],
            "!ban": stats["bans"],
            "!mute": stats["mutes"],
            "!kick": stats["kicks"],
        }

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        await self._refresh_room()
        for room_user in self.users.values():
            self.store.register_user(room_user.id, room_user.username)
            if room_user.id == self.owner_id:
                self.store.set_role(room_user.id, room_user.username, "owner")
            self.store.start_session(room_user.id, room_user.username)
        room_id = os.getenv("BOT_ROOM_ID", session_metadata.room_info.room_name)
        print(f"\u2705 Bot connected to room {room_id}", flush=True)

    async def on_user_join(self, user: User, position: Position) -> None:
        self.users[user.id] = user
        if isinstance(position, Position):
            self.user_positions[user.id] = position
        returning, role = self.store.register_user(user.id, user.username)
        if user.id == self.owner_id:
            role = "owner"
            self.store.set_role(user.id, user.username, role)
        self.store.start_session(user.id, user.username)
        nickname_label = (
            f" ({nickname})"
            if (nickname := self.store.nickname_for(user.id))
            else ""
        )
        print(f"\U0001f44b {user.username} joined", flush=True)
        if returning:
            label = ROLE_LABEL.get(normalize_role(role) or "guest", ROLE_LABEL["guest"])
            await self.highrise.chat(
                f"Welcome Back {label} @{user.username}{nickname_label}\U0001f44b"
            )
        else:
            await self.highrise.chat(
                f"Welcome To the Room\U0001f44b @{user.username}{nickname_label} "
                "Enjoy Your stay\U0001f917"
            )

    async def on_user_leave(self, user: User) -> None:
        self._cancel_emote_loop(user.id)
        role = self._role_for(user.id)
        label = ROLE_LABEL.get(role, ROLE_LABEL["guest"])
        nickname_label = (
            f" ({nickname})"
            if (nickname := self.store.nickname_for(user.id))
            else ""
        )
        self.store.finish_session(user.id)
        print(f"\U0001f44b {user.username} left", flush=True)
        self.users.pop(user.id, None)
        self.user_positions.pop(user.id, None)
        await self.highrise.chat(
            f"Goodbye {label} @{user.username}{nickname_label} thank you for joining, "
            "Hope to see you soon\U0001f44b"
        )

    async def on_user_move(self, user: User, pos: Position) -> None:
        self.users[user.id] = user
        if isinstance(pos, Position):
            self.user_positions[user.id] = pos

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        if receiver.id != self.highrise.my_id:
            return
        if isinstance(tip, CurrencyItem) and tip.type != "gold":
            return
        amount = getattr(tip, "amount", 0)
        await self.highrise.chat(f"@{sender.username} has sent {amount}g \U0001f4b0")
        await self._refresh_room()
        message = f"@{sender.username} sent {amount}g to the bot \U0001f4b0"
        for user_id, staff_user in list(self.users.items()):
            if self._rank_for(user_id) >= ROLE_RANK["mod2"]:
                try:
                    await self.highrise.send_whisper(staff_user.id, message)
                except Exception as error:
                    print(f"\u274c Error: {error}", flush=True)
                    logger.exception("Could not whisper gold alert to %s", staff_user.id)

    async def on_chat(self, user: User, message: str) -> None:
        message = message.strip()
        command_parts = message.split(maxsplit=1)
        if command_parts and command_parts[0].casefold() == "/equip":
            message = "!" + message[1:]
        if message.casefold() in {"stop", "!stop"}:
            task = self.active_emote_loops.get(user.id)
            if task is None or task.done():
                await self.highrise.chat("You don't have an active emote.")
            else:
                target_user_ids = self.active_emote_targets.get(user.id, [user.id])
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                await asyncio.gather(
                    *(
                        self.highrise.send_emote("idle", target_user_id=target_user_id)
                        for target_user_id in target_user_ids
                    )
                )
            return
        if not message.startswith("!"):
            if message.startswith("(") and message.endswith(")"):
                location_name = message[1:-1].strip()
                if self.store.get_teleport(location_name) is not None:
                    try:
                        await self._teleport_user_to_location(user, location_name)
                    except Exception as error:
                        print(f"\u274c Error: {error}", flush=True)
                        logger.exception(
                            "Teleport %s failed for user %s", location_name, user.id
                        )
                        await self.highrise.chat(
                            "That teleport could not be completed."
                        )
                    return
            await self._handle_emote_message(user, message)
            return
        try:
            parts = shlex.split(message)
        except ValueError:
            await self.highrise.chat("Invalid command syntax.")
            return
        if not parts:
            return
        try:
            await self._handle_command(user, parts[0].casefold(), parts[1:])
        except Exception as error:
            print(f"\u274c Error: {error}", flush=True)
            logger.exception("Command %s failed for user %s", parts[0], user.id)
            await self.highrise.chat("That command could not be completed.")

    async def _handle_command(self, user: User, command: str, args: list[str]) -> None:
        minimum_rank = COMMAND_MIN_RANK.get(command)
        if minimum_rank is not None and not await self._require_rank(user.id, minimum_rank):
            return

        if command == "!equip":
            if len(args) > 1 or (args and not args[0].isdigit()):
                await self.highrise.chat("Usage: /equip <1-10>")
                return
            preset_number = int(args[0]) if args else 1
            if not 1 <= preset_number <= 10:
                await self.highrise.chat("Usage: /equip <1-10>")
                return
            outfit = self._outfit_for_preset(preset_number)
            if outfit is None:
                await self.highrise.chat(
                    f"Outfit {preset_number} is not configured yet."
                )
                return
            await self._apply_outfit(user, outfit)
            return

        if command == "!outfit":
            if len(args) != 1 or args[0] != "1":
                await self.highrise.chat("Usage: !outfit 1")
                return
            outfit = self._outfit_for_preset(2)
            if outfit is not None:
                await self._apply_outfit(user, outfit)
            return

        if command == "!emote":
            await self._handle_emote_command(user, args)
            return

        if command == "!tp":
            await self._handle_tp_command(user, args)
            return

        if command == "!settp":
            if not await self._require_rank(user.id, ROLE_RANK["mod2"]):
                return
            if not args:
                await self.highrise.chat("Usage: !settp <location_name> [minimum_role]")
                return
            requested_role = normalize_role(args[-1]) if len(args) > 1 else None
            role = requested_role or "guest"
            location_name = (
                " ".join(args[:-1]) if requested_role is not None else " ".join(args)
            )
            await self._save_teleport_at_user_position(
                user, location_name.strip(), role
            )
            return

        if command == "!setowner":
            if not self.store.set_owner_once(user.id, user.username):
                self.owner_id = self.owner_id or self.store.get_owner_id() or ""
                await self.highrise.chat(
                    "The OWNER has already been set. This can only be changed from code."
                )
                return
            self.owner_id = user.id
            await self.highrise.chat(
                f"{ROLE_LABEL['owner']} has been set to @{user.username}"
            )
            self._log("!setowner", 0, "", user.username, user.id)
            return

        if command == "!rf":
            await self.highrise.chat("\U0001f504 Bot refreshing...")
            print("\U0001f504 Bot refreshing...", flush=True)
            asyncio.create_task(self._restart_process())
            return

        if command == "!info":
            if len(args) > 1:
                await self.highrise.chat("Usage: !info [@username]")
                return
            target = user
            if args:
                target = await self._find_user(args[0])
                if target is None:
                    await self.highrise.chat("User not found in this room.")
                    return
            info = await self._build_info_message(target)
            await self.highrise.chat(info)
            return

        if command == "!roles":
            user_ids = list(self.store.data["roles"])
            if self.owner_id and self.owner_id not in user_ids:
                user_ids.append(self.owner_id)
            members_by_role = {role: [] for role in ROLE_RANK}
            for user_id in user_ids:
                role = self._role_for(user_id)
                username = self.store.data["usernames"].get(user_id, user_id)
                members_by_role[role].append(f"@{username}")
            lines = [
                f"{ROLE_LABEL[role]}: {', '.join(members_by_role[role]) or 'None'}"
                for role in ROLE_RANK
            ]
            await self.highrise.chat("ROOM ROLES\n" + "\n".join(lines))
            return

        if command == "!nickname":
            nickname = " ".join(args).strip()
            if not nickname:
                await self.highrise.chat('Usage: !nickname "nickname"')
                return
            self.store.set_nickname(user.id, nickname)
            await self.highrise.chat(
                f'@{user.username}, your nickname is now "{nickname}".'
            )
            return

        if command == "!note":
            if len(args) < 2:
                await self.highrise.chat("Usage: !note @username <note>")
                return
            target = await self._find_user(args[0])
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            note = " ".join(args[1:]).strip()
            self.store.set_note(target.id, note)
            await self.highrise.chat(f"Saved note for @{target.username}.")
            return

        if command == "!warn":
            if len(args) != 2 or not args[1].isdigit() or int(args[1]) not in (1, 2, 3):
                await self.highrise.chat("Invalid syntax. Usage: !warn @username <1|2|3>")
                return
            target = await self._find_user(args[0])
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            warning_number = int(args[1])
            result = self.store.add_warning(target.id, warning_number)
            if result == "maximum":
                await self.highrise.chat("User already has maximum warnings.")
                return
            if result == "duplicate":
                await self.highrise.chat(f"@{target.username} already has warning {warning_number}.")
                return
            await self.highrise.chat(f"@{target.username} has been warned ({warning_number}/3)")
            self._log(
                "!warn", 0, f"warning {warning_number}/3", target.username, target.id
            )
            return

        if command == "!unwarn":
            if len(args) != 1:
                await self.highrise.chat("Usage: !unwarn @username")
                return
            target = await self._find_user(args[0])
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            removed = self.store.clear_warnings(target.id)
            if not removed:
                await self.highrise.chat(f"@{target.username} has no active warnings.")
                return
            await self.highrise.chat(
                f"Removed {removed} warning(s) from @{target.username}."
            )
            self._log(
                "!unwarn", 0, f"removed {removed} warning(s)", target.username, target.id
            )
            return

        if command in {"!kick", "!ban", "!mute"}:
            await self._moderate_command(command, args)
            return

        if command == "!log":
            await self._handle_log_command(user, args)
            return

        if command == "!give":
            if len(args) < 2:
                await self.highrise.chat("Invalid syntax. Usage: !give @username <role>")
                return
            target = await self._find_user(args[0])
            role = normalize_role(" ".join(args[1:]))
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            if role is None or not can_assign_role(self._role_for(user.id), role):
                await self.highrise.chat("Invalid role. Use one of the 10 defined roles.")
                return
            if role == "owner":
                await self.highrise.chat("The OWNER role can only be set via !setowner.")
                return
            if target.id == self.owner_id:
                await self.highrise.chat("The configured OWNER role cannot be changed.")
                return
            self.store.set_role(target.id, target.username, role)
            label = ROLE_LABEL[role]
            await self.highrise.chat(f"@{target.username} has been given the role {label}")
            self._log("!give", 0, role, target.username, target.id)
            return

        if command == "!remove":
            if args and args[0].casefold() == "tele":
                await self._remove_teleport(args[1:], user.username, user.id)
                return
            if (
                len(args) == 2
                and args[0].casefold() == "all"
                and args[1].casefold() == "tele"
            ):
                await self._remove_all_teleports(user.username, user.id)
                return
            if len(args) < 2:
                await self.highrise.chat(
                    "Usage: !remove @username <role>, !remove tele <location>, "
                    "or !remove all tele"
                )
                return
            target = await self._find_user(args[0])
            role = normalize_role(" ".join(args[1:]))
            if role == "owner":
                await self.highrise.chat("Cannot remove the OWNER role.")
                return
            if role is None:
                await self.highrise.chat("Invalid role. Use one of the 10 defined roles.")
                return
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            if self._role_for(target.id) != role:
                await self.highrise.chat(
                    f"@{target.username} does not have the role {ROLE_LABEL[role]}."
                )
                return
            self.store.set_role(target.id, target.username, "guest")
            await self.highrise.chat(
                f"@{target.username} has been removed from the role {ROLE_LABEL[role]}"
            )
            self._log("!remove", 0, role, target.username, target.id)
            return

        if command == "!cords":
            position = self.user_positions.get(user.id)
            if position is None:
                await self.highrise.chat("Could not find your position. Move slightly and try again.")
                return
            await self.highrise.chat(
                f"@{user.username} is at X: {position.x}, Y: {position.y}, Z: {position.z}"
            )
            return

        if command in {"!bring", "!summon"}:
            if not 1 <= len(args) <= 5:
                await self.highrise.chat("Invalid syntax. Usage: !bring @username1 ... (up to 5 users)")
                return
            sender_position = self.user_positions.get(user.id)
            if sender_position is None:
                await self.highrise.chat("Could not find your position. Move slightly and try again.")
                return
            await self._refresh_room()
            brought: list[str] = []
            for name in args:
                target = await self._find_user(name, refresh=False)
                if target is None:
                    await self.highrise.chat(f"@{name.lstrip('@')} not found in room.")
                    continue
                destination = Position(
                    sender_position.x,
                    sender_position.y,
                    sender_position.z,
                    sender_position.facing,
                )
                try:
                    await self.highrise.teleport(target.id, destination)
                    brought.append(f"@{target.username}")
                except Exception:
                    logger.exception("Could not bring user %s", target.id)
                    await self.highrise.chat(f"Could not teleport @{target.username}.")
            await self.highrise.chat(
                f"Brought {', '.join(brought) if brought else '0 users'} to @{user.username}"
            )
            self._log(
                "!bring", 0, f"brought {len(brought)} users", user.username, user.id
            )
            return

        if command == "!tele":
            if any("," in argument for argument in args):
                coordinate_text = " ".join(args)
                coordinate_parts = [
                    coordinate.strip() for coordinate in coordinate_text.split(",")
                ]
                if len(coordinate_parts) != 3:
                    await self.highrise.chat("Usage: !tele <x>,<y>,<z>")
                    return
                try:
                    x, y, z = (float(coordinate) for coordinate in coordinate_parts)
                except ValueError:
                    await self.highrise.chat(
                        "Coordinates must be numbers. Usage: !tele <x>,<y>,<z>"
                    )
                    return
                if not all(math.isfinite(value) for value in (x, y, z)):
                    await self.highrise.chat("Coordinates must be finite numbers.")
                    return
                await self.highrise.teleport(
                    user.id, Position(x, y, z, "FrontRight")
                )
                await self.highrise.chat(
                    f"Teleported @{user.username} to X: {x:g}, Y: {y:g}, Z: {z:g}"
                )
                self._log(
                    "!tele",
                    0,
                    f"coordinates ({x:g}, {y:g}, {z:g})",
                    user.username,
                    user.id,
                )
                return
            if len(args) == 1 and args[0].casefold() == "list":
                teleports = self.store.data["teleports"]
                if not teleports:
                    await self.highrise.chat("No teleport points have been created.")
                    return
                entries = []
                for name, location in sorted(
                    teleports.items(), key=lambda item: item[0].casefold()
                ):
                    role = normalize_role(
                        str(location.get("min_role", "guest"))
                    ) or "guest"
                    entries.append(f"{name} (min role: {role.title()})")
                await self.highrise.chat("Teleport points: " + ", ".join(entries))
                return
            if len(args) < 2:
                await self.highrise.chat(
                    "Usage: !tele <x>,<y>,<z>, !tele @username <location_name>, "
                    "or !tele list"
                )
                return
            target = await self._find_user(args[0])
            location_name = " ".join(args[1:])
            location = self.store.get_teleport(location_name)
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            if location is None:
                await self.highrise.chat(f'Teleport location "{location_name}" not found.')
                return
            minimum_rank = self._teleport_min_rank(location)
            if self._rank_for(target.id) < minimum_rank:
                await self._whisper_rank_requirement(target.id, minimum_rank)
                return
            await self.highrise.teleport(
                target.id,
                Position(location["x"], location["y"], location["z"], location["facing"]),
            )
            await self.highrise.chat(f"Teleported @{target.username} to {location_name}")
            self._log("!tele", 0, location_name, target.username, target.id)
            return

        if command == "!goto":
            if not args:
                await self.highrise.chat("Invalid syntax. Usage: !goto <location_name>")
                return
            location_name = " ".join(args)
            location = self.store.get_teleport(location_name)
            if location is None:
                await self.highrise.chat(f'Teleport location "{location_name}" not found.')
                return
            minimum_rank = self._teleport_min_rank(location)
            if not await self._require_rank(user.id, minimum_rank):
                return
            await self.highrise.teleport(
                user.id,
                Position(location["x"], location["y"], location["z"], location["facing"]),
            )
            await self.highrise.chat(f"Teleported @{user.username} to {location_name}")
            self._log("!goto", 0, location_name, user.username, user.id)
            return

        if command == "!create":
            if len(args) < 3 or args[0].casefold() != "tele":
                await self.highrise.chat("Invalid syntax. Usage: !create tele <location_name> <role>")
                return
            role = normalize_role(args[-1])
            location_name = " ".join(args[1:-1]).strip()
            if not location_name or role is None:
                await self.highrise.chat("Invalid location name or role.")
                return
            if self.store.teleport_exists(location_name):
                await self.highrise.chat(
                    f'Teleport location "{location_name}" already exists. '
                    f"Use !remove tele {location_name} first."
                )
                return
            await self._save_teleport_at_user_position(user, location_name, role)
            return

        if command == "!say":
            if not args:
                await self.highrise.chat("Invalid syntax. Usage: !say <message>")
                return
            text = " ".join(args)
            await self.highrise.chat(text)
            self._log("!say", 0, text, user.username, user.id)
            return

        if command == "!loop":
            if len(args) < 2 or not args[-1].isdigit() or int(args[-1]) < 1:
                await self.highrise.chat("Invalid syntax. Usage: !loop <message> <seconds>")
                return
            seconds, text = int(args[-1]), " ".join(args[:-1])
            if not text:
                await self.highrise.chat("Invalid syntax. Usage: !loop <message> <seconds>")
                return
            self._cancel_task(self.loop_task)
            self.loop_task = asyncio.create_task(self._repeat_message(text, seconds))
            await self.highrise.chat(f'Loop started: "{text}" every {seconds}s')
            self._log("!loop", seconds, text, user.username, user.id)
            return

        if command == "!stoploop":
            if self.loop_task is None or self.loop_task.done():
                await self.highrise.chat("No active loop to stop.")
                return
            self._cancel_task(self.loop_task)
            self.loop_task = None
            await self.highrise.chat("Loop stopped.")
            return

        if command == "!tip":
            if len(args) != 2 or not args[1].isdigit() or int(args[1]) < 1:
                await self.highrise.chat("Invalid syntax. Usage: !tip @username <amount>")
                return
            target = await self._find_user(args[0])
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            amount = int(args[1])
            try:
                denominations = split_gold_amount(amount)
            except ValueError as error:
                await self.highrise.chat(str(error))
                return
            if await self._wallet_gold() < amount:
                await self.highrise.chat("Bot wallet does not have enough gold for this tip.")
                return
            result = await self._tip_gold(target.id, denominations)
            if result != "success":
                await self.highrise.chat("Bot wallet does not have enough gold for this tip.")
                return
            await self.highrise.chat(f"🪙tipped @{target.username} ({amount}g)🪙")
            self._log("!tip", 0, f"{amount}g", target.username, target.id)
            return

        if command == "!autotip":
            if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
                await self.highrise.chat("Invalid syntax. Usage: !autotip <amount> <seconds>")
                return
            amount, seconds = int(args[0]), int(args[1])
            if amount < 1 or seconds < 1:
                await self.highrise.chat("Amount and seconds must be greater than zero.")
                return
            try:
                split_gold_amount(amount)
            except ValueError as error:
                await self.highrise.chat(str(error))
                return
            self._cancel_task(self.autotip_task)
            self.autotip_task = asyncio.create_task(
                self._autotip(amount, seconds, user.id)
            )
            await self.highrise.send_whisper(
                user.id,
                f"Auto-tip started: {amount}g to everyone every {seconds}s"
            )
            self._log("!autotip", seconds, f"{amount}g to all", "ALL")
            return

        if command == "!stopautotip":
            if self.autotip_task is None or self.autotip_task.done():
                await self.highrise.send_whisper(user.id, "Auto-tip stopped.")
                return
            self._cancel_task(self.autotip_task)
            self.autotip_task = None
            await self.highrise.send_whisper(user.id, "Auto-tip stopped.")
            return

        if command == "!help":
            await self._handle_help(args)
            return

        if command in INTERACTION_ACTIONS:
            if not await self._require_rank(user.id, REQUIRES_VIP):
                return
            await self._handle_interaction(user, command, args)
            return
        emote_command = command.lstrip("!")
        if resolve_emote(emote_command) is not None:
            if args and args[0].startswith("@"):
                await self._handle_targeted_emote(user, emote_command, args[0])
                return
            await self._handle_emote_message(user, " ".join([emote_command, *args]))
            return

    async def _apply_outfit(self, user: User, outfit: list[Item]) -> None:
        result = await self.highrise.set_outfit(outfit=outfit)
        if isinstance(result, Error):
            logger.error(
                "Highrise rejected the bot outfit requested by user %s: %r",
                user.id,
                result,
            )
            await self.highrise.chat("Highrise rejected the bot's outfit change.")
            return
        if result is not None:
            logger.error(
                "Unexpected response applying bot outfit requested by user %s: %r",
                user.id,
                result,
            )
            await self.highrise.chat("The bot's outfit could not be changed.")
            return
        await self.highrise.chat("Highrise accepted the outfit change request.")

    @staticmethod
    def _outfit_for_preset(preset_number: int) -> list[Item] | None:
        first_outfit = (
            ("body-flesh", 27),
            ("hair_front-n_basic2018curlypulledback", -1),
            ("eye-n_basic2018malesquaresleepy", 7),
            ("eyebrow-n_basic2018newbrows07", 0),
            ("nose-n_basic2018newnose05", 0),
            ("mouth-basic2018chippermouth", -1),
            ("shirt-n_starteritems2019tankwhite", -1),
            ("shorts-f_pantyhoseshortsnavy", -1),
            ("shoes-n_whitedans", -1),
            ("glasses-n_starteritems201roundframesbrown", -1),
        )
        presets: dict[int, tuple[tuple[str, int], ...]] = {
            1: first_outfit,
            2: (
                ("hair_front-n_malenew04", -1),
                ("gloves-n_room32019basketball", -1),
                ("bag-n_room32019sidebagblack", -1),
                ("necklace-n_room12019necklace", -1),
                ("watch-n_room32019blackwatch", -1),
                ("pants-n_room32019longshortswithsocksblack", -1),
                ("shirt-n_starteritems2019maletshirtblack", -1),
                ("shoes-n_room32019socksneakersblack", -1),
            ),
        }
        items = presets.get(preset_number)
        if items is None:
            return None
        return [
            Item(
                type="clothing",
                amount=1,
                id=item_id,
                account_bound=False,
                active_palette=palette,
            )
            for item_id, palette in items
        ]

    async def _handle_help(self, args: list[str]) -> None:
        help_text = {
            "!nickname": "Set your saved nickname. Usage: !nickname <nickname>",
            "!roles": "List every role and the players assigned to it.",
            "!info": "Show your profile or a player's public profile and room stats. Usage: !info [@username]",
            "!note": "Save a note for a player. SeniorAdmin+. Usage: !note @username <note>",
            "!warn": "Add warning 1, 2, or 3 to a player. SeniorAdmin+. Usage: !warn @username <1|2|3>",
            "!unwarn": "Clear a player's warnings. SeniorAdmin+. Usage: !unwarn @username",
            "!kick": "Kick a player. Mod2+. Usage: !kick @username [reason]",
            "!ban": "Ban a player for seconds. Mod2+. Usage: !ban @username <seconds> [reason]",
            "!mute": "Mute a player for seconds. Mod2+. Usage: !mute @username <seconds> [reason]",
            "!log": "Whisper recent logs or a player's moderation history. Mod2+. Usage: !log [public|private|@username]",
            "!give": "Assign a role to a player. Mod2+. Usage: !give @username <role>",
            "!remove": "Remove a player's role, or delete teleport points. Mod2+. Usage: !remove @username <role> | !remove tele (<name>) | !remove all tele",
            "!cords": "Show your current room coordinates. SeniorAdmin+.",
            "!bring": "Bring up to five players to your position. SeniorAdmin+. Usage: !bring @user1 [@user2 ...]",
            "!summon": "Alias for !bring. SeniorAdmin+. Usage: !summon @user1 [@user2 ...]",
            "!tele": "Teleport yourself to coordinates with !tele <x>,<y>,<z>, show saved points with !tele list, or teleport a player (VIP+). Usage: !tele <x>,<y>,<z> | !tele list | !tele @username <location>",
            "!tp": "Teleport yourself with !tp <location>; list points with !tp list; Admin+ can use !tp all <location>, and SeniorAdmin+ can use !tp @username <location>.",
            "!goto": "Teleport yourself to a saved point. You must meet that point's minimum role. Usage: !goto <location>",
            "!create tele": "Save your current position as a named teleport point. Mod2+. Usage: !create tele <name> <minimum_role>",
            "!settp": "Alias to save your position as a teleport point; minimum role defaults to Guest. Mod2+. Usage: !settp <name> [minimum_role]",
            "!tip": "Tip a player using the bot's wallet. SeniorAdmin+. Usage: !tip @username <amount>",
            "!autotip": "Repeatedly tip room members. SeniorAdmin+. Usage: !autotip <amount> <seconds>",
            "!stopautotip": "Stop the active automatic tipping task. SeniorAdmin+.",
            "!say": "Post a message as the bot. SeniorAdmin+. Usage: !say <message>",
            "!loop": "Repeat a message at an interval. SeniorAdmin+. Usage: !loop <message> <seconds>",
            "!stoploop": "Stop the active repeating message. SeniorAdmin+.",
            "!setowner": "Claim the Owner role once if no owner has been configured. Usage: !setowner",
            "!rf": "Restart the bot. Coowner+.",
            "!punch": "Play the punch interaction on a player. VIP+. Usage: !punch @username",
            "!slap": "Play the slap interaction on a player. VIP+. Usage: !slap @username",
            "!kiss": "Play the kiss interaction on a player. VIP+. Usage: !kiss @username",
            "!hug": "Play the hug interaction on a player. VIP+. Usage: !hug @username",
            "!scare": "Play the scare interaction on a player. VIP+. Usage: !scare @username",
            "!faint": "Play the faint interaction on a player. VIP+. Usage: !faint @username",
            "!rofl": "Play the ROFL interaction on a player. VIP+. Usage: !rofl @username",
            "!dizzy": "Play the dizzy interaction on a player. VIP+. Usage: !dizzy @username",
            "!emote": "Play or loop an emote; use !emote list for the catalog. Usage: !emote <name> [@username] | !emote all <name> (Admin+)",
            "!emote list": "Display the full emote catalog with free/paid labels. Usage: !emote list",
            "stop": "Stop your active emote loop. Usage: stop",
            "!help": "Show command help. Usage: !help [command]",
            "!equip": "Change the bot's outfit. Usage: /equip <1-10>. Outfits 1 and 2 are configured.",
            "!outfit": "Legacy alias for outfit 2. Usage: !outfit 1",
        }
        if not args:
            await self.highrise.chat(
                "Help: !help <command> for details. Commands: "
                + ", ".join(sorted(help_text))
            )
            return

        requested = " ".join(args).casefold().strip()
        if requested.startswith("/"):
            requested = "!" + requested[1:]
        elif not requested.startswith("!"):
            requested = "!" + requested
        description = help_text.get(requested)
        if description is None:
            await self.highrise.chat(
                f"No help is available for {requested}. Try !help for commands."
            )
            return
        await self.highrise.chat(description)

    async def _handle_tp_command(self, user: User, args: list[str]) -> None:
        if not args:
            await self.highrise.chat(
                "Usage: !tp <location>, !tp @username <location>, "
                "!tp all <location>, or !tp list"
            )
            return

        if args[0].casefold() == "list":
            teleports = self.store.data["teleports"]
            if not teleports:
                await self.highrise.chat("No teleport points have been created.")
                return
            entries = []
            for name, location in sorted(
                teleports.items(), key=lambda item: item[0].casefold()
            ):
                role = normalize_role(str(location.get("min_role", "guest"))) or "guest"
                entries.append(f"{name} (min role: {role.title()})")
            await self.highrise.chat("Teleport points: " + ", ".join(entries))
            return

        if args[0].casefold() == "all":
            if not await self._require_rank(user.id, REQUIRES_ADMIN):
                return
            location_name = " ".join(args[1:]).strip().strip("()").strip()
            if not location_name:
                await self.highrise.chat("Usage: !tp all <location>")
                return
            location = self.store.get_teleport(location_name)
            if location is None:
                await self.highrise.chat(
                    f'Teleport location "{location_name}" not found.'
                )
                return

            await self._refresh_room()
            min_rank = self._teleport_min_rank(location)
            succeeded = 0
            skipped = 0
            failed = 0
            destination = Position(
                location["x"], location["y"], location["z"], location["facing"]
            )
            for target in self.users.values():
                if self._rank_for(target.id) < min_rank:
                    skipped += 1
                    continue
                try:
                    await self.highrise.teleport(target.id, destination)
                    succeeded += 1
                except Exception:
                    failed += 1
                    logger.exception(
                        "Could not teleport user %s to %s",
                        target.id,
                        location_name,
                    )
            await self.highrise.chat(
                f"Teleported {succeeded} user(s) to {location_name}; "
                f"skipped {skipped} below the minimum role; failed {failed}."
            )
            self._log(
                "!tp all",
                0,
                f"{location_name}: {succeeded} succeeded, {skipped} skipped, "
                f"{failed} failed",
                user.username,
                user.id,
            )
            return

        if args[0].startswith("@"):
            if not await self._require_rank(
                user.id, ROLE_RANK["senioradmin"]
            ):
                return
            if len(args) < 2:
                await self.highrise.chat("Usage: !tp @username <location>")
                return
            target = await self._find_user(args[0])
            if target is None:
                await self.highrise.chat("User not found in this room.")
                return
            location_name = " ".join(args[1:]).strip().strip("()").strip()
            location = self.store.get_teleport(location_name)
            if location is None:
                await self.highrise.chat(
                    f'Teleport location "{location_name}" not found.'
                )
                return
            minimum_rank = self._teleport_min_rank(location)
            if self._rank_for(target.id) < minimum_rank:
                await self._whisper_rank_requirement(target.id, minimum_rank)
                return
            await self.highrise.teleport(
                target.id,
                Position(
                    location["x"], location["y"], location["z"], location["facing"]
                ),
            )
            await self.highrise.chat(
                f"Teleported @{target.username} to {location_name}"
            )
            self._log("!tp", 0, location_name, target.username, target.id)
            return

        await self._teleport_user_to_location(user, " ".join(args))

    async def _teleport_user_to_location(
        self, user: User, requested_name: str
    ) -> None:
        location_name = requested_name.strip().strip("()").strip()
        if not location_name:
            await self.highrise.chat("Usage: !tp <location>")
            return
        location = self.store.get_teleport(location_name)
        if location is None:
            await self.highrise.chat(
                f'Teleport location "{location_name}" not found.'
            )
            return
        minimum_rank = self._teleport_min_rank(location)
        if not await self._require_rank(user.id, minimum_rank):
            return
        await self.highrise.teleport(
            user.id,
            Position(location["x"], location["y"], location["z"], location["facing"]),
        )
        await self.highrise.chat(f"Teleported @{user.username} to {location_name}")
        self._log("!tp", 0, location_name, user.username, user.id)

    async def _save_teleport_at_user_position(
        self, user: User, location_name: str, min_role: str
    ) -> None:
        if not location_name:
            await self.highrise.chat("Teleport location name cannot be empty.")
            return
        if self.store.teleport_exists(location_name):
            await self.highrise.chat(
                f'Teleport location "{location_name}" already exists. '
                f"Use !remove tele ({location_name}) first."
            )
            return
        await self._refresh_room()
        position = self.user_positions.get(user.id)
        if position is None:
            await self.highrise.chat(
                "Could not find your position. Move slightly and try again."
            )
            return
        self.store.save_teleport(
            location_name,
            position.x,
            position.y,
            position.z,
            position.facing,
            min_role,
        )
        await self.highrise.chat(
            f'Teleport "{location_name}" created at your location. '
            f"Minimum role: {ROLE_LABEL[min_role]}"
        )
        self._log(
            "!settp",
            0,
            f"{location_name} ({min_role})",
            user.username,
            user.id,
        )

    async def _handle_emote_message(self, user: User, message: str) -> None:
        if not message:
            return
        if message.startswith("(") and message.endswith(")"):
            emote_name = message[1:-1].strip()
            emote_id = resolve_emote(emote_name)
            if emote_id is None:
                await self.highrise.chat(f"Unknown emote: {emote_name}")
                return
            self._start_emote_loop(
                user.id,
                emote_id,
                [user.id],
                resolve_emote_duration(emote_name),
                user.id,
            )
            return

        parts = message.split()
        target = None
        emote_parts = parts
        if len(parts) > 1 and parts[-1].startswith("@"):
            target = await self._find_user(parts[-1])
            if target is None:
                await self.highrise.chat(f"{parts[-1]} is not in the room.")
                return
            emote_parts = parts[:-1]

        emote_name = " ".join(emote_parts)
        emote_id = resolve_emote(emote_name)
        if emote_id is None:
            return

        target_user_ids = [user.id]
        if (
            target is not None
            and target.id != user.id
            and is_emote_free(emote_id) is not False
        ):
            target_user_ids.append(target.id)
        self._start_emote_loop(
            user.id,
            emote_id,
            target_user_ids,
            resolve_emote_duration(emote_name),
            user.id,
        )

    async def _handle_emote_command(self, user: User, args: list[str]) -> None:
        if not args:
            await self.highrise.chat(
                "Usage: !emote <name> [@username], !emote all <name>, "
                "or !emote list"
            )
            return

        if len(args) == 1 and args[0].casefold() == "list":
            await self._send_emote_catalog()
            return

        if args[0].casefold() == "all":
            if not await self._require_rank(user.id, REQUIRES_ADMIN):
                return
            emote_name = " ".join(args[1:]).strip().strip("()").strip()
            if not emote_name:
                await self.highrise.chat("Usage: !emote all <name>")
                return
            emote_id = resolve_emote(emote_name)
            if emote_id is None:
                await self.highrise.chat(f"Unknown emote: {emote_name}")
                return
            if is_emote_free(emote_id) is False:
                self._start_emote_loop(
                    user.id,
                    emote_id,
                    [user.id],
                    resolve_emote_duration(emote_name),
                    user.id,
                )
                return
            if is_emote_free(emote_id) is not True:
                await self.highrise.chat(
                    "That emote's ownership status is unknown, so I can't use it "
                    "room-wide."
                )
                return
            await self._refresh_room()
            duration = resolve_emote_duration(emote_name)
            for target in self.users.values():
                self._start_emote_loop(
                    target.id, emote_id, [target.id], duration, user.id
                )
            return

        target_name = None
        emote_parts = args
        if args[0].startswith("@") and len(args) > 1:
            target_name = args[0]
            emote_parts = args[1:]
        elif len(args) > 1 and args[-1].startswith("@"):
            target_name = args[-1]
            emote_parts = args[:-1]

        emote_name = " ".join(emote_parts).strip().strip("()").strip()
        emote_id = resolve_emote(emote_name)
        if emote_id is None:
            await self.highrise.chat(f"Unknown emote: {emote_name}")
            return

        target = user
        if target_name is not None:
            target = await self._find_user(target_name)
            if target is None:
                await self.highrise.chat(f"{target_name} is not in the room.")
                return
        if target.id != user.id and is_emote_free(emote_id) is False:
            target = user
        self._start_emote_loop(
            target.id,
            emote_id,
            [target.id],
            resolve_emote_duration(emote_name),
            user.id,
        )

    async def _send_emote_catalog(self) -> None:
        max_message_length = 220
        names = sorted(EMOTE_DATA.items(), key=lambda entry: entry[0].casefold())
        entries = [
            f"{name} [{'free' if data[2] else 'paid'}]"
            for name, data in names
        ]

        content_pages: list[list[str]] = []
        current_page: list[str] = []
        current_length = 0
        for entry in entries:
            separator_length = 3 if current_page else 0
            if current_page and current_length + separator_length + len(entry) > 185:
                content_pages.append(current_page)
                current_page = []
                current_length = 0
                separator_length = 0
            current_page.append(entry)
            current_length += separator_length + len(entry)
        if current_page:
            content_pages.append(current_page)

        total_pages = len(content_pages)
        for page_number, page in enumerate(content_pages, start=1):
            message = (
                f"EMOTE CATALOG | {page_number}/{total_pages}\n"
                + " • ".join(page)
            )
            if len(message) > max_message_length:
                raise ValueError("Emote catalog page exceeds the chat message limit.")
            await self.highrise.chat(message)

    async def _handle_targeted_emote(
        self, user: User, emote_name: str, target_name: str
    ) -> None:
        target = await self._find_user(target_name)
        if target is None:
            await self.highrise.chat(f"{target_name} is not in the room.")
            return
        emote_id = resolve_emote(emote_name)
        if emote_id is None:
            await self.highrise.chat(f"Unknown emote: {emote_name}")
            return
        if target.id != user.id and is_emote_free(emote_id) is False:
            target = user
        await self.highrise.send_emote(emote_id, target_user_id=target.id)

    def _start_emote_loop(
        self,
        owner_id: str,
        emote_id: str,
        target_user_ids: list[str],
        duration: float,
        requester_id: str,
    ) -> None:
        self._cancel_emote_loop(owner_id)
        self.active_emote_targets[owner_id] = target_user_ids
        self.active_emote_loops[owner_id] = asyncio.create_task(
            self._emote_loop(
                emote_id, owner_id, target_user_ids, duration, requester_id
            )
        )

    async def _emote_loop(
        self,
        emote_id: str,
        owner_id: str,
        target_user_ids: list[str],
        duration: float,
        requester_id: str,
    ) -> None:
        task = asyncio.current_task()
        try:
            while True:
                await asyncio.gather(
                    *(
                        self.highrise.send_emote(
                            emote_id, target_user_id=target_user_id
                        )
                        for target_user_id in target_user_ids
                    )
                )
                await asyncio.sleep(duration)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Emote loop failed for user %s", owner_id)
            if "not free or owned" in str(error).casefold():
                await self.highrise.send_whisper(
                    requester_id,
                    "Highrise rejected that emote: it must be free or owned by "
                    "the user it is directed to."
                )
            else:
                await self.highrise.send_whisper(
                    requester_id,
                    "The emote failed. Check the bot logs for details."
                )
        finally:
            if self.active_emote_loops.get(owner_id) is task:
                del self.active_emote_loops[owner_id]
                self.active_emote_targets.pop(owner_id, None)

    def _cancel_emote_loop(self, user_id: str) -> None:
        task = self.active_emote_loops.pop(user_id, None)
        self.active_emote_targets.pop(user_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def _handle_interaction(
        self,
        user: User,
        command: str,
        args: list[str],
    ) -> None:
        if len(args) != 1:
            await self.highrise.chat(f"Usage: {command} @username")
            return
        target = await self._find_user(args[0])
        if target is None:
            await self.highrise.chat(f"{args[0]} is not in the room.")
            return

        if command == "!punch":
            now = time.monotonic()
            remaining = 5 - (now - self.punch_cooldowns.get(user.id, 0))
            if remaining > 0:
                await self.highrise.chat(
                    f"You can punch again in {math.ceil(remaining)}s."
                )
                return
            self.punch_cooldowns[user.id] = now

        emote_id, message = INTERACTION_ACTIONS[command]
        await self.highrise.send_emote(emote_id, target_user_id=target.id)
        await self.highrise.chat(
            message.format(sender=user.username, target=target.username)
        )

    async def _handle_log_command(self, user: User, args: list[str]) -> None:
        if not args or args[0].casefold() in {"public", "private"}:
            private = not args or args[0].casefold() == "private"
            entries = self.store.recent_command_logs(10)
            if entries:
                lines = [
                    f"[{entry['timestamp']}] {entry['command']} | "
                    f"{entry['duration_seconds']}s | {entry['reason']} | "
                    f"@{entry['target_username']}"
                    for entry in entries
                ]
                message = "\n".join(lines)
            else:
                message = "No commands have been logged."
            if private:
                await self.highrise.send_whisper(user.id, message)
            else:
                await self.highrise.chat(message)
            return

        if len(args) != 1 or not args[0].startswith("@"):
            await self.highrise.chat("Usage: !log [public|private|@username]")
            return
        target = await self._find_user(args[0])
        user_id = target.id if target else self.store.user_id_for_username(args[0])
        if user_id is None:
            await self.highrise.send_whisper(user.id, "No saved user history was found.")
            return
        history = [
            entry
            for entry in self.store.actions_for(user_id)
            if entry.get("command") in {"!warn", "!kick", "!ban", "!mute"}
        ]
        username = target.username if target else self.store.data["usernames"].get(user_id, args[0])
        if history:
            message = "\n".join(
                f"[{entry['timestamp']}] {entry['command']} | "
                f"{entry['duration_seconds']}s | {entry['reason']}"
                for entry in history
            )
        else:
            message = f"No moderation records found for @{username}."
        await self.highrise.send_whisper(user.id, message)

    async def _build_info_message(self, user: User) -> str:
        stats = self.store.session_stats(user.id)
        joined_at = self._format_timestamp(stats["joined_at"])
        current_time = self._format_duration(stats["current_seconds"])
        total_time = self._format_duration(stats["total_seconds"])
        counts = self._action_counts(user.id)
        warnings = len(self.store.warnings_for(user.id))
        note = self.store.note_for(user.id)

        crew_name = "N/A"
        account_age = "N/A"
        try:
            profile_response = await self.webapi.get_user(user.id)
            profile_user = profile_response.user
            crew = profile_user.crew
            crew_name = crew.name if crew else "None"
            if profile_user.joined_at:
                account_age = self._format_account_age(profile_user.joined_at)
        except Exception as error:
            print(f"\u274c Error: {error}", flush=True)
            logger.exception("Could not fetch public profile for %s", user.id)

        message = (
            f"USER PROFILE | @{user.username}\n"
            f"Role: {ROLE_LABEL[self._role_for(user.id)]}\n"
            f"Crew: {crew_name} | 18+ status: Not provided by Highrise\n"
            f"Highrise account: {account_age}\n"
            f"\nROOM ACTIVITY\n"
            f"First seen: {joined_at}\n"
            f"Current session: {current_time} | Total time: {total_time}\n"
            f"\nMODERATION\n"
            f"Bans: {counts['!ban']} | Kicks: {counts['!kick']} | "
            f"Mutes: {counts['!mute']} | Warnings: {warnings}"
        )
        if note:
            color_choices = [
                color for color in NOTE_COLORS if color != self.last_note_color
            ]
            self.last_note_color = random.choice(color_choices)
            message += f"\n\nNOTE\n{self.last_note_color}{note}"
        return message

    @staticmethod
    def _format_account_age(created_at: datetime) -> str:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        years = now.year - created_at.year
        months = now.month - created_at.month
        if now.day < created_at.day:
            months -= 1
        if months < 0:
            years -= 1
            months += 12
        return f"{max(0, years)} years, {months} months"

    @staticmethod
    def _format_timestamp(value: str | None) -> str:
        if not value:
            return "Unavailable"
        try:
            timestamp = datetime.fromisoformat(value)
            return timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        hours, remainder = divmod(max(0, total_seconds), 3_600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

    async def _moderate_command(self, command: str, args: list[str]) -> None:
        if not args:
            usage = (
                f"{command} @username"
                if command == "!kick"
                else f"{command} @username <seconds>"
            )
            await self.highrise.chat(f"Invalid syntax. Usage: {usage}")
            return
        target = await self._find_user(args[0])
        if target is None:
            await self.highrise.chat("User not found in this room.")
            return
        if command == "!kick":
            reason = " ".join(args[1:])
            await self.highrise.moderate_room(target.id, "kick", 0)
            message = f"@{target.username} has been kicked"
            if reason:
                message += f" for {reason}"
            duration = 0
        else:
            if len(args) < 2 or not args[1].isdigit() or int(args[1]) < 1:
                await self.highrise.chat(
                    f"Invalid syntax. Usage: {command} @username <seconds>"
                )
                return
            duration = int(args[1])
            reason = " ".join(args[2:])
            action = "ban" if command == "!ban" else "mute"
            await self.highrise.moderate_room(target.id, action, duration)
            past_tense = "banned" if action == "ban" else "muted"
            message = f"@{target.username} has been {past_tense} for {duration}s"
            if reason:
                message += f" \u2014 {reason}"
        await self.highrise.chat(message)
        self._log(command, duration, reason, target.username, target.id)

    async def _remove_teleport(
        self, args: list[str], sender_username: str, sender_user_id: str
    ) -> None:
        if not args:
            await self.highrise.chat(
                "Usage: !remove tele <location_name> or !remove all tele"
            )
            return
        location_name = " ".join(args).strip().strip("()").strip()
        if location_name.casefold() == "all tele":
            await self._remove_all_teleports(sender_username, sender_user_id)
            return
        if not self.store.remove_teleport(location_name):
            await self.highrise.chat(f'Teleport location "{location_name}" not found.')
            return
        await self.highrise.chat(f'Teleport "{location_name}" removed.')
        self._log("!remove tele", 0, location_name, sender_username, sender_user_id)

    async def _remove_all_teleports(
        self, sender_username: str, sender_user_id: str
    ) -> None:
        removed = self.store.remove_all_teleports()
        if not removed:
            await self.highrise.chat("There are no teleport points to remove.")
            return
        await self.highrise.chat(
            f"Removed all {len(removed)} teleport point(s): {', '.join(removed)}."
        )
        self._log(
            "!remove all tele",
            0,
            f"removed {len(removed)} teleport points",
            sender_username,
            sender_user_id,
        )

    async def _wallet_gold(self) -> int:
        wallet = await self.highrise.get_wallet()
        if not hasattr(wallet, "content"):
            return 0
        return sum(
            currency.amount
            for currency in wallet.content
            if isinstance(currency, CurrencyItem) and currency.type == "gold"
        )

    async def _tip_gold(self, user_id: str, denominations: list[str]) -> str:
        for denomination in denominations:
            result = await self.highrise.tip_user(user_id, denomination)
            if result != "success":
                return result if isinstance(result, str) else "error"
        return "success"

    async def _autotip(
        self, amount: int, seconds: int, requester_id: str
    ) -> None:
        task = asyncio.current_task()
        try:
            while True:
                await self._refresh_room()
                recipients = [
                    user_id for user_id in self.users if user_id != self.highrise.my_id
                ]
                if recipients and await self._wallet_gold() < amount * len(recipients):
                    await self.highrise.send_whisper(
                        requester_id, "Auto-tip stopped. Bot wallet is empty."
                    )
                    return
                denominations = split_gold_amount(amount)
                for user_id in recipients:
                    if await self._tip_gold(user_id, denominations) != "success":
                        await self.highrise.send_whisper(
                            requester_id, "Auto-tip stopped. Bot wallet is empty."
                        )
                        return
                    recipient = self.users.get(user_id)
                    username = (
                        recipient.username
                        if recipient is not None
                        else self.store.data["usernames"].get(user_id, user_id)
                    )
                    await self.highrise.chat(
                        f"🪙tipped @{username} ({amount}g)🪙"
                    )
                await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            raise
        finally:
            if self.autotip_task is task:
                self.autotip_task = None

    async def _repeat_message(self, message: str, seconds: int) -> None:
        task = asyncio.current_task()
        try:
            while True:
                await asyncio.sleep(seconds)
                await self.highrise.chat(message)
        except asyncio.CancelledError:
            raise
        finally:
            if self.loop_task is task:
                self.loop_task = None

    def _restart_command(self) -> list[str]:
        room_id = os.getenv("BOT_ROOM_ID", "")
        api_token = os.getenv("BOT_API_TOKEN", "")
        if room_id and api_token:
            return [
                sys.executable,
                "-m",
                "highrise",
                "main:Bot",
                room_id,
                api_token,
            ]
        return [sys.executable, *sys.argv]

    async def _restart_process(self) -> None:
        await asyncio.sleep(REFRESH_DELAY_SECONDS)
        os.execv(sys.executable, self._restart_command())

    @staticmethod
    def _cancel_task(task: asyncio.Task[None] | None) -> None:
        if task is not None and not task.done():
            task.cancel()


def run_cli(arguments: list[str]) -> int:
    if len(arguments) != 3 or arguments[0].casefold() != "startbot":
        print(
            "Usage: python main.py startbot <ROOM_ID> <API_TOKEN>",
            file=sys.stderr,
        )
        return 2
    _, room_id, api_token = arguments
    environment = os.environ.copy()
    environment["BOT_ROOM_ID"] = room_id
    environment["BOT_API_TOKEN"] = api_token
    return subprocess.call(
        [sys.executable, "-m", "highrise", "main:Bot", room_id, api_token],
        env=environment,
    )


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))