“””
commands.py - All slash commands for RFRXDex
Styled to match F1dex/Ballsdex UX exactly.
“””

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
import json

import database as db
import card_utils as cu

# ── Colors ───────────────────────────────────────────────────────────────────

RFRX_COLOR   = 0x5865F2
MARKET_COLOR = 0xF1C40F
SUCCESS_COLOR = 0x57F287
ERROR_COLOR   = 0xED4245

ROSTER_TYPES = [“Offense”, “Defense”, “Balance”]
SEASONS      = [“F1 2024”, “Icons”, “F1 2025”, “Limited”, “F1 2026”]
SPECIALS     = [“Contributor”, “Italian GP”, “Dutch GP”, “Summer Break”, “Singapore GP”,
“Chinese GP”, “Japanese GP”, “Bahrain GP”, “Saudi GP”, “Australian GP”]

# ── Embed helpers ─────────────────────────────────────────────────────────────

def err(msg: str) -> discord.Embed:
return discord.Embed(description=f”:x: {msg}”, color=ERROR_COLOR)

def ok(desc: str, color: int = SUCCESS_COLOR) -> discord.Embed:
return discord.Embed(description=desc, color=color)

# ── Generic paginator ─────────────────────────────────────────────────────────

class Pages(discord.ui.View):
def **init**(self, pages: list[discord.Embed], author_id: int):
super().**init**(timeout=120)
self.pages = pages
self.author_id = author_id
self.idx = 0
self._sync()

```
def _sync(self):
    self.btn_first.disabled = self.idx == 0
    self.btn_back.disabled  = self.idx == 0
    self.btn_next.disabled  = self.idx >= len(self.pages) - 1
    self.btn_last.disabled  = self.idx >= len(self.pages) - 1
    self.btn_page.label     = f"{self.idx + 1}/{len(self.pages)}"

async def _guard(self, i: discord.Interaction) -> bool:
    if i.user.id != self.author_id:
        await i.response.send_message("This menu isn't yours.", ephemeral=True)
        return False
    return True

@discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
async def btn_first(self, i: discord.Interaction, b: discord.ui.Button):
    if not await self._guard(i): return
    self.idx = 0; self._sync()
    await i.response.edit_message(embed=self.pages[self.idx], view=self)

@discord.ui.button(label="Back", style=discord.ButtonStyle.primary)
async def btn_back(self, i: discord.Interaction, b: discord.ui.Button):
    if not await self._guard(i): return
    self.idx = max(0, self.idx - 1); self._sync()
    await i.response.edit_message(embed=self.pages[self.idx], view=self)

@discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
async def btn_page(self, i: discord.Interaction, b: discord.ui.Button): pass

@discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
async def btn_next(self, i: discord.Interaction, b: discord.ui.Button):
    if not await self._guard(i): return
    self.idx = min(len(self.pages) - 1, self.idx + 1); self._sync()
    await i.response.edit_message(embed=self.pages[self.idx], view=self)

@discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
async def btn_last(self, i: discord.Interaction, b: discord.ui.Button):
    if not await self._guard(i): return
    self.idx = len(self.pages) - 1; self._sync()
    await i.response.edit_message(embed=self.pages[self.idx], view=self)

@discord.ui.button(label="Quit", style=discord.ButtonStyle.danger)
async def btn_quit(self, i: discord.Interaction, b: discord.ui.Button):
    if not await self._guard(i): return
    self.stop()
    for c in self.children: c.disabled = True
    await i.response.edit_message(view=self)

async def on_timeout(self):
    for c in self.children: c.disabled = True
```

# ── Collection helper ─────────────────────────────────────────────────────────

def _collection_pages(target: discord.Member, inventory: list, season: str = None) -> list[discord.Embed]:
all_cards = [c for c in cu.get_all_cards() if c.get(“spawnable”)]
if season:
all_cards = [c for c in all_cards if c.get(“season”, “”).lower() == season.lower()]

