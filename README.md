# Highrise Metaverse Bot

Moderation and room utility bot using the official `highrise-bot-sdk`.

## Setup

Use Python 3.11 and install dependencies with `python -m pip install -r requirements.txt`. The SDK's pinned `pendulum<3` dependency fails to build on Python 3.12 because it imports removed `distutils`; `startbot` automatically hands off to Python 3.11 on Windows when the `py` launcher is available. Create a bot and API token in Highrise account settings and grant it access to the room. Set `ROOM_ID` and `HIGHRISE_API_TOKEN` in PowerShell before launch. `BOT_OWNER_ID` is optional; without it, the first user to type `!setowner` becomes the permanent owner. `.env.example` lists the settings; the CLI does not load `.env` automatically.

PowerShell launch:

```powershell
$env:ROOM_ID = "your_room_id"
$env:HIGHRISE_API_TOKEN = "your_bot_api_token"
$env:BOT_OWNER_ID = "your_highrise_user_id"
python main.py startbot $env:ROOM_ID $env:HIGHRISE_API_TOKEN
```

### Always-on deployment on Render

The included `render.yaml` configures a paid background worker with a persistent disk for `bot_data.json`. To deploy:

1. Push this project to a GitHub repository.
2. In Render, create a new Blueprint and select that repository. Render will read `render.yaml` and provision the worker and persistent disk.
3. Set `ROOM_ID` and `HIGHRISE_API_TOKEN` when prompted. Keep the API token private; do not add it to the repository.
4. Deploy the worker. Check its logs to confirm the bot connects to the intended room.

The persistent disk keeps roles, owner settings, and other bot data across worker restarts. The worker runs while the Render service is active; it does not depend on VS Code or your local computer being open. Render hosting and persistent storage may incur charges.

`bot_data.json` (or `BOT_DATA_PATH`) stores roles, nicknames, warnings, `known_users` first-join timestamps, user IDs/names, session totals, cumulative ban/kick/mute/warn counts, all per-user moderation records, teleport points, `owner_set`/`owner_id`, and the latest 100 global command logs. Per-user moderation history is retained for `!log @username`.

## Commands

- `!nickname "nickname"`: set or change your own saved nickname. Nicknames are tied to your account and persist across bot restarts.
- `/equip <1-10>`: apply a numbered outfit to the bot avatar. Outfit 1 is your body/face look with a white tank, navy shorts, white shoes, and brown glasses; outfit 2 is the black Upward Swoosh look. `/equip` without a number defaults to outfit 1. `!outfit 1` remains an alias for outfit 2.
- `!note @username <note>`: save or replace a user's note, shown at the end of their `!info` output (SeniorAdmin+).
- `!warn @username 1|2|3`: apply a warning number once; three warnings maximum.
- `!unwarn @username`: clear all active warnings for that user.
- `!kick @username`, `!ban @username seconds`, `!mute @username seconds`. A reason may be added but is optional.
- `!log`: whisper the 10 most recent command logs to the caller. `!log public` posts them in public chat; `!log private` is an explicit whisper alias. `!log @username` whispers all saved moderation records for that user.
- `!give @username role`, `!remove @username role`: assign a role or reset a matching role to Guest. OWNER cannot be given or removed with these commands; use `!setowner` to claim OWNER.
- `!cords`: display your cached X/Y/Z position. Move slightly if no position is available.
- `!bring @user1 ... @user5` or `!summon ...`: bring up to five users to you.
- `!tele x,y,z`: teleport yourself directly to coordinates (VIP+); for example, `!tele 1,2,3`. Facing defaults to FrontRight. `!tp location`, `!goto location`, or `(location)`: teleport yourself to a saved point, subject to its minimum role. `!tp @username location` teleports a target (SeniorAdmin+); `!tele @username location` is the VIP+ target-teleport alias. `!tp all location` teleports everyone eligible for that point (Admin+). `!tp list` / `!tele list` shows saved points and their minimum roles (VIP+ for `!tele list`).
- `!settp location [minimum_role]` or `!create tele location minimum_role`: save your current position as a teleport point (Mod2+); `!settp` defaults to Guest if no minimum role is specified. `!remove tele (location)`, `!remove all tele`: remove one point or every point. Existing names must be removed before reuse.
- `!tip @username amount`: tip from the bot wallet after checking its gold balance; successful tips are announced in chat as `🪙tipped @username (amountg)🪙`.
- `!autotip amount seconds`, `!stopautotip`: repeatedly tip everyone else in the room; start/stop notices are whispered to the caller, and each successful tip is announced in chat. A new autotip replaces the existing one.
- `!punch @username`, `!slap @username`, `!kiss @username`, `!hug @username`, `!scare @username`, `!faint @username`, `!rofl @username`, `!dizzy @username`: VIP+ only; play the matching interaction emote on the target. `!punch` has a 5-second sender cooldown.
- `!emote <name> [@username]`, `!emote @username (<name>)`, `!emote all <name>`, or `(emote name)`: loop a catalog emote for you, a named user, or the whole room. `!emote list` prints the full catalog in numbered chat pages, with free/paid labels. Targeted emotes are available to all roles; room-wide emotes require Admin+. Legacy shortcuts such as `!ghostfloat` are also supported. Paid emotes are directed to the requester’s avatar only; Highrise validates that the avatar owns the emote. Room-wide playback is available for free emotes. `stop` stops your active emote and resets affected avatars.
- `!say message`, `!loop message seconds`, `!stoploop`.
- `!setowner`: claim OWNER once when no `BOT_OWNER_ID` or saved owner is configured. The persisted `owner_set` flag prevents later claims.
- `!rf`: after a 2-second notice, restart the Highrise runner process (Coowner and OWNER only).
- `!info [@username]`: publicly show your own profile, or the named user's role, crew, room session time, account age, and moderation counts. Highrise does not provide age or birth-date data in its public profile, so the 18+ status is shown as unavailable rather than guessed.
- `!roles`: list every role and the saved usernames assigned to it, including users who are currently offline.
- `!help`: list command names; `!help <command>` shows what a command does, its usage, and any role requirement (for example, `!help !tele`).

