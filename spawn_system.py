import discord
import asyncio
import random
import uuid

import database as db
import card_utils as cu


# ─── Sign Modal ───────────────────────────────────────────────────────────────

class SignModal(discord.ui.Modal, title="Sign the Card!"):
    guess = discord.ui.TextInput(
        label="Type the full name of the card to claim it",
        placeholder="e.g. McLaren, Red Bull, Interlagos Brazil...",
        min_length=1,
        max_length=60,
        required=True
    )

    def __init__(self, spawn_id: str, card: dict, variant: str, spawn_value: int, view):
        super().__init__()
        self.spawn_id = spawn_id
        self.card = card
        self.variant = variant
        self.spawn_value = spawn_value
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        db.ensure_user(str(user.id), user.display_name)
        typed = self.guess.value.strip().lower()

        # Build valid names list from card name + all aliases
        valid_names = [self.card["name"].lower()]
        for alias in self.card.get("aliases", []):
            valid_names.append(alias.lower())

        # Wrong guess
        if typed not in valid_names:
            fail = cu.get_fail_caption()
            await interaction.response.send_message(
                f"**Wrong!** {fail}",
                ephemeral=True
            )
            return

        # Atomic claim - prevent double-signing
        claimed = db.claim_spawn(self.spawn_id, str(user.id))
        if not claimed:
            await interaction.response.send_message(
                f"**Too slow!** {cu.get_fail_caption()}",
                ephemeral=True
            )
            return

        # Add card to inventory
        instance_id = cu.generate_instance_id()
        current_value = cu.calculate_spawn_value(self.card, self.variant)
        db.add_card_to_inventory(
            str(user.id), self.card["id"], self.variant, current_value, instance_id
        )
        db.set_current_value(self.card["id"], self.variant, current_value)

        # Auto-grant info card for driver/team cards
        info_card = None
        info_card_id = self.card.get("info_card_id")
        if info_card_id and self.card.get("type") in ("driver", "team"):
            db.grant_info_card(str(user.id), info_card_id)
            info_card = cu.get_card_by_id(info_card_id)

        # Disable the Sign button for everyone else
        self.parent_view.sign_button.disabled = True
        self.parent_view.sign_button.label = f"Signed by {user.display_name}"
        self.parent_view.sign_button.style = discord.ButtonStyle.secondary
        self.parent_view.stop()
        await interaction.message.edit(view=self.parent_view)

        # Build value strings
        x_str, y_str = cu.format_value_change(
            current_value, self.card["base_value"], self.card["base_value"]
        )
        card_type = self.card.get("type", "card").capitalize()
        variant_display = self.variant if self.variant != "Standard" else "Normal"
        v_emoji = cu.get_variant_emoji(self.variant)
        r_emoji = cu.get_rarity_emoji(self.card["rarity"])
        card_display = cu.get_card_display_name(self.card, self.variant)
        sign_caption = cu.get_sign_caption()

        # Build the catch message
        lines = [
            f"**{user.display_name}** signed **'{card_display}'**! "
            f"`(#{instance_id[:8]}, {x_str}/{y_str})`",
        ]

        # GP Special exclusivity line
        if self.variant == "GP Specs":
            active_gp = cu.get_active_gp()
            if active_gp:
                flag = active_gp.get("flag", "")
                excl = active_gp.get("exclusivity_msg", "This is a GP exclusive!")
                lines.append(f"***{flag} {excl}***")

        # Sign flavour caption
        lines.append(sign_caption)
        lines.append("")
        lines.append(f"**Card Type:** {card_type}")
        lines.append(f"**Variant:** {variant_display}")
        lines.append(
            f"**Current Value:** {current_value:,} coins ({x_str}/{y_str})"
        )
        lines.append(
            f"**Rarity:** {r_emoji} {self.card['rarity'].capitalize()}"
        )
        if info_card:
            lines.append(f"**Info Card granted:** {info_card['name']}")

        await interaction.response.send_message("\n".join(lines))


# ─── Sign View (button) ───────────────────────────────────────────────────────

class SignView(discord.ui.View):
    def __init__(self, spawn_id: str, card: dict, variant: str, spawn_value: int):
        super().__init__(timeout=None)
        self.spawn_id = spawn_id
        self.card = card
        self.variant = variant
        self.spawn_value = spawn_value

    @discord.ui.button(label="Sign", style=discord.ButtonStyle.primary, custom_id="sign_card")
    async def sign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if already claimed before opening modal
        spawn = db.get_spawn(self.spawn_id)
        if spawn and not spawn["is_active"]:
            await interaction.response.send_message(
                f"**Already signed!** {cu.get_fail_caption()}",
                ephemeral=True
            )
            return

        modal = SignModal(
            spawn_id=self.spawn_id,
            card=self.card,
            variant=self.variant,
            spawn_value=self.spawn_value,
            view=self
        )
        await interaction.response.send_modal(modal)


# ─── Spawn message builder ────────────────────────────────────────────────────

def build_spawn_message(card: dict, variant: str, value: int, caption: str) -> str:
    v_emoji = cu.get_variant_emoji(variant)
    r_emoji = cu.get_rarity_emoji(card["rarity"])
    variant_display = variant if variant != "Standard" else "Normal"

    # GP Special label
    gp_line = ""
    if variant == "GP Specs":
        active_gp = cu.get_active_gp()
        if active_gp:
            flag = active_gp.get("flag", "")
            gp_name = active_gp.get("name", "GP Special")
            gp_line = f"\n**{flag} {gp_name}** — GP Exclusive card!"

    lines = [
        f"{v_emoji} **A card has appeared!**",
        f"*{caption}*{gp_line}",
        f"",
        card["image_url"],
        f"",
        (
            f"**Type:** {card['type'].capitalize()}  |  "
            f"**Rarity:** {r_emoji} {card['rarity'].capitalize()}  |  "
            f"**Variant:** {variant_display}  |  "
            f"**Est. Value:** {value:,} coins"
        ),
    ]
    return "\n".join(lines)


# ─── Spawn System ─────────────────────────────────────────────────────────────

class SpawnSystem:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.active_spawns: dict = {}
        self.spawn_channel_ids: list[int] = []
        self._task = None

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
            interval = random.randint(300, 900)  # 5-15 minutes
            await asyncio.sleep(interval)
            await self.do_spawn()

    async def do_spawn(self, channel_id: int = None):
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

        content = build_spawn_message(card, variant, value, caption)
        view = SignView(spawn_id, card, variant, value)

        try:
            msg = await channel.send(content=content, view=view)
            db.update_spawn_message(spawn_id, str(msg.id))
            self.active_spawns[spawn_id] = True
        except discord.HTTPException as e:
            print(f"[Spawn] Failed to send spawn: {e}")
