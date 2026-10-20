from __future__ import annotations

from bot_emotes import EMOTE_DATA, LEGACY_EMOTE_IDS


NOTE_COLORS = (
    "<#FFFFFF>", "<#F7F7F5>", "<#EDEDEA>", "<#D9D9D6>", "<#B8B8B3>",
    "<#8C8C87>", "<#5E5E5A>", "<#3A3A37>", "<#242422>", "<#121212>",
    "<#000000>", "<#FF0000>", "<#E63946>", "<#C1121F>", "<#8D0801>",
    "<#FF4D6D>", "<#FF758F>", "<#FFB3C1>", "<#FFF0F3>", "<#D90429>",
    "<#A4133C>", "<#800F2F>", "<#FFCAD4>", "<#FF9F1C>", "<#FFBF69>",
    "<#FFD60A>", "<#FFC300>", "<#F77F00>", "<#FCBF49>", "<#EAE2B7>",
    "<#FFE066>", "<#F4A261>", "<#E76F51>", "<#FFB703>", "<#FB8500>",
    "<#2EC4B6>", "<#20A39E>", "<#006D77>", "<#83C5BE>", "<#EDF6F5>",
    "<#386641>", "<#6A994E>", "<#A7C957>", "<#F2E8CF>", "<#081C15>",
    "<#1B4332>", "<#52B788>", "<#03045E>", "<#0077B6>", "<#00B4D8>",
    "<#90E0EF>", "<#CAF0F8>", "<#1D3557>", "<#457B9D>", "<#A8DADC>",
    "<#F1FAEE>", "<#219EBC>", "<#8ECAE6>", "<#023047>", "<#5A189A>",
    "<#7B2CBF>", "<#9D4EDD>", "<#C77DFF>", "<#E0AAFF>", "<#240046>",
    "<#3C096C>", "<#10002B>", "<#6930C3>", "<#480CA8>", "<#B5179E>",
    "<#F72585>", "<#7F5539>", "<#9C6644>", "<#B08968>", "<#DDB892>",
    "<#E6CCB2>", "<#5E503F>", "<#432818>", "<#974636>", "<#C68B59>",
    "<#E0D6C0>", "<#3E2C20>", "<#A68A64>", "<#FFD6E0>", "<#FFEFDA>",
    "<#FDFFB6>", "<#CAFFBF>", "<#9BF6FF>", "<#A0C4FF>", "<#BDB2FF>",
    "<#FFC6FF>", "<#E2F0CB>", "<#FFDAC1>", "<#B5EAD7>", "<#C7CEEA>",
    "<#003049>", "<#D62828>", "<#F77F00>", "<#FCBF49>", "<#EAE2B7>",
    "<#2A9D8F>", "<#264653>", "<#E9C46A>", "<#F4A261>", "<#6D597A>",
    "<#355070>", "<#B56576>",
)


ROLE_RANK = {
    "guest": 0,
    "vip": 1,
    "senioradmin": 2,
    "admin": 3,
    "mod": 4,
    "mod1": 5,
    "mod2": 6,
    "host": 7,
    "coowner": 8,
    "owner": 9,
}

REQUIRES_VIP = ROLE_RANK["vip"]
REQUIRES_ADMIN = ROLE_RANK["admin"]

ROLE_DISPLAY = {
    "Guest": "<#808080>Guest\U0001f464",
    "Vip": "<#FFD700>Vip\u2b50",
    "SeniorAdmin": "<#FFA500>SeniorAdmin\U0001f31f",
    "Admin": "<#FF7F00>Admin\U0001f396\ufe0f",
    "Mod": "<#FFCC66>Mod\U0001f510",
    "Mod1": "<#E86100>Mod1\U0001f6e1\ufe0f",
    "Mod2": "<#FF4500>Mod2\U0001f6e1\ufe0f\U0001f6e1\ufe0f",
    "Host": "<#B22222>Host\u2699\ufe0f",
    "Coowner": "<#E63946>Coowner\u269c\ufe0f",
    "OWNER": "<#800080>OWNER\U0001f451",
}

ROLE_LABEL = {
    "guest": ROLE_DISPLAY["Guest"],
    "vip": ROLE_DISPLAY["Vip"],
    "senioradmin": ROLE_DISPLAY["SeniorAdmin"],
    "admin": ROLE_DISPLAY["Admin"],
    "mod": ROLE_DISPLAY["Mod"],
    "mod1": ROLE_DISPLAY["Mod1"],
    "mod2": ROLE_DISPLAY["Mod2"],
    "host": ROLE_DISPLAY["Host"],
    "coowner": ROLE_DISPLAY["Coowner"],
    "owner": ROLE_DISPLAY["OWNER"],
}

ROLE_PERMISSION_NAME = {
    "guest": "Guest👤",
    "vip": "Vip⭐",
    "senioradmin": "SeniorAdmin🌟",
    "admin": "Admin🎖️",
    "mod": "Mod🔏",
    "mod1": "Mod1🛡️",
    "mod2": "Mod2🛡️🛡️",
    "host": "Host⚙️",
    "coowner": "Coowner⚜️",
    "owner": "OWNER👑",
}