Ranks from lowest to highest: Guest👤, Vip⭐, SeniorAdmin🌟, Admin🎖️, Mod🔏, Mod1🛡️, Mod2🛡️🛡️, Host⚙️, Coowner⚜️, OWNER👑. SeniorAdmin and higher can warn, use `!tele` and other staff utilities, tip, autotip, say, and loop. `!goto <location>` is available to all roles, but each point enforces its saved minimum role: anyone at that role or higher can use it. Mod2 and higher can kick, ban, mute, view logs, assign/remove roles, and create/remove teleport points. `BOT_OWNER_ID` is protected as OWNER and can bootstrap role assignment. Role labels include the requested `<#HEX>` strings; whether Highrise renders those strings as colors depends on client chat formatting support.

Highrise accepts tips only in denominations of 1, 5, 10, 50, 100, 500, 1,000, 5,000, or 10,000 gold bars; amounts are split into supported transfers. Autotip checks that the wallet can cover a full room cycle before tipping.

Gold sent to the bot is announced publicly and whispered individually to online Mod2+ staff. Self-emotes, stopping emotes, and targeting another user with a free emote are available to all roles; paid-emote handling remains subject to Highrise's ownership checks. Interaction commands require VIP+, and room-wide emotes require Admin+. The emote catalog uses each animation's listed duration when looping; legacy shorthand names remain supported. Highrise still checks whether a target is allowed to use a requested emote. If the platform rejects one, the bot reports the failed command instead of claiming it worked. Crew and Highrise account age in `!info` come from the public WebAPI and show `N/A` if unavailable. Highrise does not provide users' ages or birth dates in that public profile, so `!info` reports the 18+ status as unavailable. “First seen” and room session duration are tracked locally, starting when the bot first sees each user. The terminal prints connection, join/leave, moderation-counter, refresh, and error messages.

New users receive `Welcome To the Room👋 @username (nickname) Enjoy Your stay🤗`; returning users receive `Welcome Back <Role> @username (nickname)👋`. Departures receive `Goodbye <Role> @username (nickname) thank you for joining, Hope to see you soon👋`. The nickname suffix is omitted when a user has not set one.

Run tests with `python -m unittest discover -s tests`.