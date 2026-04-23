import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.load_extension('cogs.music')

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

bot = MusicBot()

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))