COMMAND_MIN_RANK = {
    "!warn": ROLE_RANK["senioradmin"],
    "!unwarn": ROLE_RANK["senioradmin"],
    "!note": ROLE_RANK["senioradmin"],
    "!kick": ROLE_RANK["mod2"],
    "!ban": ROLE_RANK["mod2"],
    "!mute": ROLE_RANK["mod2"],
    "!log": ROLE_RANK["mod2"],
    "!give": ROLE_RANK["mod2"],
    "!remove": ROLE_RANK["mod2"],
    "!create": ROLE_RANK["mod2"],
    "!cords": ROLE_RANK["senioradmin"],
    "!bring": ROLE_RANK["senioradmin"],
    "!summon": ROLE_RANK["senioradmin"],
    "!tele": ROLE_RANK["vip"],
    "!goto": ROLE_RANK["guest"],
    "!tip": ROLE_RANK["senioradmin"],
    "!autotip": ROLE_RANK["senioradmin"],
    "!stopautotip": ROLE_RANK["senioradmin"],
    "!say": ROLE_RANK["senioradmin"],
    "!loop": ROLE_RANK["senioradmin"],
    "!stoploop": ROLE_RANK["senioradmin"],
    "!rf": ROLE_RANK["coowner"],
}

GOLD_DENOMINATIONS = (
    (10_000, "gold_bar_10k"),
    (5_000, "gold_bar_5000"),
    (1_000, "gold_bar_1k"),
    (500, "gold_bar_500"),
    (100, "gold_bar_100"),
    (50, "gold_bar_50"),
    (10, "gold_bar_10"),
    (5, "gold_bar_5"),
    (1, "gold_bar_1"),
)

_EMOTE_NAMES = (
    "ghostfloat", "hello", "tired", "sad", "happy", "angry", "surprised",
    "sleepy", "laugh", "wave", "thumbsup", "heart", "clap", "dance",
    "jump", "spin", "bow", "punch", "hit", "fall", "karate", "yoga",
    "stretch", "meditate", "prance", "ghost", "fairy", "fairytwirl",
    "astronaut", "levitate", "teleport", "cartwheel", "handstand", "pushups",
    "surf", "shuffle", "shrink", "attention", "stunned", "knock", "cute",
    "uwu", "relaxing", "propose", "smooch", "flirtywave", "sheep", "moonlit",
    "kawaii", "charging", "handshake", "armcannon", "twerk", "yap", "fresh",
    "russian", "nocturnal", "idlespace", "collapse", "orangejuice", "attentive",
    "passionate",
)
_DANCE_NAMES = (
    "dance-macarena", "dance-floss", "dance-slowjam", "dance-twist",
    "dance-breakdance", "dance-robot", "dance-salsa", "dance-waltz",
)
EMOTE_MAP = {
    **{name: f"emote-{name}" for name in _EMOTE_NAMES},
    **{name: name for name in _DANCE_NAMES},
}
EMOTE_DURATIONS = {
    name.casefold(): data[1]
    for name, data in EMOTE_DATA.items()
}
EMOTE_FREE_BY_ID = {
    emote_id.casefold(): is_free
    for emote_id, _, is_free in EMOTE_DATA.values()
}
for _name, _data in EMOTE_DATA.items():
    EMOTE_MAP.setdefault(_name.casefold(), _data[0])
    EMOTE_DURATIONS.setdefault(_data[0].casefold(), _data[1])
    EMOTE_DURATIONS.setdefault(_name.casefold().replace(" ", ""), _data[1])
EMOTE_MAP.update(LEGACY_EMOTE_IDS)


def resolve_emote(name: str) -> str | None:
    normalized = " ".join(name.strip().casefold().split())
    if normalized.startswith("emote-"):
        normalized = normalized[len("emote-"):]
    return EMOTE_MAP.get(normalized) or EMOTE_MAP.get(normalized.replace(" ", ""))


def resolve_emote_duration(name: str) -> float:
    normalized = " ".join(name.strip().casefold().split())
    if normalized.startswith("emote-"):
        normalized = normalized[len("emote-"):]
    return EMOTE_DURATIONS.get(
        normalized, EMOTE_DURATIONS.get(normalized.replace(" ", ""), 3.0)
    )


def is_emote_free(emote_id: str) -> bool | None:
    return EMOTE_FREE_BY_ID.get(emote_id.casefold())


def normalize_role(value: str) -> str | None:
    normalized = "".join(character for character in value.casefold() if character.isalnum())
    return normalized if normalized in ROLE_RANK else None


def can_use_staff_commands(role: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK["senioradmin"]


def can_assign_role(actor_role: str, requested_role: str) -> bool:
    return ROLE_RANK.get(actor_role, -1) >= ROLE_RANK["mod2"] and requested_role in ROLE_RANK


def split_gold_amount(amount: int) -> list[str]:
    if amount < 1 or amount > 100_000:
        raise ValueError("Gold amount must be between 1 and 100000.")

    tips: list[str] = []
    remaining = amount
    for denomination, sdk_value in GOLD_DENOMINATIONS:
        count, remaining = divmod(remaining, denomination)
        tips.extend([sdk_value] * count)
    return tips