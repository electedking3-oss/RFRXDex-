“””
card_utils.py — Card data loading, RNG spawn logic, variant resolution
“””

import json
import random
import os
import uuid
from typing import Optional, Tuple

CARDS_PATH = os.path.join(os.path.dirname(**file**), “cards.json”)
_card_cache = None

def load_cards() -> dict:
global _card_cache
if _card_cache is None:
with open(CARDS_PATH, “r”) as f:
_card_cache = json.load(f)
return _card_cache

def get_all_cards() -> list:
return load_cards()[“cards”]

def get_card_by_id(card_id: str) -> Optional[dict]:
for card in get_all_cards():
if card[“id”] == card_id:
return card
return None

def get_spawnable_cards() -> list:
return [c for c in get_all_cards() if c.get(“spawnable”, False)]

def get_card_by_name(name: str) -> Optional[dict]:
name_lower = name.lower().strip()
for card in get_all_cards():
if card[“name”].lower() == name_lower:
return card
for alias in card.get(“aliases”, []):
if alias.lower() == name_lower:
return card
return None

def get_rarity_color(rarity: str) -> int:
“”“Returns Discord embed color int for each rarity.”””
colors = {
“common”:   0xAAAAAA,  # grey
“rare”:     0x3498DB,  # blue
“epic”:     0x9B59B6,  # purple
“mythic”:   0xFF8C00,  # dark orange
“champion”: 0xFFD700,  # gold
“limited”:  0xFF0000,  # red
}
return colors.get(rarity.lower(), 0xFFFFFF)

def get_variant_emoji(variant: str) -> str:
emojis = {
“Standard”:          “🃏”,
“Shiny”:             “✨”,
“DOTD”:              “🏆”,
“GP Specs”:          “🏎️”,
“Secret Rare”:       “🔮”,
“Ultra Rare”:        “💎”,
“Collectors Special”:“👑”,
}
return emojis.get(variant, “🃏”)

def get_rarity_emoji(rarity: str) -> str:
emojis = {
“common”:   “⚪”,
“rare”:     “🔵”,
“epic”:     “🟣”,
“mythic”:   “🟠”,
“champion”: “🌟”,
“limited”:  “🔴”,
}
return emojis.get(rarity.lower(), “⚪”)

def roll_variant(card: dict) -> str:
“”“Rolls for a special variant. Returns ‘Standard’ if none proc.”””
data = load_cards()
variant_chances = data[“variant_chances”]
active_gp = data[“gp_specs”].get(“active”)

```
available_variants = card.get("special_variants", [])
# Check GP Specs availability
if "GP Specs" in available_variants and not active_gp:
    available_variants = [v for v in available_variants if v != "GP Specs"]

# Roll from rarest to most common
order = ["Ultra Rare", "Secret Rare", "Shiny", "DOTD", "GP Specs"]
for v in order:
    if v not in available_variants:
        continue
    chance = variant_chances.get(v, 0)
    if random.uniform(0, 100) <= chance:
        return v
return "Standard"
```

def calculate_spawn_value(card: dict, variant: str) -> int:
“”“Returns the current dynamic value for a card+variant spawn.”””
from database import get_current_value
data = load_cards()
multipliers = data[“variant_value_multipliers”]
base = card[“base_value”]
current = get_current_value(card[“id”], variant, base)
mult = multipliers.get(variant, 1.0)
return max(1, int(current * mult))

def pick_spawn_card() -> Tuple[dict, str]:
“””
Picks a random spawnable card weighted by rarity,
then rolls for a variant.
Returns (card_dict, variant_str)
“””
data = load_cards()
rarity_weights = data[“rarity_weights”]
spawnable = get_spawnable_cards()

```
# Group by rarity
by_rarity: dict[str, list] = {}
for card in spawnable:
    r = card["rarity"]
    by_rarity.setdefault(r, []).append(card)

# Weighted rarity roll
rarities = list(rarity_weights.keys())
weights = [rarity_weights[r] for r in rarities]
chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

# Fallback if no cards for that rarity
if chosen_rarity not in by_rarity or not by_rarity[chosen_rarity]:
    all_cards = spawnable
    chosen_card = random.choice(all_cards)
else:
    chosen_card = random.choice(by_rarity[chosen_rarity])

variant = roll_variant(chosen_card)
return chosen_card, variant
```

def generate_instance_id() -> str:
return str(uuid.uuid4())

def get_spawn_caption() -> str:
return random.choice(load_cards()[“spawn_captions”])

def get_fail_caption() -> str:
return random.choice(load_cards()[“fail_captions”])

def format_value_change(current_value: int, catch_value: int, base_value: int) -> Tuple[str, str]:
“””
Returns (+X%, +Y%) strings for catch message.
X = % change since last sale, Y = % change since base.
“””
if catch_value and catch_value > 0:
x_pct = ((current_value - catch_value) / catch_value) * 100
x_str = f”+{x_pct:.1f}%” if x_pct >= 0 else f”{x_pct:.1f}%”
else:
x_str = “+0.0%”

```
if base_value and base_value > 0:
    y_pct = ((current_value - base_value) / base_value) * 100
    y_str = f"+{y_pct:.1f}%" if y_pct >= 0 else f"{y_pct:.1f}%"
else:
    y_str = "+0.0%"

return x_str, y_str
```

def get_card_display_name(card: dict, variant: str) -> str:
name = card[“name”]
if variant and variant != “Standard”:
name = f”{name} [{variant}]”
return name

def paginate(items: list, page: int, per_page: int = 10) -> Tuple[list, int]:
“”“Returns (page_items, total_pages).”””
total = len(items)
total_pages = max(1, (total + per_page - 1) // per_page)
page = max(1, min(page, total_pages))
start = (page - 1) * per_page
return items[start:start + per_page], total_pages