```
owned_ids = set(item["card_id"] for item in inventory)
total     = len(all_cards)
owned_n   = sum(1 for c in all_cards if c["id"] in owned_ids)
pct       = (owned_n / total * 100) if total else 0.0

PER_PAGE  = 20
pages     = []
chunks    = [all_cards[i:i+PER_PAGE] for i in range(0, max(len(all_cards), 1), PER_PAGE)]

for p_idx, chunk in enumerate(chunks):
    owned_chunk   = [c for c in chunk if c["id"] in owned_ids]
    missing_chunk = [c for c in chunk if c["id"] not in owned_ids]

    embed = discord.Embed(color=RFRX_COLOR)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
    embed.description = f"**RFRXDex progression: {pct:.1f}%**"

    if owned_chunk:
        grid = " ".join(cu.get_rarity_emoji(c["rarity"]) for c in owned_chunk)
        embed.add_field(name="__Owned cards__", value=grid, inline=False)

    if missing_chunk:
        grid = " ".join(":white_circle:" for _ in missing_chunk)
        embed.add_field(name="__Missing cards__", value=grid, inline=False)
    elif not missing_chunk and not owned_chunk:
        embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)
    elif not missing_chunk:
        embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)

    embed.set_footer(text=f"Page {p_idx+1}/{len(chunks)} | {owned_n}/{total} owned | RFRXDex")
    pages.append(embed)

return pages or [discord.Embed(description="No cards found.", color=RFRX_COLOR)]
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Collection

# ─────────────────────────────────────────────────────────────────────────────

class CollectionCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
@app_commands.command(name="collection", description="View your card collection")
@app_commands.describe(
    card="The card you want to see the collection of",
    season="The season to filter by, shows every season if none"
)
async def collection(self, i: discord.Interaction,
                     card: Optional[str] = None,
                     season: Optional[str] = None):
    db.ensure_user(str(i.user.id), i.user.display_name)
    inv = db.get_user_inventory(str(i.user.id))

    if card:
        c = cu.get_card_by_name(card)
        if not c:
            await i.response.send_message(embed=err(f"Card `{card}` not found."), ephemeral=True)
            return
        # Show single card detail
        color = cu.get_rarity_color(c["rarity"])
        val   = db.get_current_value(c["id"], "Standard", c["base_value"])
        embed = discord.Embed(title=f"{cu.get_rarity_emoji(c['rarity'])} {c['name']}", color=color)
        embed.set_image(url=c["image_url"])
        embed.add_field(name="Type",   value=c["type"].capitalize(), inline=True)
        embed.add_field(name="Rarity", value=c["rarity"].capitalize(), inline=True)
        embed.add_field(name="Value",  value=f":coin: {val:,}", inline=True)
        owned_count = sum(1 for it in inv if it["card_id"] == c["id"])
        embed.add_field(name="You own", value=str(owned_count), inline=True)
        await i.response.send_message(embed=embed)
        return

    pages = _collection_pages(i.user, inv, season=season)
    view  = Pages(pages, i.user.id)
    await i.response.send_message(embed=pages[0], view=view)

@app_commands.command(name="completion", description="View collection completion percentage")
@app_commands.describe(
    user="The user whose completion you want to view, if not yours",
    special="The special you want to see the completion of",
    season="The season to filter by, shows every season if none",
    all="Show all cards in the bot, ignored if none"
)
async def completion(self, i: discord.Interaction,
                     user: Optional[discord.Member] = None,
                     special: Optional[str] = None,
                     season: Optional[str] = None,
                     all: Optional[str] = None):
    target = user or i.user
    db.ensure_user(str(target.id), target.display_name)
    inv = db.get_user_inventory(str(target.id))

    all_cards = [c for c in cu.get_all_cards() if c.get("spawnable")]
    if season:
        all_cards = [c for c in all_cards if c.get("season", "").lower() == season.lower()]
    if special:
        all_cards = [c for c in all_cards if special.lower() in [s.lower() for s in c.get("special_variants", [])]]

    owned_ids = set(it["card_id"] for it in inv)
    owned_n   = sum(1 for c in all_cards if c["id"] in owned_ids)
    total     = len(all_cards)
    pct       = (owned_n / total * 100) if total else 0.0

    show_missing = all and all.lower() == "true"
    display_cards = all_cards if show_missing else [c for c in all_cards if c["id"] in owned_ids]

    PER_PAGE = 30
    pages    = []
    chunks   = [display_cards[j:j+PER_PAGE] for j in range(0, max(len(display_cards), 1), PER_PAGE)]

    for p_idx, chunk in enumerate(chunks):
        embed = discord.Embed(color=RFRX_COLOR)
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
        embed.description = f"**RFRXDex progression: {pct:.1f}%**"

        owned_ch   = [c for c in chunk if c["id"] in owned_ids]
        missing_ch = [c for c in chunk if c["id"] not in owned_ids]

        if owned_ch:
            embed.add_field(name="__Owned cards__",
                            value=" ".join(cu.get_rarity_emoji(c["rarity"]) for c in owned_ch), inline=False)
        if missing_ch:
            embed.add_field(name="__Missing cards__",
                            value=" ".join(":white_circle:" for _ in missing_ch), inline=False)
        if not missing_ch and not owned_ch:
            embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)
        elif not missing_ch and owned_ch:
            embed.add_field(name="", value=":tada: No missing cards, congratulations! :tada:", inline=False)

        embed.set_footer(text=f"Page {p_idx+1}/{len(chunks)} | {owned_n}/{total} owned | RFRXDex")
        pages.append(embed)

    view = Pages(pages, i.user.id)
    await i.response.send_message(embed=pages[0], view=view)

@completion.autocomplete("all")
async def completion_all_autocomplete(self, i: discord.Interaction, current: str):
    return [
        app_commands.Choice(name="True",  value="True"),
        app_commands.Choice(name="False", value="False"),
    ]

@completion.autocomplete("season")
async def completion_season_autocomplete(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SEASONS if current.lower() in s.lower()][:25]

@completion.autocomplete("special")
async def completion_special_autocomplete(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SPECIALS if current.lower() in s.lower()][:25]

@collection.autocomplete("season")
async def collection_season_autocomplete(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SEASONS if current.lower() in s.lower()][:25]

@app_commands.command(name="coins", description="Check your coin balance")
@app_commands.describe(user="Check another user's balance")
async def coins(self, i: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or i.user
    db.ensure_user(str(target.id), target.display_name)
    data  = db.get_user(str(target.id))
    embed = discord.Embed(title=f"{target.display_name}'s Balance",
                          description=f":coin: **{data['coins']:,}** coins", color=MARKET_COLOR)
    embed.set_thumbnail(url=target.display_avatar.url)
    await i.response.send_message(embed=embed)

@app_commands.command(name="card", description="View details of a specific card")
@app_commands.describe(name="Card name")
async def card_info(self, i: discord.Interaction, name: str):
    c = cu.get_card_by_name(name)
    if not c:
        await i.response.send_message(embed=err(f"Card `{name}` not found."), ephemeral=True)
        return
    color = cu.get_rarity_color(c["rarity"])
    val   = db.get_current_value(c["id"], "Standard", c["base_value"])
    embed = discord.Embed(title=f"{cu.get_rarity_emoji(c['rarity'])} {c['name']}", color=color)
    embed.set_image(url=c["image_url"])
    embed.add_field(name="Type",       value=c["type"].capitalize(), inline=True)
    embed.add_field(name="Rarity",     value=c["rarity"].capitalize(), inline=True)
    embed.add_field(name="Value",      value=f":coin: {val:,}", inline=True)
    embed.add_field(name="Marketable", value="Yes" if c.get("marketable") else "No", inline=True)
    embed.add_field(name="Giftable",   value="Yes" if c.get("giftable", True) else "No", inline=True)
    embed.set_footer(text="RFRXDex")
    await i.response.send_message(embed=embed)
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Give

# ─────────────────────────────────────────────────────────────────────────────

class GiveCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
@app_commands.command(name="give", description="Give a card to another user")
@app_commands.describe(
    user="The user you want to give a card to",
    card="The card you are giving away",
    special="Optional: variant/special of the card",
    season="Optional: season tag filter"
)
async def give(self, i: discord.Interaction,
               user: discord.Member,
               card: str,
               special: Optional[str] = None,
               season: Optional[str] = None):
    if user.id == i.user.id:
        await i.response.send_message(embed=err("You can't give cards to yourself!"), ephemeral=True)
        return
    if user.bot:
        await i.response.send_message(embed=err("You cannot give cards to bots."), ephemeral=True)
        return

    db.ensure_user(str(i.user.id), i.user.display_name)
    db.ensure_user(str(user.id), user.display_name)

    c = cu.get_card_by_name(card)
    if not c:
        await i.response.send_message(embed=err(f"Card `{card}` not found."), ephemeral=True)
        return
    if not c.get("giftable", True):
        await i.response.send_message(embed=err(f"**{c['name']}** cannot be gifted."), ephemeral=True)
        return

    inv = db.get_user_inventory(str(i.user.id))
    matches = [it for it in inv if it["card_id"] == c["id"]]
    if special:
        matches = [it for it in matches if it["variant"].lower() == special.lower()]
    if season:
        matches = [it for it in matches if c.get("season", "").lower() == season.lower()]

    if not matches:
        desc = f"**{c['name']}**"
        if special: desc += f" [{special}]"
        await i.response.send_message(embed=err(f"You don't have {desc} in your inventory."), ephemeral=True)
        return

    item = matches[0]
    db.transfer_card(item["instance_id"], str(user.id))

    v_emoji = cu.get_variant_emoji(item["variant"])
    embed   = discord.Embed(description=f"{v_emoji} **{cu.get_card_display_name(c, item['variant'])}** given to **{user.display_name}**!", color=SUCCESS_COLOR)
    embed.set_author(name="Card Given!", icon_url=i.user.display_avatar.url)
    await i.response.send_message(embed=embed)

@give.autocomplete("special")
async def give_special_autocomplete(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SPECIALS if current.lower() in s.lower()][:25]

@give.autocomplete("season")
async def give_season_autocomplete(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SEASONS if current.lower() in s.lower()][:25]
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Market

# ─────────────────────────────────────────────────────────────────────────────

class MarketCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
def _market_pages(self, listings: list, guild: discord.Guild) -> list[discord.Embed]:
    PER_PAGE = 10
    pages    = []
    chunks   = [listings[i:i+PER_PAGE] for i in range(0, max(len(listings), 1), PER_PAGE)]
    for p_idx, chunk in enumerate(chunks):
        embed = discord.Embed(title=":shopping_cart: RFRXDex Global Market", color=MARKET_COLOR)
        if not chunk:
            embed.description = "No cards listed for sale right now."
        else:
            for lst in chunk:
                c = cu.get_card_by_id(lst["card_id"])
                if not c: continue
                seller = guild.get_member(int(lst["seller_id"])) if guild else None
                sname  = seller.display_name if seller else f"User#{lst['seller_id'][-4:]}"
                embed.add_field(
                    name=f"{cu.get_variant_emoji(lst['variant'])} {c['name']} [{lst['variant']}]",
                    value=f"{cu.get_rarity_emoji(c['rarity'])} {c['rarity'].capitalize()} | :coin: **{lst['price']:,}** | {sname} | ID: `{lst['listing_id']}`",
                    inline=False
                )
        embed.set_footer(text=f"Page {p_idx+1}/{len(chunks)} | /buy <id> to purchase | RFRXDex")
        pages.append(embed)
    return pages

@app_commands.command(name="market", description="Browse the global card market")
@app_commands.describe(card="Filter by card name")
async def market(self, i: discord.Interaction, card: Optional[str] = None):
    cfilter = None
    if card:
        cfilter = cu.get_card_by_name(card)
        if not cfilter:
            await i.response.send_message(embed=err(f"Card `{card}` not found."), ephemeral=True)
            return
    listings = db.get_active_listings(cfilter["id"] if cfilter else None)
    pages    = self._market_pages(listings, i.guild)
    view     = Pages(pages, i.user.id)
    await i.response.send_message(embed=pages[0], view=view)

@app_commands.command(name="sell", description="List a card for sale on the market")
@app_commands.describe(instance_id="Card instance ID (from /collection)", price="Asking price in coins")
async def sell(self, i: discord.Interaction, instance_id: str, price: int):
    db.ensure_user(str(i.user.id), i.user.display_name)
    inv  = db.get_user_inventory(str(i.user.id))
    item = next((x for x in inv if x["instance_id"].startswith(instance_id)), None)
    if not item:
        await i.response.send_message(embed=err("Card not found in your inventory."), ephemeral=True)
        return
    c = cu.get_card_by_id(item["card_id"])
    if not c or not c.get("marketable", True):
        await i.response.send_message(embed=err(f"**{c['name'] if c else instance_id}** cannot be sold."), ephemeral=True)
        return
    if price < 1:
        await i.response.send_message(embed=err("Price must be at least 1 coin."), ephemeral=True)
        return
    db.remove_card_from_inventory(item["instance_id"])
    lid = db.create_listing(str(i.user.id), c["id"], item["variant"], item["instance_id"], price)
    embed = discord.Embed(description=f"{cu.get_variant_emoji(item['variant'])} **{cu.get_card_display_name(c, item['variant'])}** listed for :coin: **{price:,}**\nListing ID: `{lid}`", color=SUCCESS_COLOR)
    embed.set_author(name="Card Listed!", icon_url=i.user.display_avatar.url)
    await i.response.send_message(embed=embed)

@app_commands.command(name="buy", description="Buy a card from the market")
@app_commands.describe(listing_id="Listing ID from /market")
async def buy(self, i: discord.Interaction, listing_id: int):
    db.ensure_user(str(i.user.id), i.user.display_name)
    listings = db.get_active_listings()
    listing  = next((l for l in listings if l["listing_id"] == listing_id), None)
    if not listing:
        await i.response.send_message(embed=err("Listing not found or already sold."), ephemeral=True)
        return
    if listing["seller_id"] == str(i.user.id):
        await i.response.send_message(embed=err("You can't buy your own listing!"), ephemeral=True)
        return
    buyer_data = db.get_user(str(i.user.id))
    if buyer_data["coins"] < listing["price"]:
        await i.response.send_message(embed=err(f"Not enough coins. Need :coin: {listing['price']:,}, have :coin: {buyer_data['coins']:,}."), ephemeral=True)
        return
    done = db.complete_listing(listing_id, str(i.user.id))
    if not done:
        await i.response.send_message(embed=err("Listing no longer available."), ephemeral=True)
        return
    db.deduct_coins(str(i.user.id), listing["price"])
    db.add_coins(listing["seller_id"], listing["price"])
    new_iid = cu.generate_instance_id()
    db.add_card_to_inventory(str(i.user.id), listing["card_id"], listing["variant"], listing["price"], new_iid)
    c = cu.get_card_by_id(listing["card_id"])
    if c:
        db.update_dynamic_price(c["id"], listing["variant"], c["base_value"], listing["price"])
        db.record_sale(c["id"], listing["variant"], listing["price"], listing["seller_id"], str(i.user.id))
    embed = discord.Embed(description=f"{cu.get_variant_emoji(listing['variant'])} **{cu.get_card_display_name(c, listing['variant'])}** purchased for :coin: **{listing['price']:,}**!", color=SUCCESS_COLOR)
    embed.set_author(name="Purchase Complete!", icon_url=i.user.display_avatar.url)
    await i.response.send_message(embed=embed)

@app_commands.command(name="delist", description="Remove your listing from the market")
@app_commands.describe(listing_id="Listing ID to cancel")
async def delist(self, i: discord.Interaction, listing_id: int):
    db.ensure_user(str(i.user.id), i.user.display_name)
    listing = next((l for l in db.get_active_listings() if l["listing_id"] == listing_id), None)
    if not listing:
        await i.response.send_message(embed=err("Listing not found."), ephemeral=True)
        return
    if listing["seller_id"] != str(i.user.id):
        await i.response.send_message(embed=err("That is not your listing."), ephemeral=True)
        return
    db.cancel_listing(listing_id, str(i.user.id))
    new_iid = cu.generate_instance_id()
    db.add_card_to_inventory(str(i.user.id), listing["card_id"], listing["variant"], listing["price"], new_iid)
    await i.response.send_message(embed=ok("Listing cancelled. Card returned to your inventory."))
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Auction

# ─────────────────────────────────────────────────────────────────────────────

class AuctionCheckView(discord.ui.View):
def **init**(self, user_id: int):
super().**init**(timeout=120)
self.user_id  = user_id
self.showing  = “bids”  # or “listings”

```
def _build_embed(self, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title="My auction bids", color=RFRX_COLOR)
    if self.showing == "bids":
        self.btn_mybids.style    = discord.ButtonStyle.primary
        self.btn_listings.style  = discord.ButtonStyle.secondary
        bids = db.get_user_bids(str(self.user_id))
        if not bids:
            embed.description = "You have no active bids."
        else:
            for a in bids[:10]:
                c = cu.get_card_by_id(a["card_id"])
                name = c["name"] if c else a["card_id"]
                embed.add_field(
                    name=f"#{a['auction_id']} - {name} [{a['variant']}]",
                    value=f":coin: Current bid: **{a['current_bid']:,}** | Ends: {a['ends_at'][:16]}",
                    inline=False
                )
    else:
        self.btn_mybids.style    = discord.ButtonStyle.secondary
        self.btn_listings.style  = discord.ButtonStyle.primary
        embed.title = "Bids on my auctions"
        listings = db.get_user_auction_listings(str(self.user_id))
        if not listings:
            embed.description = "You have no active auctions."
        else:
            for a in listings[:10]:
                c = cu.get_card_by_id(a["card_id"])
                name = c["name"] if c else a["card_id"]
                bidder = f"<@{a['top_bidder']}>" if a["top_bidder"] else "No bids yet"
                embed.add_field(
                    name=f"#{a['auction_id']} - {name} [{a['variant']}]",
                    value=f":coin: **{a['current_bid']:,}** | Top: {bidder} | Ends: {a['ends_at'][:16]}",
                    inline=False
                )
    return embed

