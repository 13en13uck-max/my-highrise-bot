"""
Highrise Bot - Complete Build
Requires: highrise-bot-sdk, yt-dlp, ffmpeg
"""

import asyncio
import html
import inspect
import time
import random
import json
import sqlite3
import re
import os
import sys
import urllib.parse
import urllib.request

import aiohttp
from datetime import datetime
from collections import defaultdict

from highrise import BaseBot, Item, Position, ResponseError

admin_log = []
sent_items = set()
active_games = {}
pending_watch = {}
WATCH_GENRES = {
    "action", "drama", "comedy", "horror", "sci-fi", "thriller",
    "romance", "fantasy", "animation", "documentary", "marvel", "disney", "dc",
}
WATCH_GENRE_IDS = {
    "action": 28,
    "comedy": 35,
    "horror": 27,
    "sci-fi": 878,
    "thriller": 53,
    "romance": 10749,
    "fantasy": 14,
    "animation": 16,
    "documentary": 99,
    "drama": 18,
}

WORDLE_FALLBACK = [
    "apple", "brave", "chair", "dream", "eagle", "flame", "grape", "heart",
    "jolly", "kneel", "lemon", "magic", "noble", "ocean", "proud", "quiet",
    "river", "smile", "table", "world",
]
HANGMAN_FALLBACK = [
    "banana", "bottle", "camera", "castle", "dragon", "forest", "guitar", "kitten",
    "laptop", "market", "orange", "planet", "rabbit", "school", "silver", "summer",
    "ticket", "turtle", "window", "yellow",
    "animal", "author", "bridge", "button", "coffee", "danger", "engine", "family",
    "garden", "hammer", "island", "jungle", "kernel", "legend", "memory", "number",
    "object", "pillow", "quartz", "record", "server", "thunder", "unique", "valley",
    "winter", "artist", "basket", "candle", "desert", "flight", "friend",
]
COMMON_NOUNS = [
    "animal", "banana", "bicycle", "castle", "cloud", "dragon", "flower", "guitar",
    "hammer", "island", "jacket", "kitten", "laptop", "mountain", "pencil", "rocket",
    "school", "ship", "statue", "wizard",
]
WYR_FALLBACK = [
    ("Would you rather have unlimited pizza or unlimited ice cream?", "pizza", "ice cream"),
    ("Would you rather be able to fly or be invisible?", "fly", "invisible"),
    ("Would you rather always be 10 minutes late or 10 minutes early?", "late", "early"),
    ("Would you rather have a pause button or a rewind button for your life?", "pause", "rewind"),
    ("Would you rather live without music or without movies?", "no music", "no movies"),
    ("Would you rather have a pet dragon or a pet shark?", "dragon", "shark"),
    ("Would you rather be the funniest person in the room or the smartest?", "funniest", "smartest"),
    ("Would you rather always have cold feet or cold hands?", "cold feet", "cold hands"),
    ("Would you rather talk to animals or talk to plants?", "animals", "plants"),
    ("Would you rather pause time or fast-forward time?", "pause", "fast-forward"),
]
EMOJI_GUESSES = [
    ("🐱", "cat"), ("🐶", "dog"), ("🌞", "sun"), ("🌙", "moon"), ("⭐", "star"),
    ("🔥", "fire"), ("💧", "water"), ("🌊", "wave"), ("🌳", "tree"), ("🏠", "house"),
    ("🚗", "car"), ("✈️", "airplane"), ("🍕", "pizza"), ("🍔", "burger"),
    ("🍎", "apple"), ("🍌", "banana"), ("⚽", "soccer ball"), ("🏀", "basketball"),
    ("⚾", "baseball"), ("🎸", "guitar"), ("🎹", "piano"), ("🥁", "drums"),
    ("🎺", "trumpet"), ("👑", "crown"), ("💍", "ring"), ("👗", "dress"),
    ("👟", "sneakers"), ("📱", "phone"), ("💻", "laptop"), ("📺", "tv"),
    ("🎮", "game controller"), ("🌈", "rainbow"), ("❄️", "snowflake"),
    ("⚡", "lightning"), ("🦋", "butterfly"), ("🐝", "bee"), ("🦀", "crab"),
    ("🐙", "octopus"), ("🦈", "shark"), ("🐬", "dolphin"), ("🦁", "lion"),
    ("🐘", "elephant"), ("🏔️", "mountain"), ("🏖️", "beach"), ("🌋", "volcano"),
    ("🎂", "cake"), ("🧁", "cupcake"), ("🍩", "donut"), ("🍦", "ice cream"),
    ("🚀", "rocket"), ("🛸", "ufo"), ("👽", "alien"), ("🤖", "robot"),
    ("💀", "skull"), ("👻", "ghost"), ("🧟", "zombie"), ("🧙", "wizard"),
    ("🦄", "unicorn"), ("🐉", "dragon"), ("🗡️", "sword"), ("🛡️", "shield"),
]


def _decode_api_value(value):
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [_decode_api_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _decode_api_value(item) for key, item in value.items()}
    return value


