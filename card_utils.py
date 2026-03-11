import json
import os
import random
import string
import uuid

CARDS_PATH = os.path.join(os.path.dirname(__file__), "cards.json")
_cards_cache = None

RARITY_WEIGHTS = {
    "common":   45,
    "rare":     30,
    "epic":     15,
    "mythic":    6,
    "champion":  3,
    "limited":   1,
}

RARITY_COLORS = {
    "common":   0xAAAAAA,
    "rare":     0x3498DB,
    "epic":     0x9B59B6,
    "mythic":   0xFF8C00,
    "champion": 0xFFD700,
    "limited":  0xFF0000,
}

RARITY_EMOJIS = {
    "common":   ":white_circle:",
    "rare":     ":blue_circle:",
    "epic":     ":purple_circle:",
    "mythic":   ":orange_circle:",
    "champion": ":star:",
    "limited":  ":red_circle:",
}

VARIANT_MULTIPLIERS = {
    "Standard":           1.0,
    "GP Specs":           2.5,
    "DOTD":               1.8,
    "Shiny":              2.0,
    "Secret Rare":        4.0,
    "Ultra Rare":         8.0,
    "Collectors Special": 15.0,
}

VARIANT_WEIGHTS = {
    "Standard":    100,
    "GP Specs":     20,
    "DOTD":         15,
    "Shiny":        10,
    "Secret Rare":   3,
    "Ultra Rare":    1,
}

VARIANT_EMOJIS = {
    "Standard":           "",
    "GP Specs":           ":race_car:",
    "DOTD":               ":trophy:",
    "Shiny":              ":sparkles:",
    "Secret Rare":        ":crystal_ball:",
    "Ultra Rare":         ":gem:",
    "Collectors Special": ":crown:",
}


def _load_cards():
    global _cards_cache
    if _cards_cache is not None:
        return _cards_cache
    with open(CARDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cards_cache = data
    return data


def get_all_cards() -> list:
    return _load_cards().get("cards", [])


def get_card_by_id(card_id: str) -> dict | None:
    for c in get_all_cards():
        if c["id"] == card_id:
            return c
    return None


def get_card_by_name(name: str) -> dict | None:
    name_lower = name.lower().strip()
    # Exact match first
    for c in get_all_cards():
        if c["name"].lower() == name_lower:
            return c
    # Alias match
    for c in get_all_cards():
        aliases = [a.lower() for a in c.get("aliases", [])]
        if name_lower in aliases:
            return c
    # Partial match
    for c in get_all_cards():
        if name_lower in c["name"].lower():
            return c
    return None


def get_rarity_color(rarity: str) -> int:
    return RARITY_COLORS.get(rarity.lower(), 0xAAAAAA)


def get_rarity_emoji(rarity: str) -> str:
    return RARITY_EMOJIS.get(rarity.lower(), ":white_circle:")


def get_variant_emoji(variant: str) -> str:
    return VARIANT_EMOJIS.get(variant, "")


def get_card_display_name(card: dict, variant: str = "Standard") -> str:
    v_emoji = get_variant_emoji(variant)
    if v_emoji:
        return f"{v_emoji} {card['name']} [{variant}]"
    return card["name"]


def generate_instance_id() -> str:
    """Generate a unique instance ID like #2959CF"""
    return uuid.uuid4().hex[:6].upper()


def roll_variant(active_gp: bool = False, card_type: str = "") -> str:
    """Roll for a card variant.
    GP Specs only eligible if active_gp=True AND card is not a track.
    """
    pool = dict(VARIANT_WEIGHTS)
    if not active_gp or card_type.lower() == "track":
        pool.pop("GP Specs", None)

    total = sum(pool.values())
    roll  = random.randint(1, total)
    cumulative = 0
    for variant, weight in pool.items():
        cumulative += weight
        if roll <= cumulative:
            return variant
    return "Standard"


def get_gp_variant_label(active_gp: dict) -> str:
    """Return dynamic GP variant name e.g. 'Dutch GP Spec'"""
    return f"{active_gp.get('race_weekend', 'GP')} Spec"


def get_gp_exclusivity_line(active_gp: dict) -> str:
    """Return the exclusivity line shown on catch e.g. '🇳🇱 *This card is a Dutch GP exclusive!*'"""
    flag = active_gp.get("flag", "")
    msg  = active_gp.get("exclusivity_msg", f"Caught during the {active_gp.get('race_weekend', 'GP')} race weekend!")
    return f"{flag} *{msg}*"


def pick_random_spawnable_card() -> dict | None:
    """Pick a random card weighted by rarity from spawnable cards."""
    spawnable = [c for c in get_all_cards() if c.get("spawnable")]
    if not spawnable:
        return None

    weights = [RARITY_WEIGHTS.get(c["rarity"].lower(), 1) for c in spawnable]
    return random.choices(spawnable, weights=weights, k=1)[0]


def get_active_gp() -> dict | None:
    """Return the currently active GP spec from cards.json, or None."""
    data = _load_cards()
    gps  = data.get("gp_specs", {}).get("list", [])
    for gp in gps:
        if gp.get("active"):
            return gp
    return None


def compute_catch_value(card: dict, variant: str) -> int:
    """Compute the initial value for a caught card."""
    import database as db
    base = db.get_current_value(card["id"], variant, card.get("base_value", 100))
    mult = VARIANT_MULTIPLIERS.get(variant, 1.0)
    return int(base * mult)


def roll_atk_hp_mods() -> tuple[int, int]:
    """Roll ATK and HP modifier percentages for a card instance (-20 to +20)."""
    atk = random.randint(-20, 20)
    hp  = random.randint(-20, 20)
    return atk, hp


def format_value_change(old_val: int, new_val: int) -> str:
    """Return a formatted string showing value change percentage."""
    if old_val == 0:
        return "+0%"
    pct = ((new_val - old_val) / old_val) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"