@discord.ui.button(label="My bids", style=discord.ButtonStyle.primary)
async def btn_mybids(self, i: discord.Interaction, b: discord.ui.Button):
    if i.user.id != self.user_id:
        await i.response.send_message("This menu isn't yours.", ephemeral=True)
        return
    self.showing = "bids"
    await i.response.edit_message(embed=self._build_embed(i.guild), view=self)

@discord.ui.button(label="Bids on my auctions", style=discord.ButtonStyle.secondary)
async def btn_listings(self, i: discord.Interaction, b: discord.ui.Button):
    if i.user.id != self.user_id:
        await i.response.send_message("This menu isn't yours.", ephemeral=True)
        return
    self.showing = "listings"
    await i.response.edit_message(embed=self._build_embed(i.guild), view=self)
```

class AuctionCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
auction = app_commands.Group(name="auction", description="Auction house commands")

@auction.command(name="create", description="Create an auction for a card")
@app_commands.describe(
    card="The card you want to auction",
    duration="Duration in hours",
    special="Optional: variant/special of the card",
    season="Optional: season filter",
    starting_bid="Starting bid amount",
    buyout="Optional: buyout price"
)
async def auction_create(self, i: discord.Interaction,
                          card: str,
                          duration: int,
                          special: Optional[str] = None,
                          season: Optional[str] = None,
                          starting_bid: int = 1,
                          buyout: Optional[int] = None):
    db.ensure_user(str(i.user.id), i.user.display_name)
    c = cu.get_card_by_name(card)
    if not c:
        await i.response.send_message(embed=err(f"Card `{card}` not found."), ephemeral=True)
        return
    if not c.get("marketable", True):
        await i.response.send_message(embed=err(f"**{c['name']}** cannot be auctioned."), ephemeral=True)
        return
    if duration < 1 or duration > 168:
        await i.response.send_message(embed=err("Duration must be between 1 and 168 hours."), ephemeral=True)
        return

    inv     = db.get_user_inventory(str(i.user.id))
    matches = [it for it in inv if it["card_id"] == c["id"]]
    if special:
        matches = [it for it in matches if it["variant"].lower() == special.lower()]
    if not matches:
        desc = f"**{c['name']}**" + (f" [{special}]" if special else "")
        await i.response.send_message(embed=err(f"You don't have {desc} in your inventory."), ephemeral=True)
        return

    item = matches[0]
    db.remove_card_from_inventory(item["instance_id"])
    aid  = db.create_auction(str(i.user.id), c["id"], item["variant"], item["instance_id"],
                              starting_bid, duration, buyout)

    v_emoji = cu.get_variant_emoji(item["variant"])
    embed   = discord.Embed(color=SUCCESS_COLOR)
    embed.set_author(name="Auction Created!", icon_url=i.user.display_avatar.url)
    embed.add_field(name="Card",         value=f"{v_emoji} {cu.get_card_display_name(c, item['variant'])}", inline=True)
    embed.add_field(name="Starting Bid", value=f":coin: {starting_bid:,}", inline=True)
    embed.add_field(name="Duration",     value=f"{duration}h", inline=True)
    if buyout:
        embed.add_field(name="Buyout", value=f":coin: {buyout:,}", inline=True)
    embed.set_footer(text=f"Auction ID: #{aid} | RFRXDex")
    await i.response.send_message(embed=embed)

@auction_create.autocomplete("special")
async def ac_special(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SPECIALS if current.lower() in s.lower()][:25]

@auction_create.autocomplete("season")
async def ac_season(self, i: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in SEASONS if current.lower() in s.lower()][:25]

@auction.command(name="bid", description="Place a bid on an auction")
@app_commands.describe(auction_id="The auction ID to bid on", amount="Your bid amount in coins")
async def auction_bid(self, i: discord.Interaction, auction_id: int, amount: int):
    db.ensure_user(str(i.user.id), i.user.display_name)
    a = db.get_auction(auction_id)
    if not a or a["status"] != "active":
        await i.response.send_message(embed=err("Auction not found or no longer active."), ephemeral=True)
        return
    if a["seller_id"] == str(i.user.id):
        await i.response.send_message(embed=err("You can't bid on your own auction."), ephemeral=True)
        return
    if amount <= a["current_bid"]:
        await i.response.send_message(embed=err(f"Bid must be higher than current bid of :coin: **{a['current_bid']:,}**."), ephemeral=True)
        return
    user_data = db.get_user(str(i.user.id))
    if user_data["coins"] < amount:
        await i.response.send_message(embed=err(f"Not enough coins. You have :coin: {user_data['coins']:,}."), ephemeral=True)
        return

    # Check buyout
    c = cu.get_card_by_id(a["card_id"])
    if a["buyout_price"] and amount >= a["buyout_price"]:
        # Instant win
        db.place_bid(auction_id, str(i.user.id), a["buyout_price"])
        db.deduct_coins(str(i.user.id), a["buyout_price"])
        db.add_coins(a["seller_id"], a["buyout_price"])
        new_iid = cu.generate_instance_id()
        db.add_card_to_inventory(str(i.user.id), a["card_id"], a["variant"], a["buyout_price"], new_iid)
        conn = __import__("database").get_conn()
        conn.execute("UPDATE auctions SET status = 'completed', top_bidder = ? WHERE auction_id = ?", (str(i.user.id), auction_id))
        conn.commit(); conn.close()
        embed = discord.Embed(description=f":trophy: Buyout! **{cu.get_card_display_name(c, a['variant'])}** is yours for :coin: **{a['buyout_price']:,}**!", color=SUCCESS_COLOR)
        await i.response.send_message(embed=embed)
        return

    db.place_bid(auction_id, str(i.user.id), amount)
    embed = discord.Embed(description=f":raising_hand: Bid of :coin: **{amount:,}** placed on **{cu.get_card_display_name(c, a['variant'])}** (Auction #{auction_id}).", color=SUCCESS_COLOR)
    embed.set_footer(text="You'll be notified if you win! | RFRXDex")
    await i.response.send_message(embed=embed)

@auction.command(name="cancel", description="Cancel your active auction")
@app_commands.describe(auction_id="The auction ID to cancel")
async def auction_cancel(self, i: discord.Interaction, auction_id: int):
    db.ensure_user(str(i.user.id), i.user.display_name)
    a = db.get_auction(auction_id)
    if not a:
        await i.response.send_message(embed=err("Auction not found."), ephemeral=True)
        return
    if a["seller_id"] != str(i.user.id):
        await i.response.send_message(embed=err("That is not your auction."), ephemeral=True)
        return
    if a["status"] != "active":
        await i.response.send_message(embed=err("This auction is no longer active."), ephemeral=True)
        return
    db.cancel_auction(auction_id, str(i.user.id))
    # Return card
    new_iid = cu.generate_instance_id()
    db.add_card_to_inventory(str(i.user.id), a["card_id"], a["variant"], a["starting_bid"], new_iid)
    await i.response.send_message(embed=ok(f"Auction #{auction_id} cancelled. Card returned to your inventory."), ephemeral=True)

@auction.command(name="check", description="View your auction bids and listings")
async def auction_check(self, i: discord.Interaction):
    db.ensure_user(str(i.user.id), i.user.display_name)
    view  = AuctionCheckView(i.user.id)
    embed = view._build_embed(i.guild)
    await i.response.send_message(embed=embed, view=view, ephemeral=True)

@auction.command(name="history", description="View your auction history")
async def auction_history(self, i: discord.Interaction):
    db.ensure_user(str(i.user.id), i.user.display_name)
    history = db.get_auction_history(str(i.user.id))
    if not history:
        await i.response.send_message(embed=discord.Embed(description="No auction history found.", color=RFRX_COLOR), ephemeral=True)
        return
    embed = discord.Embed(title="Your Auction History", color=RFRX_COLOR)
    embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
    for a in history[:10]:
        c     = cu.get_card_by_id(a["card_id"])
        name  = c["name"] if c else a["card_id"]
        role  = "Seller" if a["seller_id"] == str(i.user.id) else "Buyer"
        stat  = {"completed": ":white_check_mark:", "cancelled": ":x:", "active": ":hourglass:"}.get(a["status"], "?")
        embed.add_field(name=f"{stat} #{a['auction_id']} - {name}",
                        value=f"{role} | Final: :coin: {a['current_bid']:,} | {a['created_at'][:10]}",
                        inline=False)
    await i.response.send_message(embed=embed, ephemeral=True)

@auction.command(name="list", description="Browse active auctions")
async def auction_list(self, i: discord.Interaction):
    auctions = db.get_active_auctions()
    if not auctions:
        await i.response.send_message(embed=discord.Embed(description="No active auctions right now.", color=RFRX_COLOR))
        return
    PER_PAGE = 8
    pages    = []
    chunks   = [auctions[j:j+PER_PAGE] for j in range(0, len(auctions), PER_PAGE)]
    for p_idx, chunk in enumerate(chunks):
        embed = discord.Embed(title=":hammer: Active Auctions", color=MARKET_COLOR)
        for a in chunk:
            c    = cu.get_card_by_id(a["card_id"])
            name = c["name"] if c else a["card_id"]
            embed.add_field(
                name=f"#{a['auction_id']} {cu.get_variant_emoji(a['variant'])} {name} [{a['variant']}]",
                value=f":coin: Current: **{a['current_bid']:,}** | Buyout: {(':coin: ' + str(a['buyout_price'])) if a['buyout_price'] else 'None'} | Ends: {a['ends_at'][:16]}",
                inline=False
            )
        embed.set_footer(text=f"Page {p_idx+1}/{len(chunks)} | /auction bid <id> <amount> | RFRXDex")
        pages.append(embed)
    view = Pages(pages, i.user.id)
    await i.response.send_message(embed=pages[0], view=view)
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Battle

# ─────────────────────────────────────────────────────────────────────────────

class BattleAcceptView(discord.ui.View):
def **init**(self, battle_id: int, challenger_id: int, opponent_id: int, wage: int):
super().**init**(timeout=120)
self.battle_id     = battle_id
self.challenger_id = challenger_id
self.opponent_id   = opponent_id
self.wage          = wage

```
@discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
async def accept(self, i: discord.Interaction, b: discord.ui.Button):
    if i.user.id != self.opponent_id:
        await i.response.send_message("This battle challenge isn't for you.", ephemeral=True)
        return
    self.stop()
    for c in self.children: c.disabled = True
    await i.message.edit(view=self)
    # Run battle
    import random
    log = []
    c_roster = db.get_roster(str(self.challenger_id))
    o_roster = db.get_roster(str(self.opponent_id))
    c_power  = sum(10 for s in c_roster if s["instance_id"]) or 10
    o_power  = sum(10 for s in o_roster if s["instance_id"]) or 10
    c_power  += random.randint(0, 20)
    o_power  += random.randint(0, 20)
    winner_id = self.challenger_id if c_power >= o_power else self.opponent_id
    loser_id  = self.opponent_id if winner_id == self.challenger_id else self.challenger_id
    log.append(f"<@{self.challenger_id}> power: {c_power}")
    log.append(f"<@{self.opponent_id}> power: {o_power}")
    db.resolve_battle(self.battle_id, str(winner_id), log)
    if self.wage > 0:
        db.deduct_coins(str(loser_id), self.wage)
        db.add_coins(str(winner_id), self.wage)
    embed = discord.Embed(title=":crossed_swords: Battle Result!", color=SUCCESS_COLOR)
    embed.add_field(name="Winner", value=f"<@{winner_id}>", inline=True)
    embed.add_field(name="Power", value=f"{max(c_power, o_power)}", inline=True)
    if self.wage > 0:
        embed.add_field(name="Winnings", value=f":coin: {self.wage:,}", inline=True)
    embed.description = "\n".join(log)
    await i.response.send_message(embed=embed)

@discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
async def decline(self, i: discord.Interaction, b: discord.ui.Button):
    if i.user.id not in (self.opponent_id, self.challenger_id):
        await i.response.send_message("You can't decline this.", ephemeral=True)
        return
    db.decline_battle(self.battle_id)
    self.stop()
    for c in self.children: c.disabled = True
    await i.message.edit(view=self)
    await i.response.send_message(":x: Battle declined.")
```

class BattleCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
battle = app_commands.Group(name="battle", description="Battle commands")
roster = app_commands.Group(name="roster", description="Battle roster commands", parent=battle)

@battle.command(name="begin", description="Challenge a user to a card battle")
@app_commands.describe(
    user="The user you want to battle with",
    wage="The amount of coins that both users will give for the battle, winner gets all"
)
async def battle_begin(self, i: discord.Interaction,
                        user: discord.Member,
                        wage: Optional[int] = 0):
    if user.id == i.user.id:
        await i.response.send_message(embed=err("You can't battle yourself."), ephemeral=True)
        return
    if user.bot:
        await i.response.send_message(embed=err("You cannot battle with bots."), ephemeral=True)
        return

    db.ensure_user(str(i.user.id), i.user.display_name)
    db.ensure_user(str(user.id), user.display_name)
    db.init_roster(str(i.user.id))
    db.init_roster(str(user.id))

    if wage and wage > 0:
        for uid in (str(i.user.id), str(user.id)):
            udata = db.get_user(uid)
            if not udata or udata["coins"] < wage:
                await i.response.send_message(embed=err(f"Both users need at least :coin: {wage:,} to battle at this wage."), ephemeral=True)
                return

    bid   = db.create_battle(str(i.user.id), str(user.id), wage or 0)
    embed = discord.Embed(title=":crossed_swords: Battle Challenge!", color=RFRX_COLOR)
    embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
    embed.description = f"{user.mention}, you have been challenged to a battle by **{i.user.display_name}**!"
    if wage and wage > 0:
        embed.add_field(name="Wage", value=f":coin: {wage:,} (winner takes all)", inline=False)
    embed.set_footer(text=f"Battle #{bid} | Expires in 2 minutes | RFRXDex")
    view = BattleAcceptView(bid, i.user.id, user.id, wage or 0)
    await i.response.send_message(content=user.mention, embed=embed, view=view)

@roster.command(name="fill", description="Fill a roster slot with cards from your inventory")
@app_commands.describe(slot="Which roster slot to fill (Roster 1, 2, or 3)")
async def roster_fill(self, i: discord.Interaction, slot: str):
    db.ensure_user(str(i.user.id), i.user.display_name)
    db.init_roster(str(i.user.id))

    # Parse slot number
    slot_num = None
    for n in ["1", "2", "3"]:
        if n in slot:
            slot_num = int(n)
            break
    if not slot_num:
        await i.response.send_message(embed=err("Invalid slot. Choose Roster 1, 2, or 3."), ephemeral=True)
        return

    inv = db.get_user_inventory(str(i.user.id))
    if not inv:
        await i.response.send_message(embed=err("You have no cards in your inventory."), ephemeral=True)
        return

    # Build pages of cards to pick
    PER_PAGE = 10
    pages    = []
    chunks   = [inv[j:j+PER_PAGE] for j in range(0, len(inv), PER_PAGE)]
    slot_row = db.get_roster_slot(str(i.user.id), slot_num)
    stype    = slot_row["roster_type"] if slot_row else ROSTER_TYPES[slot_num - 1]

    for p_idx, chunk in enumerate(chunks):
        embed = discord.Embed(title=f"Select a card for Roster {slot_num} ({stype})", color=RFRX_COLOR)
        embed.description = "Use instance IDs from your collection below.\nRun `/battle roster config` to set a card."
        for item in chunk:
            c = cu.get_card_by_id(item["card_id"])
            if not c: continue
            embed.add_field(
                name=f"`#{item['instance_id'][:8]}` {cu.get_rarity_emoji(c['rarity'])} {c['name']} [{item['variant']}]",
                value=f":coin: {item['catch_value']:,} | {item['caught_at'][:10]}",
                inline=False
            )
        embed.set_footer(text=f"Page {p_idx+1}/{len(chunks)} | RFRXDex")
        pages.append(embed)

    view = Pages(pages, i.user.id)
    await i.response.send_message(embed=pages[0], view=view, ephemeral=True)

