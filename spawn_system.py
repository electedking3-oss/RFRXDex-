import discord
import asyncio
import random
import uuid

import database as db
import card_utils as cu

SPAWN_INTERVAL_MIN = 300   # 5 min
SPAWN_INTERVAL_MAX = 900   # 15 min

FAIL_CAPTIONS = [
    "{user} I am schupid… I am schupid.",
    "{user} WHY WHAT ARE YOU DOING?",
    "{user} thought he caught a Howard Lau.",
    "{user} I CAN'T IT'S BWOKEN, IT'S BWOKEN.",
    "{user} thought he can go for the gap.",
    "{user} GP2 Engine…",
    "{user} I cannot fucking believe it, I cannot FUCKING believe it.",
    "{user} Habibi must be the water.",
    "{user} WHAT a fucking idiot. What a FUCKING idiot.",
    "{user} NOOOOOOOOOOOOOOOOO-",
    "{user} HEY HEY! STEERING WHEEL!",
    "{user} Nothing just an inchident.",
    "{user} rather value my life and my limbs.",
    "{user} If my mom had balls, you would have caught it early.",
    "{user} sorry that was Perez, Verstappen plus 20.",
    "{user} Gap behind you muppet.",
    "{user} WHAT THE FUCK ARE WE DOING HERE? I'm going home.",
    "{user} I am SOO fucking shit. That's what I am.",
]

SPAWN_CAPTIONS = [
    "It's friday then, it's saturday, sunday WHAT?",
    "Smooooooth Operator",
    "Simply Simply Lovely",
    "But satisfaction",
    "KI KI AYY",
    "catch it, might be a shiny one?",
    "bwoah",
    "I had brisket, I had sausage, I had- oh, its an RFRX spawn!",
    "real",
    "when I do this, you start catching. Holla Todos!",
    "NICOOOOO HUUUUUUUUUUULKENBBEERGGG",
    "You've got a problem, catch this fucking RFRX Spawn.",
    "If you no longer go for a catch that exist, you're no longer having this RFRX Spawn.",
]


class SignModal(discord.ui.Modal):
    def __init__(self, spawn_id: str, card: dict, spawn_msg: discord.Message):
        super().__init__(title="Sign this card!")
        self.spawn_id  = spawn_id
        self.card      = card
        self.spawn_msg = spawn_msg
        self.answer    = discord.ui.TextInput(
            label="What is the name of this card?",
            placeholder="Type the card name...",
            min_length=1,
            max_length=100,
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.answer.value.strip().lower()
        card_name  = self.card["name"].lower()
        aliases    = [a.lower() for a in self.card.get("aliases", [])]
        valid      = [card_name] + aliases

        # Wrong answer — public fail caption
        if user_input not in valid:
            raw     = random.choice(FAIL_CAPTIONS)
            caption = raw.replace("{user}", f"**{interaction.user.display_name}**")
            await interaction.response.send_message(caption)
            return

        # Atomic claim
        claimed = db.claim_spawn(self.spawn_id, str(interaction.user.id))
        if not claimed:
            await interaction.response.send_message(
                ":x: This card was already signed by someone else!",
                ephemeral=True
            )
            return

        spawn   = db.get_spawn(self.spawn_id)
        variant = spawn["variant"]
        card    = self.card

        # Roll ATK/HP mods
        atk_mod, hp_mod = cu.roll_atk_hp_mods()

        # Calculate value
        old_val   = db.get_current_value(card["id"], variant, card.get("base_value", 100))
        catch_val = cu.compute_catch_value(card, variant)
        gained    = catch_val - old_val
        iid       = cu.generate_instance_id()

        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        db.add_card_to_inventory(str(interaction.user.id), card["id"], variant, catch_val, iid,
                                 atk_mod=atk_mod, hp_mod=hp_mod)

        # Grant info card if applicable
        info_granted = None
        if card.get("info_card_id"):
            db.grant_info_card(str(interaction.user.id), card["info_card_id"])
            info_card = cu.get_card_by_id(card["info_card_id"])
            if info_card:
                info_granted = info_card["name"]

        # Disable the Sign me! button on original spawn message
        try:
            disabled_view = SpawnView(self.spawn_id, card, disabled=True)
            await self.spawn_msg.edit(view=disabled_view)
        except Exception:
            pass

        # Catch confirmation — plain message, F1dex style:
        # @user You signed **Card Name**! (#IIIIII, ATK:+x%/HP:+x%) (+value 🪙)
        atk_str    = f"{atk_mod:+d}%"
        hp_str     = f"{hp_mod:+d}%"
        gained_str = f"+{gained:,}" if gained >= 0 else f"{gained:,}"

        msg = (
            f"{interaction.user.mention} You signed **{card['name']}**! "
            f"(#{iid}, ATK:{atk_str}/HP:{hp_str}) "
            f"({gained_str} :coin:)"
        )

        if info_granted:
            msg += f"\n> :card_index: You also received the **{info_granted}** info card!"

        await interaction.response.send_message(msg)


class SpawnView(discord.ui.View):
    def __init__(self, spawn_id: str, card: dict, disabled: bool = False):
        super().__init__(timeout=None)
        self.spawn_id = spawn_id
        self.card     = card

        btn = discord.ui.Button(
            label="Sign me!",
            style=discord.ButtonStyle.primary,
            custom_id=f"sign_{spawn_id}",
            disabled=disabled,
        )
        btn.callback = self._sign_callback
        self.add_item(btn)

    async def _sign_callback(self, interaction: discord.Interaction):
        spawn = db.get_spawn(self.spawn_id)
        if not spawn or not spawn["is_active"]:
            await interaction.response.send_message(
                ":x: This card has already been signed!", ephemeral=True
            )
            return
        modal = SignModal(self.spawn_id, self.card, interaction.message)
        await interaction.response.send_modal(modal)


class SpawnSystem:
    def __init__(self, bot: discord.Client):
        self.bot               = bot
        self.spawn_channel_ids: list[int] = []
        self._task             = None

    def set_channels(self, channel_ids: list):
        """Alias to set spawn_channel_ids directly."""
        self.spawn_channel_ids = channel_ids

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

        spawn_id = str(uuid.uuid4())
        db.register_spawn(spawn_id, card["id"], variant, str(channel_id))

        # Spawn embed — large image, black/near-black, minimal text, matches F1dex
        embed = discord.Embed(color=0x000001)
        embed.set_image(url=card["image_url"])

        # Only show variant label if not Standard
        if variant != "Standard":
            v_emoji  = cu.get_variant_emoji(variant)
            gp_extra = ""
            if variant == "GP Specs" and active_gp:
                gp_extra = f" {active_gp.get('flag', '')} *{active_gp.get('name', 'GP Special')}*"
            embed.description = f"{v_emoji} **{variant}**{gp_extra}"

        embed.set_footer(text="Type the card name to sign it! | RFRXDex")

        spawn_caption = random.choice(SPAWN_CAPTIONS)
        view = SpawnView(spawn_id, card)
        msg  = await channel.send(
            content=f"*{spawn_caption}*",
            embed=embed,
            view=view
        )
        db.update_spawn_message(spawn_id, str(msg.id))
