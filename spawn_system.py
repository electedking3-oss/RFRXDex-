import discord
import asyncio
import random
import uuid
from datetime import datetime

import database as db
import card_utils as cu

SPAWN_CHANNEL_IDS: list[int] = []   # Populated from main.py config

class CatchButton(discord.ui.View):
def **init**(self, spawn_id: str, card: dict, variant: str, spawn_value: int):
super().**init**(timeout=None)
self.spawn_id = spawn_id
self.card = card
self.variant = variant
self.spawn_value = spawn_value

```
@discord.ui.button(label="✋ Sign", style=discord.ButtonStyle.success, custom_id="catch_card")
async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    user = interaction.user
    db.ensure_user(str(user.id), user.display_name)

    # Attempt to claim spawn (atomic)
    claimed = db.claim_spawn(self.spawn_id, str(user.id))
    if not claimed:
        # Already caught by someone else
        fail_cap = cu.get_fail_caption()
        await interaction.response.send_message(
            f"❌ **Too slow!** {fail_cap}", ephemeral=True
        )
        return

    # Give card to user
    instance_id = cu.generate_instance_id()
    current_value = cu.calculate_spawn_value(self.card, self.variant)
    db.add_card_to_inventory(str(user.id), self.card["id"], self.variant, current_value, instance_id)

    # Auto-grant info card if applicable
    info_card_id = self.card.get("info_card_id")
    info_card = None
    if info_card_id:
        db.grant_info_card(str(user.id), info_card_id)
        info_card = cu.get_card_by_id(info_card_id)

    # Record spawn value in history
    db.set_current_value(self.card["id"], self.variant, current_value)

    # Build catch message
    x_str, y_str = cu.format_value_change(current_value, self.card["base_value"], self.card["base_value"])
    card_display = cu.get_card_display_name(self.card, self.variant)
    variant_emoji = cu.get_variant_emoji(self.variant)
    rarity_emoji = cu.get_rarity_emoji(self.card["rarity"])

    catch_msg = (
        f"🏁 **{user.display_name}** caught **{variant_emoji} {card_display}**! "
        f"`(#{instance_id[:8]}, {x_str}/{y_str})`\n"
        f"**Value:** 🪙 {current_value:,} coins   {rarity_emoji} *{self.card['rarity'].capitalize()}*"
    )

    if info_card:
        catch_msg += f"\n📋 **Info Card granted:** *{info_card['name']}*"

    # Disable the button
    button.disabled = True
    button.label = f"✅ Caught by {user.display_name}"
    button.style = discord.ButtonStyle.secondary

    await interaction.message.edit(view=self)
    await interaction.response.send_message(catch_msg)
```

def build_spawn_embed(card: dict, variant: str, value: int, caption: str) -> discord.Embed:
rarity = card[“rarity”]
color = cu.get_rarity_color(rarity)
variant_emoji = cu.get_variant_emoji(variant)
rarity_emoji = cu.get_rarity_emoji(rarity)

```
embed = discord.Embed(
    title=f"{variant_emoji} A card has appeared!",
    description=f"*{caption}*",
    color=color,
    timestamp=datetime.utcnow()
)

card_name = card["name"]
if variant != "Standard":
    card_name = f"{card_name} [{variant}]"

embed.add_field(name="📛 Card", value=card_name, inline=True)
embed.add_field(name=f"{rarity_emoji} Rarity", value=rarity.capitalize(), inline=True)
embed.add_field(name="🪙 Estimated Value", value=f"{value:,} coins", inline=True)

if variant != "Standard":
    embed.add_field(name="✨ Variant", value=variant, inline=True)

embed.set_image(url=card["image_url"])
embed.set_footer(text="RFRXDex • Click Sign to catch!")
return embed
```

class SpawnSystem:
def **init**(self, bot: discord.Client):
self.bot = bot
self.active_spawns: dict = {}   # spawn_id -> True
self.spawn_channel_ids: list[int] = []
self._task = None

```
def set_channels(self, channel_ids: list[int]):
    self.spawn_channel_ids = channel_ids

def start(self):
    self._task = asyncio.create_task(self._spawn_loop())

def stop(self):
    if self._task:
        self._task.cancel()

async def _spawn_loop(self):
    await self.bot.wait_until_ready()
    while not self.bot.is_closed():
        interval = random.randint(300, 900)   # 5–15 minutes
        await asyncio.sleep(interval)
        await self.do_spawn()

async def do_spawn(self, channel_id: int = None):
    """Trigger a spawn. If channel_id is None, picks a random configured channel."""
    if not self.spawn_channel_ids and channel_id is None:
        return

    target_channel_id = channel_id or random.choice(self.spawn_channel_ids)
    channel = self.bot.get_channel(target_channel_id)
    if channel is None:
        return

    card, variant = cu.pick_spawn_card()
    value = cu.calculate_spawn_value(card, variant)
    caption = cu.get_spawn_caption()
    spawn_id = str(uuid.uuid4())

    db.register_spawn(spawn_id, card["id"], variant, str(target_channel_id))

    embed = build_spawn_embed(card, variant, value, caption)
    view = CatchButton(spawn_id, card, variant, value)

    try:
        msg = await channel.send(embed=embed, view=view)
        db.update_spawn_message(spawn_id, str(msg.id))
        self.active_spawns[spawn_id] = True
    except discord.HTTPException as e:
        print(f"[Spawn] Failed to send spawn: {e}")
```