@roster_fill.autocomplete("slot")
async def roster_fill_ac(self, i: discord.Interaction, current: str):
    return [
        app_commands.Choice(name="Roster 1 (Offense)", value="Roster 1 (Offense)"),
        app_commands.Choice(name="Roster 2 (Defense)", value="Roster 2 (Defense)"),
        app_commands.Choice(name="Roster 3 (Balance)", value="Roster 3 (Balance)"),
    ]

@roster.command(name="config", description="Configure a roster slot")
@app_commands.describe(
    slot="Which roster slot (1, 2, or 3)",
    action="What to do with the slot",
    card="Instance ID of the card (for Add action)"
)
async def roster_config(self, i: discord.Interaction,
                         slot: str,
                         action: str,
                         card: Optional[str] = None):
    db.ensure_user(str(i.user.id), i.user.display_name)
    db.init_roster(str(i.user.id))

    slot_num = None
    for n in ["1", "2", "3"]:
        if n in slot:
            slot_num = int(n)
            break
    if not slot_num:
        await i.response.send_message(embed=err("Invalid slot."), ephemeral=True)
        return

    slot_row = db.get_roster_slot(str(i.user.id), slot_num)
    stype    = slot_row["roster_type"] if slot_row else ROSTER_TYPES[slot_num - 1]

    if action.lower() == "show":
        embed = discord.Embed(title=f"Roster {slot_num} ({stype})", color=RFRX_COLOR)
        if slot_row and slot_row["instance_id"]:
            item = db.get_inventory_instance(slot_row["instance_id"])
            if item:
                c = cu.get_card_by_id(item["card_id"])
                embed.description = f"{cu.get_rarity_emoji(c['rarity'])} **{cu.get_card_display_name(c, item['variant'])}**\n:coin: {item['catch_value']:,}"
            else:
                embed.description = "Card no longer in inventory."
        else:
            embed.description = "This slot is empty."
        await i.response.send_message(embed=embed, ephemeral=True)

    elif action.lower() == "add":
        if not card:
            await i.response.send_message(embed=err("Provide a card instance ID with the `card` option."), ephemeral=True)
            return
        inv  = db.get_user_inventory(str(i.user.id))
        item = next((x for x in inv if x["instance_id"].startswith(card)), None)
        if not item:
            await i.response.send_message(embed=err("Card not found in your inventory."), ephemeral=True)
            return
        db.set_roster_slot(str(i.user.id), slot_num, stype, item["instance_id"])
        c = cu.get_card_by_id(item["card_id"])
        await i.response.send_message(embed=ok(f"Added **{cu.get_card_display_name(c, item['variant'])}** to Roster {slot_num} ({stype})."), ephemeral=True)

    elif action.lower() == "remove":
        db.set_roster_slot(str(i.user.id), slot_num, stype, None)
        await i.response.send_message(embed=ok(f"Removed card from Roster {slot_num}."), ephemeral=True)

    elif action.lower() == "clear":
        db.clear_roster_slot(str(i.user.id), slot_num)
        await i.response.send_message(embed=ok(f"Roster {slot_num} cleared."), ephemeral=True)
    else:
        await i.response.send_message(embed=err("Unknown action. Choose Show, Add, Remove, or Clear."), ephemeral=True)

