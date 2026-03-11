import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

import database as db
from spawn_system import SpawnSystem

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class RFRXDex(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.spawn_system = SpawnSystem(self)

    async def setup_hook(self):
        await self.load_extension("commands")
        await self.tree.sync()
        print("[BOT] Commands synced.")

    async def on_ready(self):
        print(f"[BOT] Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="cards spawn | /help"
            )
        )
        self.spawn_system.start()
        print("[BOT] Spawn system started.")

    async def on_command_error(self, ctx, error):
        pass


async def main():
    db.init_db()
    bot = RFRXDex()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
