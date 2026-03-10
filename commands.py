import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json

import database as db
import card_utils as cu

# ─── Embed helpers ────────────────────────────────────────────────────────────

def embed_error(msg: str) -> discord.Embed:
    return discord.Embed(description=f":x: {msg}", color=0xFF4444)

def embed_ok(title: str, desc: str, color: int = 0x5865F2) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)

RFRX_COLOR = 0x5865F2
MARKET_COLOR = 0xF1C40F
SUCCESS_COLOR = 0x00CC66

# ─── Pagination View ──────────────────────────────────────────────────────────

class PaginatorView(discord.ui.View):
    """Generic paginator: <<  Back  [page/total]  Next  >>  Quit"""
    def __init__(self, pages: list, author_id: int, title: str = ""):
        super().__init__(timeout=120)
        self.pages = pages
        self.author_id = author_id
        self.title = title
        self.current = 0
        self._refresh()

    def _refresh(self):
        self.first_btn.disabled = self.current == 0
        self.back_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current >= len(self.pages) - 1
        self.last_btn.disabled = self.current >= len(self.pages) - 1
        self.page_btn.label = f"{self.current + 1}/{len(self.pages)}"

    def current_embed(self) -> discord.Embed:
        return self.pages[self.current]

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(":x: This isn't your menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.primary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current = max(0, self.current - 1)
        self._refresh()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._refresh()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current = len(self.pages) - 1
        self._refresh()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.danger)
    async def quit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


# ─── Card icon grid builder ───────────────────────────────────────────────────

def build_icon_grid(card_ids: list, owned_ids: set, per_row: int = 10) -> str:
    """Returns emoji grid: colored circle if owned, grey if missing."""
    lines = []
    row = []
    for cid in card_ids:
        card = cu.get_card_by_id(cid)
        if not card:
            continue
        if cid in owned_ids:
            row.append(cu.get_rarity_emoji(card["rarity"]))
        else:
            row.append(":white_circle:")
        if len(row) == per_row:
            lines.append("".join(row))
            row = []
    if row:
        lines.append("".join(row))
    return "\n".join(lines) if lines else "None"


