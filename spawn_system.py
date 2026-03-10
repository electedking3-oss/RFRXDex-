import discord
import asyncio
import random
import uuid
from datetime import datetime

import database as db
import card_utils as cu

SPAWN_INTERVAL_MIN = 300   # 5 min
SPAWN_INTERVAL_MAX = 900   # 15 min

FAIL_CAPTIONS = [
    "Wrong! Take a closer look...",
    "Nope! Try again.",
    "That's not quite right!",
    "Almost! But not quite.",
    "Hmm, that doesn't match!",
    "Not this time! Keep trying.",
]


class SignModal(discord.ui.Modal):
    def __init__(self, spawn_id: str, card: dict):
        super().__init__(title=f"Sign this card!")
        self.spawn_id = spawn_id
        self.card     = card
        self.answer   = discord.ui.TextInput(
            label="What is the name of this card?",
            placeholder=f"Type the card name...",
            min_length=1,
            max_length=100,
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.answer.value.strip().lower()
        card_name  = self.card["name"].lower()
        aliases    = [a.lower() for a in self.card.get("aliases", [])]
        valid      = [card_name] + aliases

        if user_input not in valid:
            caption = random.choice(FAIL_CAPTIONS)
            await interaction.response.send_message(
                f":x: **{caption}** (You typed: `{self.answer.value}`)",
                ephemeral=True
            )
            return

        # Atomic claim
        claimed = db.claim_spawn(self.spawn_id, str(interaction.user.id))
        if not claimed:
            await interaction.response.send_message(
                ":x: This card was already signed by someone else!",
                ephemeral=True
            )
            return

        # Get spawn info
        spawn = db.get_spawn(self.spawn_id)
        variant = spawn["variant"]
        card    = self.card

        # Calculate value
        old_val    = db.get_current_value(card["id"], variant, card.get("base_value", 100))
        catch_val  = cu.compute_catch_value(card, variant)
        val_change = cu.format_value_change(old_val, catch_val)
        iid        = cu.generate_instance_id()

        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        db.add_card_to_inventory(str(interaction.user.id), card["id"], variant, catch_val, iid)

        # Grant info card if applicable
        info_granted = None
        if card.get("info_card_id"):
            db.grant_info_card(str(interaction.user.id), card["info_card_id"])
            info_card = cu.get_card_by_id(card["info_card_id"])
            if info_card:
                info_granted = info_card["name"]

        # Build catch message
        r_emoji   = cu.get_rarity_emoji(card["rarity"])
        v_emoji   = cu.get_variant_emoji(variant)
        color     = cu.get_rarity_color(card["rarity"])

        embed = discord.Embed(color=color)
        embed.set_author(
            name=f"{interaction.user.display_name} signed a new card!",
            icon_url=interaction.user.display_avatar.url
        )

        desc_parts = [
            f"{r_emoji} **{card['name']}**",
            f"**Rarity:** {card['rarity'].capitalize()}",
        ]
        if variant != "Standard":
            desc_parts.append(f"**Variant:** {v_emoji} {variant}")
        desc_parts.append(f"**Value:** :coin: {catch_val:,} ({val_change})")
        desc_parts.append(f"**Instance:** `#{iid}`")
        if info_granted:
            desc_parts.append(f"\n:card_index: *You also received the **{info_granted}** info card!*")

        embed.description = "\n".join(desc_parts)
        embed.set_thumbnail(url=card["image_url"])
        embed.set_footer(text="RFRXDex")

        # Edit original message to disable button
        try:
            original_msg = interaction.message
            if original_msg:
                disabled_view = SpawnView(self.spawn_id, card, disabled=True)
                await original_msg.edit(view=disabled_view)
        except Exception:
            pass

        await interaction.response.send_message(embed=embed)


class SpawnView(discord.ui.View):
    def __init__(self, spawn_id: str, card: dict, disabled: bool = False):
        super().__init__(timeout=None)
        self.spawn_id = spawn_id
        self.card     = card
        btn           = discord.ui.Button(
            label="Sign",
            style=discord.ButtonStyle.primary,
            custom_id=f"sign_{spawn_id}",
            disabled=disabled,
        )
        btn.callback = self._sign_callback
        self.add_item(btn)

    async def _sign_callback(self, interaction: discord.Interaction):
        # Check if already claimed
        spawn = db.get_spawn(self.spawn_id)
        if not spawn or not spawn["is_active"]:
            await interaction.response.send_message(":x: This card has already been signed!", ephemeral=True)
            return
        modal = SignModal(self.spawn_id, self.card)
        await interaction.response.send_modal(modal)


class SpawnSystem:
    def __init__(self, bot: discord.Client):
        self.bot              = bot
        self.spawn_channel_ids: list[int] = []
        self._task            = None

    def start(self):
        self._task = asyncio.create_task(self._spawn_loop())

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _spawn_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            delay = random.randint(SPAWN_INTERVAL_MIN, SPAWN_INTERVAL_MAX)
            await asyncio.sleep(delay)
            if self.spawn_channel_ids:
                channel_id = random.choice(self.spawn_channel_ids)
                await self.do_spawn(channel_id=channel_id)

    async def do_spawn(self, channel_id: int = None):
        if not channel_id:
            if not self.spawn_channel_ids:
                return
            channel_id = random.choice(self.spawn_channel_ids)

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        card = cu.pick_random_spawnable_card()
        if not card:
            return

        active_gp = cu.get_active_gp()
        variant   = cu.roll_variant(active_gp=active_gp is not None)

        # For GP Specs, attach the GP flag emoji
        gp_tag = ""
        if variant == "GP Specs" and active_gp:
            gp_tag = f" {active_gp.get('flag', '')} {active_gp.get('name', 'GP Special')}"

        spawn_id = str(uuid.uuid4())
        db.register_spawn(spawn_id, card["id"], variant, str(channel_id))

        color   = cu.get_rarity_color(card["rarity"])
        r_emoji = cu.get_rarity_emoji(card["rarity"])
        v_emoji = cu.get_variant_emoji(variant)
        val     = db.get_current_value(card["id"], variant, card.get("base_value", 100))

        embed = discord.Embed(color=color)
        embed.set_image(url=card["image_url"])

        tag_line = f"**Type:** {card['type'].capitalize()} | **Rarity:** {r_emoji} {card['rarity'].capitalize()}"
        if variant != "Standard":
            tag_line += f" | **Variant:** {v_emoji} {variant}{gp_tag}"
        tag_line += f"\n**Value:** :coin: {val:,}"

        embed.description = tag_line
        embed.set_footer(text="Type the card name to sign it! | RFRXDex")

        view = SpawnView(spawn_id, card)
        msg  = await channel.send(embed=embed, view=view)
        db.update_spawn_message(spawn_id, str(msg.id))