@roster_config.autocomplete("slot")
async def rc_slot_ac(self, i: discord.Interaction, current: str):
    return [
        app_commands.Choice(name="Roster 1 (Offense)", value="Roster 1 (Offense)"),
        app_commands.Choice(name="Roster 2 (Defense)", value="Roster 2 (Defense)"),
        app_commands.Choice(name="Roster 3 (Balance)", value="Roster 3 (Balance)"),
    ]

@roster_config.autocomplete("action")
async def rc_action_ac(self, i: discord.Interaction, current: str):
    return [
        app_commands.Choice(name="Show",   value="Show"),
        app_commands.Choice(name="Add",    value="Add"),
        app_commands.Choice(name="Remove", value="Remove"),
        app_commands.Choice(name="Clear",  value="Clear"),
    ]

@roster_config.autocomplete("card")
async def rc_card_ac(self, i: discord.Interaction, current: str):
    inv     = db.get_user_inventory(str(i.user.id))
    choices = []
    for item in inv[:25]:
        c    = cu.get_card_by_id(item["card_id"])
        name = f"#{item['instance_id'][:8]} {c['name'] if c else item['card_id']} ATK:{item.get('atk_mod', 0):+d}% HP:{item.get('hp_mod', 0):+d}%" if c else item["instance_id"][:8]
        if current.lower() in name.lower():
            choices.append(app_commands.Choice(name=name[:100], value=item["instance_id"][:8]))
    return choices[:25]
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Trade

# ─────────────────────────────────────────────────────────────────────────────

class TradeConfirmView(discord.ui.View):
def **init**(self, trade_id: int, target_id: int):
super().**init**(timeout=120)
self.trade_id  = trade_id
self.target_id = target_id

```
@discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
async def accept(self, i: discord.Interaction, b: discord.ui.Button):
    if i.user.id != self.target_id:
        await i.response.send_message("This trade isn't for you.", ephemeral=True)
        return
    trade = db.get_trade(self.trade_id)
    if not trade or trade["status"] != "pending":
        await i.response.send_message("Trade is no longer active.", ephemeral=True)
        return
    for iid in trade["offer_cards"]:
        db.transfer_card(iid, str(self.target_id))
    for iid in trade["request_cards"]:
        db.transfer_card(iid, trade["initiator_id"])
    db.resolve_trade(self.trade_id, "completed")
    self.stop()
    for c in self.children: c.disabled = True
    await i.message.edit(view=self)
    await i.response.send_message(f":white_check_mark: Trade #{self.trade_id} completed!")

@discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
async def decline(self, i: discord.Interaction, b: discord.ui.Button):
    trade = db.get_trade(self.trade_id)
    if not trade:
        await i.response.send_message("Trade not found.", ephemeral=True)
        return
    if i.user.id != self.target_id and str(i.user.id) != trade["initiator_id"]:
        await i.response.send_message("You can't decline this.", ephemeral=True)
        return
    db.resolve_trade(self.trade_id, "declined")
    self.stop()
    for c in self.children: c.disabled = True
    await i.message.edit(view=self)
    await i.response.send_message(":x: Trade declined.")
```

class TradeCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
@app_commands.command(name="trade", description="Propose a card trade with another user")
@app_commands.describe(
    user="User to trade with",
    offer="Instance ID(s) you offer, comma-separated",
    request="Instance ID(s) you want, comma-separated"
)
async def trade(self, i: discord.Interaction,
                user: discord.Member,
                offer: str,
                request: str):
    if user.id == i.user.id:
        await i.response.send_message(embed=err("You can't trade with yourself."), ephemeral=True)
        return
    db.ensure_user(str(i.user.id), i.user.display_name)
    db.ensure_user(str(user.id), user.display_name)

    offer_ids   = [x.strip() for x in offer.split(",")]
    request_ids = [x.strip() for x in request.split(",")]
    my_inv      = db.get_user_inventory(str(i.user.id))
    their_inv   = db.get_user_inventory(str(user.id))

    def resolve(id_list, inv):
        result = []
        for short in id_list:
            match = next((x for x in inv if x["instance_id"].startswith(short)), None)
            if not match: return None, short
            result.append(match["instance_id"])
        return result, None

    full_offer, e = resolve(offer_ids, my_inv)
    if e:
        await i.response.send_message(embed=err(f"Card `{e}` not in your inventory."), ephemeral=True)
        return
    full_req, e = resolve(request_ids, their_inv)
    if e:
        await i.response.send_message(embed=err(f"{user.display_name} doesn't have card `{e}`."), ephemeral=True)
        return

    tid   = db.create_trade(str(i.user.id), str(user.id), full_offer, full_req)

    def card_str(ids, inv):
        parts = []
        for iid in ids:
            item = next((x for x in inv if x["instance_id"] == iid), None)
            if item:
                c = cu.get_card_by_id(item["card_id"])
                parts.append(f"{cu.get_variant_emoji(item['variant'])} {cu.get_card_display_name(c, item['variant'])} `#{iid[:8]}`")
        return "\n".join(parts) or "None"

    embed = discord.Embed(title=f":arrows_counterclockwise: Trade Proposal #{tid}", color=RFRX_COLOR)
    embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
    embed.add_field(name=f"{i.user.display_name} offers",    value=card_str(full_offer, my_inv),   inline=True)
    embed.add_field(name=f"{i.user.display_name} requests",  value=card_str(full_req, their_inv), inline=True)
    embed.set_footer(text="Expires in 2 minutes | RFRXDex")
    view = TradeConfirmView(tid, user.id)
    await i.response.send_message(content=user.mention, embed=embed, view=view)

@app_commands.command(name="trade_history", description="View your recent trade history")
async def trade_history(self, i: discord.Interaction):
    db.ensure_user(str(i.user.id), i.user.display_name)
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE initiator_id = ? OR target_id = ? ORDER BY created_at DESC LIMIT 10",
                        (str(i.user.id), str(i.user.id))).fetchall()
    conn.close()
    if not rows:
        await i.response.send_message(embed=discord.Embed(description="No trades yet.", color=RFRX_COLOR), ephemeral=True)
        return
    embed = discord.Embed(title="Your Trade History", color=RFRX_COLOR)
    embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
    for row in rows:
        t       = dict(row)
        s_emoji = {"completed": ":white_check_mark:", "declined": ":x:", "pending": ":hourglass:"}.get(t["status"], "?")
        other   = t["target_id"] if t["initiator_id"] == str(i.user.id) else t["initiator_id"]
        embed.add_field(name=f"{s_emoji} Trade #{t['trade_id']}",
                        value=f"With <@{other}> | {t['status'].capitalize()} | {t['created_at'][:10]}",
                        inline=False)
    await i.response.send_message(embed=embed, ephemeral=True)
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Stats / Leaderboard

# ─────────────────────────────────────────────────────────────────────────────

class StatsCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
@app_commands.command(name="card_history", description="View market history for a card")
@app_commands.describe(name="Card name", variant="Variant (default: Standard)")
async def card_history(self, i: discord.Interaction, name: str, variant: str = "Standard"):
    c = cu.get_card_by_name(name)
    if not c:
        await i.response.send_message(embed=err(f"Card `{name}` not found."), ephemeral=True)
        return
    stats   = db.get_card_history_stats(c["id"], variant)
    cur_val = db.get_current_value(c["id"], variant, c["base_value"])
    pct     = ((cur_val - c["base_value"]) / c["base_value"] * 100) if c["base_value"] else 0
    pct_str = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
    embed   = discord.Embed(title=f"{cu.get_variant_emoji(variant)} {c['name']} [{variant}]", color=cu.get_rarity_color(c["rarity"]))
    embed.set_thumbnail(url=c["image_url"])
    embed.add_field(name="Base Value",    value=f":coin: {c['base_value']:,}", inline=True)
    embed.add_field(name="Current Value", value=f":coin: {cur_val:,} ({pct_str})", inline=True)
    embed.add_field(name="Total Sales",   value=str(stats["total_sales"]), inline=True)
    if stats["total_sales"] > 0:
        embed.add_field(name="Lowest Sale",  value=f":coin: {stats['min']:,}", inline=True)
        embed.add_field(name="Highest Sale", value=f":coin: {stats['max']:,}", inline=True)
        embed.add_field(name="Average Sale", value=f":coin: {stats['avg']:,}", inline=True)
    embed.set_footer(text="RFRXDex Market History")
    await i.response.send_message(embed=embed)

@app_commands.command(name="leaderboard", description="View RFRXDex leaderboards")
@app_commands.describe(category="collectors | rare | wealth")
@app_commands.choices(category=[
    app_commands.Choice(name="Collectors - most cards owned", value="collectors"),
    app_commands.Choice(name="Rare - most special variant cards", value="rare"),
    app_commands.Choice(name="Wealth - highest total card value", value="wealth"),
])
async def leaderboard(self, i: discord.Interaction, category: str = "collectors"):
    if category == "collectors":
        rows, key, unit = db.leaderboard_collectors(), "card_count", "cards"
        title = ":trophy: Top Collectors"
    elif category == "rare":
        rows, key, unit = db.leaderboard_rare(), "rare_count", "special cards"
        title = ":gem: Rare Card Leaders"
    else:
        rows, key, unit = db.leaderboard_wealth(), "total_value", "coins value"
        title = ":moneybag: Wealthiest Collectors"
    medals = [":first_place:", ":second_place:", ":third_place:"]
    embed  = discord.Embed(title=title, color=MARKET_COLOR)
    lines  = []
    for idx, row in enumerate(rows):
        medal = medals[idx] if idx < 3 else f"**#{idx+1}**"
        val   = row.get(key) or 0
        name  = row.get("username") or f"User#{row['user_id'][-4:]}"
        lines.append(f"{medal} **{name}** — {val:,} {unit}")
    embed.description = "\n".join(lines) if lines else "No data yet."
    embed.set_footer(text="RFRXDex Leaderboard")
    await i.response.send_message(embed=embed)
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Admin