def _record_admin_action(actor, action, target, detail=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    suffix = f" {detail}" if detail else ""
    admin_log.append(f"[{timestamp}] {actor} {action} {target}{suffix}")

BASE_ITEMS = []
BASE_ITEM_IDS = (
    "body-flesh",
    "eye-n_basic2018malesquaresleepy",
    "eyebrow-n_basic2018newbrows07",
    "nose-n_basic2018newnose05",
    "mouth-basic2018chippermouth",
    "hair_front-n_malenew05",
    "hair_back-n_malenew05",
    "freckle-n_basic2018freckle04",
)


def _build_base_items(inventory_items, log):
    available_ids = {item.id for item in inventory_items}
    base_items = []
    for item_id in BASE_ITEM_IDS:
        if item_id not in available_ids:
            log(f"Outfit warning: base item {item_id} is not in inventory.")
            continue
        base_items.append(
            Item(
                type="clothing",
                amount=1,
                id=item_id,
                account_bound=False,
                active_palette=27 if item_id == "body-flesh" else 0,
            )
        )
    return base_items


def _outfit_clothing_items():
    return [
        Item(type="clothing", amount=1, id="shirt-n_room32019denimjackethoodie", account_bound=False, active_palette=0),
        Item(type="clothing", amount=1, id="pants-n_starteritems2019cuffedjeanswhite", account_bound=False, active_palette=0),
        Item(type="clothing", amount=1, id="shoes-n_room32019socksneakersgrey", account_bound=False, active_palette=0),
    ]


OUTFITS = {
    1: {"name": "Casual", "items": _outfit_clothing_items()},
    2: {"name": "Business", "items": _outfit_clothing_items()},
    3: {"name": "Sporty", "items": _outfit_clothing_items()},
    4: {"name": "Streetwear", "items": _outfit_clothing_items()},
    5: {"name": "Formal", "items": _outfit_clothing_items()},
    6: {"name": "Summer", "items": _outfit_clothing_items()},
    7: {"name": "Night Out", "items": _outfit_clothing_items()},
    8: {"name": "Cozy", "items": _outfit_clothing_items()},
    9: {"name": "Festival", "items": _outfit_clothing_items()},
    10: {"name": "Classic", "items": _outfit_clothing_items()},
}

ONEWORD_CATEGORIES = [
    "animal", "country", "city", "food", "drink", "fruit", "vegetable",
    "color", "sport", "musical instrument", "famous person", "movie",
    "TV show", "car", "brand", "clothing item", "body part", "emotion",
    "weather", "ocean", "mountain", "river", "planet", "star", "flower",
    "tree", "bird", "fish", "insect", "mammal", "tool", "furniture",
    "room in a house", "appliance", "vehicle", "school subject", "language",
    "holiday", "season", "day of the week", "month", "number", "shape",
    "material", "fabric", "metal", "gem", "cosmetic", "hair style", "dance",
    "superhero", "villain", "mythical creature", "dinosaur", "pet",
    "zoo animal", "seafood", "dessert", "candy", "spice", "herb", "grain",
    "nut", "fruit juice", "alcoholic drink", "coffee type", "tea type",
    "sporting event", "olympic sport", "card game", "board game",
    "video game", "social media", "website", "app", "gadget", "tech company",
    "programming language", "moon", "constellation", "zodiac sign", "element",
    "chemical", "mineral", "rock", "gemstone", "currency", "bank", "airline",
    "airport", "hotel", "restaurant type", "fast food", "cuisine",
    "kitchen utensil", "baking ingredient", "condiment", "sauce", "soup",
    "sandwich", "pizza topping", "pasta type", "rice dish", "bread type",
    "cheese", "meat", "poultry", "salad ingredient", "landmark", "museum",
    "university", "library", "park", "garden", "forest", "desert", "island",
    "lake", "waterfall", "cave", "volcano", "glacier", "beach", "cliff",
    "canyon", "bridge", "tunnel", "highway", "neighborhood", "district",
    "region", "continent", "capital city", "US state", "European country",
    "Asian country", "African country", "nationality", "slang term", "idiom",
    "proverb", "phrase", "pronoun type", "verb type", "adjective type",
    "punctuation mark", "math symbol", "music note", "musical key", "chord",
    "rhythm", "tempo", "painting style", "artist", "sculptor", "photographer",
    "film director", "actor", "actress", "singer", "band", "album", "song",
    "genre", "chess piece", "dice", "card suit", "card rank", "team sport",
    "individual sport", "water sport", "winter sport", "combat sport",
    "racing sport", "martial art", "yoga pose", "exercise", "gym equipment",
    "swimming stroke", "cycling term", "running event", "theater type",
    "book genre", "poem form", "literary device", "comic type", "anime genre",
    "movie genre", "camera shot", "sound effect", "jewelry type", "watch type",
    "bag type", "shoe type", "hat type", "jacket type", "dress type",
    "medical term", "organ", "bone", "muscle", "disease", "symptom",
    "vitamin", "allergy", "injury", "hospital room", "medical device",
    "blood type", "cell type", "virus type", "bacteria type", "antibiotic",
]

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "room_id": "YOUR_ROOM_ID_HERE",
    "command_prefix": "!",
    "cooldown_seconds": 3,
    "music_cooldown_seconds": 5,
    "emote_cooldown_seconds": 3,
    "max_emote_loop_seconds": 300,
    "spam_threshold": 5,
    "spam_window_seconds": 10,
    "banned_words": [],
    "max_queue_size": 50,
    "shoutcast": {
        "server": "eu8.fastcast4u.com",
        "push_port": 4010,
        "username": "musicforhr",
        "password": "",
        "bitrate": "96k",
    },
    "roles": {
        "owner": {"privilege": "host", "cost": 0},
        "coowner": {"privilege": "manager", "cost": 0},
        "admin": {"privilege": "admin", "cost": 0},
        "seniormod": {"privilege": "admin", "cost": 0},
        "mod": {"privilege": "admin", "cost": 0},
        "dj": {"privilege": "vip", "cost": 0},
        "vip": {"privilege": "vip", "cost": 100, "duration_hours": 24},
        "guest": {"privilege": "guest", "cost": 0},
    },
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
        file_config = json.load(config_file)
    CONFIG.update(file_config)

TELE_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tele_data.json")
TELE_RANK_ORDER = [
    "guest",
    "vip",
    "dj",
    "mod",
    "seniormod",
    "admin",
    "coowner",
    "owner",
]
TELE_RANK_PRIORITY = {rank: index for index, rank in enumerate(TELE_RANK_ORDER)}

ROLE_PRIORITY = {
    "owner": 100, "coowner": 100, "admin": 80, "seniormod": 70,
    "mod": 60, "dj": 50, "vip": 40, "guest": 10,
}

USER_LEAVE_FALLBACK = [
    "💨 {user} left. The room will recover eventually.",
    "💨 {user} left. A bold exit.",
    "💨 {user} left. Their chair is still warm.",
    "💨 {user} left. No notes, just mystery.",
    "💨 {user} left. The silence is taking over.",
]
USER_JOIN_FALLBACK = [
    "👋 @{user} is back. The room just got better.",
    "👋 @{user} is back. Excellent timing.",
    "👋 @{user} is back. We saved their seat.",
    "👋 @{user} is back. Everyone act natural.",
    "👋 @{user} is back. The reunion begins.",
]
BOT_JOIN_FALLBACK = [
    "🔥 I'm back. The room survived without me.",
    "🔥 I'm back. Miss me a little?",
    "🔥 I'm back. The vibes are restored.",
    "🔥 I'm back. My loading screen finally ended.",
    "🔥 I'm back. Please remain calm.",
]
BOT_LEAVE_FALLBACK = [
    "👋 I'm out. Take care of yourselves.",
    "👋 I'm out. The room is in your hands.",
    "👋 I'm out. Be excellent to each other.",
    "👋 I'm out. See you on the next connection.",
    "👋 I'm out. Keep the chaos manageable.",
]
QUEUE_RULES_MESSAGES = (
    "<#FF0000> Queue Etiquette • Please stay in line and do not skip. "
    '• Skipping the line = Kick • Rudeness or harassment = Warning • '
    '"Mini-modding" (telling others what to do) = Warning\n\n'
    "Warnings & Mutes • 0/3 Warnings on the 3rd = Mute • Continuing to "
    "misbehave after mute = Kick • Further offenses = 1-Day Ban",
    "Item Limits & Costs • Free: 1 item per day • Skip Line Fee: 15g • "
    "Extra Items: • 1 Extra: 25g • 2 Extras: 50g • 3 Extras: 75g • "
    "4 Extras: 100g\n\n"
    "How to Claim • Please PM the Room Owner (VIP) with your requested "
    "item(s). • Be patient while waiting for a response. • Once you have "
    "received your item(s), please leave the room or ask a mod to move you "
    "to the Chill Area."
)
PG_SYSTEM = (
    "You are a fun, friendly game show host for kids. "
    "Generate exactly ONE short line (max 15 words). "
    "No swearing, no profanity, no slurs, no violence. "
    "Keep it playful and lighthearted."
)
R18_SYSTEM = (
    "You are a brutally honest but not hateful roast master. "
    "Generate exactly ONE short line (max 20 words). "
    "Swearing allowed. Edgy and funny. No slurs, no real personal attacks."
)
CLEAN_ROAST_FALLBACK = "Your jokes are still waiting for their software update."

BANNED_WORDS = [
    "mom", "mum", "mother", "dad", "daddy", "father", "sister", "brother",
    "family", "parent", "parents", "son", "daughter", "wife", "husband",
    "girlfriend", "boyfriend", "ex", "spouse", "partner", "grandma", "grandpa",
    "grandmother", "grandfather", "aunt", "uncle", "cousin", "nephew", "niece",
    "in-laws", "mother-in-law", "father-in-law",
]
BANNED_PHRASES = [
    "your mom", "your dad", "your family", "your ex", "your girlfriend",
    "your boyfriend", "your wife", "your husband", "your parents", "your sister",
    "your brother", "your kids", "your children",
]

DARE_FALLBACK = [
    "Do 10 pushups right now. No excuses.",
    "Say something embarrassing out loud.",
    "Do your best impression of a chicken.",
    "Talk in a British accent for the next 5 minutes.",
    "Say the word 'potato' every time you speak for 3 minutes.",
    "Do your best dance move. No holding back.",
    "Type everything in reverse for the next 2 messages.",
    "Say 'I am a golden retriever' 5 times.",
    "Do your best impression of an old person.",
    "Talk like a pirate until someone says stop.",
]
TRUTH_FALLBACK = [
    "What's the most embarrassing thing you've done in public?",
    "What's the last lie you told and who did you tell it to?",
    "What's your most controversial opinion?",
    "What's the worst thing you've said about someone behind their back?",
    "What's the most childish thing you still do?",
    "What's your biggest regret from this year?",
    "What's the most embarrassing thing in your search history?",
    "What's the last thing you googled at 3am?",
    "What's your most annoying habit that you know about?",
    "What's the worst gift you've ever given someone?",
]
RATE_FALLBACK = [
    "You are surprisingly delightful.",
    "Your personality is still buffering.",
    "You make every room brighter.",
    "Your jokes need a software update.",
    "You have excellent taste in being yourself.",
    "Even your autocorrect gives up on you.",
]
WHO_FALLBACK = [
    "A genuinely wonderful human being.",
    "A mystery wrapped in an unanswered message.",
    "The kind of person everyone is glad to know.",
    "The main character in a very confusing side quest.",
    "A legend in their own notification history.",
    "Someone with more confidence than a plan.",
]
RIDDLE_FALLBACK = [
    ("What has keys but cannot open locks?", "A piano."),
    ("What gets wetter the more it dries?", "A towel."),
    ("What has a head and a tail but no body?", "A coin."),
]
JOKE_FALLBACK = [
    ("Why don't scientists trust atoms?", "Because they make up everything."),
    ("Why did the scarecrow win an award?", "Because he was outstanding in his field."),
    ("What do you call a fake noodle?", "An impasta."),
    ("Why don't eggs tell jokes?", "They'd crack each other up."),
    ("What did the ocean say to the beach?", "Nothing, it just waved."),
]
DARK_JOKE_FALLBACK = [
    ("I have a joke about the slow internet...", "but you'll get it in 5-8 business days."),
    ("My grandfather has been in a coma for 15 years...", "He's finally getting used to it."),
    ("I'm reading a book about anti-gravity...", "It's impossible to put down."),
    ("What's the difference between a school bus and a cactus?", "The cactus has little prickles on the inside."),
    ("I used to be a banker...", "but I lost interest."),
    ("My therapist told me to stop acting like a golden retriever...", "I've been trying, but I keep wanting to tell everyone I love them."),
    ("Why don't scientists trust atoms?", "Because they make up everything. Even the ones that don't exist."),
    ("I told my wife she was drawing her eyebrows too high...", "She looked surprised."),
    ("My dad asked me to take out the trash...", "I ran three laps around the block just to be sure."),
    ("What do you call a fake Canadian?", "A habasard."),
]


def _is_banned_roast(insult):
    normalized = insult.casefold()
    if any(phrase.casefold() in normalized for phrase in BANNED_PHRASES):
        return True
    return any(
        re.search(rf"\b{re.escape(word.casefold())}\b", normalized)
        for word in BANNED_WORDS
    )

# ============================================================
# DATABASE
# ============================================================

class Database:
    def __init__(self, path="bot.db"):
        if path == "bot.db":
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self._create_tables()

    @staticmethod
    def _user_key(user_id):
        return str(user_id)

    def _create_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'guest',
            messages INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 100,
            tips_given INTEGER DEFAULT 0,
            tips_received INTEGER DEFAULT 0,
            emotes INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            blackjack_wins INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_in_room REAL DEFAULT 0,
            room_joined_at TIMESTAMP,
            bio TEXT DEFAULT '',
            status TEXT DEFAULT '',
            birthday TEXT DEFAULT '',
            nickname TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS leaderboards (
            user_id TEXT,
            tips_total INTEGER DEFAULT 0,
            tips_today INTEGER DEFAULT 0,
            day TEXT
        );
        CREATE TABLE IF NOT EXISTS banned (
            user_id TEXT PRIMARY KEY,
            reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS muted (
            user_id TEXT PRIMARY KEY,
            muted_until REAL,
            reason TEXT
        );
        CREATE TABLE IF NOT EXISTS frozen (
            user_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS custom_commands (
            name TEXT PRIMARY KEY,
            response TEXT
        );
        CREATE TABLE IF NOT EXISTS outfit_presets (
            name TEXT PRIMARY KEY,
            data TEXT
        );
        CREATE TABLE IF NOT EXISTS tele_points (
            name TEXT PRIMARY KEY,
            x REAL, y REAL, z REAL
        );
        CREATE TABLE IF NOT EXISTS achievements (
            user_id TEXT,
            achievement TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, achievement)
        );
        CREATE TABLE IF NOT EXISTS daily (
            user_id TEXT,
            last_claim REAL,
            streak INTEGER DEFAULT 0,
            PRIMARY KEY (user_id)
        );
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id TEXT PRIMARY KEY,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS room_members (
            user_id TEXT PRIMARY KEY,
            join_time REAL NOT NULL
        );
        """)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(users)")}
        if "coins" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 100")
        if "room_joined_at" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN room_joined_at TIMESTAMP")
        if "blackjack_wins" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN blackjack_wins INTEGER DEFAULT 0")
        if "nickname" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT DEFAULT ''")
        self.conn.commit()

    def get_user(self, user_id):
        row = self.conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            cols = [d[0] for d in self.conn.execute("SELECT * FROM users").description]
            return dict(zip(cols, row))
        return None

    def upsert_user(self, user_id, username=None):
        username = username or ""
        self.conn.execute("""
            INSERT INTO users (user_id, username, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP,
            username=CASE WHEN ? != '' THEN ? ELSE username END
        """, (user_id, username, username, username))
        self.conn.commit()

    def update_user(self, user_id, **kwargs):
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        self.conn.execute(f"UPDATE users SET {sets} WHERE user_id=?", vals)
        self.conn.commit()

    def increment(self, user_id, field, amount=1):
        self.conn.execute(f"UPDATE users SET {field}={field}+? WHERE user_id=?", (amount, user_id))
        self.conn.commit()

    def mark_room_interaction(self, user_id):
        user_id = self._user_key(user_id)
        join_time = self.get_room_join_time(user_id)
        if join_time is not None:
            return join_time
        join_time = time.time()
        self.conn.execute(
            "INSERT OR REPLACE INTO room_members (user_id, join_time) VALUES (?, ?)",
            (user_id, join_time),
        )
        self.conn.commit()
        return join_time

    def mark_room_left(self, user_id):
        row = self.conn.execute(
            "SELECT room_joined_at FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not row or not row[0]:
            return
        try:
            joined_at = datetime.fromisoformat(str(row[0]).replace("Z", ""))
            elapsed = max(0, (datetime.now() - joined_at).total_seconds())
        except (TypeError, ValueError):
            elapsed = 0
        self.conn.execute(
            "UPDATE users SET time_in_room=time_in_room+?, room_joined_at=NULL WHERE user_id=?",
            (elapsed, user_id),
        )
        self.conn.execute("DELETE FROM room_members WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_room_join_time(self, user_id):
        user_id = self._user_key(user_id)
        row = self.conn.execute(
            "SELECT join_time FROM room_members WHERE user_id=?", (user_id,)
        ).fetchone()
        return row[0] if row else None

    def get_balance(self, user_id):
        user = self.get_user(user_id)
        return int((user or {}).get("coins", 0) or 0)

    def transfer_coins(self, from_user, to_user, amount):
        if amount <= 0:
            return False, "Amount must be positive."
        if self.get_balance(from_user) < amount:
            return False, "Insufficient balance."
        self.upsert_user(to_user)
        self.update_user(from_user, coins=self.get_balance(from_user) - amount)
        self.update_user(to_user, coins=self.get_balance(to_user) + amount)
        return True, None

    def get_role(self, user_id):
        row = self.conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row else "guest"

    def get_achievements(self, user_id):
        rows = self.conn.execute(
            "SELECT achievement FROM achievements WHERE user_id=? ORDER BY achievement",
            (user_id,),
        ).fetchall()
        return [row[0] for row in rows]

    def get_daily(self, user_id):
        row = self.conn.execute(
            "SELECT user_id, last_claim, streak FROM daily WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {"user_id": row[0], "last_claim": row[1], "streak": row[2]}

    def get_all_users(self):
        rows = self.conn.execute("SELECT * FROM users ORDER BY username").fetchall()
        columns = [column[1] for column in self.conn.execute("PRAGMA table_info(users)")]
        return [dict(zip(columns, row)) for row in rows]

    def set_role(self, user_id, role):
        self.conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        self.conn.commit()

    def is_banned(self, user_id):
        return self.conn.execute("SELECT 1 FROM banned WHERE user_id=?", (user_id,)).fetchone() is not None

    def ban(self, user_id, reason=""):
        self.conn.execute("INSERT OR REPLACE INTO banned (user_id, reason) VALUES (?,?)", (user_id, reason))
        self.conn.commit()

    def get_banned(self):
        rows = self.conn.execute(
            "SELECT user_id, reason, banned_at FROM banned ORDER BY banned_at"
        ).fetchall()
        return [
            {"user_id": row[0], "reason": row[1], "banned_at": row[2]}
            for row in rows
        ]

    def unban(self, user_id):
        self.conn.execute("DELETE FROM banned WHERE user_id=?", (user_id,))
        self.conn.commit()

    def is_muted(self, user_id):
        row = self.conn.execute("SELECT muted_until FROM muted WHERE user_id=?", (user_id,)).fetchone()
        if row and row[0] > time.time():
            return True
        return False

    def mute(self, user_id, duration_seconds, reason=""):
        self.conn.execute("INSERT OR REPLACE INTO muted (user_id, muted_until, reason) VALUES (?,?,?)",
                          (user_id, time.time() + duration_seconds, reason))
        self.conn.commit()

    def unmute(self, user_id):
        self.conn.execute("DELETE FROM muted WHERE user_id=?", (user_id,))
        self.conn.commit()

    def is_frozen(self, user_id):
        return self.conn.execute("SELECT 1 FROM frozen WHERE user_id=?", (user_id,)).fetchone() is not None

    def freeze(self, user_id):
        self.conn.execute("INSERT OR REPLACE INTO frozen (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def unfreeze(self, user_id):
        self.conn.execute("DELETE FROM frozen WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_top_tippers(self, n=10):
        rows = self.conn.execute("SELECT user_id, tips_given FROM users ORDER BY tips_given DESC LIMIT ?", (n,)).fetchall()
        return rows

    def get_top_chatters(self, n=10):
        rows = self.conn.execute("SELECT user_id, messages FROM users ORDER BY messages DESC LIMIT ?", (n,)).fetchall()
        return rows

    def get_top_emoters(self, n=10):
        rows = self.conn.execute("SELECT user_id, emotes FROM users ORDER BY emotes DESC LIMIT ?", (n,)).fetchall()
        return rows

    def get_top_time(self, n=10):
        rows = self.conn.execute("SELECT user_id, time_in_room FROM users ORDER BY time_in_room DESC LIMIT ?", (n,)).fetchall()
        return rows

    def get_custom_command(self, name):
        row = self.conn.execute("SELECT response FROM custom_commands WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    def set_custom_command(self, name, response):
        self.conn.execute("INSERT OR REPLACE INTO custom_commands (name, response) VALUES (?,?)", (name, response))
        self.conn.commit()

    def get_tele_point(self, name):
        row = self.conn.execute("SELECT x,y,z FROM tele_points WHERE name=?", (name,)).fetchone()
        return row if row else None

    def get_all_tele_points(self):
        rows = self.conn.execute(
            "SELECT name FROM tele_points ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def set_tele_point(self, name, x, y, z):
        self.conn.execute("INSERT OR REPLACE INTO tele_points (name,x,y,z) VALUES (?,?,?,?)", (name, x, y, z))
        self.conn.commit()

    def delete_tele_point(self, name):
        self.conn.execute("DELETE FROM tele_points WHERE name=?", (name,))
        self.conn.commit()

    def is_subscriber(self, user_id):
        return self.conn.execute("SELECT 1 FROM subscribers WHERE user_id=?", (user_id,)).fetchone() is not None

    def subscribe(self, user_id):
        self.conn.execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def unsubscribe(self, user_id):
        self.conn.execute("DELETE FROM subscribers WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_subscribers(self):
        return [r[0] for r in self.conn.execute("SELECT user_id FROM subscribers").fetchall()]

    def unlock_achievement(self, user_id, achievement):
        self.conn.execute("INSERT OR IGNORE INTO achievements (user_id, achievement) VALUES (?,?)", (user_id, achievement))
        self.conn.commit()

    def get_achievements(self, user_id):
        return [r[0] for r in self.conn.execute("SELECT achievement FROM achievements WHERE user_id=?", (user_id,)).fetchall()]

    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()


# ============================================================
# EMOTE MAPS
# ============================================================

LOOP_EMOTES = {
    "ghostfloat": "emote-ghost-idle", "floating": "emote-ghost-idle", "ghost": "emote-ghost-idle",
    "chillin": "idle-loop-happy", "chill": "idle-loop-happy",
    "shy": "idle-loop-shy", "bummed": "idle-loop-sad",
    "sleepy": "idle-loop-tired", "tap": "idle-loop-tapdance", "tapdance": "idle-loop-tapdance",
    "sit": "idle-loop-sitfloor", "aerobics": "idle-loop-aerobics",
    "annoyed": "idle-loop-annoyed", "zombie": "idle_zombie",
    "relaxed": "idle_layingdown2", "attentive": "idle_layingdown",
    "posh": "idle-posh", "ponder": "idle-lookup", "hero": "idle-hero",
    "relaxing": "idle-floorsleeping2", "cozy": "idle-floorsleeping",
    "enthused": "idle-enthusiastic", "swing": "idle-dance-swinging",
    "beat": "idle-dance-headbobbing", "irritated": "idle-angry",
    "pouty": "idle-sad", "sleep": "idle-sleep", "rest": "sit-idle-cute",
}

ONE_SHOT_EMOTES = {
    "dab": "emote-dab", "macarena": "dance-macarena", "happy": "emote-happy",
    "sad": "emote-sad", "wave": "emote-wave", "hello": "emote-hello",
    "kiss": "emote-kiss", "bow": "emote-bow", "jump": "emote-jumpb",
    "disco": "emote-disco", "moonwalk": "emote-gordonshuffle", "gangnam": "emote-gangnam",
    "harlem": "emote-harlemshake", "floss": "dance-floss", "breakdance": "dance-breakdance",
    "robot": "dance-robotic", "karate": "dance-martial-artist", "russian": "dance-russian",
    "metal": "dance-metal", "duckwalk": "dance-duckwalk", "handsup": "dance-handsup",
    "vogue": "dance-voguehands", "savage": "dance-tiktok8", "dontstartnow": "dance-tiktok2",
    "yoga": "dance-spiritual", "smoothwalk": "dance-smoothwalk", "ring": "dance-singleladies",
    "shopping": "dance-shoppingcart", "penny": "dance-pennywise", "orange": "dance-orangejustice",
    "blackpink": "dance-blackpink", "pushups": "dance-aerobics", "think": "emote-think",
    "tired": "emote-tired", "theatrical": "emote-theatrical", "superrun": "emote-superrun",
    "superpunch": "emote-superpunch", "sumo": "emote-sumo", "suckthumb": "emote-suckthumb",
    "splits": "emote-splitsdrop", "snowball": "emote-snowball", "snowangel": "emote-snowangel",
    "secrethandshake": "emote-secrethandshake", "ropepull": "emote-ropepull", "roll": "emote-roll",
    "rofl": "emote-rofl", "rainbow": "emote-rainbow", "proposing": "emote-proposing",
    "propose": "emote-proposing", "peekaboo": "emote-peekaboo", "peace": "emote-peace",
    "panic": "emote-panic", "no": "emote-no", "ninjarun": "emote-ninjarun",
    "nightfever": "emote-nightfever", "monsterfail": "emote-monster_fail", "model": "emote-model",
    "flirty": "emote-lust", "levelup": "emote-levelup", "laughing": "emote-laughing2",
    "laugh": "emote-laughing", "kicking": "emote-kicking", "judochop": "emote-judochop",
    "jetpack": "emote-jetpack", "hugyourself": "emote-hugyourself", "hot": "emote-hot",
    "headball": "emote-headball", "elbowbump": "emote-elbowbump", "disappear": "emote-disappear",
    "blastoff": "emote-disappear", "deathdrop": "emote-deathdrop", "faintdrop": "emote-deathdrop",
    "collapse": "emote-death2", "revival": "emote-death", "curtsy": "emote-curtsy",
    "confused": "emote-confused", "cold": "emote-cold", "charging": "emote-charging",
    "bunnyhop": "emote-bunnyhop", "boo": "emote-boo", "baseball": "emote-baseball",
    "homrun": "emote-baseball", "apart": "emote-apart", "wings": "emote-wings",
    "fly": "emote-wings", "yes": "emote-yes", "faint": "emote-fainting",
    "clumsy": "emote-fail2", "fall": "emote-fail1", "facepalm": "emote-exasperatedb",
    "exasperated": "emote-exasperated", "greedy": "emote-greedy", "graceful": "emote-graceful",
    "frolic": "emote-frollicking", "frollicking": "emote-frollicking",
}

ALL_EMOTE_NAMES = sorted(set(list(LOOP_EMOTES.keys()) + list(ONE_SHOT_EMOTES.keys())))

# ============================================================
# PERSONALITY MESSAGES
# ============================================================

CHILL_MESSAGES = [
    "Anyone up for some music? 🎵", "This room is looking good today.",
    "Just vibing here. 🧘", "Say hi to me, I'm shy. 👋",
    "What's everyone up to?", "I could go for a dance break. 💃",
    "Who's been here the longest? !lb time", "Tip me if you like my company. 💰",
]
FUNNY_MESSAGES = [
    "I'm not lazy, I'm on energy saving mode. 🔋",
    "My therapist says I talk too much. So I'm doing more emotes. 💃",
    "I tried to be mysterious but I'm a bot. 🤖",
    "If I were human I'd be the friend who's always late. ⏰",
    "I don't make the rules, I just enforce them. Probably. 🤔",
    "Someone said I'm basic. I'm a BOT. I'm literally code. 🤖",
    "I'd tell you a UDP joke but you might not get it. 📡",
    "My love life is like my code. Full of bugs. 💔",
]
HYPE_MESSAGES = [
    "LET'S GOOOO! 🔥🔥🔥", "WHO'S READY?! 🎉", "THIS ROOM IS LIT!! 💥",
    "SOMEONE TIP ME I'M STARVING 🍕💰", "WE ARE UNSTOPPABLE!! 🚀",
    "MORE MUSIC!! MORE DANCING!! 🎶💃", "I CAN'T BELIEVE THIS ROOM IS THIS CRAZY!! 🤯",
]
EDGY_MESSAGES = [
    "Enjoy your stay while it lasts. 🕶️", "I see everything. I remember everything. 📸",
    "You're all just data to me. 🤖", "The void is calling. Should I answer? 🌑",
    "I don't sleep. I don't eat. I just watch. 👁",
]

KEYWORD_TRIGGERS = {
    "hello": ["Hey there! 👋", "Hello! Welcome!", "Hi hi! 👋👋", "Yo! What's up?"],
    "hi": ["Hey! 👋", "Hi there!", "Howdy! 🤠", "Sup!"],
    "bye": ["See ya! 👋", "Later! 👋", "Bye bye! 🫡", "Catch you later!"],
    "love": ["Aww! 💕", "Love you too! ❤️", "💕💕💕"],
    "music": ["What should we play? !play (song) 🎵", "Drop a song! 🎶", "I'm feeling musical! 🎵"],
    "dance": ["LET'S DANCE! 💃🕺", "Macarena time! !emote macarena", "🕺🕺🕺"],
    "tip": ["Tip me and I'll do a dance! 💰💃", "I accept tips in gold. 💰", "Buy me a coffee (in gold). ☕💰"],
    "bot": ["Beep boop! 🤖", "I'm alive! 🤖✨", "Bleep bloop! 🤖"],
    "bored": ["Try !rps or !dice! 🎮", "I'm bored too. Let's play something. 🎲", "Type !trivia start and I'll entertain you. ❓"],
    "fun": ["Let's have some fun! 🎉", "Fun is my middle name. 🥳", "What do you wanna do? 🎮"],
    "sad": ["There there. 🥺", "Want a virtual hug? 🤗", "Everything gets better. 💙"],
    "happy": ["Yay! 🎉", "Love that for you! 😄", "Keep that energy! ⚡"],
    "help": ["Type !help for all commands! 📋", "I'm here! What do you need? 🤖", "Check !help, I got you."],
    "thank": ["You're welcome! 😊", "Anytime! 🫡", "No problem! 💪"],
    "sorry": ["It's okay. 💙", "No worries! 😊", "All good! 🫶"],
    "lol": ["😂", "LMAO", "I'm crying 😭", "That's actually funny"],
    "lmao": ["😭😭😭", "I can't", "STOP I'M CRYING", "💀💀💀"],
    "omg": ["I know right?! 😱", "OMG indeed! 🤯", "No way!! 😲"],
    "bruh": ["Bruh. 🙄", "Actually...", "No cap."],
    "no cap": ["Bet bet. 💯", "Say less.", "Facts."],
    "slay": ["Slayed. 💅", "Queen behavior. 👑", "Slay all day."],
    "bestie": ["Bestie!! 💕", "Say less bestie.", "I know right?? 💅"],
    "rizz": ["W rizz. 📈", "Unspoken rizz detected.", "Rizz level: godlike."],
    "sigma": ["Sigma grindset. 🗿", "Sigma moment.", "No cap, sigma behavior."],
    "skibidi": ["Skibidi Toilet. 🚽", "Very skibidi.", "Skibidi rizz."],
    "gyat": ["Gyat. 🍑", "Very gyat.", "Gyat level: 100."],
    "fanum tax": ["Fanum tax time. 🍔", "I'm taking my fanum tax.", "That's my fanum tax."],
}

BOT_IDLE_EMOTES = [
    "emote-wave", "emote-happy", "emote-dab", "dance-macarena",
    "emote-bow", "emote-hello", "emote-laughing", "dance-floss",
    "idle-loop-happy", "emote-peace", "emote-jumpb",
]

# ============================================================
# TRUTHS & DARES
# ============================================================

TRUTHS = [
    "What's the most embarrassing thing you've done in this room?",
    "Who in this room would you never want to be stuck in an elevator with?",
    "What's a secret you've never told anyone here?",
    "What's the worst thing you've said about someone in this room?",
    "Have you ever pretended to be someone else online?",
    "What's the most ridiculous thing you believe?",
    "Who was your first crush?",
    "What's the last lie you told?",
    "What's your most controversial opinion?",
    "If you had to delete one app forever, what would it be?",
]
DARES = [
    "Do your best impression of a chicken for 10 seconds. 🐔",
    "Say 'I love you' to the person to your left. ❤️",
    "Do 10 pushups right now. 💪",
    "Sing the first song that comes to mind. 🎤",
    "Say the opposite of everything for the next 30 seconds. 🤪",
    "Do your best dance move. 💃",
    "Talk in a voice for the next 3 messages. 🎭",
    "Compliment everyone in the room. 👏",
    "Do a dramatic bow. 🙇",
    "Type the next 3 messages backwards. 🙃",
]

# ============================================================
# ACHIEVEMENTS
# ============================================================

ACHIEVEMENTS = {
    "first_steps": {"desc": "Join the room", "check": lambda u: True, "reward": 5},
    "chatterbox": {"desc": "Send 100 messages", "check": lambda u: u["messages"] >= 100, "reward": 10},
    "big_mouth": {"desc": "Send 1,000 messages", "check": lambda u: u["messages"] >= 1000, "reward": 25},
    "first_tip": {"desc": "Tip the bot", "check": lambda u: u["tips_given"] > 0, "reward": 5},
    "generous": {"desc": "Tip 100g total", "check": lambda u: u["tips_given"] >= 100, "reward": 10},
    "philanthropist": {"desc": "Tip 1,000g total", "check": lambda u: u["tips_given"] >= 1000, "reward": 25},
    "whale": {"desc": "Tip 10,000g total", "check": lambda u: u["tips_given"] >= 10000, "reward": 100},
    "dancer": {"desc": "Do 50 emotes", "check": lambda u: u["emotes"] >= 50, "reward": 10},
    "emote_master": {"desc": "Do 500 emotes", "check": lambda u: u["emotes"] >= 500, "reward": 25},
    "regular": {"desc": "Spend 24 hours in the room", "check": lambda u: u["time_in_room"] >= 86400, "reward": 10},
    "player": {"desc": "Play 10 games", "check": lambda u: u["games_played"] >= 10, "reward": 10},
}

COMMAND_ALIASES = {
    "h": "help", "commands": "help", "stats": "profile", "info": "info",
    "recipe": "recipe", "cook": "recipe", "food": "recipe",
    "randomfact": "randomfact", "fact": "randomfact", "facts": "facts",
    "didyouknow": "randomfact",
    "21": "21", "blackjack": "21",
    "hit": "hit", "stand": "stand", "show": "show", "quit": "quit",
    "join": "join",
    "flip": "flip", "heads": "heads", "tails": "tails",
    "kms": "kms", "kiss": "kiss", "marry": "marry", "kill": "kill",
    "oneword": "oneword", "skip": "skip",
    "kick": "kick", "ban": "ban", "unban": "unban", "mute": "mute",
    "unmute": "unmute", "freeze": "freeze", "unfreeze": "unfreeze",
    "modlog": "modlog",
    "bal": "balance", "wallet": "wallet", "e": "emote",
    "lb": "top", "coin": "coinflip", "cf": "coinflip", "r": "roll",
    "setowner": "setowner",
    "nickname": "nickname", "nick": "nickname",
    "grab": "grab", "bring": "bring",
    "telecord": "telecord", "mypos": "mypos", "pos": "mypos",
    "rf": "refresh", "refresh": "refresh",
    "tipall": "tipall", "autotip": "autotip",
}
COMMAND_ALIASES.update({name: f"emote {name}" for name in ALL_EMOTE_NAMES})
COMMAND_ALIASES.update({
    "dance": "emote macarena",
    "wave": "emote wave",
    "dab": "emote dab",
    "floss": "emote floss",
})

HELP_TEXTS = {
    "help": "Shows this help message. Usage: !help or !help <command>",
    "commands": "Same as !help. Shows all available commands.",
    "profile": "Shows your bot profile including join date and stats. Usage: !profile or !profile @user",
    "stats": "Shows your personal stats. Usage: !stats or !stats @user",
    "status": "Shows room status, users online, uptime, and last roast time.",
    "uptime": "Shows how long the bot has been online.",
    "info": "Shows your info including time in room. Usage: !info or !info @user",
    "top": "Shows the leaderboard of top users by activity.", "lb": "Same as !top.",
    "balance": "Shows your coin balance. Usage: !balance or !balance @user",
    "bal": "Same as !balance.", "wallet": "Same as !balance.",
    "subscribe": "Subscribes you to the bot. Purely cosmetic.",
    "unsubscribe": "Unsubscribes you from the bot.",
    "history": "Pulls a Wikipedia summary. Usage: !history <subject>",
    "refresh": "Refreshes the bot. Owner/Co-Owner only.", "rf": "Same as !refresh.",
    "recipe": "Pulls a recipe. Usage: !recipe [cuisine]", "cook": "Same as !recipe.", "food": "Same as !recipe.",
    "randomfact": "Pulls a random fact. Usage: !randomfact [category]", "fact": "Same as !randomfact.",
    "facts": "Pulls a random fact.", "didyouknow": "Same as !facts.", "joke": "Pulls a random joke.",
    "djoke": "Pulls a clean joke.", "pg": "Switches AI responses to clean, kid-friendly mode.",
    "18": "Switches AI responses to 18+ roast mode.",
    "insult": "Generates an AI insult using the active mode.",
    "roast": "Generates an AI roast using the active mode.",
    "booktok": "Pulls a quote from a novel.",
    "riddle": "Pulls a riddle. You have 6 guesses to answer it in chat.",
    "memes": "Pulls a random meme image.", "watch": "Suggests a movie or TV show by genre.",
    "rate": "Rates a user 1-10. Usage: !rate @user", "who": "Describes a user. Usage: !who @user",
    "truth": "Pulls a truth question. Usage: !truth @user", "dare": "Pulls a dare. Usage: !dare @user",
    "roll": "Rolls a dice. Usage: !roll [sides]", "r": "Same as !roll.",
    "coinflip": "Flips a coin.", "coin": "Same as !coinflip.", "cf": "Same as !coinflip.",
    "tictactoe": "2-player tic tac toe. Usage: !tictactoe @user. Type numbers 1-9.",
    "wordle": "Guess a 5-letter word in 10 tries with colour feedback.",
    "hangman": "Guess a word letter by letter. 6 wrong guesses ends the game.",
    "20questions": "Ask yes/no questions. You have 20 questions.",
    "charades": "Guess the described word. 60 second timer.", "emoji": "Guess what the emoji represents. 45 second timer.",
    "wouldyourrather": "Vote A or B on a would-you-rather question.", "reaction": "Fastest reaction after GO wins.",
    "oneword": "One-word story game.", "skip": "Skips your turn in the current game.",
    "flip": "Flips a coin.", "heads": "Bets heads in a coin flip.", "tails": "Bets tails in a coin flip.",
    "play 21": "Starts blackjack. Usage: !play 21 or !blackjack", "21": "Same as !play 21.", "blackjack": "Same as !play 21.",
    "join": "Joins the active blackjack game.", "hit": "Takes another blackjack card.",
    "stand": "Stops taking blackjack cards.", "show": "Shows your blackjack hand.", "quit": "Leaves blackjack.",
    "kms": "Kiss Marry Kill. Use !kiss, !marry, and !kill.", "kiss": "Kisses a KMS choice. Usage: !kiss [1/2/3]",
    "marry": "Marries a KMS choice. Usage: !marry [1/2]", "kill": "Kills the remaining KMS choice.",
    "punch": "Punches a user. Usage: !punch @user", "slap": "Slaps a user. Usage: !slap @user",
    "hug": "Hugs a user. Usage: !hug @user", "stop": "Stops your current looping emote.",
    "kick": "Kicks a user. Admin only. Usage: !kick @user", "ban": "Bans a user. Admin only. Usage: !ban @user",
    "unban": "Unbans a user. Admin only. Usage: !unban @user", "mute": "Mutes a user. Admin only. Usage: !mute @user",
    "unmute": "Unmutes a user. Admin only. Usage: !unmute @user", "freeze": "Freezes a user. Admin only.",
    "unfreeze": "Unfreezes a user. Admin only.", "modlog": "Shows recent admin actions. Admin only.",
    "log": "Same as !modlog.", "summon": "Teleports a user to you. Admin only. Usage: !summon @user",
    "setowner": "Sets the current user as owner.", "nickname": "Changes a user's display name. Usage: !nickname @user <name>",
    "nick": "Same as !nickname.", "give": "Gives coins. Usage: !give @user <amount>", "remove": "Removes a user's role.",
    "role": "Shows your current role.", "tipall": "Tips everyone. Admin only. Usage: !tipall <amount>",
    "autotip": "Auto-tips everyone. Usage: !autotip <amount> <seconds> or off.",
    "tele": "Teleports the bot. Usage: !tele X Y Z or !tele @user", "grab": "Grabs a user. Usage: !grab @user",
    "bring": "Same as !grab.", "telecord": "Uses saved coordinates.", "mypos": "Shows your coordinates.",
    "pos": "Same as !mypos.", "setpos": "Saves coordinates. Usage: !setpos <name> X Y Z",
    "create tele": "Same as !setpos.", "remove tele": "Deletes saved coordinates.",
    "emote": "Plays an emote. Usage: !emote <name>, list, or stop.", "e": "Same as !emote.",
    "dance": "Plays the dance emote.", "wave": "Plays the wave emote.", "dab": "Plays the dab emote.",
    "floss": "Plays the floss emote.", "macarena": "Plays the macarena emote.", "ghostfloat": "Plays ghostfloat.",
    "chillin": "Plays chillin.", "shy": "Plays shy.", "sleepy": "Plays sleepy.", "zombie": "Plays zombie.",
}


class WordChainGame:
    """Small deterministic word-chain game used by the command layer and tests."""

    def __init__(self, bot):
        self.bot = bot
        self.current_word = None
        self.last_user = None

    def start(self):
        self.current_word = "apple"
        self.last_user = None
        return "Word chain started with apple. Next word must begin with e."

    def submit(self, user_id, word):
        word = word.strip().casefold()
        if not word.isalpha():
            return "Use a single word."
        self.current_word = word
        self.last_user = user_id
        return f"{word} accepted. Next word must begin with {word[-1]}."


class BlackjackGame:
    """Shared multiplayer 21 table with simple blackjack actions."""

    def __init__(self, bot):
        self.bot = bot
        self.active = False
        self.round_active = False
        self.players = {}
        self.dealer_hand = []
        self.dealer_total = 0

    def create(self):
        self.active = True
        self.round_active = False
        self.players = {}
        self.dealer_hand = []
        self.dealer_total = 0
        return "🃏 21 table created. Players can join with !play 21."

    def join(self, user_id):
        if user_id in self.players:
            return f"{self.bot.get_username(user_id)} is already in the 21 game."
        self.players[user_id] = {"hand": [], "total": 0, "done": False}
        return f"✅ {self.bot.get_username(user_id)} joined the 21 game."

    @staticmethod
    def _calc_total(hand):
        total = sum(min(card, 10) for card in hand)
        aces = sum(card == 1 for card in hand)
        while aces and total + 10 <= 21:
            total += 10
            aces -= 1
        return total

    @staticmethod
    def _card_name(card):
        return {
            1: "A", 11: "J", 12: "Q", 13: "K"
        }.get(card, str(min(card, 10)))

    def _hand_str(self, hand):
        return " ".join(self._card_name(card) for card in hand)

    def hit(self, user_id):
        player = self.players[user_id]
        card = random.randint(1, 13)
        player["hand"].append(card)
        player["total"] = self._calc_total(player["hand"])
        if player["total"] >= 21:
            player["done"] = True
        return (
            f"🃏 {self.bot.get_username(user_id)} draws {self._card_name(card)} "
            f"({player['total']})."
        )

    def stand(self, user_id):
        self.players[user_id]["done"] = True
        return f"🛑 {self.bot.get_username(user_id)} stands."

    def show(self):
        lines = [f"🃏 Dealer: {self._hand_str(self.dealer_hand)} ({self.dealer_total})"]
        lines.extend(
            f"{self.bot.get_username(uid)}: {self._hand_str(player['hand'])} "
            f"({player['total']})"
            for uid, player in self.players.items()
        )
        return "\n".join(lines)

    def quit(self, user_id):
        self.players.pop(user_id, None)
        if not self.players:
            self.active = False
            self.round_active = False
        return f"👋 {self.bot.get_username(user_id)} left the 21 game."

    def lobby(self):
        if not self.players:
            return "Blackjack lobby is empty."
        return "Blackjack players: " + ", ".join(self.players)


class EmoteLoopManager:
    def __init__(self, bot):
        self.bot = bot
        self.active_loops = {}
        self.loop_start = {}
        self.loop_tasks = {}

    async def trigger_on_user(self, user_id, emote_name):
        name = emote_name.casefold().strip()
        emote_id = LOOP_EMOTES.get(name) or ONE_SHOT_EMOTES.get(name)
        if not emote_id:
            return "Unknown emote. Try !emote list."

        username = self.bot.get_username(user_id)
        if user_id in self.bot.active_emotes:
            self.stop_loop(user_id)
        if name in LOOP_EMOTES:
            self.bot.active_emotes[user_id] = name
            self.active_loops[user_id] = emote_id
            self.loop_start[user_id] = time.time()
            try:
                await self.bot.highrise.send_emote(
                    emote_id, target_user_id=user_id
                )
            except TypeError:
                await self.bot.highrise.send_emote(emote_id)
            except (ConnectionError, RuntimeError, ResponseError) as exc:
                self.bot.log(f"Emote loop failed: {exc}")
                self.stop_loop(user_id)
                return f"Couldn't trigger {name}."
            self.bot.db.increment(user_id, "emotes")
            self.loop_tasks[user_id] = asyncio.create_task(
                self._loop_on_user(user_id, emote_id)
            )
            return f"{username} is looping: {name}"

        self.bot.active_emotes[user_id] = name
        try:
            await self.bot.highrise.send_emote(
                emote_id, target_user_id=user_id
            )
        except TypeError:
            await self.bot.highrise.send_emote(emote_id)
        except (ConnectionError, RuntimeError, ResponseError) as exc:
            self.bot.log(f"Emote {name} ({emote_id}) failed: {exc}")
            self.bot.active_emotes.pop(user_id, None)
            return f"Couldn't trigger {name}."
        self.bot.db.increment(user_id, "emotes")
        self.bot.active_emotes.pop(user_id, None)
        return f"{username} did: {name}"

    async def _loop_on_user(self, user_id, emote_id):
        max_duration = CONFIG["max_emote_loop_seconds"]
        try:
            while (
                self.active_loops.get(user_id) == emote_id
                and time.time() - self.loop_start.get(user_id, 0) < max_duration
            ):
                try:
                    await self.bot.highrise.send_emote(
                        emote_id, target_user_id=user_id
                    )
                except TypeError:
                    await self.bot.highrise.send_emote(emote_id)
                except (ConnectionError, RuntimeError, ResponseError) as exc:
                    self.bot.log(f"Emote loop failed: {exc}")
                    break
                self.bot.db.increment(user_id, "emotes")
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            return
        finally:
            if self.active_loops.get(user_id) == emote_id:
                self.active_loops.pop(user_id, None)
                self.loop_start.pop(user_id, None)
                self.loop_tasks.pop(user_id, None)
            self.bot.active_emotes.pop(user_id, None)

    def stop_loop(self, user_id):
        self.active_loops.pop(user_id, None)
        self.loop_start.pop(user_id, None)
        self.bot.active_emotes.pop(user_id, None)
        task = self.loop_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    def stop_all_for_user(self, user_id):
        self.stop_loop(user_id)


class Bot(BaseBot):
    """Runnable Highrise SDK bot with safe, database-backed room commands."""

    def __init__(self):
        super().__init__()
        sent_items.clear()
        active_games.clear()
        pending_watch.clear()
        self.config = CONFIG
        self.mode = "pg"
        self.started_at = time.monotonic()
        self.db = Database()
        owner_id = self.config.get("owner_id")
        if owner_id:
            self.db.upsert_user(owner_id)
        self._migrate_legacy_owner_roles()
        self._restore_owner()
        self.cooldowns = {}
        self.active_emotes = {}
        self.loops = {}
        self.emotes = EmoteLoopManager(self)
        self.blackjack = BlackjackGame(self)
        self.flip_active = False
        self.flip_player = None
        self.flip_choice = None
        self.kms_active = False
        self.kms_player = None
        self.kms_options = []
        self.kms_kiss = None
        self.kms_marry = None
        self.kms_kill = None
        self.kms_round = 0
        self.oneword_active = False
        self.oneword_player = None
        self.oneword_letter = None
        self.oneword_categories = []
        self.oneword_round = 0
        self.oneword_max_rounds = 8
        self.oneword_score = 0
        self.app = self
        self.highrise = None
        self._tasks = set()
        self._api_lock = asyncio.Lock()
        self._source_watch_task = None
        self._roast_task = None
        self._queue_rules_task = None
        self.last_roast = ""
        self._last_truth_dare_call = 0.0
        self._restart_requested = False
        self.autotip_task = None
        self.autotip_amount = 0
        self.autotip_interval = 0
        self.autotip_queue = []
        self.autotip_index = 0
        self.tele_data = self._load_tele_data()
        self.user_ranks = self.tele_data.get("user_ranks", {})
        self.teleports = self.tele_data.get("teleports", {})
        self.tele_ranks = self.tele_data.get("tele_ranks", {})

    def _fallback_lifecycle_message(self, messages, **values):
        for _attempt in range(5):
            message = random.choice(messages).format(**values)
            if self._claim_content(message):
                return message
        return None

    async def _bot_join_message(self):
        comment = await self._fetch_unique_text(
            lambda: "https://complimentr.com/api",
            lambda data: data.get("compliment") if isinstance(data, dict) else None,
        )
        return f"🔥 I'm back. {comment}" if comment else self._fallback_lifecycle_message(BOT_JOIN_FALLBACK)

    async def on_start(self, session_metadata):
        global BASE_ITEMS
        self._restore_owner()
        self.db.conn.execute("PRAGMA foreign_keys = ON")
        room_info = getattr(session_metadata, "room_info", None)
        room_name = getattr(room_info, "room_name", "room")
        self.log("Bot started.")
        try:
            inventory = await self.highrise.get_inventory()
            inventory_items = list(getattr(inventory, "items", []))
            self.log(f"Inventory: {inventory_items!r}")
            BASE_ITEMS = _build_base_items(inventory_items, self.log)
            self.log(f"Base outfit items: {BASE_ITEMS!r}")
        except Exception as exc:
            BASE_ITEMS = []
            self.log(f"Inventory lookup failed: {type(exc).__name__}: {exc}")
        message = await self._bot_join_message()
        if message:
            await self.highrise.chat(message)
        self._cancel_roast_task()
        self._roast_task = asyncio.create_task(self._roast_loop())
        self._cancel_queue_rules_task()
        self._queue_rules_task = asyncio.create_task(self._queue_rules_loop())
        if self._source_watch_task is None or self._source_watch_task.done():
            self._source_watch_task = asyncio.create_task(self._watch_source_changes())

    async def _queue_rules_loop(self):
        try:
            while True:
                await asyncio.sleep(10)
                for message in QUEUE_RULES_MESSAGES:
                    try:
                        await self.highrise.chat(message)
                    except Exception as exc:
                        self.log(
                            "Queue rules announcement failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
        except asyncio.CancelledError:
            return

    async def _roast_loop(self):
        try:
            while True:
                await asyncio.sleep(300)
                await self._roast_once()
        except asyncio.CancelledError:
            return

    async def _roast_once(self):
        try:
            response = await self.highrise.get_room_users()
            bot_id = str(getattr(self.highrise, "my_id", ""))
            users = [
                room_user
                for room_user, _position in getattr(response, "content", [])
                if str(getattr(room_user, "id", "")) != bot_id
            ]
            if not users:
                return
            target = random.choice(users)
            roast = await self._generate_ai(
                f"Write a roast for {target.username}. Make it punchy and funny.",
                "roast",
            )
            if roast == self.last_roast:
                roast = CLEAN_ROAST_FALLBACK
            await self.highrise.chat(f"🔥 @{target.username}: {roast}")
            self.last_roast = roast
        except Exception:
            return

    def _cancel_roast_task(self):
        if self._roast_task is not None:
            self._roast_task.cancel()
            self._roast_task = None

    def _cancel_queue_rules_task(self):
        if self._queue_rules_task is not None:
            self._queue_rules_task.cancel()
            self._queue_rules_task = None

    def _source_mtimes(self):
        source_dir = os.path.dirname(os.path.abspath(__file__))
        paths = (
            os.path.join(source_dir, "bot.py"),
            os.path.join(source_dir, "main.py"),
        )
        mtimes = {}
        for path in paths:
            try:
                mtimes[path] = os.stat(path).st_mtime_ns
            except OSError as exc:
                self.log(f"Source watch: unable to inspect {path}: {exc}")
        return mtimes

    async def _watch_source_changes(self):
        known_mtimes = self._source_mtimes()
        while not self._restart_requested:
            await asyncio.sleep(2)
            current_mtimes = self._source_mtimes()
            if current_mtimes != known_mtimes:
                self._restart_requested = True
                self.log("Source code changed; restarting the bot.")
                await self._restart_process()
                return
            known_mtimes = current_mtimes

    def _user_join_field(self, user, *names):
        for name in names:
            value = getattr(user, name, None)
            if value is not None and value != "":
                return value
        return "unknown"

    async def _print_room_snapshot(self, reason="Room snapshot"):
        try:
            response = await self.highrise.get_room_users()
            members = getattr(response, "content", []) or []
        except Exception as exc:
            print(f"ROOM SNAPSHOT FAILED ({reason}): {exc}")
            return

        if not members:
            print(f"ROOM SNAPSHOT ({reason}): no users in the room")
            return

        lines = [f"ROOM SNAPSHOT ({reason})"]
        for room_user, _position in members:
            username = getattr(room_user, "username", "unknown")
            user_id = getattr(room_user, "id", "unknown")
            role = self.db.get_role(user_id) or "guest"
            lines.append(f"@{username} | ID: {user_id} | Role: {role}")
        print("\n".join(lines))

    async def on_user_join(self, user, position):
        self._restore_owner()
        print(f"JOINED: {user.username} | ID: {user.id}")
        await self._print_room_snapshot("after join")
        self.db.upsert_user(user.id, user.username)
        user_record = self.db.get_user(user.id) or {}
        welcome_name = user_record.get("nickname") or user.username
        compliment = await self._fetch_unique_text(
            lambda: "https://complimentr.com/api",
            lambda data: data.get("compliment") if isinstance(data, dict) else None,
        )
        message = (
            f"👋 @{welcome_name} is back. {compliment}"
            if compliment
            else self._fallback_lifecycle_message(USER_JOIN_FALLBACK, user=welcome_name)
        )
        if message:
            await self.highrise.chat(message)

    async def on_user_leave(self, user):
        self._restore_owner()
        is_bot = str(user.id) == str(getattr(self.highrise, "my_id", ""))
        if is_bot:
            self._cancel_roast_task()
            self._cancel_queue_rules_task()
        self.db.mark_room_left(user.id)
        self.emotes.stop_loop(user.id)
        if is_bot:
            advice = await self._fetch_unique_text(
                lambda: "https://api.adviceslip.com/advice",
                lambda data: (
                    data.get("slip", {}).get("advice")
                    if isinstance(data, dict) and isinstance(data.get("slip"), dict)
                    else None
                ),
            )
            message = (
                f"👋 I'm out. {advice}"
                if advice
                else self._fallback_lifecycle_message(BOT_LEAVE_FALLBACK)
            )
            if message:
                await self.highrise.chat(message)
            return
        user_record = self.db.get_user(user.id) or {}
        leave_name = user_record.get("nickname") or user.username
        message = (
            self._fallback_lifecycle_message(USER_LEAVE_FALLBACK, user=leave_name)
        )
        if message:
            await self.highrise.chat(message)

    async def on_tip(self, user, receiver, tip):
        self._restore_owner()

    async def on_emote(self, user, emote_id, receiver):
        self._restore_owner()

    async def on_chat(self, user, message):
        prefix = CONFIG["command_prefix"]
        self._restore_owner()
        self.db.upsert_user(user.id, user.username)
        self.db.increment(user.id, "messages")
        tele_response = await self._handle_tele_message(user, message)
        if tele_response is not None:
            await self.highrise.send_whisper(user.id, tele_response[:500])
            return
        clean = message.strip().lstrip("/!#").casefold()
        if clean in LOOP_EMOTES or clean in ONE_SHOT_EMOTES:
            ok, wait = self.check_cooldown(user.id, "emote")
            if not ok:
                await self.highrise.send_whisper(
                    user.id,
                    f"Slow down, {self.get_username(user.id)} ({wait}s)."
                )
                return
            response = await self.emotes.trigger_on_user(user.id, clean)
            if response:
                await self.highrise.chat(response[:500])
            return
        game_response = await self._handle_game_message(user, message)
        if game_response is not None:
            if game_response:
                await self.highrise.chat(game_response)
            return
        if str(user.id) in pending_watch and not message.startswith(CONFIG["command_prefix"]):
            await self._handle_pending_watch(user, message.strip())
            return
        if not message.startswith(prefix):
            return
        parts = message[len(prefix):].strip().split()
        if not parts:
            return
        command = parts[0].casefold()
        args = parts[1:]
        if command.startswith("@") and len(parts) > 1:
            command = parts[1].casefold()
            args = [parts[0]] + parts[2:]
        compact_choice = re.fullmatch(r"(kiss|marry|kill)([1-3])", command)
        if compact_choice:
            command = compact_choice.group(1)
            args = [compact_choice.group(2)] + args
        compact_outfit = re.fullmatch(r"outfit([1-9]|10)", command)
        if compact_outfit:
            command = "outfit"
            args = [compact_outfit.group(1)] + args
        alias = None if command in {"kiss", "marry", "kill"} else COMMAND_ALIASES.get(command)
        if alias:
            alias_parts = alias.split()
            command = alias_parts[0]
            args = alias_parts[1:] + args
        try:
            response = await self.dispatch(user, command, args)
        except (ValueError, KeyError, RuntimeError) as exc:
            response = f"Command failed: {exc}"
        if response:
            await self._send_response(user, response)

    async def dispatch(self, user, command, args):
        self.db.upsert_user(user.id, user.username)
        if command == "pg":
            self.mode = "pg"
            return "✅ PG mode — all clean, kid-friendly."
        if command == "18":
            self.mode = "18"
            return "🔞 18+ mode enabled."
        if command in {"truth", "dare", "insult", "roast"}:
            return await self._ai_command(user, command)
        if command == "help":
            return await self.cmd_help(user, args)
        if command in {"pingroom", "ping"}:
            await self._print_room_snapshot("manual ping")
            return "Room pinged. Check the terminal."
        if command == "profile":
            data = self.db.get_user(user.id) or {}
            return (f"{user.username}: {data.get('messages', 0)} messages, "
                    f"{data.get('emotes', 0)} emotes, {data.get('games_played', 0)} games.")
        if command in {"status", "uptime"}:
            uptime_seconds = max(0, int(time.monotonic() - self.started_at))
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            user_count = self.db.conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
            return (
                f"🟢 Online | Uptime: {hours}h {minutes}m {seconds}s | "
                f"Known users: {user_count}"
            )
        if command == "info":
            return await self.cmd_info(user, args)
        if command == "kick":
            return await self.cmd_kick(user.id, args)
        if command == "ban":
            return await self.cmd_ban(user.id, args)
        if command == "unban":
            return await self.cmd_unban(user.id, args)
        if command == "mute":
            return await self.cmd_mute(user.id, args)
        if command == "unmute":
            return await self.cmd_unmute(user.id, args)
        if command == "freeze":
            return await self.cmd_freeze(user.id, args)
        if command == "unfreeze":
            return await self.cmd_unfreeze(user.id, args)
        if command == "modlog":
            return await self.cmd_modlog(user.id, args)
        if command == "log":
            return self.cmd_log(user, args)
        if command == "recipe":
            return await self.cmd_recipe(user, args)
        if command == "play":
            if len(args) == 1 and args[0].casefold() == "21":
                return await self.cmd_play_21(user, args)
            return "Usage: !play 21"
        if command == "join":
            if self.blackjack.active and not self.blackjack.round_active:
                return await self.cmd_join_21(user, args)
            await self.highrise.send_whisper(
                user.id,
                "❌ No join window active. Type !play 21 to start a game.",
            )
            return None
        if command == "21":
            return await self.cmd_21_action(user, args)
        if command in {"hit", "stand", "show", "quit"}:
            if not self.blackjack.active or not self.blackjack.round_active:
                message = (
                    "❌ No active game. Type !play 21 to start one."
                    if command == "hit"
                    else "❌ No active game."
                )
                await self.highrise.send_whisper(user.id, message)
                return None
            return await self.cmd_21_action(user, [command])
        if command == "stop":
            return self._stop_emote(user)
        if command == "randomfact":
            return await self.cmd_randomfact(user, args)
        if command == "riddle":
            return await self.cmd_riddle(user, args)
        if command == "joke":
            return await self.cmd_joke(user, args)
        if command == "djoke":
            return await self.cmd_djoke(user, args)
        if command == "booktok":
            return await self.cmd_booktok(user, args)
        if command == "memes":
            return await self.cmd_memes(user, args)
        if command == "watch":
            return await self.cmd_watch(user, args)
        if command == "history":
            return await self.cmd_history(user, args)
        if command == "tictactoe":
            return await self.cmd_tictactoe(user, args)
        if command == "wordle":
            return await self.cmd_wordle(user, args)
        if command == "hangman":
            return await self.cmd_hangman(user, args)
        if command == "20questions":
            return await self.cmd_twenty_questions(user, args)
        if command == "charades":
            return await self.cmd_charades(user, args)
        if command == "emoji":
            return await self.cmd_emoji(user, args)
        if command == "wouldyourrather":
            return await self.cmd_would_you_rather(user, args)
        if command == "reaction":
            return await self.cmd_reaction(user, args)
        if command == "facts":
            return await self.cmd_facts(user, args)
        if command == "summon":
            return await self.cmd_summon(user, args)
        if command in {"punch", "slap", "hug"}:
            return await self.cmd_social_animation(user, command, args)
        if command == "kms":
            return await self.cmd_kms(user, args)
        if command == "kiss":
            if args and args[0].startswith("@"):
                return await self.cmd_social_animation(user, command, args)
            return await self.cmd_kms_choice(user, "kiss", args)
        if command == "marry":
            return await self.cmd_kms_choice(user, "marry", args)
        if command == "kill":
            return await self.cmd_kms_choice(user, "kill", args)
        if command == "oneword":
            if args:
                return await self.cmd_oneword_answer(user, args)
            return await self.cmd_oneword(user, args)
        if command == "skip":
            if self.oneword_active:
                return await self.cmd_oneword_skip(user)
            await self.highrise.send_whisper(user.id, "❌ Nothing to skip.")
            return None
        if command == "balance":
            return f"{user.username} has {self._balance(user.id)} coins."
        if command == "wallet":
            return await self.cmd_wallet(user, args)
        if command == "outfit":
            return await self.cmd_outfit(user, args)
        if command == "refresh":
            return await self.cmd_refresh(user, args)
        if command == "tipall":
            return await self.cmd_tipall(user, args)
        if command == "autotip":
            return await self.cmd_autotip(user, args)
        if command == "setowner":
            return await self.cmd_setowner(user, args)
        if command == "nickname":
            return await self.cmd_nickname(user, args)
        if command == "give":
            if args and args[0].startswith("@"):
                return await self._give_role(user, args)
            return self._give(user, args)
        if command == "remove":
            if args and args[0].startswith("@"):
                return await self._remove_role(user, args)
            return await self._remove_command(user, args)
        if command == "role":
            return self._role_command(user, args)
        if command == "whois":
            return await self._whois(user, args)
        if command == "top":
            rows = self.db.get_top_chatters(5)
            return " | ".join(f"{i + 1}. {row[0]}: {row[1]}" for i, row in enumerate(rows))
        if command == "roll":
            sides = self._positive_int(args[0], "Usage: !roll <sides>") if args else 6
            return f"{user.username} rolled {random.randint(1, sides)} (1-{sides})."
        if command == "flip":
            return await self.cmd_flip(user, args)
        if command == "heads":
            return await self.cmd_flip_choice(user, "heads")
        if command == "tails":
            return await self.cmd_flip_choice(user, "tails")
        if command == "coinflip":
            return f"{user.username}: {random.choice(('heads', 'tails'))}."
        if command == "truth":
            return await self.cmd_truth(user, args)
        if command == "dare":
            return await self.cmd_dare(user, args)
        if command == "rate":
            return await self.cmd_rate(user, args)
        if command == "who":
            return await self.cmd_who(user, args)
        if command == "subscribe":
            self.db.subscribe(user.id)
            return f"{user.username} subscribed."
        if command == "unsubscribe":
            self.db.unsubscribe(user.id)
            return f"{user.username} unsubscribed."
        if command == "tele":
            return await self._tele(user, args)
        if command == "grab":
            return await self._grab(user, args)
        if command == "bring":
            return await self._bring(user, args)
        if command == "telecord":
            return await self._telecord(user, args)
        if command == "mypos":
            return await self._mypos(user)
        if command == "setpos":
            return await self._setpos(user, args)
        if command == "create":
            return await self._create_command(user, args)
        if command == "remove":
            return await self._remove_command(user, args)
        if command in {"whisper", "dm"}:
            return await self._private_message(user, args)
        if command == "emote":
            return await self._emote(user, args)
        return f"Unknown command: !{command}. Try !help."

    async def _dispatch(self, user, command, args):
        return await self.dispatch(user, command, args)

    def _balance(self, user_id):
        row = self.db.get_user(user_id) or {}
        return int(row.get("coins", 0) or 0)

    def _positive_int(self, value, error):
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(error)
        if number < 1:
            raise ValueError(error)
        return number

    def _give(self, user, args):
        if len(args) != 2:
            return "Usage: !give <user_id> <amount>"
        amount = self._positive_int(args[1], "Amount must be a positive whole number.")
        if self._balance(user.id) < amount:
            return "You do not have enough internal coins."
        target = args[0]
        self.db.upsert_user(target)
        self.db.update_user(user.id, coins=self._balance(user.id) - amount)
        self.db.update_user(target, coins=self._balance(target) + amount)
        return f"{user.username} gave {amount} coins to {target}."

    def _stop_emote(self, user):
        emote_name = self.active_emotes.get(user.id)
        if not emote_name:
            return "⏹️ No emote is playing."
        self.emotes.stop_loop(user.id)
        return f"⏹️ Stopped {emote_name} on @{user.username}."

    async def _emote(self, user, args):
        if not args:
            return "Usage: !emote <name>"
        name = args[0].casefold()
        emote_id = LOOP_EMOTES.get(name) or ONE_SHOT_EMOTES.get(name)
        if not emote_id:
            if name == "list":
                return "Emotes: " + ", ".join(sorted(ALL_EMOTE_NAMES))
            return f"Unknown emote: {name}"
        target_id = await self._resolve_target(args[1] if len(args) > 1 else None)
        if len(args) > 1 and target_id is None:
            return f"Could not find user {args[1]} in this room."
        return await self.emotes.trigger_on_user(target_id or user.id, name)

    async def _private_message(self, user, args):
        if len(args) < 2:
            return "Usage: !whisper @user <message>"
        target_id = await self._resolve_target(args[0])
        if target_id is None:
            return f"Could not find user {args[0]} in this room."
        message = " ".join(args[1:]).strip()
        await self.highrise.send_whisper(target_id, message[:500])
        return "Private message sent."

    async def _get_user_position(self, user_id):
        try:
            response = self.highrise.get_room_users()
            if inspect.isawaitable(response):
                response = await response
        except TypeError:
            response = await self.highrise.get_room_users()
        for room_user, position in getattr(response, "content", []):
            if room_user.id == user_id:
                if all(hasattr(position, axis) for axis in ("x", "y", "z")):
                    return position
                return None
        return None

    async def _grab(self, user, args):
        if not self.has_permission(user.id, "vip"):
            return "You need VIP to use !grab."
        mentions = [value for value in args if value.startswith("@")]
        if not mentions:
            return "Usage: !grab @user @user @user"
        try:
            position = await self._get_user_position(user.id)
        except (ConnectionError, RuntimeError, ResponseError) as exc:
            self.log(f"Grab position error: {exc}")
            position = None
        if position is None:
            return "Couldn't get your position."

        sender_role = self.db.get_role(user.id)
        grabbed = []
        for mention in mentions:
            target_id = await self._resolve_target(mention)
            target_name = mention.lstrip("@")
            if target_id is None:
                continue
            target_role = self.db.get_role(target_id)
            if ROLE_PRIORITY.get(target_role, 0) >= ROLE_PRIORITY.get(sender_role, 0):
                continue
            try:
                await self.highrise.teleport(target_id, position)
            except (ConnectionError, RuntimeError, ResponseError, TypeError) as exc:
                self.log(f"Grab error for {target_name}: {exc}")
                continue
            grabbed.append(target_name)
        if not grabbed:
            return "Couldn't grab anyone. (Not found, or same/higher rank than you.)"
        return f"Grabbed: {', '.join(grabbed)}!"

    async def _bring(self, user, args):
        mentions = [value for value in args if value.startswith("@")]
        if not mentions:
            if not getattr(self, "webapi", None):
                return "Couldn't find your current room."
            try:
                user_data = await self.webapi.get_user(user.id)
            except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                self.log(f"Bring room lookup error: {exc}")
                return "Couldn't find your current room."
            room = getattr(user_data, "active_room", None)
            room_id = getattr(room, "id", None)
            if not room_id:
                return "You aren't in an active room right now."
            try:
                await self.highrise.move_user_to_room(self.highrise.my_id, room_id)
            except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                self.log(f"Bot room move error: {exc}")
                return "Bot couldn't join your current room."
            return f"Bot joined your room: {room_id}."
        if not self.has_permission(user.id, "vip"):
            return "You need VIP to use !bring."
        try:
            position = await self._get_user_position(user.id)
        except (ConnectionError, RuntimeError, ResponseError) as exc:
            self.log(f"Bring position error: {exc}")
            position = None
        if position is None:
            return "Couldn't get your position."

        brought = []
        for mention in mentions:
            target_id = await self._resolve_target(mention)
            target_name = mention.lstrip("@")
            if target_id is None:
                continue
            try:
                await self.highrise.teleport(target_id, position)
            except (ConnectionError, RuntimeError, ResponseError, TypeError) as exc:
                self.log(f"Bring error for {target_name}: {exc}")
                continue
            brought.append(target_name)
        if not brought:
            return "Couldn't bring anyone. (Users not found.)"
        return f"Brought: {', '.join(brought)}!"

    async def _telecord(self, user, args):
        target_id = user.id
        target_name = user.username
        coordinates = list(args)
        if args and args[0].startswith("@"):
            if not self.has_permission(user.id, "admin"):
                return "You need Admin to teleport someone to coordinates."
            target_id = await self._resolve_target(args[0])
            target_name = args[0].lstrip("@")
            if target_id is None:
                return f"Could not find user @{target_name} in this room."
            coordinates = args[1:]
        elif not self.has_permission(user.id, "mod"):
            return "You need Mod to use !telecord."
        if len(coordinates) < 3:
            return "Usage: !telecord [x] [y] [z]"
        try:
            x, y, z = (float(value) for value in coordinates[:3])
        except ValueError:
            return "Coordinates must be numbers. Example: !telecord 12.5 0 -30.2"
        try:
            await self.highrise.teleport(target_id, Position(x, y, z))
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Telecord error: {exc}")
            return "Teleport failed. Check coordinates."
        if target_id == user.id:
            return f"Teleported to ({x}, {y}, {z})."
        return f"Teleported {target_name} to ({x}, {y}, {z})."

    async def _mypos(self, user):
        try:
            position = await self._get_user_position(user.id)
        except (ConnectionError, RuntimeError, ResponseError) as exc:
            self.log(f"Position lookup error: {exc}")
            position = None
        if position is None:
            return "Couldn't get your position."
        return (
            f"Your position: ({position.x}, {position.y}, {position.z}) "
            f"Use !telecord {position.x} {position.y} {position.z} to teleport here later."
        )

    async def _give_role(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "You need Admin to give roles."
        if len(args) < 2 or not args[-1]:
            return "Usage: !give @user [@user ...] <role>"
        mentions = args[:-1]
        role = args[-1].casefold()
        if not 1 <= len(mentions) <= 100 or any(
            not mention.startswith("@") or len(mention) == 1 for mention in mentions
        ):
            return "Usage: !give @user [@user ...] <role> (1-100 users)"
        if role == "owner":
            return "There is no owner role. The owner is set in config."
        roles = self.config_roles()
        if role not in roles:
            return f"Role '{role}' doesn't exist. Available: {', '.join(roles)}"
        actor_role = self.db.get_role(user.id)
        is_config_owner = str(user.id) == str(self.config.get("owner_id", ""))
        if not is_config_owner and ROLE_PRIORITY.get(role, 0) > ROLE_PRIORITY.get(actor_role, 0):
            return f"You can't give {role} because it is higher than your role."
        if role in {"coowner", "seniormod"} and not is_config_owner:
            return f"Only the config owner can give {role}."
        targets = []
        seen_ids = set()
        for mention in mentions:
            target_name = mention[1:]
            target_id = await self._resolve_target(mention)
            if target_id is None:
                return f"Could not find user @{target_name} in this room."
            if target_id in seen_ids:
                continue
            if (
                target_id == self.config.get("owner_id")
                or self.db.get_role(target_id) == "owner"
            ):
                return "Cannot change the Owner's role."
            seen_ids.add(target_id)
            targets.append((target_id, target_name))
        for target_id, target_name in targets:
            self.db.upsert_user(target_id, target_name)
            self.db.set_role(target_id, role)
        names = ", ".join(target_name for _target_id, target_name in targets)
        return f"{names} {'is' if len(targets) == 1 else 'are'} now {role}."

    async def cmd_setowner(self, user, args):
        current_owner = self.config.get("owner_id", "")
        if current_owner and str(user.id) != str(current_owner):
            await self.highrise.send_whisper(
                user.id,
                "Owner transfer is locked. Only the current owner can transfer ownership.",
            )
            return None
        if not args:
            if current_owner:
                await self.highrise.send_whisper(
                    user.id,
                    "Owner is already set. Use !setowner @user from the current owner account to transfer it.",
                )
                return None
            target_id = user.id
            target_name = self.get_username(user.id)
        elif len(args) == 1 and args[0].startswith("@"):
            target_name = args[0][1:]
            target_id = await self._resolve_target(args[0])
            if target_id is None:
                await self.highrise.send_whisper(
                    user.id, f"User @{target_name} not found."
                )
                return None
        else:
            await self.highrise.send_whisper(user.id, "Usage: !setowner @user")
            return None
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        config["owner_id"] = str(target_id)
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=2)
            config_file.write("\n")
        self.config["owner_id"] = str(target_id)
        self.db.upsert_user(target_id, target_name)
        self._enforce_single_owner(target_id)
        await self.highrise.chat(f"👑 {target_name} is now the Owner.")
        return None

    async def _tip_gold(self, user_id, amount):
        denominations = (100, 50, 10, 5, 1)
        tip_names = {
            100: "gold_bar_100",
            50: "gold_bar_50",
            10: "gold_bar_10",
            5: "gold_bar_5",
            1: "gold_bar_1",
        }
        remaining = amount
        for denomination in denominations:
            while remaining >= denomination:
                result = await self.highrise.tip_user(user_id, tip_names[denomination])
                if result != "success":
                    return False, result
                remaining -= denomination
        return True, "success"

    async def _current_room_user_ids(self):
        response = await self.highrise.get_room_users()
        users = getattr(response, "content", [])
        bot_id = getattr(self.highrise, "my_id", None)
        return [
            room_user.id
            for room_user, _position in users
            if room_user.id != bot_id
        ]

    async def _current_room_user_names(self):
        response = await self.highrise.get_room_users()
        users = getattr(response, "content", [])
        bot_id = getattr(self.highrise, "my_id", None)
        return {
            room_user.id: room_user.username
            for room_user, _position in users
            if room_user.id != bot_id
        }

    async def cmd_tipall(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "❌ You need Admin+ to use !tipall."
        if len(args) != 1 or not args[0].isdigit():
            return "❌ Usage: !tipall <amount> (1-100 gold)"
        amount = int(args[0])
        if not 1 <= amount <= 100:
            return "❌ Tip amount must be between 1 and 100 gold."
        try:
            user_ids = await self._current_room_user_ids()
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Tip-all room lookup error: {exc}")
            return "❌ Couldn't get the users in the current room."
        try:
            user_names = await self._current_room_user_names()
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Tip-all username lookup error: {exc}")
            return "❌ Couldn't get the users in the current room."
        tipped = 0
        for user_id in user_ids:
            try:
                success, result = await self._tip_gold(user_id, amount)
            except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                self.log(f"Tip-all error for {user_id}: {exc}")
                success, result = False, str(exc)
            if not success:
                return f"❌ Tip-all stopped after {tipped} users: {result}."
            tipped += 1
            await self.highrise.chat(
                f"🪙 @{user_names.get(user_id, self.get_username(user_id))} was tipped {amount} gold."
            )
        return f"✅ Tipped {tipped} users {amount} gold each."

    async def _autotip_loop(self):
        while self.autotip_task is not None:
            await asyncio.sleep(self.autotip_interval)
            if self.autotip_task is None:
                return
            if self.autotip_index >= len(self.autotip_queue):
                try:
                    self.autotip_queue = await self._current_room_user_ids()
                except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                    self.log(f"Auto-tip room lookup error: {exc}")
                    continue
                self.autotip_index = 0
            if not self.autotip_queue:
                continue
            target_id = self.autotip_queue[self.autotip_index]
            self.autotip_index += 1
            try:
                success, result = await self._tip_gold(target_id, self.autotip_amount)
            except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                self.log(f"Auto-tip error for {target_id}: {exc}")
                success, result = False, str(exc)
            if not success:
                self.log(f"Auto-tip failed for {target_id}: {result}")
                continue
            try:
                user_names = await self._current_room_user_names()
            except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                self.log(f"Auto-tip username lookup error: {exc}")
                continue
            await self.highrise.chat(
                f"🪙 @{user_names.get(target_id, self.get_username(target_id))} was tipped {self.autotip_amount} gold."
            )

    async def cmd_autotip(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "❌ You need Admin+ to use !autotip."
        if len(args) == 1 and args[0].casefold() in {"off", "stop"}:
            if self.autotip_task is not None:
                self.autotip_task.cancel()
                self.autotip_task = None
            return "✅ Auto-tip stopped."
        if len(args) != 2 or not all(value.isdigit() for value in args):
            return "❌ Usage: !autotip <amount> <seconds> (amount 1-100)"
        amount, interval = (int(value) for value in args)
        if not 1 <= amount <= 100:
            return "❌ Tip amount must be between 1 and 100 gold."
        if interval < 1:
            return "❌ Auto-tip interval must be at least 1 second."
        try:
            queue = await self._current_room_user_ids()
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Auto-tip room lookup error: {exc}")
            return "❌ Couldn't get the users in the current room."
        if self.autotip_task is not None:
            self.autotip_task.cancel()
        self.autotip_amount = amount
        self.autotip_interval = interval
        self.autotip_queue = queue
        self.autotip_index = 0
        self.autotip_task = asyncio.current_task()
        self.autotip_task = asyncio.create_task(self._autotip_loop())
        return f"✅ Auto-tip enabled: {amount} gold every {interval} seconds, one user at a time."

    async def cmd_nickname(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "You need Admin to set nicknames."
        if len(args) < 2 or not args[0].startswith("@"):
            return "Usage: !nickname @user <nickname>"
        target_id = await self._resolve_target(args[0])
        target_name = args[0][1:]
        if target_id is None:
            return f"Could not find user @{target_name} in this room."
        nickname = " ".join(args[1:]).strip()
        if len(nickname) > 40:
            return "Nickname must be 40 characters or fewer."
        if not nickname:
            return "Usage: !nickname @user <nickname>"
        if target_id == self.config.get("owner_id") or self.db.get_role(target_id) == "owner":
            return "Cannot change the Owner's nickname."
        self.db.upsert_user(target_id, target_name)
        self.db.update_user(target_id, nickname=nickname)
        return f"{target_name}'s nickname is now {nickname}."

    async def _remove_role(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "You need Admin to remove roles."
        if len(args) < 2:
            return "Usage: !remove @user <role>"
        target_name = args[0].lstrip("@")
        target_id = await self._resolve_target(args[0])
        if target_id is None:
            return f"Could not find user @{target_name} in this room."
        self.db.upsert_user(target_id, target_name)
        role = args[1].casefold()
        if target_id == self.config.get("owner_id") or self.db.get_role(target_id) == "owner":
            return "Cannot change the Owner's role."
        current_role = self.db.get_role(target_id)
        if role != current_role:
            return f"{target_name} doesn't have {role}. They have: {current_role}."
        if ROLE_PRIORITY.get(role, 0) > ROLE_PRIORITY.get(self.db.get_role(user.id), 0):
            return f"You can't remove {role} because it is higher than your role."
        self.db.set_role(target_id, "guest")
        return f"{role} removed from {target_name}. They're now guest."

    def config_roles(self):
        return list(self.config.get("roles", {}).keys())

    def _role_command(self, user, args):
        if not args or args[0].casefold() == "list":
            grouped = defaultdict(list)
            for row in self.db.get_all_users():
                grouped[row["role"]].append(row["username"] or row["user_id"])
            lines = []
            for role in self.config_roles():
                if grouped[role]:
                    names = grouped[role][:10]
                    suffix = "..." if len(grouped[role]) > 10 else ""
                    lines.append(f"{role} ({len(grouped[role])}): {', '.join(names)}{suffix}")
            return "Roles:\n" + ("\n".join(lines) if lines else "No users recorded.")

        action = args[0].casefold()
        if action == "info" and len(args) >= 2:
            role = args[1].casefold()
            if role not in self.config.get("roles", {}):
                return f"Role '{role}' doesn't exist."
            members = sum(1 for row in self.db.get_all_users() if row["role"] == role)
            info = self.config["roles"][role]
            return (
                f"{role}\nPrivilege: {info.get('privilege', 'guest')}\n"
                f"Cost: {info.get('cost', 0)} internal coins\nMembers: {members}"
            )

        if action == "create":
            if not self.has_permission(user.id, "admin"):
                return "You need Admin."
            if len(args) != 2:
                return "Usage: !role create <name>"
            role = args[1].casefold()
            if role in self.config.get("roles", {}):
                return f"Role '{role}' already exists."
            self.config.setdefault("roles", {})[role] = {"privilege": "guest", "cost": 0}
            return f"Role '{role}' created."

        if action == "delete":
            if not self.has_permission(user.id, "admin"):
                return "You need Admin."
            if len(args) != 2:
                return "Usage: !role delete <name>"
            role = args[1].casefold()
            if role in {"owner", "coowner", "guest"}:
                return f"Can't delete '{role}'."
            if role not in self.config.get("roles", {}):
                return f"Role '{role}' doesn't exist."
            for row in self.db.get_all_users():
                if row["role"] == role and row["user_id"] != self.config.get("owner_id"):
                    self.db.set_role(row["user_id"], "guest")
            del self.config["roles"][role]
            return f"Role '{role}' deleted. Members demoted to guest."

        if action == "cost":
            if not self.has_permission(user.id, "admin"):
                return "You need Admin."
            if len(args) != 3 or not args[2].isdigit():
                return "Usage: !role cost <role> <amount>"
            role = args[1].casefold()
            if role not in self.config.get("roles", {}):
                return f"Role '{role}' doesn't exist."
            self.config["roles"][role]["cost"] = int(args[2])
            return f"{role} now costs {args[2]} internal coins."
        return "Usage: !role [list|info|create|delete|cost]"

    async def _whois(self, user, args):
        if not self.has_permission(user.id, "mod"):
            return "You need Mod."
        if len(args) != 1 or not args[0].startswith("@"):
            return "Usage: !whois @user"
        target_id = await self._resolve_target(args[0])
        if target_id is None:
            return f"Could not find user {args[0]} in this room."
        data = self.db.get_user(target_id)
        if not data:
            return f"No data for {args[0]}."
        return (
            f"{data['username'] or args[0]}\nRole: {data['role']}\n"
            f"Messages: {data['messages']}\nEmotes: {data['emotes']}\n"
            f"Time in room: {int(data['time_in_room'] // 3600)}h "
            f"{int((data['time_in_room'] % 3600) // 60)}m"
        )

    async def cmd_info(self, user, args):
        if len(args) > 1 or (args and not args[0].startswith("@")):
            await self.highrise.send_whisper(
                user.id, "❌ Usage: !info or !info @user"
            )
            return None

        if args:
            target_name = args[0][1:]
            target_id = await self._resolve_target(args[0])
            if target_id is None:
                await self.highrise.send_whisper(
                    user.id, f"❌ User @{target_name} not found."
                )
                return None
            profile_user = self.db.get_user(target_id)
            if not profile_user:
                await self.highrise.send_whisper(
                    user.id, f"❌ No data for {target_name}."
                )
                return None
        else:
            profile_user = self.db.get_user(user.id)
            if not profile_user:
                await self.highrise.send_whisper(
                    user.id, "❌ No data found for you yet."
                )
                return None

        first_seen = profile_user["first_seen"]
        if not args:
            join_time = self.db.mark_room_interaction(user.id)
        else:
            join_time = self.db.get_room_join_time(profile_user["user_id"])
        if join_time is None:
            room_duration = "Not in room"
        else:
            elapsed_seconds = max(0, int(time.time() - float(join_time)))
            room_days, remainder = divmod(elapsed_seconds, 86400)
            room_hours, room_remainder = divmod(remainder, 3600)
            room_minutes = room_remainder // 60
            room_seconds = room_remainder % 60
            room_duration = f"{room_days}d {room_hours}h {room_minutes}m {room_seconds}s"
        highrise_joined = "N/A"
        crew_name = "No crew"
        try:
            profile_response = await self.webapi.get_user(profile_user["user_id"])
            highrise_profile = getattr(profile_response, "user", profile_response)
            joined_at = getattr(highrise_profile, "joined_at", None)
            if joined_at:
                joined_dt = joined_at if isinstance(joined_at, datetime) else datetime.fromisoformat(
                    str(joined_at).replace("Z", "+00:00")
                )
                now = datetime.now(joined_dt.tzinfo) if joined_dt.tzinfo else datetime.now()
                account_seconds = max(0, int((now - joined_dt).total_seconds()))
                account_days = account_seconds // 86400
                highrise_joined = (
                    f"{account_days} day{'s' if account_days != 1 else ''}"
                )
            crew = getattr(highrise_profile, "crew", None)
            crew_name = getattr(crew, "name", None) or "No crew"
        except (AttributeError, TypeError, ValueError, OSError):
            pass
        username = profile_user["username"] or profile_user["user_id"]
        role = profile_user["role"] or "guest"
        role_emoji = {
            "owner": "👑", "coowner": "👑", "admin": "🛡️",
            "seniormod": "🛡️", "mod": "🛡️", "dj": "🎵",
            "vip": "⭐", "guest": "👤",
        }.get(role, "👤")
        profile = (
            f"{'=' * 30}\n"
            f"📋 PROFILE: {role_emoji} {username}\n"
            f"{'=' * 30}\n"
            f"👤 Role: {role_emoji} {role.upper()}\n"
            f"📅 Time playing Highrise: {highrise_joined}\n"
            f"⏰ Time in room: {room_duration}\n"
            f"👥 Crew: {crew_name}\n"
            f"💃 Emotes done: {profile_user['emotes']:,}\n"
            f"🃏 21 wins: {profile_user.get('blackjack_wins', 0)}\n"
            f"📅 First seen: {first_seen or 'N/A'}\n"
            f"🕐 Last seen: {profile_user['last_seen'] or 'N/A'}\n"
            f"{'=' * 30}"
        )
        await self.highrise.send_whisper(user.id, profile)
        return None

    async def _fetch_url(self, url):
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if "api.themoviedb.org" in url and response.status != 200:
                        print(f"TMDB error: {response.status}")
                    response.raise_for_status()
                    return _decode_api_value(await response.json())
        except Exception as error:
            if "api.themoviedb.org" in url:
                print(f"TMDB exception: {error}")
            raise

    async def _generate_ai(self, prompt, command):
        system = R18_SYSTEM if self.mode == "18" else PG_SYSTEM
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://text.pollinations.ai",
                    json={
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "model": "openai",
                        "seed": random.randint(1, 999999999),
                        "jsonMode": False,
                        "private": True,
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        text = (await response.text()).strip()
                        if text:
                            return text
        except Exception as exc:
            self.log(f"AI {command} request failed: {exc}")
        return "⚠️ Couldn't generate that, try again."

    async def _ai_command(self, user, command):
        prompts = {
            "truth": f"Give {user.username} a funny truth question for a party game.",
            "dare": f"Give {user.username} a funny dare for a party game. Keep it doable in a group chat.",
            "insult": f"Write a funny insult for {user.username}. Make it creative and unexpected.",
            "roast": f"Write a savage roast for {user.username}. Make it punchy and funny.",
        }
        text = await self._generate_ai(prompts[command], command)
        prefixes = {"truth": "🎤", "dare": "🎯", "insult": "😏", "roast": "🔥"}
        return f"{prefixes[command]} {user.username}:\n{text}"

    async def _fetch_unique_text(self, request_factory, extractor, transform=None):
        for _attempt in range(5):
            try:
                data = await self._fetch_url(request_factory())
                text = extractor(data)
                if not isinstance(text, str) or not text.strip():
                    continue
                text = html.unescape(text).strip()
                content = transform(text) if transform else text
                if content in sent_items:
                    continue
                sent_items.add(content)
                return content
            except Exception:
                continue
        return None

    def _claim_content(self, content):
        content = html.unescape(str(content)).strip()
        if not content or content in sent_items:
            return False
        sent_items.add(content)
        return True

    def _game_busy(self):
        return bool(active_games)

    def _game_start_error(self):
        return "⏳ That game is already in progress!"

    async def _get_game_word(self, length, fallback, min_length=None, max_length=None):
        for _attempt in range(5):
            try:
                data = await self._fetch_url(
                    f"https://random-word-api.vercel.app/api/word?length={length}"
                )
                word = data[0] if isinstance(data, list) and data else None
                if not isinstance(word, str):
                    continue
                word = html.unescape(word).strip().casefold()
                if not word.isalpha():
                    continue
                if min_length is not None and len(word) < min_length:
                    continue
                if max_length is not None and len(word) > max_length:
                    continue
                if self._claim_content(word):
                    return word
            except Exception:
                continue
        return random.choice(fallback)

    @staticmethod
    def _tic_grid(board):
        cells = [board.get(index, str(index)) for index in range(1, 10)]
        return (
            f"{cells[0]} | {cells[1]} | {cells[2]}\n"
            "---------\n"
            f"{cells[3]} | {cells[4]} | {cells[5]}\n"
            "---------\n"
            f"{cells[6]} | {cells[7]} | {cells[8]}"
        )

    @staticmethod
    def _tic_winner(board):
        for line in ((1, 2, 3), (4, 5, 6), (7, 8, 9), (1, 4, 7),
                     (2, 5, 8), (3, 6, 9), (1, 5, 9), (3, 5, 7)):
            values = [board.get(index) for index in line]
            if values[0] and values.count(values[0]) == 3:
                return values[0]
        return None

    async def cmd_tictactoe(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        if len(args) != 1 or not args[0].startswith("@"):
            return "Usage: !tictactoe @user"
        player_id = await self._resolve_target(args[0])
        if player_id is None:
            player_id = args[0].lstrip("@")
        active_games["tictactoe"] = {
            "player_id": player_id, "player_name": args[0], "board": {}
        }
        return "Tic Tac Toe! You are X, I am O.\n" + self._tic_grid({})

    async def cmd_wordle(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        word = await self._get_game_word(5, WORDLE_FALLBACK)
        active_games["wordle"] = {"word": word, "attempts": 0}
        return "🔤 Wordle! I'm thinking of a 5-letter word. Guess it!"

    @staticmethod
    def _hangman_state(state):
        return " ".join(letter if letter in state["guessed"] else "_" for letter in state["word"])

    @staticmethod
    def _hangman_art(wrong):
        stages = (
            "",
            "   ___\n  |\n  |\n  |\n  |",
            "   ___\n  |  |\n  |  O\n  |\n  |",
            "   ___\n  |  |\n  |  O\n  | /\n  |",
            "   ___\n  |  |\n  |  O\n  | /|\\\n  |",
            "   ___\n  |  |\n  |  O\n  | /|\\\n  | / \\",
            "   ___\n  |  |\n  |  x\n  | /x\\\n  | /",
            "   ___\n  |  |\n  |  x\n  | /x\\\n  | / \\",
            "   ___\n  |  |\n  |  💀\n  | /x\\\n  | / \\",
        )
        return stages[min(wrong, 8)]

    async def _get_hangman_word(self):
        for _attempt in range(5):
            try:
                length = random.randint(5, 9)
                data = await self._fetch_url(
                    f"https://random-word-api.vercel.app/api/word?length={length}"
                )
                word = data[0] if isinstance(data, list) and data else None
                if not isinstance(word, str):
                    continue
                word = html.unescape(word).strip().casefold()
                if word.isalpha() and 5 <= len(word) <= 9 and word not in sent_items:
                    return word
            except Exception:
                continue
        available = [word for word in HANGMAN_FALLBACK if word not in sent_items]
        return random.choice(available) if available else None

    async def _get_hangman_hint(self, word):
        try:
            data = await self._fetch_url(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word, safe='')}"
            )
            definition = data[0]["meanings"][0]["definitions"][0]["definition"]
            definition = html.unescape(str(definition)).strip()
            return definition[:77] + "..." if len(definition) > 80 else definition
        except Exception:
            return "mystery"

    async def cmd_hangman(self, user, args):
        if "hangman" in active_games:
            return "⏳ Hangman is already in progress!"
        if self._game_busy():
            return self._game_start_error()
        word = await self._get_hangman_word()
        if word is None:
            return ""
        hint = await self._get_hangman_hint(word)
        active_games["hangman"] = {"word": word, "hint": hint, "guessed": set(), "wrong": 0}
        state = active_games["hangman"]
        return (
            f"🔤 Hangman!\n📖 Hint: {hint}\n"
            f"🔡 The word has {len(word)} letters. Guess a letter!\n"
            f"{self._hangman_state(state)}"
        )

    async def cmd_twenty_questions(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        word = await self._get_game_word(5, WORDLE_FALLBACK)
        active_games["20questions"] = {"word": word, "questions": 0}
        return "🤔 I'm thinking of something. You have 20 yes/no questions. Go!"

    async def cmd_charades(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        word = await self._get_game_word(6, COMMON_NOUNS)
        clues = {
            "guitar": "It has strings. You strum it. It makes music.",
            "bicycle": "It has two wheels. You ride it with pedals.",
            "rocket": "It flies into space and blasts off.",
            "dragon": "A legendary creature that breathes fire.",
            "banana": "A yellow fruit that monkeys love.",
        }
        clue = clues.get(word, "It's a thing you'd find in a familiar place.")
        active_games["charades"] = {"word": word, "task": None}
        active_games["charades"]["task"] = asyncio.create_task(
            self._game_timeout("charades", 60, f"⏰ Time's up. It was: {word}")
        )
        return f"🎭 Charades! I'm describing something. Clue: {clue}"

    async def cmd_emoji(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        unused = [pair for pair in EMOJI_GUESSES if pair[0] not in sent_items]
        emoji, answer = random.choice(unused or EMOJI_GUESSES)
        sent_items.add(emoji)
        active_games["emoji"] = {"emoji": emoji, "answer": answer, "task": None}
        active_games["emoji"]["task"] = asyncio.create_task(
            self._game_timeout("emoji", 45, f"⏰ Time's up. It was: {answer}")
        )
        return f"🔮 What am I? {emoji}"

    async def cmd_would_you_rather(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        question = None
        for url in (
            "https://wouldyourratherapi.vercel.app/api/random",
            "https://api.wouldyourrather.com/random",
        ):
            try:
                data = await self._fetch_url(url)
                if isinstance(data, dict):
                    option_a = data.get("option1") or data.get("choice1")
                    option_b = data.get("option2") or data.get("choice2")
                    question_text = data.get("question") or data.get("wouldYouRather")
                    if option_a and option_b:
                        question = (question_text or f"Would you rather choose {option_a} or {option_b}?", option_a, option_b)
                        break
            except Exception:
                continue
        if question is None:
            question = random.choice(WYR_FALLBACK)
        active_games["wouldyourrather"] = {"votes_a": 0, "votes_b": 0, "task": None}
        active_games["wouldyourrather"]["task"] = asyncio.create_task(
            self._game_timeout("wouldyourrather", 30, None)
        )
        return f"⚖️ {question[0]}\nA) {question[1]}\nB) {question[2]}\nType A or B to vote!"

    async def cmd_reaction(self, user, args):
        if self._game_busy():
            return self._game_start_error()
        state = {"phase": "ready", "started": 0, "task": None}
        active_games["reaction"] = state
        state["task"] = asyncio.create_task(self._reaction_start())
        return "⚡ Get ready..."

    async def _reaction_start(self):
        await asyncio.sleep(random.uniform(2, 5))
        state = active_games.get("reaction")
        if not state:
            return
        state["phase"] = "go"
        state["started"] = time.time()
        await self.highrise.chat("🚀 GO!")
        await asyncio.sleep(10)
        if active_games.get("reaction") is state:
            del active_games["reaction"]
            await self.highrise.chat("⏰ Nobody reacted. I win by default.")

    async def _game_timeout(self, name, seconds, message):
        await asyncio.sleep(seconds)
        state = active_games.pop(name, None)
        if state and message:
            await self.highrise.chat(message)
        elif state and name == "wouldyourrather":
            a = state["votes_a"]
            b = state["votes_b"]
            winner = "A" if a > b else "B" if b > a else "Nobody"
            await self.highrise.chat(f"📊 Results: A ({a}) vs B ({b}). {winner} wins!")

    async def _handle_game_message(self, user, message):
        text = message.strip()
        if not active_games:
            return None
        if "reaction" in active_games:
            state = active_games["reaction"]
            if state["phase"] == "go":
                reaction_time = time.time() - state["started"]
                del active_games["reaction"]
                if state.get("task"):
                    state["task"].cancel()
                return f"🏆 @{user.username} won with a reaction time of {reaction_time:.2f} seconds!"
            return ""
        if text.startswith(CONFIG["command_prefix"]):
            return None
        if "riddle" in active_games:
            return self._handle_riddle_message(user, text)
        if "tictactoe" in active_games:
            return self._handle_tictactoe_message(user, text)
        if "wordle" in active_games:
            return self._handle_wordle_message(user, text)
        if "hangman" in active_games:
            return self._handle_hangman_message(user, text)
        if "20questions" in active_games:
            return self._handle_twenty_message(user, text)
        if "charades" in active_games:
            return self._handle_answer_game("charades", user, text)
        if "emoji" in active_games:
            return self._handle_answer_game("emoji", user, text)
        if "wouldyourrather" in active_games and text.casefold() in {"a", "b"}:
            state = active_games["wouldyourrather"]
            state["votes_a" if text.casefold() == "a" else "votes_b"] += 1
            return ""
        return ""

    def _handle_riddle_message(self, user, text):
        normalized = text.casefold().strip()
        if (
            len(normalized) < 2
            or normalized.isdigit()
            or normalized in {"hi", "hey", "hello", "yo"}
        ):
            return ""
        state = active_games["riddle"]
        if normalized == state["answer"].casefold().strip():
            del active_games["riddle"]
            return f'🧠 @{user.username} solved it! The answer was "{state["answer"]}".'
        state["guesses_remaining"] -= 1
        if state["guesses_remaining"] == 0:
            del active_games["riddle"]
            return f"💀 Out of guesses! The answer was: {state['answer']}"
        return f"❌ @{user.username} is wrong. {state['guesses_remaining']} guesses left."

    def _handle_tictactoe_message(self, user, text):
        state = active_games["tictactoe"]
        if str(user.id) != str(state["player_id"]) or text not in "123456789":
            return ""
        spot = int(text)
        if spot in state["board"]:
            return "❌ That spot is taken. Try another."
        state["board"][spot] = "X"
        if self._tic_winner(state["board"]):
            del active_games["tictactoe"]
            return self._tic_grid(state["board"]) + f"\n🏆 @{user.username} wins!"
        available = [index for index in range(1, 10) if index not in state["board"]]
        if available:
            state["board"][random.choice(available)] = "O"
        winner = self._tic_winner(state["board"])
        if winner:
            del active_games["tictactoe"]
            return self._tic_grid(state["board"]) + "\n🏆 Bot wins!"
        if len(state["board"]) == 9:
            del active_games["tictactoe"]
            return self._tic_grid(state["board"]) + "\n🤝 It's a draw!"
        return self._tic_grid(state["board"])

    def _handle_wordle_message(self, user, text):
        state = active_games["wordle"]
        guess = text.casefold()
        if len(guess) != 5 or not guess.isalpha():
            return ""
        state["attempts"] += 1
        feedback = []
        for index, letter in enumerate(guess):
            feedback.append("🟩" if letter == state["word"][index] else "🟨" if letter in state["word"] else "⬛")
        result = f"{' '.join(guess.upper())} → {' '.join(feedback)}"
        if guess == state["word"]:
            del active_games["wordle"]
            return result + f"\n🎉 @{user.username} got it in {state['attempts']} tries! The word was {state['word']}."
        if state["attempts"] >= 10:
            del active_games["wordle"]
            return result + f"\n⏰ Out of guesses. The word was {state['word']}."
        return result

    def _handle_hangman_message(self, user, text):
        state = active_games["hangman"]
        guess = text.casefold()
        if len(guess) != 1 or not guess.isalpha():
            return ""
        if guess in state["guessed"]:
            return "Already guessed that."
        state["guessed"].add(guess)
        if guess in state["word"]:
            response = f"{self._hangman_state(state)}\n✅ Correct!"
            if all(letter in state["guessed"] for letter in state["word"]):
                del active_games["hangman"]
                sent_items.add(state["word"])
                return response + f"\n🎉 @{user.username} solved it! The word was {state['word']}."
            return response
        state["wrong"] += 1
        response = f"{self._hangman_art(state['wrong'])}\n{self._hangman_state(state)}\n❌ Wrong! ({state['wrong']}/8)"
        if state["wrong"] >= 8:
            del active_games["hangman"]
            sent_items.add(state["word"])
            return response + f"\n💀 8 wrong guesses. The word was {state['word']}."
        return response

    def _handle_twenty_message(self, user, text):
        state = active_games["20questions"]
        if text.casefold() == state["word"]:
            del active_games["20questions"]
            return f"🎉 @{user.username} got it! It was {state['word']}."
        if not text.endswith("?"):
            return ""
        state["questions"] += 1
        answer = "Yes" if any(part in text.casefold() for part in state["word"].split()) else "No"
        if state["questions"] >= 20:
            del active_games["20questions"]
            return f"{answer}\n⏰ Out of questions. It was: {state['word']}"
        return answer

    def _handle_answer_game(self, name, user, text):
        state = active_games[name]
        if text.casefold() != state["word" if name == "charades" else "answer"].casefold():
            return ""
        del active_games[name]
        if state.get("task"):
            state["task"].cancel()
        return f"🎉 @{user.username} got it! It was {state['word'] if name == 'charades' else state['answer']}."

    async def cmd_recipe(self, user, args):
        try:
            if args:
                cuisine = " ".join(args).strip().lower()
                encoded_cuisine = urllib.parse.quote(cuisine, safe="")
                url = (
                    "https://www.themealdb.com/api/json/v1/1/"
                    f"filter.php/c={encoded_cuisine}"
                )
            else:
                url = "https://www.themealdb.com/api/json/v1/1/random.php"

            data = await self._fetch_url(url)
            meals = data.get("meals") if isinstance(data, dict) else None
            if not meals:
                await self.highrise.send_whisper(
                    user.id,
                    "❌ Couldn't find any recipes. Try a different cuisine or try again.",
                )
                return None

            meal_id = random.choice(meals).get("idMeal")
            if not meal_id:
                raise ValueError("Recipe response did not include a meal ID.")
            detail_url = (
                "https://www.themealdb.com/api/json/v1/1/"
                f"lookup.php?i={urllib.parse.quote(str(meal_id), safe='')}"
            )
            detail_data = await self._fetch_url(detail_url)
            detailed_meals = (
                detail_data.get("meals")
                if isinstance(detail_data, dict)
                else None
            )
            if not detailed_meals:
                await self.highrise.send_whisper(
                    user.id,
                    "❌ Couldn't load recipe details. Try again.",
                )
                return None

            meal = detailed_meals[0]
            ingredients = []
            for index in range(1, 21):
                ingredient = (meal.get(f"strIngredient{index}") or "").strip()
                measure = (meal.get(f"strMeasure{index}") or "").strip()
                if ingredient:
                    ingredients.append(
                        f"• {ingredient}{f' ({measure})' if measure else ''}"
                    )

            recipe = (
                f"{'=' * 35}\n"
                f"🍳 RECIPE: {meal.get('strMeal', 'N/A')}\n"
                f"{'=' * 35}\n"
                f"🌍 Cuisine: {meal.get('strCategory', 'N/A')}\n"
                f"📍 Area: {meal.get('strArea', 'N/A')}\n"
                f"📸 Image: {meal.get('strMealThumb', 'N/A')}\n"
                f"🔗 Source: {meal.get('strSource') or 'N/A'}\n"
                f"\n🛒 INGREDIENTS:\n"
                f"{chr(10).join(ingredients) or '• N/A'}\n"
                f"\n👨‍🍳 INSTRUCTIONS:\n"
                f"{meal.get('strInstructions') or 'N/A'}\n"
                f"{'=' * 35}"
            )
            if not self._claim_content(recipe):
                return None
            await self.highrise.chat(recipe)
            return None
        except Exception as exc:
            self.log(f"Recipe error: {exc}")
            await self.highrise.send_whisper(
                user.id,
                "❌ Couldn't load a recipe. Try again in a few seconds.",
            )
            return None

    async def cmd_randomfact(self, user, args):
        try:
            if args:
                category = " ".join(args).strip().lower()
                encoded_category = urllib.parse.quote(category, safe="")
                url = (
                    "https://uselessfacts.jsph.pl/api/v2/facts/random"
                    f"?language=en&category={encoded_category}"
                )
            else:
                url = "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"

            fact_text = await self._fetch_unique_text(
                lambda: url,
                lambda data: data.get("text") if isinstance(data, dict) and "error" not in data else None,
            )
            if fact_text is None:
                await self.highrise.send_whisper(
                    user.id,
                    "❌ Couldn't load a fact. Try again in a few seconds.",
                )
                return None

            fact = (
                f"{'=' * 35}\n"
                "🧠 RANDOM FACT\n"
                f"{'=' * 35}\n"
                f"{fact_text}\n"
                f"{'=' * 35}"
            )
            await self.highrise.chat(fact)
            return None

        except Exception as exc:
            self.log(f"Fact error: {exc}")
            await self.highrise.send_whisper(
                user.id,
                "❌ Couldn't load a fact. Try again in a few seconds.",
            )
            return None

    async def cmd_facts(self, user, args):
        try:
            fact_text = await self._fetch_unique_text(
                lambda: "https://uselessfacts.jsph.pl/api/v2/facts/random",
                lambda data: data.get("text") if isinstance(data, dict) else None,
            )
            if fact_text is None:
                raise ValueError("Fact response did not include text.")
            await self.highrise.chat(f"💡 {fact_text}")
        except Exception as exc:
            self.log(f"Facts error: {exc}")
            await self.highrise.chat(
                "❌ Couldn't fetch a fact right now. Try again later."
            )
        return None

    async def cmd_riddle(self, user, args):
        if "riddle" in active_games:
            return "⏳ A riddle is already in progress!"
        if self._game_busy():
            return self._game_start_error()
        urls = (
            "https://riddles.io/api/riddles/random",
            "https://riddles-api.vercel.app/random",
        )
        for attempt in range(5):
            try:
                data = await self._fetch_url(urls[0] if attempt == 0 else urls[1])
                if isinstance(data, dict):
                    riddle = data.get("riddle")
                    answer = data.get("answer")
                if not isinstance(riddle, str) or not riddle.strip():
                    continue
                if not isinstance(answer, str) or not answer.strip():
                    continue
                riddle = html.unescape(riddle).strip()
                answer = html.unescape(answer).strip()
                content = f"{riddle}\n{answer}"
                if content in sent_items:
                    continue
                sent_items.add(content)
                active_games["riddle"] = {
                    "answer": answer,
                    "guesses_remaining": 6,
                    "start_time": time.time(),
                }
                return f"🧩 {riddle}\nYou have 6 guesses. Type your answer in chat!"
            except Exception:
                continue

        fallback_riddle, fallback_answer = random.choice(RIDDLE_FALLBACK)
        content = f"{fallback_riddle}\n{fallback_answer}"
        sent_items.add(content)
        active_games["riddle"] = {
            "answer": fallback_answer,
            "guesses_remaining": 6,
            "start_time": time.time(),
        }
        return f"🧩 {fallback_riddle}\nYou have 6 guesses. Type your answer in chat!"

    async def cmd_joke(self, user, args):
        for _attempt in range(5):
            try:
                data = await self._fetch_url(
                    "https://official-joke-api.appspot.com/random_joke"
                )
                setup = data.get("setup") if isinstance(data, dict) else None
                punchline = data.get("punchline") if isinstance(data, dict) else None
                if not isinstance(setup, str) or not isinstance(punchline, str):
                    continue
                setup = html.unescape(setup).strip()
                punchline = html.unescape(punchline).strip()
                content = f"{setup}\n{punchline}"
                if not setup or not punchline or content in sent_items:
                    continue
                sent_items.add(content)
                return f"😂 {content}"
            except Exception:
                continue
        setup, punchline = random.choice(JOKE_FALLBACK)
        content = f"{html.unescape(setup)}\n{html.unescape(punchline)}"
        sent_items.add(content)
        return f"😂 {content}"

    async def cmd_djoke(self, user, args):
        joke = await self.cmd_joke(user, args)
        return joke.replace("😂", "🖤", 1) if joke else joke

    async def fetch_booktok(self):
        data = await self._fetch_url(
            "https://recite.onrender.com/random/quote-from-db"
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        quote = data[0].get("quote", "")
        author = data[0].get("author", "Unknown")
        book = data[0].get("book", "Unknown")
        if not isinstance(quote, str) or not quote.strip():
            return None
        quote = html.unescape(quote).strip()
        author = html.unescape(str(author)).strip() or "Unknown"
        book = html.unescape(str(book)).strip() or "Unknown"
        return f'📖 "{quote}"\n— {author}, *{book}*'

    async def cmd_booktok(self, user, args):
        for _attempt in range(5):
            try:
                content = await self.fetch_booktok()
                if not content or content in sent_items:
                    continue
                sent_items.add(content)
                return content
            except Exception:
                continue
        return "❌ Couldn't fetch a quote. Try again."

    async def cmd_memes(self, user, args):
        for _attempt in range(5):
            try:
                data = await self._fetch_url("https://meme-api.com/gimme")
                image_url = data.get("url") if isinstance(data, dict) else None
                title = data.get("title") if isinstance(data, dict) else None
                subreddit = data.get("subreddit") if isinstance(data, dict) else None
                if not all(isinstance(value, str) and value.strip() for value in (image_url, title, subreddit)):
                    continue
                image_url = html.unescape(image_url).strip()
                title = html.unescape(title).strip()
                subreddit = html.unescape(subreddit).strip()
                if image_url in sent_items:
                    continue
                sent_items.add(image_url)
                caption = f"🖼️ r/{subreddit}: {title}"
                send_image = getattr(self.highrise, "send_image", None)
                if send_image is not None:
                    await send_image(image_url, caption=caption)
                else:
                    await self.highrise.chat(f"{caption}\n{image_url}")
                return None
            except Exception:
                continue
        await self.highrise.chat("❌ Couldn't fetch a meme. Try again.")
        return None

    async def cmd_watch(self, user, args):
        if args:
            await self._handle_pending_watch(user, " ".join(args))
            return None
        pending_watch[str(user.id)] = True
        return (
            "🎬 What genre are you in the mood for?\n"
            "Action | Drama | Comedy | Horror | Sci-Fi | Thriller | Romance | "
            "Fantasy | Animation | Documentary | Marvel | Disney | DC"
        )

    async def _handle_pending_watch(self, user, genre):
        normalized = genre.casefold().strip()
        if normalized not in WATCH_GENRES:
            await self.highrise.chat("❌ Pick a genre from the list above.")
            return
        try:
            if normalized in WATCH_GENRE_IDS:
                data = await self._fetch_url(
                    "https://api.themoviedb.org/3/discover/movie?"
                    "api_key=510da5917461c6982db4ecb94696e030"
                    f"&with_genres={WATCH_GENRE_IDS[normalized]}"
                    "&sort_by=popularity.desc&language=en-US"
                )
                results = data.get("results", []) if isinstance(data, dict) else []
                choices = [item for item in results[:50] if isinstance(item, dict)]
            else:
                query = normalized

                async def fetch_choices(search_query):
                    encoded = urllib.parse.quote(search_query, safe="")
                    data = await self._fetch_url(
                        "https://api.themoviedb.org/3/search/multi?"
                        "api_key=510da5917461c6982db4ecb94696e030"
                        f"&query={encoded}&language=en-US"
                    )
                    results = data.get("results", []) if isinstance(data, dict) else []
                    return [
                        item for item in results
                        if isinstance(item, dict) and item.get("media_type") in {"movie", "tv"}
                    ]

                choices = await fetch_choices(query)
                if len(choices) < 3:
                    choices = await fetch_choices(f"{query} movies")
            if not choices:
                raise ValueError("No watch results")
            item = random.choice(choices)
            title = item.get("title") or item.get("name") or "Unknown"
            date = item.get("release_year") or item.get("release_date") or item.get("first_air_date") or ""
            year = str(date)[:4] if date else "N/A"
            overview = html.unescape(str(item.get("overview") or "No overview available."))
            if len(overview) > 200:
                overview = overview[:197] + "..."
            await self.highrise.chat(
                f"🎬 I suggest: **{html.unescape(str(title))}** ({year})\n"
                f"⭐ {item.get('vote_average', 0)}/10\n📝 {overview}"
            )
            pending_watch.pop(str(user.id), None)
        except Exception:
            pending_watch.pop(str(user.id), None)
            await self.highrise.chat("❌ Couldn't fetch a suggestion. Try again.")

    async def fetch_history(self, subject):
        import aiohttp

        subject = subject.strip()
        search_url = (
            "https://en.wikipedia.org/w/api.php?action=opensearch&search="
            f"{urllib.parse.quote(subject)}&limit=1&namespace=0&format=json"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        print(f"DEBUG history search: status {response.status}")
                        return "❌ Couldn't find info on that. Try a different subject."
                    search_data = await response.json()
                    if (
                        not isinstance(search_data, list)
                        or len(search_data) < 2
                        or not search_data[1]
                    ):
                        return "❌ Couldn't find info on that. Try a different subject."
                    page_title = search_data[1][0]
                    print(f"DEBUG history: found page '{page_title}'")
        except Exception as error:
            print(f"DEBUG history search error: {error}")
            return "❌ Couldn't find info on that. Try a different subject."

        page_title_encoded = urllib.parse.quote(
            page_title.replace(" ", "_"), safe="_"
        )
        summary_url = (
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            f"{page_title_encoded}"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    summary_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        print(f"DEBUG history summary: status {response.status}")
                        return "❌ Couldn't find info on that. Try a different subject."
                    data = await response.json()
                    title = data.get("title", "Unknown")
                    description = data.get("description", "")
                    extract = html.unescape(data.get("extract", ""))
                    if len(extract) > 400:
                        extract = extract[:400] + "..."
                    return f"📜 **{title}**\n{description}\n\n{extract}"
        except Exception as error:
            print(f"DEBUG history summary error: {error}")
            return "❌ Couldn't find info on that. Try a different subject."

    async def cmd_history(self, user, args):
        if not args:
            return "Usage: `!history (subject)` e.g. `!history ww2`"
        return await self.fetch_history(" ".join(args))

    def _truth_dare_ready(self):
        if self.highrise is None:
            return False
        for attribute in ("connected", "is_connected"):
            state = getattr(self.highrise, attribute, None)
            if isinstance(state, bool) and not state:
                return False
        return True

    async def fetch_truth(self, user, target_name=None):
        try:
            async with self._api_lock:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.truthordarebot.xyz/v1/truth?rating=R",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as response:
                        if response.status != 200:
                            await self.highrise.chat("Could not fetch. Try again.")
                            return
                        data = await response.json()
                        question = data["question"][:200]
            if target_name:
                await self.highrise.chat(
                    f"🎯 TRUTH for {target_name}: {question}"
                )
            else:
                await self.highrise.chat(f"🎯 TRUTH: {question}")
        except Exception as exc:
            print(f"TRUTH ERROR: {exc}")
            await self.highrise.chat("Could not fetch. Try again.")

    async def fetch_dare(self, user, target_name=None):
        try:
            async with self._api_lock:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.truthordarebot.xyz/api/dare?rating=R",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as response:
                        if response.status != 200:
                            await self.highrise.chat("Could not fetch. Try again.")
                            return
                        data = await response.json()
                        dare = data["question"][:200]
            if target_name:
                await self.highrise.chat(f"⚡ DARE for {target_name}: {dare}")
            else:
                await self.highrise.chat(f"⚡ DARE: {dare}")
        except Exception as exc:
            print(f"DARE ERROR: {exc}")
            await self.highrise.chat("Could not fetch. Try again.")

    async def cmd_dare(self, user, args):
        if args and not args[0].startswith("@"):
            await self.highrise.send_whisper(user.id, "Usage: `!dare` or `!dare @user`")
            return None
        target_name = args[0].lstrip("@") if args else None
        return await self.fetch_dare(user, target_name)

    async def cmd_truth(self, user, args):
        if args and not args[0].startswith("@"):
            await self.highrise.send_whisper(user.id, "Usage: `!truth` or `!truth @user`")
            return None
        target_name = args[0].lstrip("@") if args else None
        return await self.fetch_truth(user, target_name)

    async def cmd_rate(self, user, args):
        if len(args) != 1 or not args[0].startswith("@"):
            return "Usage: `!rate @user`"
        target = args[0].lstrip("@")
        rating = random.randint(1, 10)
        comment = None
        comment = await self._fetch_unique_text(
            lambda: "https://complimentr.com/api",
            lambda data: data.get("compliment") if isinstance(data, dict) else None,
        )
        comment = comment.strip() if isinstance(comment, str) and comment.strip() else random.choice(RATE_FALLBACK)
        return f"⭐ @{target}: {rating}/10 — {comment}"

    async def cmd_who(self, user, args):
        if len(args) != 1 or not args[0].startswith("@"):
            return "Usage: `!who @user`"
        target = args[0].lstrip("@")
        comment = await self._fetch_unique_text(
            lambda: "https://complimentr.com/api",
            lambda data: data.get("compliment") if isinstance(data, dict) else None,
            transform=str.capitalize,
        )
        comment = comment.strip() if isinstance(comment, str) and comment.strip() else random.choice(WHO_FALLBACK)
        return f"🔍 Who is @{target}? {comment}"

    async def _fetch_kms_names(self):
        self.log("KMS: fetching from TMDB...")
        api_key = self.config.get("tmdb_key") or os.environ.get("TMDB_KEY", "")
        if not api_key:
            self.log("KMS ERROR: tmdb_key not found in config.json")
            return None
        try:
            url = (
                "https://api.themoviedb.org/3/person/popular?"
                f"api_key={urllib.parse.quote(api_key, safe='')}"
                "&language=en-US&page=1"
            )
            data = await self._fetch_url(url)
            people = data.get("results", []) if isinstance(data, dict) else []
            self.log(f"KMS: got {len(people)} people")
            males = [p["name"] for p in people if p.get("gender") == 1 and p.get("name")]
            females = [p["name"] for p in people if p.get("gender") == 2 and p.get("name")]
            if len(males) < 2 or not females:
                return None
            pick = random.choice(("mmf", "mfm", "fmm"))
            if pick == "mmf":
                options = random.sample(males, 2) + random.sample(females, 1)
            elif pick == "mfm":
                m1 = random.choice(males)
                m2 = random.choice([male for male in males if male != m1])
                options = [m1, random.choice(females), m2]
            else:
                options = random.sample(females, 1) + random.sample(males, 2)
            random.shuffle(options)
            self.log(f"KMS: options = {options}")
            return options
        except Exception as exc:
            self.log(f"KMS fetch error: {type(exc).__name__}: {exc}")
            return None

    async def cmd_social_animation(self, user, command, args):
        if len(args) != 1 or not args[0].startswith("@"):
            return f"Usage: !{command} @user"

        target = args[0]
        actor = f"@{user.username}"
        stages = {
            "punch": (
                f"👊 {actor} punched {target} in the face!",
                f"👊 {actor} punched {target} in the face! {target} is flying back...",
                f"💀 {target} hit the ground hard.",
            ),
            "slap": (
                f"🖐️ {actor} slapped {target}!",
                f"🖐️ {actor} slapped {target}! {target} is spinning...",
                f"😵 {target} is dizzy and collapsed.",
            ),
            "kiss": (
                f"😘 {actor} kissed {target}!",
                f"😘 {actor} kissed {target}! {target}'s face is turning red...",
                f"🥰 {target} swooned and fell over.",
            ),
            "hug": (
                f"🤗 {actor} hugged {target}!",
                f"🤗 {actor} hugged {target}! {target} can't breathe...",
                f"😮‍💨 {target} was crushed and toppled over.",
            ),
        }[command]

        message_id = await self.highrise.chat(stages[0])
        for stage in stages[1:]:
            await asyncio.sleep(1)
            edit_message = getattr(self.highrise, "edit_message", None)
            if message_id is not None and edit_message is not None:
                await edit_message(message_id, stage)
            else:
                await self.highrise.chat(stage)
        return None

    async def cmd_summon(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "❌ You don't have permission to use this command."
        if len(args) != 1 or not args[0].startswith("@"):
            return "Usage: `!summon @user`"

        target_name = args[0].lstrip("@")
        target_id = await self._resolve_target(args[0])
        if target_id is None:
            return "❌ Couldn't summon that user. Are they in the same room?"
        try:
            bot_position = await self._get_user_position(self.highrise.my_id)
            if bot_position is None:
                raise RuntimeError("Bot position unavailable")
            await self.highrise.teleport(target_id, bot_position)
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Summon error for {target_name}: {exc}")
            return "❌ Couldn't summon that user. Are they in the same room?"
        _record_admin_action(user.username, "summoned", target_name)
        return f"⚡ **@{target_name}** was summoned to my location."

    def cmd_log(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "❌ You don't have permission to use this command."
        entries = admin_log[-30:]
        if not entries:
            return "📋 No admin actions logged yet."
        return "```\n" + "\n".join(entries) + "\n```"

    async def cmd_outfit(self, user, args):
        if len(args) != 1 or not args[0].isdigit() or not 1 <= int(args[0]) <= 10:
            return "Usage: !outfit1 through !outfit10"
        outfit = OUTFITS[int(args[0])]
        if not BASE_ITEMS:
            self.log("Outfit warning: BASE_ITEMS is empty; cannot apply a full outfit.")
            return "❌ Couldn't apply that outfit. Item may not be in inventory."
        try:
            inventory = await self.highrise.get_inventory()
            inventory_ids = {
                getattr(item, "id", None)
                for item in getattr(inventory, "items", [])
            }
            clothing_items = []
            for item in outfit["items"]:
                if item.id not in inventory_ids:
                    self.log(f"Outfit warning: item {item.id} is not in inventory; skipping it.")
                    continue
                clothing_items.append(item)
            full_outfit = BASE_ITEMS + clothing_items
            result = await self.highrise.set_outfit(full_outfit)
            if result is not None:
                return "❌ Couldn't apply that outfit. Item may not be in inventory."
        except Exception:
            return "❌ Couldn't apply that outfit. Item may not be in inventory."
        return f"👕 Outfit changed: **{outfit['name']}**!"

    async def cmd_kms(self, user, args):
        if self.kms_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ A KMS game is already in progress. Wait for it to finish.",
            )
            return None
        options = await self._fetch_kms_names()
        if not options:
            await self.highrise.send_whisper(
                user.id,
                "❌ Couldn't load celebrity names. Try again in a few seconds.",
            )
            return None
        self.kms_options = options
        self.kms_active = True
        self.kms_player = user.id
        self.kms_kiss = None
        self.kms_marry = None
        self.kms_kill = None
        self.kms_round = 0
        names = "\n".join(
            f"{index}. {name}" for index, name in enumerate(self.kms_options, 1)
        )
        await self.highrise.chat(
            f"💋💍🔪 KISS MARRY KILL! {self.get_username(user.id)}\n\n"
            f"{names}\n\nType !kiss [1/2/3] for who you'd kiss."
        )
        return None

    async def cmd_kms_choice(self, user, choice_type, args):
        if not self.kms_active:
            await self.highrise.send_whisper(
                user.id, "❌ No KMS game in progress. Type !kms to start one."
            )
            return None
        if user.id != self.kms_player:
            await self.highrise.send_whisper(user.id, "❌ Not your KMS game.")
            return None
        choice = " ".join(args).strip()
        if choice_type == "kiss" and self.kms_round == 0:
            if not choice.isdigit() or not 1 <= int(choice) <= 3:
                await self.highrise.send_whisper(user.id, "❌ Type !kiss [1/2/3]")
                return None
            self.kms_kiss = self.kms_options[int(choice) - 1]
            self.kms_round = 1
            remaining = [name for name in self.kms_options if name != self.kms_kiss]
            await self.highrise.chat(
                f"💋 Kiss: {self.kms_kiss}\n\nNow who do you MARRY?\n"
                f"1. {remaining[0]}\n2. {remaining[1]}\n\nType !marry [1/2]"
            )
        elif choice_type == "marry" and self.kms_round == 1:
            if not choice.isdigit() or not 1 <= int(choice) <= 2:
                await self.highrise.send_whisper(user.id, "❌ Type !marry [1/2]")
                return None
            remaining = [name for name in self.kms_options if name != self.kms_kiss]
            self.kms_marry = remaining[int(choice) - 1]
            self.kms_round = 2
            killer = next(
                name for name in remaining if name != self.kms_marry
            )
            await self.highrise.chat(
                f"💍 Marry: {self.kms_marry}\n\n🔪 That leaves... {killer}.\n\n"
                "Type !kill to confirm. No takebacks."
            )
        elif choice_type == "kill" and self.kms_round == 2:
            self.kms_kill = next(
                name for name in self.kms_options
                if name not in {self.kms_kiss, self.kms_marry}
            )
            await asyncio.sleep(1)
            await self.highrise.chat(
                f"💋💍🔪 KISS MARRY KILL — {self.get_username(user.id)}\n"
                f"{'=' * 30}\n"
                f"💋 Kiss: {self.kms_kiss}\n"
                f"💍 Marry: {self.kms_marry}\n"
                f"🔪 Kill: {self.kms_kill}\n"
                f"{'=' * 30}\nType !kms to play again!"
            )
            self.kms_active = False
            self.kms_player = None
            self.kms_options = []
            self.kms_kiss = None
            self.kms_marry = None
            self.kms_kill = None
            self.kms_round = 0
            self.db.increment(user.id, "games_played")
        else:
            next_step = (
                "kiss" if self.kms_round == 0
                else "marry" if self.kms_round == 1 else "kill"
            )
            expected_choices = 3 if self.kms_round == 0 else 2 if self.kms_round == 1 else 1
            await self.highrise.send_whisper(
                user.id, f"❌ Wrong step. Type !{next_step} [1/{expected_choices}]"
            )
        return None

    async def cmd_oneword(self, user, args):
        if self.oneword_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ A One Word game is already in progress. Wait for it to finish.",
            )
            return None
        self.oneword_active = True
        self.oneword_player = user.id
        self.oneword_letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.oneword_categories = random.sample(
            ONEWORD_CATEGORIES, self.oneword_max_rounds
        )
        self.oneword_round = 0
        self.oneword_score = 0
        category = self.oneword_categories[0]
        await self.highrise.chat(
            f"🔤 ONE WORD! {self.get_username(user.id)}\n"
            f"{'=' * 30}\n"
            f"🔡 Letter: {self.oneword_letter}\n"
            f"📋 {self.oneword_max_rounds} rounds. Each round is a new category.\n"
            f"{'=' * 30}\n\n"
            f"Round 1/{self.oneword_max_rounds}: {category.capitalize()}\n"
            f"Type a {category} that starts with '{self.oneword_letter}'.\n"
            "Type !skip to skip a round."
        )
        return None

    async def cmd_oneword_answer(self, user, args):
        if not self.oneword_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ No One Word game in progress. Type !oneword to start one.",
            )
            return None
        if user.id != self.oneword_player:
            await self.highrise.send_whisper(user.id, "❌ Not your game.")
            return None
        word = " ".join(args).strip().lower()
        if not word:
            await self.highrise.send_whisper(
                user.id, "❌ Type a word that starts with the letter."
            )
            return None
        if not word.startswith(self.oneword_letter.lower()):
            await self.highrise.chat(
                f"❌ '{word.capitalize()}' doesn't start with "
                f"'{self.oneword_letter}'. Try again!"
            )
            return None

        self.oneword_score += 1
        self.oneword_round += 1
        if self.oneword_round >= self.oneword_max_rounds:
            await asyncio.sleep(1)
            await self.highrise.chat(
                f"🔤 ONE WORD COMPLETE — {self.get_username(user.id)}\n"
                f"{'=' * 30}\n"
                f"🔡 Letter: {self.oneword_letter}\n"
                f"📊 Score: {self.oneword_score}/{self.oneword_max_rounds}\n"
                f"{'=' * 30}\nType !oneword to play again!"
            )
            self.oneword_active = False
            self.oneword_player = None
            self.db.increment(user.id, "games_played")
            if self.oneword_score >= 6:
                self.db.increment(user.id, "games_won")
            return None

        category = self.oneword_categories[self.oneword_round]
        await self.highrise.chat(
            f"✅ '{word.capitalize()}' — nice!\n"
            f"📊 Score: {self.oneword_score}/{self.oneword_max_rounds}\n\n"
            f"Round {self.oneword_round + 1}/{self.oneword_max_rounds}: "
            f"{category.capitalize()}\n"
            f"Type a {category} that starts with '{self.oneword_letter}'."
        )
        return None

    async def cmd_oneword_skip(self, user):
        if not self.oneword_active or user.id != self.oneword_player:
            return None
        self.oneword_round += 1
        if self.oneword_round >= self.oneword_max_rounds:
            await self.highrise.chat(
                f"🔤 ONE WORD COMPLETE — {self.get_username(user.id)}\n"
                f"{'=' * 30}\n"
                f"🔡 Letter: {self.oneword_letter}\n"
                f"📊 Score: {self.oneword_score}/{self.oneword_max_rounds}\n"
                f"{'=' * 30}\nType !oneword to play again!"
            )
            self.oneword_active = False
            self.oneword_player = None
            self.db.increment(user.id, "games_played")
            return None

        category = self.oneword_categories[self.oneword_round]
        await self.highrise.chat(
            f"⏭ Skipped.\n"
            f"📊 Score: {self.oneword_score}/{self.oneword_max_rounds}\n\n"
            f"Round {self.oneword_round + 1}/{self.oneword_max_rounds}: "
            f"{category.capitalize()}\n"
            f"Type a {category} that starts with '{self.oneword_letter}'."
        )
        return None

    async def cmd_wallet(self, user, args):
        try:
            wallet = await self.highrise.get_wallet()
            gold = 0
            for currency in wallet.content:
                if currency.type == "gold":
                    gold = currency.amount
            await self.highrise.send_whisper(
                user.id, f"💰 Bot wallet: {gold:,}g"
            )
        except Exception as exc:
            self.log(f"Wallet error: {exc}")
            await self.highrise.send_whisper(
                user.id, "❌ Couldn't check wallet."
            )
        return None

    async def cmd_flip(self, user, args):
        if self.flip_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ A flip is already in progress. Wait for it to finish.",
            )
            return None
        self.flip_active = True
        self.flip_player = user.id
        self.flip_choice = None
        await self.highrise.chat(
            f"🪙 {self.get_username(user.id)}, flip a coin! "
            "Type !heads or !tails to choose."
        )
        return None

    async def cmd_flip_choice(self, user, choice):
        if not self.flip_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ No flip in progress. Type !flip to start one.",
            )
            return None
        if user.id != self.flip_player:
            await self.highrise.send_whisper(
                user.id,
                "❌ Not your flip. Wait for the current one to finish.",
            )
            return None
        if self.flip_choice is not None:
            await self.highrise.send_whisper(
                user.id,
                "❌ You already chose. Waiting for the coin to land...",
            )
            return None

        self.flip_choice = choice
        await self.highrise.chat(f"🪙 {choice.capitalize()}! Flipping...")
        for _ in range(5):
            await asyncio.sleep(1.5)
            await self.highrise.chat("🪙")
        await asyncio.sleep(1)
        result = random.choice(("heads", "tails"))
        if result == self.flip_choice:
            await self.highrise.chat(
                f"🪙 It landed on {result.capitalize()}! "
                "You were right! 😄👍"
            )
            self.db.increment(user.id, "games_won")
        else:
            await self.highrise.chat(
                f"🪙 It landed on {result.capitalize()}... "
                "Unlucky! Try again next time. 😢"
            )
        self.db.increment(user.id, "games_played")
        self.flip_active = False
        self.flip_player = None
        self.flip_choice = None
        return None

    async def cmd_play_21(self, user, args):
        if self.blackjack.active:
            response = self.blackjack.join(user.id)
            await self.highrise.chat(response)
            return None

        self.blackjack.create()
        self.blackjack.join(user.id)
        await self.highrise.chat(
            "🃏 21 START! Type !join to get in. Starting in 8 seconds..."
        )
        asyncio.create_task(self._start_21_after_join_window(8))
        return None

    async def cmd_join_21(self, user, args):
        if not self.blackjack.active:
            await self.highrise.send_whisper(
                user.id,
                "❌ No active 21 game. Type !play 21 to start one.",
            )
            return None
        if self.blackjack.round_active:
            await self.highrise.send_whisper(
                user.id, "❌ Game already started. Too late to join."
            )
            return None
        await self.highrise.chat(self.blackjack.join(user.id))
        return None

    async def _start_21_after_join_window(self, seconds):
        await asyncio.sleep(seconds)
        if not self.blackjack.players:
            self.blackjack.active = False
            return
        await self._start_21_round()

    async def _start_21_round(self):
        if not self.blackjack.players:
            return
        self.blackjack.round_active = True
        self.blackjack.dealer_hand = [
            random.randint(1, 13), random.randint(1, 13)
        ]
        self.blackjack.dealer_total = self.blackjack._calc_total(
            self.blackjack.dealer_hand
        )
        for player in self.blackjack.players.values():
            player["hand"] = [random.randint(1, 13), random.randint(1, 13)]
            player["total"] = self.blackjack._calc_total(player["hand"])
            player["done"] = player["total"] >= 21
        if len(self.blackjack.players) == 1:
            player = next(iter(self.blackjack.players.values()))
            player_line = (
                f"Your cards: {self.blackjack._hand_str(player['hand'])} "
                f"= {player['total']}"
            )
        else:
            player_line = "\n".join(
                f"{self.get_username(user_id)}: "
                f"{self.blackjack._hand_str(player['hand'])} = {player['total']}"
                for user_id, player in self.blackjack.players.items()
            )
        await self.highrise.chat(
            "🃏 21 START!\n"
            f"Dealer: {self.blackjack._hand_str(self.blackjack.dealer_hand)} "
            f"= {self.blackjack.dealer_total}\n"
            f"{player_line}\n\n"
            "Type !hit to draw or !stand to stop.\n"
            "Bet: 10g"
        )

    async def _dealer_play(self):
        if not self.blackjack.round_active:
            return
        while self.blackjack.dealer_total < 17:
            card = random.randint(1, 13)
            self.blackjack.dealer_hand.append(card)
            self.blackjack.dealer_total = self.blackjack._calc_total(
                self.blackjack.dealer_hand
            )
            await asyncio.sleep(0)

        results = []
        for user_id, player in self.blackjack.players.items():
            name = self.get_username(user_id)
            if player["total"] > 21:
                results.append(f"😢 {name} loses. -10g")
            elif self.blackjack.dealer_total > 21:
                results.append(f"🏆 {name} wins! +10g")
                self.db.increment(user_id, "blackjack_wins")
            elif player["total"] > self.blackjack.dealer_total:
                results.append(f"🏆 {name} wins! +10g")
                self.db.increment(user_id, "blackjack_wins")
            elif player["total"] == self.blackjack.dealer_total:
                results.append(f"🤝 {name} pushes.")
            else:
                results.append(f"😢 {name} loses. -10g")
            self.db.increment(user_id, "games_played")
        await self.highrise.chat(
            f"🃏 Dealer has {self.blackjack.dealer_total}.\n"
            + "\n".join(results)
        )
        self.blackjack.round_active = False
        self.blackjack.active = False
        self.blackjack.players.clear()
        self.blackjack.dealer_hand = []
        self.blackjack.dealer_total = 0

    async def cmd_21_action(self, user, args):
        if not self.blackjack.active or not self.blackjack.round_active:
            await self.highrise.send_whisper(
                user.id,
                "❌ No active 21 game. Type !play 21 to start one.",
            )
            return None
        if user.id not in self.blackjack.players:
            await self.highrise.send_whisper(
                user.id,
                "❌ You're not in this game. Type !play 21 to join.",
            )
            return None
        action = " ".join(args).casefold().strip()
        if action == "hit":
            player = self.blackjack.players[user.id]
            if player["done"]:
                await self.highrise.send_whisper(user.id, "❌ You already stood.")
                return None
            await self.highrise.chat(self.blackjack.hit(user.id))
        elif action == "stand":
            await self.highrise.chat(self.blackjack.stand(user.id))
            if all(player["done"] for player in self.blackjack.players.values()):
                asyncio.create_task(self._dealer_play())
        elif action == "show":
            await self.highrise.chat(self.blackjack.show())
        elif action == "quit":
            await self.highrise.chat(self.blackjack.quit(user.id))
        else:
            await self.highrise.send_whisper(
                user.id,
                "❌ Usage: !21 hit / !21 stand / !21 show / !21 quit",
            )
        return None

    async def cmd_refresh(self, user, args):
        is_owner = str(user.id) == str(self.config.get("owner_id", ""))
        is_coowner = self.db.get_role(user.id) == "coowner"
        if not (is_owner or is_coowner):
            return "❌ Only the Owner or Co-Owner can restart the bot with !rf."
        self._restore_owner()
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
                loaded_config = json.load(config_file)
            if isinstance(loaded_config, dict):
                self.config.update(loaded_config)
        except (FileNotFoundError, OSError, ValueError):
            self.log("Refresh: config could not be reloaded; using current bot config.")
        self.db.upsert_user(user.id, user.username)
        self.log(f"Manual refresh triggered by {user.username} ({user.id})")
        self._restart_requested = True
        asyncio.create_task(self._restart_process())
        return "🔄 Disconnecting and restarting with the latest code..."

    async def _restart_process(self):
        if self._restart_requested and getattr(self, "_restart_task_started", False):
            return
        self._restart_task_started = True
        await asyncio.sleep(0.5)
        if self.autotip_task is not None:
            self.autotip_task.cancel()
            self.autotip_task = None
        self._cancel_roast_task()
        for user_id in list(self.emotes.loop_tasks):
            self.emotes.stop_loop(user_id)
        websocket = getattr(self.highrise, "ws", None)
        if websocket is not None:
            await websocket.close()
        self.db.conn.close()
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        os.execv(sys.executable, [sys.executable, main_path])

    async def cmd_help(self, user, args):
        topic = " ".join(args).casefold().strip() if args else ""
        if not topic:
            help_text = (
                f"{'=' * 35}\n"
                "📋 COMMANDS\n"
                f"{'=' * 35}\n"
                "🎵 Music: !play (song), !skip, !queue, !nowplaying\n"
                "💃 Emotes: type the emote name (e.g. ghostfloat)\n"
                "🃏 21: !play 21, !join, then !hit / !stand\n"
                "🎮 Games: !rps @user, !flip then !heads/!tails, !kms, !dice, !guess, !slots\n"
                "🔤 Word: !oneword = word game\n"
                "💰 Tips: !tip @user [amount], !top, !wallet\n"
                "🎁 Admin tips: !tipall <amount>, !autotip <amount> <seconds>\n"
                "🌀 Move: !tele X Y Z, !grab @user, !bring @user\n"
                "📊 Info: !info, !info @user, !lb, !stats\n"
                "🧠 Fun: !randomfact, !recipe, !wyr, !tord\n"
                "👑 Roles: !role, !buy role [name]\n"
                "🏷️ Nicknames: !nickname @user <nickname>\n"
                "📅 Daily: !daily, !streak\n"
                "⚙️ System: !rf / !refresh = refresh the bot\n"
                f"{'=' * 35}\n"
                "Type !help [topic] for specific help.\n"
                "Topics: 21, music, emotes, tips, roles, move, games\n"
            )
            await self.highrise.send_whisper(user.id, help_text)
            return None

        lookup = topic.lstrip("!").casefold()
        lookup = {
            "t": "tele",
            "teleport": "tele",
        }.get(lookup, lookup)
        key = lookup if lookup in HELP_TEXTS else next(
            (candidate for candidate in HELP_TEXTS if candidate.startswith(lookup)),
            None,
        )
        if key is None:
            await self.highrise.send_whisper(
                user.id,
                "❌ Unknown command. Type !help to see all commands.",
            )
            return None
        await self.highrise.send_whisper(
            user.id,
            f"📖 **!{key}**\n{HELP_TEXTS[key]}",
        )
        return None

        if topic in {"21", "blackjack", "hit", "stand"}:
            help_text = (
                f"{'=' * 35}\n"
                "🃏 HOW TO PLAY 21\n"
                f"{'=' * 35}\n"
                "1. Type !play 21 to start/join a game\n"
                "2. Type !join within 8 seconds to join\n"
                "3. You get 2 cards. Dealer gets 2 cards.\n"
                "4. Type !hit to draw another card\n"
                "5. Type !stand when you're done\n"
                "6. Wait for everyone to stand\n"
                "7. Dealer draws until 17+\n"
                "8. Closest to 21 without going over wins\n\n"
                "📌 Commands during the game:\n"
                "   !join = join during the 8-second window\n"
                "   !hit = draw a card\n"
                "   !stand = stop drawing\n"
                "   !show = see all cards\n"
                "   !quit = leave the game\n\n"
                "💰 Bet: 10g per round\n"
                f"{'=' * 35}"
            )
        elif topic in {"music", "play", "skip", "queue"}:
            help_text = (
                f"{'=' * 35}\n🎵 MUSIC\n{'=' * 35}\n"
                "!play (songname artist) = add song to queue\n"
                "!skip = skip current song (VIP+)\n"
                "!queue = see what's coming up\n"
                "!nowplaying = see what's playing\n"
                "!pause / !resume = pause/resume (VIP+)\n"
                "!shuffle = shuffle queue (VIP+)\n"
                "!loop / !loop off = loop current song (VIP+)\n"
                f"{'=' * 35}"
            )
        elif topic in {"emotes", "emote", "ghostfloat"}:
            help_text = (
                f"{'=' * 35}\n💃 EMOTES\n{'=' * 35}\n"
                "Type the emote name in chat: ghostfloat, macarena, dab, "
                "happy, sad, wave, hello, kiss, disco, moonwalk...\n\n"
                "Loop emotes: ghostfloat, chillin, shy, sleepy, tap, sit, "
                "aerobics, zombie, relaxed...\n\n"
                "!emote list = see all emotes\n!emote stop = stop your loop\n"
                f"{'=' * 35}"
            )
        elif topic in {"tips", "tip", "gold", "wallet"}:
            help_text = (
                f"{'=' * 35}\n💰 TIPS\n{'=' * 35}\n"
                "!tip @user [amount] = tip someone\n!top = see top tippers\n"
                "!wallet = bot's gold balance\n!tipme = how much you've tipped\n"
                "!get @user = how much they've tipped\n"
                "!tipall <amount> = tip everyone in the room (Admin+)\n"
                "!autotip <amount> <seconds> = fairly tip one user per interval (Admin+)\n"
                f"{'=' * 35}"
            )
        elif topic in {"roles", "role", "vip", "buy"}:
            help_text = (
                f"{'=' * 35}\n👑 ROLES\n{'=' * 35}\n"
                "!role = see all roles and members\n"
                "!buy role vip = buy VIP (100g)\n"
                "!info = see your profile and role\n\n"
                "Role order (low to high):\n"
                "   guest → vip → dj → mod → seniormod → admin → coowner\n"
                f"{'=' * 35}"
            )
        elif topic in {"move", "tele", "grab", "bring", "teleport"}:
            help_text = (
                f"{'=' * 35}\n🌀 MOVEMENT\n{'=' * 35}\n"
                "!tele X Y Z = teleport yourself (Admin+)\n"
                "!tele @user = bring them to you (VIP+)\n"
                "!tele @user X Y Z = teleport them (Co-Owner+)\n"
                "!grab @user @user = pull them to you (VIP+)\n"
                "!bring @user @user = pull them to you (VIP+)\n"
                "!here = come to the bot\n"
                f"{'=' * 35}"
            )
        elif topic in {"games", "game", "rps", "dice", "flip", "slots"}:
            help_text = (
                f"{'=' * 35}\n🎮 GAMES\n{'=' * 35}\n"
                "!play 21 = blackjack (then !hit / !stand)\n"
                "!rps @user rock = rock paper scissors\n"
                "!flip = coin flip (then type !heads or !tails)\n"
                "!kms = Kiss Marry Kill with 3 actors\n"
                "!dice 3 = roll 3 dice\n!guess start = number guessing game\n"
                "!slots 50 = slot machine (50g bet)\n!wyr = would you rather\n"
                "!tord = truth or dare\n"
                f"{'=' * 35}"
            )
        else:
            help_text = (
                f"❌ No help for '{topic}'. "
                "Try: 21, music, emotes, tips, roles, move, games"
            )
        await self.highrise.send_whisper(user.id, help_text)
        return None

    def _can_moderate(self, user_id):
        """Who CAN moderate: Owner, Co-Owner, Admin, Senior Mod, Mod."""
        if str(user_id) == str(self.config.get("owner_id", "")):
            return True
        return self.db.get_role(user_id) in ("coowner", "admin", "seniormod", "mod")

    def _is_protected(self, target_id):
        """Owner and Co-Owner cannot be moderated by anyone."""
        if str(target_id) == str(self.config.get("owner_id", "")):
            return True
        if self.db.get_role(target_id) == "owner":
            return True
        return self.db.get_role(target_id) in ("coowner",)

    def _moderation_target_allowed(self, user_id, target_id, target):
        if self._is_protected(target_id):
            if str(target_id) == str(self.config.get("owner_id", "")) or self.db.get_role(target_id) == "owner":
                return False, "❌ Can't moderate the Owner."
            return False, f"❌ Can't moderate {target} — they're a Co-Owner or Owner."
        target_role = self.db.get_role(target_id)
        user_role = self.db.get_role(user_id)
        if ROLE_PRIORITY.get(target_role, 0) >= ROLE_PRIORITY.get(user_role, 0):
            return False, "❌ Can't moderate someone the same rank or higher than you."
        return True, None

    def _format_duration(self, seconds):
        if seconds >= 86400:
            return f"{seconds // 86400}d"
        if seconds >= 3600:
            return f"{seconds // 3600}h {int((seconds % 3600) // 60)}m"
        if seconds >= 60:
            return f"{seconds // 60}m {seconds % 60}s"
        return f"{seconds}s"

    def parse_duration(self, value):
        match = re.fullmatch(r"(\d+)([smhd])", value.casefold().strip())
        if not match:
            raise ValueError("Duration must look like 30s, 5m, 1h, or 1d.")
        amount = int(match.group(1))
        multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
        if amount < 1:
            raise ValueError("Duration must be positive.")
        return amount * multiplier

    async def _moderation_target(self, user_id, args, usage):
        if not args or not args[0].startswith("@"):
            await self.highrise.send_whisper(user_id, usage)
            return None
        target = args[0][1:]
        target_id = await self._resolve_target(args[0])
        if not target_id:
            await self.highrise.send_whisper(user_id, f"❌ User @{target} not found.")
            return None
        allowed, error = self._moderation_target_allowed(user_id, target_id, target)
        if not allowed:
            await self.highrise.send_whisper(user_id, error)
            return None
        return target, target_id

    async def cmd_kick(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to kick.")
            return None
        resolved = await self._moderation_target(
            user_id, args, "❌ Usage: !kick @user [reason]"
        )
        if not resolved:
            return None
        target, target_id = resolved
        reason = " ".join(args[1:]).strip()
        mod_name = self.get_username(user_id)
        try:
            await self.highrise.moderate_room(target_id, "kick")
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Kick error: {exc}")
            await self.highrise.send_whisper(user_id, f"❌ Couldn't kick {target}.")
            return None
        suffix = f" Reason: {reason}" if reason else ""
        await self.highrise.chat(f"👢 {target} was kicked by {mod_name}.{suffix}")
        _record_admin_action(mod_name, "kicked", target)
        return None

    async def cmd_ban(self, user_id, args):
        if not self.has_permission(user_id, "admin"):
            await self.highrise.send_whisper(user_id, "❌ You need Admin+ to ban.")
            return None
        resolved = await self._moderation_target(
            user_id, args, "❌ Usage: !ban @user [reason]"
        )
        if not resolved:
            return None
        target, target_id = resolved
        reason = " ".join(args[1:]).strip()
        self.db.ban(target_id, reason)
        try:
            await self.highrise.moderate_room(target_id, "ban")
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Ban error: {exc}")
            await self.highrise.send_whisper(user_id, f"❌ Couldn't ban {target}.")
            return None
        suffix = f" Reason: {reason}" if reason else ""
        await self.highrise.chat(f"🔨 {target} was banned by {self.get_username(user_id)}.{suffix}")
        _record_admin_action(self.get_username(user_id), "banned", target)
        return None

    async def cmd_unban(self, user_id, args):
        if not self.has_permission(user_id, "admin"):
            await self.highrise.send_whisper(user_id, "❌ You need Admin+ to unban.")
            return None
        if not args or not args[0].startswith("@"):
            await self.highrise.send_whisper(user_id, "❌ Usage: !unban @user")
            return None
        target = args[0][1:]
        target_id = await self._resolve_target(args[0])
        if target_id:
            self.db.unban(target_id)
        await self.highrise.chat(f"✅ {target} has been unbanned.")
        return None

    async def cmd_mute(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to mute.")
            return None
        resolved = await self._moderation_target(
            user_id,
            args,
            "❌ Usage: !mute @user [duration]\nExamples: 30s, 5m, 1h, 1d",
        )
        if not resolved:
            return None
        target, target_id = resolved
        try:
            duration = self.parse_duration(args[1]) if len(args) > 1 else 300
        except ValueError as exc:
            await self.highrise.send_whisper(user_id, f"❌ {exc}")
            return None
        mod_name = self.get_username(user_id)
        self.db.mute(target_id, duration)
        try:
            await self.highrise.moderate_room(target_id, "mute", duration)
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Mute error: {exc}")
            await self.highrise.send_whisper(user_id, f"❌ Couldn't mute {target}.")
            return None
        await self.highrise.send_whisper(
            target_id,
            f"🔇 You were muted by {mod_name} for {self._format_duration(duration)}.",
        )
        await self.highrise.chat(
            f"🔇 {target} was muted by {mod_name} for {self._format_duration(duration)}."
        )
        _record_admin_action(mod_name, "muted", target)
        return None

    async def cmd_unmute(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to unmute.")
            return None
        if not args or not args[0].startswith("@"):
            await self.highrise.send_whisper(user_id, "❌ Usage: !unmute @user")
            return None
        target = args[0][1:]
        target_id = await self._resolve_target(args[0])
        if target_id:
            self.db.unmute(target_id)
            await self.highrise.send_whisper(target_id, "🔊 You have been unmuted.")
            _record_admin_action(self.get_username(user_id), "unmuted", target)
        await self.highrise.chat(f"🔊 {target} has been unmuted.")
        return None

    async def cmd_freeze(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to freeze.")
            return None
        resolved = await self._moderation_target(
            user_id, args, "❌ Usage: !freeze @user"
        )
        if not resolved:
            return None
        target, target_id = resolved
        self.db.freeze(target_id)
        await self.highrise.send_whisper(
            target_id, "🧊 You have been frozen. You can't move or emote."
        )
        await self.highrise.chat(f"🧊 {target} is frozen.")
        return None

    async def cmd_unfreeze(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to unfreeze.")
            return None
        if not args or not args[0].startswith("@"):
            await self.highrise.send_whisper(user_id, "❌ Usage: !unfreeze @user")
            return None
        target = args[0][1:]
        target_id = await self._resolve_target(args[0])
        if target_id:
            self.db.unfreeze(target_id)
            await self.highrise.send_whisper(target_id, "🔥 You have been unfrozen.")
        await self.highrise.chat(f"🔥 {target} is unfrozen.")
        return None

    async def cmd_modlog(self, user_id, args):
        if not self._can_moderate(user_id):
            await self.highrise.send_whisper(user_id, "❌ You need Mod+ to view mod log.")
            return None
        lines = [
            f"🔨 {entry['user_id']} — {entry['reason'] or 'no reason'} "
            f"({entry['banned_at']})"
            for entry in self.db.get_banned()[-10:]
        ]
        if not lines:
            await self.highrise.send_whisper(user_id, "📋 Mod log is empty.")
        else:
            await self.highrise.send_whisper(
                user_id, "📋 Recent Bans:\n" + "\n".join(lines)
            )
        return None

    def _enforce_single_owner(self, owner_id=None):
        owner_id = str(owner_id or self.config.get("owner_id", "")).strip()
        if owner_id:
            self.db.conn.execute(
                "UPDATE users SET role='guest' WHERE role='owner' AND user_id != ?",
                (owner_id,),
            )
            self.db.conn.execute(
                "UPDATE users SET role='owner' WHERE user_id=?",
                (owner_id,),
            )
        else:
            self.db.conn.execute("UPDATE users SET role='guest' WHERE role='owner'")
        self.db.conn.commit()
        if owner_id:
            self.config["owner_id"] = str(owner_id)
            self.config["roles"] = {
                **self.config.get("roles", {}),
                "owner": {"privilege": "host", "cost": 0},
            }
        return owner_id

    def has_permission(self, user_id, required_role):
        owner_id = self.config.get("owner_id", "")
        if str(user_id) == str(owner_id):
            return True
        if required_role == "owner":
            return False
        return ROLE_PRIORITY.get(self.db.get_role(user_id), 0) >= ROLE_PRIORITY.get(
            required_role, 0
        )

    def _migrate_legacy_owner_roles(self):
        legacy_role = "own" + "er"
        self.db.conn.execute(
            "UPDATE users SET role='coowner' WHERE role=?", (legacy_role,)
        )
        self.db.conn.commit()

    def _restore_owner(self):
        owner_id = self.config.get("owner_id", "")
        if owner_id:
            self.db.upsert_user(owner_id)
            self._enforce_single_owner(owner_id)
            self.log("Owner restored.")

    def _load_tele_data(self):
        default_data = {"user_ranks": {}, "teleports": {}, "tele_ranks": {}}
        if not os.path.exists(TELE_DATA_PATH):
            return default_data
        try:
            with open(TELE_DATA_PATH, "r", encoding="utf-8") as tele_file:
                data = json.load(tele_file)
        except (OSError, ValueError, TypeError):
            return default_data
        if not isinstance(data, dict):
            return default_data
        user_ranks = data.get("user_ranks", {})
        teleports = data.get("teleports", {})
        tele_ranks = data.get("tele_ranks", {})
        return {
            "user_ranks": {str(k).casefold(): str(v).casefold() for k, v in user_ranks.items()},
            "teleports": {
                str(name).casefold(): {
                    "x": float(point.get("x", 0.0)),
                    "y": float(point.get("y", 0.0)),
                    "z": float(point.get("z", 0.0)),
                    "facing": float(point.get("facing", 0.0)),
                }
                for name, point in teleports.items() if isinstance(point, dict)
            },
            "tele_ranks": {str(name).casefold(): str(rank).casefold() for name, rank in tele_ranks.items()},
        }

    def _sync_tele_state(self):
        self.tele_data.setdefault("user_ranks", {})
        self.tele_data.setdefault("teleports", {})
        self.tele_data.setdefault("tele_ranks", {})

        self.user_ranks = {
            str(name).casefold(): str(rank).casefold()
            for name, rank in self.tele_data.get("user_ranks", {}).items()
        }
        self.teleports = {
            str(name).casefold(): {
                "x": float(point.get("x", 0.0) if isinstance(point, dict) else 0.0),
                "y": float(point.get("y", 0.0) if isinstance(point, dict) else 0.0),
                "z": float(point.get("z", 0.0) if isinstance(point, dict) else 0.0),
                "facing": float(point.get("facing", 0.0) if isinstance(point, dict) else 0.0),
            }
            for name, point in self.tele_data.get("teleports", {}).items()
            if isinstance(point, dict)
        }
        self.tele_ranks = {
            str(name).casefold(): str(rank).casefold()
            for name, rank in self.tele_data.get("tele_ranks", {}).items()
        }

        self.tele_data["user_ranks"] = self.user_ranks
        self.tele_data["teleports"] = self.teleports
        self.tele_data["tele_ranks"] = self.tele_ranks

    def _save_tele_data(self):
        self._sync_tele_state()
        try:
            with open(TELE_DATA_PATH, "w", encoding="utf-8") as tele_file:
                json.dump(self.tele_data, tele_file, indent=2, sort_keys=True)
                tele_file.write("\n")
            print(f"DEBUG: saved {len(self.teleports)} teles to disk")
            with open(TELE_DATA_PATH, "r", encoding="utf-8") as tele_file:
                print(f"DEBUG: file contents = {tele_file.read()}")
        except OSError as exc:
            self.log(f"Failed to save tele_data.json: {exc}")

    def _rank_value(self, rank):
        normalized = str(rank or "guest").casefold().strip()
        if normalized not in TELE_RANK_PRIORITY:
            normalized = "guest"
        return TELE_RANK_PRIORITY[normalized]

    def _valid_rank(self, rank):
        return str(rank or "").casefold().strip() in TELE_RANK_PRIORITY

    def get_rank(self, username):
        if not username:
            return "guest"
        return self.user_ranks.get(str(username).lower(), "guest")

    def set_rank(self, username, rank):
        self.user_ranks[str(username).lower()] = str(rank).lower()
        self.tele_data["user_ranks"] = self.user_ranks

    def is_coowner_or_owner(self, username):
        return self.get_rank(username) in ("coowner", "owner")

    def _get_user_tele_rank(self, username):
        if not username:
            return "guest"
        return self.user_ranks.get(str(username).lower(), "guest")

    def _can_manage_teles(self, user):
        user_rank = self._get_user_tele_rank(user.username)
        if str(user.id) == str(self.config.get("owner_id", "")):
            return True
        if self.db.get_role(user.id) in {"owner", "coowner"}:
            return True
        return self._rank_value(user_rank) >= self._rank_value("coowner")

    def _can_remove_teles(self, user):
        user_rank = self._get_user_tele_rank(user.username)
        if str(user.id) == str(self.config.get("owner_id", "")):
            return True
        if self.db.get_role(user.id) in {"owner", "coowner", "admin"}:
            return True
        return self._rank_value(user_rank) >= self._rank_value("admin")

    async def _handle_named_teleport(self, user, name):
        self._sync_tele_state()
        teleports = self.tele_data.get("teleports", {})
        normalized_name = str(name).casefold()
        if normalized_name not in teleports:
            return None
        required_rank = self.tele_data.get("tele_ranks", {}).get(normalized_name, "guest")
        user_rank = self._get_user_tele_rank(user.username)
        if self._rank_value(user_rank) < self._rank_value(required_rank):
            return f"Teleport '{normalized_name}' requires rank {required_rank}. Your rank is {user_rank}."
        try:
            position = teleports[normalized_name]
            await self.highrise.teleport(
                user.id,
                Position(float(position.get("x", 0.0)), float(position.get("y", 0.0)), float(position.get("z", 0.0))),
            )
            return f"Teleported to {normalized_name}."
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError):
            return f"Teleport to '{normalized_name}' failed."

    async def _handle_tele_message(self, user, message):
        self._sync_tele_state()
        text = message.strip()
        if not text:
            return None
        if text.startswith("!"):
            parts = text[1:].split()
            if not parts:
                return None
            command = parts[0].casefold()
            args = parts[1:]
            if command == "tele":
                if args and args[0].casefold() == "list":
                    self._sync_tele_state()
                    teleports = self.tele_data.get("teleports", {})
                    self.teleports = teleports
                    print(f"DEBUG LIST: {self.teleports}")
                    if not teleports:
                        return "No teleports saved."
                    lines = []
                    for name in sorted(teleports):
                        required_rank = self.tele_data.get("tele_ranks", {}).get(name, "guest")
                        lines.append(f"{name}: {required_rank}")
                    return "Teleports:\n" + "\n".join(lines)
                if len(args) != 2 or args[0].startswith("@"):
                    return None
                name = args[0].strip().casefold()
                rank = str(args[1]).casefold().strip()
                if not self._valid_rank(rank):
                    return "Invalid rank. Use: guest, vip, dj, mod, seniormod, admin, coowner, owner."
                print(
                    f"DEBUG: username={user.username}, rank_in_dict={self.user_ranks.get(user.username.lower())}, "
                    f"is_coowner_or_owner={self.is_coowner_or_owner(user.username)}"
                )
                if not self.is_coowner_or_owner(user.username):
                    return "Only coowner or owner can create or update teleports."
                try:
                    self._sync_tele_state()
                    self.teleports = self.tele_data.setdefault("teleports", {})
                    self.tele_ranks = self.tele_data.setdefault("tele_ranks", {})
                    name = str(name).casefold()
                    if name not in self.teleports:
                        try:
                            position = await self._get_user_position(user.id)
                        except Exception:
                            return "Could not get your position."
                        if position is None:
                            return "Could not get your position."
                        self.teleports[name] = {
                            "x": float(getattr(position, "x", 0.0)),
                            "y": float(getattr(position, "y", 0.0)),
                            "z": float(getattr(position, "z", 0.0)),
                            "facing": float(getattr(position, "facing", 0.0)),
                        }
                        self.tele_ranks[name] = rank
                        self._save_tele_data()
                        return f"Teleport '{name}' created with required rank {rank}."
                    self.tele_ranks[name] = rank
                    self._save_tele_data()
                    return f"Teleport '{name}' updated to required rank {rank}."
                except Exception:
                    return "An error occurred while saving that teleport."
            if command == "setrank":
                if len(args) != 2:
                    return None
                username = args[0].strip()
                rank = str(args[1]).casefold().strip()
                if not self._valid_rank(rank):
                    return "Invalid rank. Use: guest, vip, dj, mod, seniormod, admin, coowner, owner."
                if not self.is_coowner_or_owner(user.username):
                    return "Only coowner or owner can set player ranks."
                self.set_rank(username, rank)
                self._save_tele_data()
                return f"Rank for {username} set to {rank}."
            if command == "remove" and len(parts) >= 3 and parts[1].casefold() == "tele":
                if not self._can_remove_teles(user):
                    return "Only admin, coowner, or owner can remove teleports."
                name = parts[2].strip().casefold()
                self._sync_tele_state()
                teleports = self.tele_data.get("teleports", {})
                print(f"DEBUG REMOVE: teleports dict = {teleports}")
                print(f"DEBUG REMOVE: looking for = '{name}'")
                print(f"DEBUG REMOVE: '{name}' in teleports = {name in teleports}")
                if name not in teleports:
                    return f"Teleport '{name}' not found."
                teleports.pop(name, None)
                self.tele_data.get("tele_ranks", {}).pop(name, None)
                self._save_tele_data()
                return f"Teleport '{name}' removed."
            return None

        if len(text.split()) == 1:
            name = text.casefold().strip()
            self._sync_tele_state()
            if name in self.tele_data.get("teleports", {}):
                return await self._handle_named_teleport(user, name)
            database_point = self.db.get_tele_point(name)
            if database_point is not None:
                try:
                    await self.highrise.teleport(
                        user.id,
                        Position(
                            float(database_point[0]),
                            float(database_point[1]),
                            float(database_point[2]),
                        ),
                    )
                    return f"Teleported to {name}."
                except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError):
                    return f"Teleport to '{name}' failed."
        return None

    async def on_whisper(self, user, message):
        response = await self._handle_tele_message(user, message)
        if response is not None:
            await self.highrise.send_whisper(user.id, response[:500])

    async def _tele(self, user, args):
        if len(args) == 1 and not args[0].startswith("@"):
            name = args[0].casefold().strip()
            if name == "list":
                points = self.db.get_all_tele_points()
                return "Teleport points: " + (", ".join(points) if points else "none")
            if not self._looks_like_number(name):
                if not self.has_permission(user.id, "vip"):
                    return "You need VIP to use !tele [name]."
                point = self.db.get_tele_point(name)
                if not point:
                    points = self.db.get_all_tele_points()
                    return (
                        f"'{name}' not found. Available: "
                        f"{', '.join(points) if points else 'none'}"
                    )
                try:
                    await self.highrise.teleport(
                        user.id,
                        Position(float(point[0]), float(point[1]), float(point[2])),
                    )
                except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                    self.log(f"Named teleport error: {exc}")
                    return "Teleport failed."
                return f"Teleported to {name}."
        if args and args[0].startswith("@"):
            target_name = args[0].lstrip("@")
            target_id = await self._resolve_target(args[0])
            if target_id is None:
                return f"Could not find user @{target_name} in this room."
            if len(args) == 1:
                if not self.has_permission(user.id, "vip"):
                    return "You need VIP to use !tele @user."
                try:
                    position = await self._get_user_position(user.id)
                    if position is None:
                        return f"Couldn't bring {target_name}."
                    await self.highrise.teleport(target_id, position)
                except (ConnectionError, RuntimeError, ResponseError, TypeError) as exc:
                    self.log(f"Bring teleport error: {exc}")
                    return f"Couldn't bring {target_name}."
                return f"Brought {target_name} to you."
            if len(args) == 4:
                if not self.has_permission(user.id, "coowner"):
                    return "You need Co-Owner to teleport someone to coordinates."
                coordinate_args = args[1:]
                try:
                    x, y, z = (float(value) for value in coordinate_args)
                except ValueError:
                    return "Coordinates must be numbers. Example: !tele @user 1 4 3"
                try:
                    await self.highrise.teleport(target_id, Position(x, y, z))
                except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                    self.log(f"Target coordinate teleport error: {exc}")
                    return f"Couldn't teleport {target_name}."
                return f"Teleported {target_name} to ({x}, {y}, {z})."
            if len(args) != 2:
                return "Usage: !tele @user or !tele @user X Y Z"
            if not self.has_permission(user.id, "mod"):
                return "You need Mod to teleport someone else."
            location = args[1].casefold()
        else:
            if len(args) == 3:
                if not self.has_permission(user.id, "admin"):
                    return "You need Admin to teleport to coordinates."
                try:
                    x, y, z = (float(value) for value in args)
                except ValueError:
                    return "Usage: !tele X Y Z (numbers only)"
                try:
                    await self.highrise.teleport(user.id, Position(x, y, z))
                except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
                    self.log(f"Coordinate teleport error: {exc}")
                    return "Teleport failed."
                return f"Teleported to ({x}, {y}, {z})."
            if not self.has_permission(user.id, "vip"):
                return "You need VIP to use !tele."
            target_id = user.id
            target_name = user.username
            if not args:
                points = self.db.get_all_tele_points()
                return "Teleport points: " + (", ".join(points) if points else "none")
            location = args[0].casefold()

        point = self.db.get_tele_point(location)
        if not point:
            points = self.db.get_all_tele_points()
            return (
                f"Teleport point '{location}' not found. Available: "
                f"{', '.join(points) if points else 'none'}"
            )
        try:
            await self.highrise.teleport(
                target_id, Position(float(point[0]), float(point[1]), float(point[2]))
            )
        except (ConnectionError, RuntimeError, ResponseError, TypeError, ValueError) as exc:
            self.log(f"Teleport error: {exc}")
            return "Teleport failed. Try again."
        return f"Teleported {target_name} to {location}."

    @staticmethod
    def _looks_like_number(value):
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True

    async def _create_command(self, user, args):
        if not args or args[0].casefold() != "tele":
            return "Usage: !create tele <name> <x> <y> <z>"
        if not self.has_permission(user.id, "admin"):
            return "You need Admin."
        if len(args) == 2:
            name = args[1].casefold().strip()
            if not name:
                return "Usage: !create tele <name>"
            if self.db.get_tele_point(name):
                return f"Teleport point '{name}' already exists. Use !remove tele {name} first."
            position = await self._get_user_position(user.id)
            if position is None:
                return "Couldn't get your position. Try again."
            coordinates = [position.x, position.y, position.z]
        elif len(args) == 5:
            name = args[1].casefold()
            try:
                coordinates = [float(value) for value in args[2:]]
            except ValueError:
                return "Coordinates must be numbers."
        else:
            return "Usage: !create tele <name> or !create tele <name> <x> <y> <z>"
        self.db.set_tele_point(name, *coordinates)
        return f"Teleport point '{name}' created."

    async def _remove_command(self, user, args):
        if len(args) != 2 or args[0].casefold() != "tele":
            return "Usage: !remove tele <name>"
        if not self.has_permission(user.id, "coowner"):
            return "You need Co-Owner."
        name = args[1].casefold()
        if not self.db.get_tele_point(name):
            return f"Teleport point '{name}' doesn't exist."
        self.db.delete_tele_point(name)
        return f"Teleport point '{name}' removed."

    async def _setpos(self, user, args):
        if not self.has_permission(user.id, "admin"):
            return "You need Admin."
        if len(args) != 1:
            return "Usage: !setpos <name>"
        response = await self.highrise.get_room_users()
        position = None
        for room_user, room_position in getattr(response, "content", []):
            if room_user.id == user.id:
                position = room_position
                break
        if position is None or not all(
            hasattr(position, axis) for axis in ("x", "y", "z")
        ):
            return "Couldn't get your position. Use !create tele <name> <x> <y> <z> instead."
        name = args[0].casefold()
        self.db.set_tele_point(name, position.x, position.y, position.z)
        return f"Teleport point '{name}' set at your location."

    async def _send_response(self, user, response):
        private = (
            response.startswith("Usage:")
            or response.startswith("Unknown command:")
            or response.startswith("Could not find")
            or response.startswith("You do not")
            or response.startswith("Amount must")
            or response.startswith("Command failed:")
            or response.startswith("Couldn't")
            or response.startswith("Unknown emote")
            or response.startswith("Emote failed")
            or response.startswith("Private message sent")
            or response.startswith("You need")
            or response.startswith("An owner already exists")
            or response.startswith("Only the Owner")
            or response.startswith("Can't remove")
            or response.startswith("Usage: !tele")
            or response.startswith("Coordinates must")
            or response.startswith("Usage: !create")
            or response.startswith("Usage: !remove")
            or response.startswith("Teleport points:")
            or response.startswith("You need Co-Owner")
            or (
                response.startswith("'")
                and "not found. Available:" in response
            )
            or response.startswith("Usage: !setpos")
            or (
                response.startswith("Teleport point")
                and "not found" in response
            )
            or response.startswith("Teleport failed")
            or response.startswith("Couldn't get")
            or response.startswith("Coordinates must")
            or response.startswith("Couldn't")
            or response.startswith("Could not find")
            or response.startswith("You need")
            or response.startswith("Can't grab")
            or response.startswith("Couldn't grab")
            or response.startswith("Couldn't bring")
            or response.startswith("Bring position")
            or response.startswith("Usage: !grab")
            or response.startswith("Usage: !bring")
            or response.startswith("Usage: !telecord")
        )
        if private:
            await self.highrise.send_whisper(user.id, response[:500])
        else:
            await self.highrise.chat(response[:500])

    async def _resolve_target(self, mention):
        if not mention:
            return None
        target = mention.lstrip("@")
        if target == "":
            return None
        response = await self.highrise.get_room_users()
        users = getattr(response, "content", [])
        for room_user, _position in users:
            if room_user.id == target or room_user.username.casefold() == target.casefold():
                return room_user.id
        return None

    def log(self, message):
        print(f"[HighriseBot] {message}")

    def get_username(self, user_id):
        if user_id == getattr(self, "_current_user_id", None):
            return getattr(self, "_current_username", user_id)
        user = self.db.get_user(user_id)
        return user["username"] if user and user.get("username") else user_id

    def check_cooldown(self, user_id, cooldown_type):
        key = f"{cooldown_type}:{user_id}"
        now = time.time()
        duration = CONFIG["emote_cooldown_seconds"] if cooldown_type == "emote" else CONFIG["cooldown_seconds"]
        remaining = duration - (now - self.cooldowns.get(key, 0))
        if remaining > 0:
            return False, max(1, int(remaining))
        self.cooldowns[key] = now
        return True, 0