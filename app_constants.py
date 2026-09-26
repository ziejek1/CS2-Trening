DATA_FILE = "pro_training_data.json"
USERS_FILE = "users.json"
REMEMBERED_LOGIN_FILE = "remembered_login.json"
PASSWORD_SCHEME = "pbkdf2_sha256"
APP_VERSION = "1.0.10"
SUPABASE_URL = "https://fvmscxuybltwzjwxagck.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_PYr7W6xo0hJyhiNwTkCkJw__WARcv9E"

PRESET_PROTOCOLS = {
    "🔥 Pro Aim & Reflex (45 min)": [
        {"type": "Warmup: Aim Lab (Gridshot / Microflex)", "duration": 10},
        {"type": "Aim Botz: One-Taps & Counter-Strafe", "duration": 15},
        {"type": "Recoil Control (AK-47 / M4A1-S Spray)", "duration": 10},
        {"type": "FFA Deathmatch (Headshot Only)", "duration": 10}
    ],
    "🎯 Sniper & Flick Master (30 min)": [
        {"type": "Warmup: Aim Lab (Flickshot)", "duration": 10},
        {"type": "CS2 Workshop: AWP Angles & Flicks", "duration": 10},
        {"type": "FFA DM: AWP Positioning & Reaction", "duration": 10}
    ],
    "🧠 Utility & Tactical Drive (40 min)": [
        {"type": "Mirage Lineups (Smokes & Flashes)", "duration": 15},
        {"type": "Anubis & Inferno Execute Lineups", "duration": 15},
        {"type": "Retake Servers (Utility Application)", "duration": 10}
    ]
}

CS2_RANKS = (
    (0, "Silver I"),
    (120, "Silver II"),
    (300, "Silver III"),
    (550, "Silver IV"),
    (850, "Silver Elite"),
    (1200, "Silver Elite Master"),
    (1650, "Gold Nova I"),
    (2200, "Gold Nova II"),
    (2900, "Gold Nova III"),
    (3700, "Gold Nova Master"),
    (4700, "Master Guardian I"),
    (5900, "Master Guardian II"),
    (7300, "Master Guardian Elite"),
    (9000, "Distinguished Master Guardian"),
    (11000, "Legendary Eagle"),
    (13500, "Legendary Eagle Master"),
    (16500, "Supreme Master First Class"),
    (20000, "Global Elite")
)

SKILL_CATEGORIES = (
    "Aim",
    "Recoil",
    "Movement",
    "Utility",
    "Game sense",
    "AWP"
)

SKILL_CATEGORY_COLORS = {
    "Aim": "#38BDF8",
    "Recoil": "#F59E0B",
    "Movement": "#34D399",
    "Utility": "#A78BFA",
    "Game sense": "#F472B6",
    "AWP": "#FB7185"
}

DEFAULT_MODULE_CATALOG = (
    ("Aim Botz (1000 Kills / Fast Taps)", "Aim"),
    ("Aim Lab (Gridshot / Microflex)", "Aim"),
    ("Recoil Master (AK47 Spray Control)", "Recoil"),
    ("CS2 Workshop (Prefire Maps)", "Game sense"),
    ("DM Headshot Only (FFA)", "Aim"),
    ("KZ / Surf (Movement)", "Movement")
)