def build_collection_pages(target: discord.Member, inventory: list, info_cards: list, filter_variant: str = None, filter_season: str = None) -> list:
    """Builds paginated embeds for /collection command."""
    all_spawnable = [c for c in cu.get_all_cards() if c.get("spawnable")]
    
    # Apply filters
    if filter_variant:
        inv_filtered = [i for i in inventory if i["variant"].lower() == filter_variant.lower()]
    else:
        inv_filtered = inventory

    owned_card_ids = set(i["card_id"] for i in inv_filtered)
    total_spawnable = len(all_spawnable)
    owned_count = len([c for c in all_spawnable if c["id"] in owned_card_ids])
    progress_pct = (owned_count / total_spawnable * 100) if total_spawnable > 0 else 0.0

    # Split into pages of 20 cards each
    PER_PAGE = 20
    pages = []
    all_ids = [c["id"] for c in all_spawnable]

    for page_start in range(0, max(len(all_ids), 1), PER_PAGE):
        chunk = all_ids[page_start:page_start + PER_PAGE]
        owned_in_chunk = [cid for cid in chunk if cid in owned_card_ids]
        missing_in_chunk = [cid for cid in chunk if cid not in owned_card_ids]
        page_num = page_start // PER_PAGE + 1
        total_pages = max(1, -(-len(all_ids) // PER_PAGE))

        embed = discord.Embed(
            color=RFRX_COLOR
        )
        embed.set_author(
            name=f"{target.display_name}",
            icon_url=target.display_avatar.url
        )
        embed.description = f"**RFRXDex progression: {progress_pct:.1f}%**"

        # Owned section
        owned_grid = build_icon_grid(owned_in_chunk, owned_card_ids)
        if owned_grid:
            embed.add_field(name="__Owned cards__", value=owned_grid, inline=False)

        # Missing section
        missing_grid = build_icon_grid(missing_in_chunk, owned_card_ids)
        if missing_grid and missing_in_chunk:
            embed.add_field(name="__Missing cards__", value=missing_grid, inline=False)
        elif not missing_in_chunk:
            embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)

        embed.set_footer(text=f"Page {page_num}/{total_pages} | RFRXDex")
        pages.append(embed)

    return pages if pages else [discord.Embed(description="No cards found.", color=RFRX_COLOR)]


# ─── COG: Collection ──────────────────────────────────────────────────────────

class CollectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="collection", description="View your card collection")
    @app_commands.describe(
        user="Whose collection to view",
        card="Filter by a specific card name",
        variant="Filter by variant (Shiny, DOTD, etc.)",
        season="Filter by season tag"
    )
    async def collection(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        card: Optional[str] = None,
        variant: Optional[str] = None,
        season: Optional[str] = None
    ):
        target = user or interaction.user
        db.ensure_user(str(target.id), target.display_name)

        inventory = db.get_user_inventory(str(target.id))
        info_cards = db.get_user_info_cards(str(target.id))

        pages = build_collection_pages(target, inventory, info_cards, filter_variant=variant, filter_season=season)
        view = PaginatorView(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view)

    @app_commands.command(name="completion", description="View collection completion percentage")
    @app_commands.describe(
        user="Whose completion to view",
        special="Filter by special variant",
        season="Filter by season",
        all="Show all cards including missing (True/False)"
    )
    async def completion(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        special: Optional[str] = None,
        season: Optional[str] = None,
        all: Optional[str] = None
    ):
        target = user or interaction.user
        db.ensure_user(str(target.id), target.display_name)
        inventory = db.get_user_inventory(str(target.id))
        all_spawnable = [c for c in cu.get_all_cards() if c.get("spawnable")]
        owned_ids = set(i["card_id"] for i in inventory)
        owned_count = len([c for c in all_spawnable if c["id"] in owned_ids])
        total = len(all_spawnable)
        pct = (owned_count / total * 100) if total > 0 else 0.0

        missing = [c for c in all_spawnable if c["id"] not in owned_ids]
        owned = [c for c in all_spawnable if c["id"] in owned_ids]

        PER_PAGE = 30
        pages = []
        show_missing = all and all.lower() == "true"

        # Build owned grid pages
        all_display = owned + (missing if show_missing else [])
        for i in range(0, max(len(all_display), 1), PER_PAGE):
            chunk = all_display[i:i + PER_PAGE]
            embed = discord.Embed(color=RFRX_COLOR)
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
            embed.description = f"**RFRXDex (F1 2025) progression: {pct:.1f}%**"

            owned_chunk = [c for c in chunk if c["id"] in owned_ids]
            missing_chunk = [c for c in chunk if c["id"] not in owned_ids]

            if owned_chunk:
                grid = " ".join(cu.get_rarity_emoji(c["rarity"]) for c in owned_chunk)
                embed.add_field(name="__Owned cards__", value=grid, inline=False)
            if missing_chunk:
                grid = " ".join(":white_circle:" for _ in missing_chunk)
                embed.add_field(name="__Missing cards__", value=grid, inline=False)
            if not missing_chunk and not owned_chunk:
                embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)

            page_num = i // PER_PAGE + 1
            total_pages = max(1, -(-len(all_display) // PER_PAGE))
            embed.set_footer(text=f"Page {page_num}/{total_pages} | {owned_count}/{total} owned | RFRXDex")
            pages.append(embed)

        view = PaginatorView(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view)

    @app_commands.command(name="card", description="View details of a specific card")
    @app_commands.describe(name="Card name or ID")
    async def card_info(self, interaction: discord.Interaction, name: str):
        card = cu.get_card_by_name(name) or cu.get_card_by_id(name.lower().replace(" ", "_"))
        if not card:
            await interaction.response.send_message(embed=embed_error(f"Card `{name}` not found."), ephemeral=True)
            return

        color = cu.get_rarity_color(card["rarity"])
        r_emoji = cu.get_rarity_emoji(card["rarity"])
        current_val = db.get_current_value(card["id"], "Standard", card["base_value"])

        embed = discord.Embed(title=f"{r_emoji} {card['name']}", color=color)
        embed.set_image(url=card["image_url"])
        embed.add_field(name="Type", value=card["type"].capitalize(), inline=True)
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Value", value=f"{current_val:,} coins", inline=True)
        embed.add_field(name="Marketable", value="Yes" if card["marketable"] else "No", inline=True)
        embed.add_field(name="Giftable", value="Yes" if card["giftable"] else "No", inline=True)
        embed.add_field(name="Spawnable", value="Yes" if card["spawnable"] else "No", inline=True)
        if card.get("special_variants"):
            embed.add_field(name="Variants", value=", ".join(card["special_variants"]), inline=False)
        if card.get("info_card_id"):
            ic = cu.get_card_by_id(card["info_card_id"])
            if ic:
                embed.add_field(name="Info Card", value=ic["name"], inline=True)
        embed.set_footer(text="RFRXDex")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coins", description="Check your coin balance")
    @app_commands.describe(user="Check another user's balance")
    async def coins(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        db.ensure_user(str(target.id), target.display_name)
        data = db.get_user(str(target.id))
        embed = discord.Embed(
            title=f"{target.display_name}'s Balance",
            description=f":coin: **{data['coins']:,}** coins",
            color=MARKET_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)


# ─── COG: Market ──────────────────────────────────────────────────────────────

class MarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_market_pages(self, listings: list, guild: discord.Guild) -> list:
        PER_PAGE = 10
        pages = []
        for i in range(0, max(len(listings), 1), PER_PAGE):
            chunk = listings[i:i + PER_PAGE]
            embed = discord.Embed(title=":shopping_cart: RFRXDex Global Market", color=MARKET_COLOR)
            if not chunk:
                embed.description = "No cards listed for sale right now."
            else:
                for lst in chunk:
                    c = cu.get_card_by_id(lst["card_id"])
                    if not c:
                        continue
                    v_emoji = cu.get_variant_emoji(lst["variant"])
                    r_emoji = cu.get_rarity_emoji(c["rarity"])
                    seller = guild.get_member(int(lst["seller_id"])) if guild else None
                    seller_name = seller.display_name if seller else f"User#{lst['seller_id'][-4:]}"
                    embed.add_field(
                        name=f"{v_emoji} {c['name']} [{lst['variant']}]",
                        value=(
                            f"{r_emoji} {c['rarity'].capitalize()} | "
                            f":coin: **{lst['price']:,}** | "
                            f"Seller: {seller_name} | "
                            f"ID: `{lst['listing_id']}`"
                        ),
                        inline=False
                    )
            page_num = i // PER_PAGE + 1
            total_pages = max(1, -(-len(listings) // PER_PAGE))
            embed.set_footer(text=f"Page {page_num}/{total_pages} | Use /buy <listing_id> | RFRXDex")
            pages.append(embed)
        return pages

    @app_commands.command(name="market", description="Browse the global card market")
    @app_commands.describe(card="Filter by card name")
    async def market(self, interaction: discord.Interaction, card: Optional[str] = None):
        card_filter = None
        if card:
            card_filter = cu.get_card_by_name(card)
            if not card_filter:
                await interaction.response.send_message(embed=embed_error(f"Card `{card}` not found."), ephemeral=True)
                return

        listings = db.get_active_listings(card_filter["id"] if card_filter else None)
        pages = self._build_market_pages(listings, interaction.guild)
        view = PaginatorView(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view)

    @app_commands.command(name="sell", description="List a card for sale on the market")
    @app_commands.describe(instance_id="Card instance ID from /collection", price="Asking price in coins")
    async def sell(self, interaction: discord.Interaction, instance_id: str, price: int):
        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        my_inv = db.get_user_inventory(str(interaction.user.id))
        item = next((x for x in my_inv if x["instance_id"].startswith(instance_id)), None)

        if not item:
            await interaction.response.send_message(embed=embed_error("Card not found in your inventory."), ephemeral=True)
            return

        card = cu.get_card_by_id(item["card_id"])
        if not card or not card["marketable"]:
            await interaction.response.send_message(embed=embed_error(f"**{card['name'] if card else instance_id}** cannot be sold."), ephemeral=True)
            return
        if price < 1:
            await interaction.response.send_message(embed=embed_error("Price must be at least 1 coin."), ephemeral=True)
            return

        db.remove_card_from_inventory(item["instance_id"])
        lid = db.create_listing(str(interaction.user.id), card["id"], item["variant"], item["instance_id"], price)

        v_emoji = cu.get_variant_emoji(item["variant"])
        embed = discord.Embed(
            description=f"{v_emoji} **{cu.get_card_display_name(card, item['variant'])}** listed for :coin: **{price:,}**\nListing ID: `{lid}`",
            color=SUCCESS_COLOR
        )
        embed.set_author(name="Card Listed!", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy a card from the market")
    @app_commands.describe(listing_id="The listing ID from /market")
    async def buy(self, interaction: discord.Interaction, listing_id: int):
        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        listings = db.get_active_listings()
        listing = next((l for l in listings if l["listing_id"] == listing_id), None)

        if not listing:
            await interaction.response.send_message(embed=embed_error("Listing not found or already sold."), ephemeral=True)
            return
        if listing["seller_id"] == str(interaction.user.id):
            await interaction.response.send_message(embed=embed_error("You can't buy your own listing!"), ephemeral=True)
            return

        buyer_data = db.get_user(str(interaction.user.id))
        if buyer_data["coins"] < listing["price"]:
            await interaction.response.send_message(
                embed=embed_error(f"Not enough coins. Need :coin: {listing['price']:,}, have :coin: {buyer_data['coins']:,}."),
                ephemeral=True
            )
            return

        completed = db.complete_listing(listing_id, str(interaction.user.id))
        if not completed:
            await interaction.response.send_message(embed=embed_error("Listing no longer available."), ephemeral=True)
            return

        db.deduct_coins(str(interaction.user.id), listing["price"])
        db.add_coins(listing["seller_id"], listing["price"])
        new_instance = cu.generate_instance_id()
        db.add_card_to_inventory(str(interaction.user.id), listing["card_id"], listing["variant"], listing["price"], new_instance)

        card = cu.get_card_by_id(listing["card_id"])
        if card:
            db.update_dynamic_price(card["id"], listing["variant"], card["base_value"], listing["price"])
            db.record_sale(card["id"], listing["variant"], listing["price"], listing["seller_id"], str(interaction.user.id))

        v_emoji = cu.get_variant_emoji(listing["variant"])
        embed = discord.Embed(
            description=f"{v_emoji} **{cu.get_card_display_name(card, listing['variant'])}** purchased for :coin: **{listing['price']:,}**!",
            color=SUCCESS_COLOR
        )
        embed.set_author(name="Purchase Complete!", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delist", description="Remove your listing from the market")
    @app_commands.describe(listing_id="Listing ID to cancel")
    async def delist(self, interaction: discord.Interaction, listing_id: int):
        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        listing = next((l for l in db.get_active_listings() if l["listing_id"] == listing_id), None)
        if not listing:
            await interaction.response.send_message(embed=embed_error("Listing not found."), ephemeral=True)
            return
        if listing["seller_id"] != str(interaction.user.id):
            await interaction.response.send_message(embed=embed_error("That is not your listing."), ephemeral=True)
            return

        cancelled = db.cancel_listing(listing_id, str(interaction.user.id))
        if cancelled:
            new_instance = cu.generate_instance_id()
            db.add_card_to_inventory(str(interaction.user.id), listing["card_id"], listing["variant"], listing["price"], new_instance)
            await interaction.response.send_message(embed=embed_ok("Listing Cancelled", "Card returned to your inventory."))
        else:
            await interaction.response.send_message(embed=embed_error("Could not cancel listing."), ephemeral=True)


# ─── COG: Trade ───────────────────────────────────────────────────────────────

class TradeConfirmView(discord.ui.View):
    def __init__(self, trade_id: int, target_id: int):
        super().__init__(timeout=120)
        self.trade_id = trade_id
        self.target_id = target_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This trade is not for you.", ephemeral=True)
            return
        trade = db.get_trade(self.trade_id)
        if not trade or trade["status"] != "pending":
            await interaction.response.send_message("Trade is no longer active.", ephemeral=True)
            return

        for inst_id in trade["offer_cards"]:
            inv = db.get_inventory_instance(inst_id)
            if inv:
                db.transfer_card(inst_id, str(self.target_id))
        for inst_id in trade["request_cards"]:
            inv = db.get_inventory_instance(inst_id)
            if inv:
                db.transfer_card(inst_id, trade["initiator_id"])

        db.resolve_trade(self.trade_id, "completed")
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f":white_check_mark: Trade `#{self.trade_id}` completed!")

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        trade = db.get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        if interaction.user.id != self.target_id and str(interaction.user.id) != trade["initiator_id"]:
            await interaction.response.send_message("You cannot decline this trade.", ephemeral=True)
            return
        db.resolve_trade(self.trade_id, "declined")
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(":x: Trade declined.")


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="trade", description="Propose a card trade with another user")
    @app_commands.describe(
        user="User to trade with",
        offer="Instance ID(s) you offer, comma-separated",
        request="Instance ID(s) you want, comma-separated"
    )
    async def trade(self, interaction: discord.Interaction, user: discord.Member, offer: str, request: str):
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=embed_error("You can't trade with yourself."), ephemeral=True)
            return

        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        db.ensure_user(str(user.id), user.display_name)

        offer_ids = [x.strip() for x in offer.split(",")]
        request_ids = [x.strip() for x in request.split(",")]

        my_inv = db.get_user_inventory(str(interaction.user.id))
        their_inv = db.get_user_inventory(str(user.id))
        my_iids = [i["instance_id"] for i in my_inv]
        their_iids = [i["instance_id"] for i in their_inv]

        def resolve(id_list, iids):
            resolved = []
            for short in id_list:
                matches = [x for x in iids if x.startswith(short)]
                if not matches:
                    return None, short
                resolved.append(matches[0])
            return resolved, None

        full_offer, err = resolve(offer_ids, my_iids)
        if err:
            await interaction.response.send_message(embed=embed_error(f"Card `{err}` not in your inventory."), ephemeral=True)
            return

        full_request, err = resolve(request_ids, their_iids)
        if err:
            await interaction.response.send_message(embed=embed_error(f"{user.display_name} doesn't have card `{err}`."), ephemeral=True)
            return

        trade_id = db.create_trade(str(interaction.user.id), str(user.id), full_offer, full_request)

        def card_list_str(ids, inv):
            parts = []
            for iid in ids:
                item = next((x for x in inv if x["instance_id"] == iid), None)
                if item:
                    c = cu.get_card_by_id(item["card_id"])
                    name = cu.get_card_display_name(c, item["variant"]) if c else item["card_id"]
                    v_emoji = cu.get_variant_emoji(item["variant"])
                    parts.append(f"{v_emoji} {name} `#{iid[:8]}`")
            return "\n".join(parts) if parts else "None"

        embed = discord.Embed(
            title=f"Trade Proposal #{trade_id}",
            color=RFRX_COLOR
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{interaction.user.display_name} offers", value=card_list_str(full_offer, my_inv), inline=True)
        embed.add_field(name=f"{interaction.user.display_name} requests", value=card_list_str(full_request, their_inv), inline=True)
        embed.set_footer(text="Expires in 2 minutes | RFRXDex")

        view = TradeConfirmView(trade_id, user.id)
        await interaction.response.send_message(content=user.mention, embed=embed, view=view)

    @app_commands.command(name="trade_history", description="View your recent trade history")
    async def trade_history(self, interaction: discord.Interaction):
        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT * FROM trades WHERE initiator_id = ? OR target_id = ? ORDER BY created_at DESC LIMIT 10",
            (str(interaction.user.id), str(interaction.user.id))
        ).fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message(embed=embed_ok("Trade History", "No trades yet."), ephemeral=True)
            return

        embed = discord.Embed(title="Your Trade History", color=RFRX_COLOR)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        for row in rows:
            t = dict(row)
            status_emoji = {"completed": ":white_check_mark:", "declined": ":x:", "pending": ":hourglass:"}.get(t["status"], "?")
            other_id = t["target_id"] if t["initiator_id"] == str(interaction.user.id) else t["initiator_id"]
            embed.add_field(
                name=f"{status_emoji} Trade #{t['trade_id']}",
                value=f"With: <@{other_id}> | {t['status'].capitalize()} | {t['created_at'][:10]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── COG: Give ────────────────────────────────────────────────────────────────

class GiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="give", description="Give a card to another user")
    @app_commands.describe(
        user="The user you want to give a card to",
        card="The card you are giving away",
        special="Optional: variant of the card",
        season="Optional: season tag filter"
    )
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        card: str,
        special: Optional[str] = None,
        season: Optional[str] = None
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=embed_error("You can't give cards to yourself!"), ephemeral=True)
            return

        db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        db.ensure_user(str(user.id), user.display_name)

        # Find card in sender's inventory by name
        my_inv = db.get_user_inventory(str(interaction.user.id))
        card_data = cu.get_card_by_name(card) or cu.get_card_by_id(card.lower().replace(" ", "_"))
        if not card_data:
            await interaction.response.send_message(embed=embed_error(f"Card `{card}` not found."), ephemeral=True)
            return

        # Find matching instance
        matching = [i for i in my_inv if i["card_id"] == card_data["id"]]
        if special:
            matching = [i for i in matching if i["variant"].lower() == special.lower()]
        if not matching:
            await interaction.response.send_message(
                embed=embed_error(f"You don't have **{card_data['name']}**{f' [{special}]' if special else ''} in your inventory."),
                ephemeral=True
            )
            return

        if not card_data.get("giftable", True):
            await interaction.response.send_message(embed=embed_error(f"**{card_data['name']}** cannot be gifted."), ephemeral=True)
            return

        item = matching[0]
        db.transfer_card(item["instance_id"], str(user.id))

        v_emoji = cu.get_variant_emoji(item["variant"])
        embed = discord.Embed(
            description=f"{v_emoji} **{cu.get_card_display_name(card_data, item['variant'])}** given to **{user.display_name}**!",
            color=SUCCESS_COLOR
        )
        embed.set_author(name="Card Given!", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)


# ─── COG: History ─────────────────────────────────────────────────────────────

class HistoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="card_history", description="View market history and stats for a card")
    @app_commands.describe(name="Card name", variant="Variant (default: Standard)")
    async def card_history(self, interaction: discord.Interaction, name: str, variant: str = "Standard"):
        card = cu.get_card_by_name(name) or cu.get_card_by_id(name.lower().replace(" ", "_"))
        if not card:
            await interaction.response.send_message(embed=embed_error(f"Card `{name}` not found."), ephemeral=True)
            return

        stats = db.get_card_history_stats(card["id"], variant)
        current_val = db.get_current_value(card["id"], variant, card["base_value"])
        base_val = card["base_value"]
        pct = ((current_val - base_val) / base_val * 100) if base_val else 0
        pct_str = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"

        v_emoji = cu.get_variant_emoji(variant)
        color = cu.get_rarity_color(card["rarity"])

        embed = discord.Embed(title=f"{v_emoji} {card['name']} [{variant}] - Market History", color=color)
        embed.set_thumbnail(url=card["image_url"])
        embed.add_field(name="Base Value", value=f":coin: {base_val:,}", inline=True)
        embed.add_field(name="Current Value", value=f":coin: {current_val:,} ({pct_str})", inline=True)
        embed.add_field(name="Total Sales", value=str(stats["total_sales"]), inline=True)
        embed.add_field(name="Total Owners", value=str(stats["total_owners"]), inline=True)
        if stats["total_sales"] > 0:
            embed.add_field(name="Lowest Sale", value=f":coin: {stats['min']:,}", inline=True)
            embed.add_field(name="Highest Sale", value=f":coin: {stats['max']:,}", inline=True)
            embed.add_field(name="Average Sale", value=f":coin: {stats['avg']:,}", inline=True)
        if stats["daily"]:
            daily_str = ""
            for d in stats["daily"][:7]:
                daily_str += f"`{d['value_date']}` avg {d['avg_price']:,} | sales {d['num_sales']}\n"
            embed.add_field(name="Recent Daily History", value=daily_str, inline=False)
        embed.set_footer(text="RFRXDex Market History")
        await interaction.response.send_message(embed=embed)


# ─── COG: Leaderboard ─────────────────────────────────────────────────────────

class LeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="View RFRXDex leaderboards")
    @app_commands.describe(category="collectors | rare | wealth")
    @app_commands.choices(category=[
        app_commands.Choice(name="Collectors - most cards owned", value="collectors"),
        app_commands.Choice(name="Rare - most special variant cards", value="rare"),
        app_commands.Choice(name="Wealth - highest total value", value="wealth"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str = "collectors"):
        if category == "collectors":
            rows = db.leaderboard_collectors()
            title = "Top Collectors"
            field_key = "card_count"
            unit = "cards"
        elif category == "rare":
            rows = db.leaderboard_rare()
            title = "Rare Card Leaders"
            field_key = "rare_count"
            unit = "special cards"
        else:
            rows = db.leaderboard_wealth()
            title = "Wealthiest Collectors"
            field_key = "total_value"
            unit = "coins value"

        medals = [":first_place:", ":second_place:", ":third_place:"]
        embed = discord.Embed(title=title, color=MARKET_COLOR)
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"**#{i+1}**"
            val = row.get(field_key) or 0
            name = row.get("username") or f"User#{row['user_id'][-4:]}"
            lines.append(f"{medal} **{name}** - {val:,} {unit}")
        embed.description = "\n".join(lines) if lines else "No data yet."
        embed.set_footer(text="RFRXDex Leaderboard")
        await interaction.response.send_message(embed=embed)


# ─── COG: Admin ───────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, user: discord.Member) -> bool:
        if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
            return True
        return any(r.name in ["DEX Admin", "Staff", "Owner"] for r in getattr(user, "roles", []))

    @app_commands.command(name="admin_give", description="[Admin] Give a card to a user")
    @app_commands.describe(user="Target user", card_name="Card name", variant="Variant (default: Standard)")
    async def admin_give(self, interaction: discord.Interaction, user: discord.Member, card_name: str, variant: str = "Standard"):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(embed=embed_error("Admin only!"), ephemeral=True)
            return

        card = cu.get_card_by_name(card_name) or cu.get_card_by_id(card_name.lower().replace(" ", "_"))
        if not card:
            await interaction.response.send_message(embed=embed_error(f"Card `{card_name}` not found."), ephemeral=True)
            return

        db.ensure_user(str(user.id), user.display_name)
        instance_id = cu.generate_instance_id()
        value = db.get_current_value(card["id"], variant, card["base_value"])
        db.add_card_to_inventory(str(user.id), card["id"], variant, value, instance_id)
        if card.get("info_card_id"):
            db.grant_info_card(str(user.id), card["info_card_id"])

        embed = discord.Embed(
            description=f"Gave **{cu.get_card_display_name(card, variant)}** to **{user.display_name}**.",
            color=SUCCESS_COLOR
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="admin_spawn", description="[Admin] Force a card spawn in this channel")
    async def admin_spawn(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(embed=embed_error("Admin only!"), ephemeral=True)
            return
        await interaction.response.send_message("Forcing a spawn...", ephemeral=True)
        await interaction.client.spawn_system.do_spawn(channel_id=interaction.channel_id)

    @app_commands.command(name="set_spawn_channel", description="[Admin] Add this channel to spawn rotation")
    async def set_spawn_channel(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(embed=embed_error("Admin only!"), ephemeral=True)
            return
        cid = interaction.channel_id
        if cid not in interaction.client.spawn_system.spawn_channel_ids:
            interaction.client.spawn_system.spawn_channel_ids.append(cid)
            await interaction.response.send_message(embed=embed_ok("Spawn Channel Added", f"<#{cid}> added to spawn rotation."))
        else:
            await interaction.response.send_message(embed=embed_ok("Already Added", f"<#{cid}> is already in spawn rotation."))

    @app_commands.command(name="admin_coins", description="[Admin] Add or remove coins from a user")
    @app_commands.describe(user="Target user", amount="Amount to add (negative to remove)")
    async def admin_coins(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(embed=embed_error("Admin only!"), ephemeral=True)
            return
        db.ensure_user(str(user.id), user.display_name)
        db.add_coins(str(user.id), amount)
        data = db.get_user(str(user.id))
        await interaction.response.send_message(
            embed=embed_ok("Coins Updated", f"**{user.display_name}** now has :coin: **{data['coins']:,}**.")
        )


# ─── COG: Help & Guide ────────────────────────────────────────────────────────

GUIDE_PAGES = [
    {
        "title": "RFRXDex Guide - Page 1: Getting Started",
        "color": RFRX_COLOR,
        "description": (
            "Welcome to **RFRXDex** - the official RFRX League collectible card bot!\n\n"
            "Cards spawn automatically in designated channels every **5-15 minutes**. "
            "When one appears, hit the **Sign** button, then type the card name to claim it!\n\n"
            "Info cards are granted **automatically** when you catch the parent card."
        ),
        "fields": [
            ("How Spawns Work", (
                "- A card image appears with a caption\n"
                "- Click **Sign** to open the name input\n"
                "- Type the correct card name to claim it\n"
                "- Wrong guess = fail message, others can still claim\n"
                "- Cards spawn every **5-15 min** (randomised)"
            ), False),
            ("Catch Message Format", (
                "```\nUser signed 'McLaren'! (#a3f2b1c8, +12.5%/+45.0%)\nCard Type: Team\nVariant: Shiny\nCurrent Value: 1,000 coins\n```"
            ), False),
        ]
    },
    {
        "title": "RFRXDex Guide - Page 2: Rarities & Variants",
        "color": MARKET_COLOR,
        "description": "Every card has a base rarity and may roll a special variant.",
        "fields": [
            ("Base Rarities", (
                ":white_circle: Common | :blue_circle: Rare | :purple_circle: Epic\n"
                ":orange_circle: Mythic | :star: Champion | :red_circle: Limited"
            ), True),
            ("Special Variants & Chances", (
                ":race_car: GP Specs - 20% (active GP only)\n"
                ":trophy: DOTD - 15%\n"
                ":sparkles: Shiny - 10%\n"
                ":crystal_ball: Secret Rare - 3%\n"
                ":gem: Ultra Rare - 1%\n"
                ":crown: Collectors Special - collection reward"
            ), True),
            ("Value Multipliers", (
                "GP Specs x2.5 | DOTD x1.8 | Shiny x2.0\n"
                "Secret Rare x4.0 | Ultra Rare x8.0 | Collectors Special x15.0"
            ), False),
        ]
    },
    {
        "title": "RFRXDex Guide - Page 3: Commands",
        "color": RFRX_COLOR,
        "description": "All available commands:",
        "fields": [
            ("Collection", (
                "`/collection` - View your cards\n"
                "`/completion` - Collection progress %\n"
                "`/card <name>` - Card details\n"
                "`/coins` - Check balance"
            ), True),
            ("Market", (
                "`/market` - Browse listings\n"
                "`/sell <id> <price>` - List card\n"
                "`/buy <listing_id>` - Buy card\n"
                "`/delist <id>` - Cancel listing"
            ), True),
            ("Trading & Gifts", (
                "`/trade @user <offer> <want>` - Trade\n"
                "`/trade_history` - Past trades\n"
                "`/give @user <card>` - Gift a card"
            ), True),
            ("Stats", (
                "`/card_history <name>` - Price history\n"
                "`/leaderboard` - Rankings"
            ), True),
            ("Admin", (
                "`/admin_give` | `/admin_spawn`\n"
                "`/set_spawn_channel` | `/admin_coins`"
            ), True),
        ]
    },
    {
        "title": "RFRXDex Guide - Page 4: Market & Trading",
        "color": MARKET_COLOR,
        "description": "Buy, sell, and trade cards with other collectors.",
        "fields": [
            ("Selling", (
                "Use `/sell <instance_id> <price>` to list a card.\n"
                "Get your instance ID from `/collection`.\n"
                "Card leaves your inventory until sold or delisted."
            ), False),
            ("Buying", (
                "Use `/market` to browse listings.\n"
                "Use `/buy <listing_id>` to purchase.\n"
                "Coins are transferred instantly."
            ), False),
            ("Trading", (
                "Use `/trade @user <offer_ids> <request_ids>`.\n"
                "Comma-separate multiple IDs.\n"
                "Target gets Accept/Decline buttons. Expires in 2 min."
            ), False),
            ("Dynamic Pricing", (
                "Prices update after each sale:\n"
                "`new = 70% old + 30% sale + 2% drift`\n"
                "High demand = rising prices."
            ), False),
        ]
    },
    {
        "title": "RFRXDex Guide - Page 5: Admin & Config",
        "color": 0xFF6B35,
        "description": "Staff commands. Requires Administrator permission or DEX Admin / Staff / Owner role.",
        "fields": [
            ("`/set_spawn_channel`", "Add current channel to spawn rotation.", True),
            ("`/admin_spawn`", "Force an immediate spawn here.", True),
            ("`/admin_give @user <card> [variant]`", "Give any card to a user. Info card auto-granted.", False),
            ("`/admin_coins @user <amount>`", "Add/remove coins. Use negative to deduct.", False),
            ("Config Tips", (
                "- Edit `cards.json` to add/modify cards\n"
                "- Set `gp_specs.active` to current GP id\n"
                "- Set `marketable: false` to block listing\n"
                "- Set `giftable: false` to block gifting"
            ), False),
        ]
    },
]


class GuidePaginatorView(discord.ui.View):
    def __init__(self, pages: list, author_id: int, current_page: int = 0):
        super().__init__(timeout=120)
        self.pages = pages
        self.author_id = author_id
        self.current_page = current_page
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
        self.page_counter.label = f"{self.current_page + 1} / {len(self.pages)}"

    def build_embed(self) -> discord.Embed:
        page = self.pages[self.current_page]
        embed = discord.Embed(title=page["title"], description=page["description"], color=page["color"])
        for field in page.get("fields", []):
            embed.add_field(name=field[0], value=field[1], inline=field[2])
        embed.set_footer(text=f"RFRXDex Guide | Page {self.current_page + 1}/{len(self.pages)}")
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your guide.", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="1 / 5", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your guide.", ephemeral=True)
            return
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.danger)
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your guide.", ephemeral=True)
            return
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View all RFRXDex commands at a glance")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="RFRXDex - Command Reference",
            description="The RFRX League collectible card bot.\nSpawn, catch, trade, and collect rare cards!\n\nUse `/guide` for the full walkthrough.",
            color=RFRX_COLOR
        )
        embed.add_field(name="Collection", value="`/collection` `/completion` `/card` `/coins`", inline=True)
        embed.add_field(name="Market", value="`/market` `/sell` `/buy` `/delist`", inline=True)
        embed.add_field(name="Trading", value="`/trade` `/trade_history` `/give`", inline=True)
        embed.add_field(name="Stats", value="`/card_history` `/leaderboard`", inline=True)
        embed.add_field(name="Admin", value="`/admin_give` `/admin_spawn` `/set_spawn_channel` `/admin_coins`", inline=True)
        embed.add_field(name="Variants", value=":race_car: GP Specs | :trophy: DOTD | :sparkles: Shiny | :crystal_ball: Secret Rare | :gem: Ultra Rare | :crown: Collectors", inline=False)
        embed.set_footer(text="RFRXDex | Use /guide for full details")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="guide", description="Full interactive RFRXDex guide (5 pages)")
    @app_commands.describe(page="Start on a specific page (1-5)")
    async def guide(self, interaction: discord.Interaction, page: int = 1):
        page_idx = max(1, min(page, len(GUIDE_PAGES))) - 1
        view = GuidePaginatorView(GUIDE_PAGES, interaction.user.id, current_page=page_idx)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─── Setup ────────────────────────────────────────────────────────────────────

async def setup(bot):
    await bot.add_cog(CollectionCog(bot))
    await bot.add_cog(MarketCog(bot))
    await bot.add_cog(TradeCog(bot))
    await bot.add_cog(GiveCog(bot))
    await bot.add_cog(HistoryCog(bot))
    await bot.add_cog(LeaderboardCog(bot))
    await bot.add_cog(AdminCog(bot))
    await bot.add_cog(HelpCog(bot))
