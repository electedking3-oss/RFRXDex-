“””
main.py — RFRXDex Bot Entry Point
Termux-friendly, reads token from .env
“””

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database as db
import commands as cmds
from spawn_system import SpawnSystem

# ─── Load environment ────────────────────────────────────────────────────────

load_dotenv()
TOKEN = os.getenv(“DISCORD_TOKEN”)
if not TOKEN:
raise RuntimeError(“DISCORD_TOKEN not set in .env!”)

# ─── Configure spawn channels ───────────────────────────────────────────────

# Add your channel IDs here (integers). You can also use /set_spawn_channel

# in Discord to add channels at runtime.

SPAWN_CHANNEL_IDS: list[int] = [
# 123456789012345678,   # #card-spawns
# 987654321098765432,   # #general
]

# ─── Bot class ───────────────────────────────────────────────────────────────

class RFRXDex(commands.Bot):
def **init**(self):
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
super().**init**(command_prefix=”!”, intents=intents)
self.spawn_system = SpawnSystem(self)

```
async def setup_hook(self):
    # Initialize DB
    db.init_db()

    # Load cogs
    await cmds.setup(self)
    print("[Bot] All cogs loaded.")

    # Sync slash commands globally
    synced = await self.tree.sync()
    print(f"[Bot] Synced {len(synced)} slash commands.")

    # Configure and start spawn system
    self.spawn_system.set_channels(SPAWN_CHANNEL_IDS)
    self.spawn_system.start()
    print(f"[Bot] Spawn system started. Channels: {SPAWN_CHANNEL_IDS or 'None (use /set_spawn_channel)'}")

async def on_ready(self):
    print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
    await self.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🏎️ RFRX League Cards | /help"
        )
    )

async def on_command_error(self, ctx, error):
    pass  # Suppress prefix command errors since we use slash commands
```

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
bot = RFRXDex()
try:
bot.run(DISCORD_TOKEN)
except KeyboardInterrupt:
print(”\n[Bot] Shutting down…”)

if **name** == “**main**”:
main()
