import logging
import collections
import discord
from discord.ext import commands

import config
import card_utils as cu

log = logging.getLogger("rfrxdex.core")


class DequeHandler(logging.Handler):
    """Keeps last N log records in memory — same pattern as Ballsdex."""
    def __init__(self, maxlen: int = 100):
        super().__init__()
        self.deque: collections.deque[logging.LogRecord] = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord):
        self.deque.append(record)


_log_handler = DequeHandler(maxlen=100)
logging.getLogger().addHandler(_log_handler)


class Core(commands.Cog):
    """Core prefix commands for RFRXDex."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Check if the bot is alive."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! `{latency}ms`")

    @commands.command()
    @commands.is_owner()
    async def reloadtree(self, ctx: commands.Context, guild_id: int | None = None):
        """Sync slash command tree. Optionally pass guild ID for guild-only sync."""
        if guild_id is None:
            await self.bot.tree.sync()
            await ctx.send("✅ Global slash command tree synced.")
        else:
            guild = discord.Object(id=guild_id)
            await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Slash command tree synced to guild `{guild_id}`.")

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, extension: str):
        """Reload a bot extension. Example: !reload commands"""
        try:
            try:
                await self.bot.reload_extension(extension)
            except commands.ExtensionNotLoaded:
                await self.bot.load_extension(extension)
            await ctx.send(f"✅ Extension `{extension}` reloaded.")
            log.info(f"Extension reloaded: {extension}")
        except commands.ExtensionNotFound:
            await ctx.send(f"❌ Extension `{extension}` not found.")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload `{extension}`: `{e}`")
            log.error(f"Failed to reload extension {extension}", exc_info=True)

    @commands.command()
    @commands.is_owner()
    async def reloadcache(self, ctx: commands.Context):
        """Reload cards.json without restarting the bot."""
        try:
            cu.reload_cache()
            cards = cu.get_all_cards()
            spawnable = [c for c in cards if c.get("spawnable")]
            await ctx.message.add_reaction("✅")
            await ctx.send(
                f"✅ Card cache reloaded. "
                f"`{len(cards)}` total cards, `{len(spawnable)}` spawnable."
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to reload cache: `{e}`")
            log.error("Failed to reload card cache", exc_info=True)

    @commands.command()
    @commands.is_owner()
    async def reloadconfig(self, ctx: commands.Context):
        """Reload config.json without restarting the bot."""
        try:
            config.reload()
            await ctx.message.add_reaction("✅")
            await ctx.send("✅ Config reloaded.")
            log.info("Config reloaded.")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload config: `{e}`")

    @commands.command()
    @commands.is_owner()
    async def forcespawn(self, ctx: commands.Context):
        """Force a card spawn in the current channel."""
        await ctx.send("*Forcing a spawn...*")
        await self.bot.spawn_system.do_spawn(channel_id=ctx.channel.id)

    @commands.command()
    @commands.is_owner()
    async def botstatus(self, ctx: commands.Context, *, status: str):
        """Change bot watching status. Example: !botstatus cards spawn | /help"""
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=status
            )
        )
        await ctx.send(f"✅ Status updated to: `{status}`")

    @commands.command()
    @commands.is_owner()
    async def logs(self, ctx: commands.Context, count: int = 20):
        """Show last N log entries (max 50). Example: !logs 30"""
        count = min(count, 50)
        records = list(_log_handler.deque)[-count:]

        if not records:
            await ctx.send("No log entries yet.")
            return

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        lines = [formatter.format(r) for r in records]

        chunks, chunk = [], ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1900:
                chunks.append(chunk)
                chunk = line
            else:
                chunk += ("\n" if chunk else "") + line
        if chunk:
            chunks.append(chunk)

        for c in chunks:
            await ctx.send(f"```\n{c}\n```")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context):
        """Gracefully shut down the bot."""
        await ctx.send("👋 Shutting down...")
        log.info("Shutdown triggered by owner.")
        self.bot.spawn_system.stop()
        await self.bot.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