# ─────────────────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
def _is_admin(self, member: discord.Member) -> bool:
    if hasattr(member, "guild_permissions") and member.guild_permissions.administrator:
        return True
    return any(r.name in ["DEX Admin", "Staff", "Owner"] for r in getattr(member, "roles", []))

@app_commands.command(name="admin_give", description="[Admin] Give a card to a user")
@app_commands.describe(user="Target user", card_name="Card name", variant="Variant (default: Standard)")
async def admin_give(self, i: discord.Interaction, user: discord.Member, card_name: str, variant: str = "Standard"):
    if not self._is_admin(i.user):
        await i.response.send_message(embed=err("Admin only."), ephemeral=True)
        return
    c = cu.get_card_by_name(card_name)
    if not c:
        await i.response.send_message(embed=err(f"Card `{card_name}` not found."), ephemeral=True)
        return
    db.ensure_user(str(user.id), user.display_name)
    iid = cu.generate_instance_id()
    val = db.get_current_value(c["id"], variant, c["base_value"])
    db.add_card_to_inventory(str(user.id), c["id"], variant, val, iid)
    if c.get("info_card_id"):
        db.grant_info_card(str(user.id), c["info_card_id"])
    await i.response.send_message(embed=ok(f"Gave **{cu.get_card_display_name(c, variant)}** to **{user.display_name}**."))

@app_commands.command(name="admin_spawn", description="[Admin] Force a card spawn in this channel")
async def admin_spawn(self, i: discord.Interaction):
    if not self._is_admin(i.user):
        await i.response.send_message(embed=err("Admin only."), ephemeral=True)
        return
    await i.response.send_message("Forcing a spawn...", ephemeral=True)
    await i.client.spawn_system.do_spawn(channel_id=i.channel_id)

@app_commands.command(name="set_spawn_channel", description="[Admin] Add this channel to the spawn rotation")
async def set_spawn_channel(self, i: discord.Interaction):
    if not self._is_admin(i.user):
        await i.response.send_message(embed=err("Admin only."), ephemeral=True)
        return
    cid = i.channel_id
    if cid not in i.client.spawn_system.spawn_channel_ids:
        i.client.spawn_system.spawn_channel_ids.append(cid)
        await i.response.send_message(embed=ok(f"<#{cid}> added to spawn rotation."))
    else:
        await i.response.send_message(embed=ok(f"<#{cid}> is already in the spawn rotation."))

@app_commands.command(name="admin_coins", description="[Admin] Add or remove coins from a user")
@app_commands.describe(user="Target user", amount="Amount to add (negative to remove)")
async def admin_coins(self, i: discord.Interaction, user: discord.Member, amount: int):
    if not self._is_admin(i.user):
        await i.response.send_message(embed=err("Admin only."), ephemeral=True)
        return
    db.ensure_user(str(user.id), user.display_name)
    db.add_coins(str(user.id), amount)
    data = db.get_user(str(user.id))
    await i.response.send_message(embed=ok(f"**{user.display_name}** now has :coin: **{data['coins']:,}**."))
```

# ─────────────────────────────────────────────────────────────────────────────

# COG: Help

# ─────────────────────────────────────────────────────────────────────────────

class HelpCog(commands.Cog):
def **init**(self, bot): self.bot = bot

```
@app_commands.command(name="help", description="View all RFRXDex commands")
async def help_cmd(self, i: discord.Interaction):
    embed = discord.Embed(title="RFRXDex — Command Reference", color=RFRX_COLOR,
                          description="The RFRX League collectible card bot. Spawn, catch, trade and collect!")
    embed.add_field(name="Collection",  value="`/collection` `/completion` `/card` `/coins`", inline=False)
    embed.add_field(name="Trading",     value="`/give` `/trade` `/trade_history`", inline=False)
    embed.add_field(name="Market",      value="`/market` `/sell` `/buy` `/delist`", inline=False)
    embed.add_field(name="Auction",     value="`/auction create` `/auction bid` `/auction cancel` `/auction check` `/auction history` `/auction list`", inline=False)
    embed.add_field(name="Battle",      value="`/battle begin` `/battle roster fill` `/battle roster config`", inline=False)
    embed.add_field(name="Stats",       value="`/card_history` `/leaderboard`", inline=False)
    embed.add_field(name="Admin",       value="`/admin_give` `/admin_spawn` `/set_spawn_channel` `/admin_coins`", inline=False)
    embed.set_footer(text="RFRXDex | Use /guide for full details")
    await i.response.send_message(embed=embed, ephemeral=True)

@app_commands.command(name="guide", description="Full interactive RFRXDex guide")
@app_commands.describe(page="Start on a specific page (1-5)")
async def guide(self, i: discord.Interaction, page: int = 1):
    guide_pages = [
        discord.Embed(title="RFRXDex Guide — Getting Started", color=RFRX_COLOR,
                      description="Welcome to **RFRXDex**!\n\nCards spawn in designated channels every 5–15 minutes.\nHit **Sign**, type the card name, and it's yours!\n\nInfo cards are granted automatically when you catch their parent card."),
        discord.Embed(title="RFRXDex Guide — Rarities & Variants", color=MARKET_COLOR,
                      description=":white_circle: Common | :blue_circle: Rare | :purple_circle: Epic | :orange_circle: Mythic | :star: Champion | :red_circle: Limited\n\n**Variants:** :race_car: GP Specs (20%) | :trophy: DOTD (15%) | :sparkles: Shiny (10%) | :crystal_ball: Secret Rare (3%) | :gem: Ultra Rare (1%)"),
        discord.Embed(title="RFRXDex Guide — Auctions", color=RFRX_COLOR,
                      description="Create auctions with `/auction create card: duration:`\nBid with `/auction bid auction_id: amount:`\nCheck your bids with `/auction check`\nCancel your auction with `/auction cancel auction_id:`"),
        discord.Embed(title="RFRXDex Guide — Battles", color=RFRX_COLOR,
                      description="Challenge users with `/battle begin user: [wage:]`\nSet up your 3 roster slots with `/battle roster config`\nSlot 1 = Offense, Slot 2 = Defense, Slot 3 = Balance"),
        discord.Embed(title="RFRXDex Guide — Admin", color=0xFF6B35,
                      description="**Admin commands** (requires Administrator, DEX Admin, Staff, or Owner role):\n`/set_spawn_channel` → add channel to spawn rotation\n`/admin_spawn` → force a spawn\n`/admin_give` → give any card to a user\n`/admin_coins` → adjust user balance"),
    ]
    for idx, p in enumerate(guide_pages):
        p.set_footer(text=f"Page {idx+1}/{len(guide_pages)} | RFRXDex Guide")

    page_idx = max(0, min(page - 1, len(guide_pages) - 1))
    pages    = guide_pages
    view     = Pages(pages, i.user.id)
    view.idx = page_idx
    view._sync()
    await i.response.send_message(embed=pages[page_idx], view=view, ephemeral=True)
```

# ─────────────────────────────────────────────────────────────────────────────

# Setup

# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot):
await bot.add_cog(CollectionCog(bot))
await bot.add_cog(GiveCog(bot))
await bot.add_cog(MarketCog(bot))
await bot.add_cog(AuctionCog(bot))
await bot.add_cog(BattleCog(bot))
await bot.add_cog(TradeCog(bot))
await bot.add_cog(StatsCog(bot))
await bot.add_cog(AdminCog(bot))
await bot.add_cog(HelpCog(bot))
