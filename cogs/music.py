import discord
from discord.ext import commands
from music_utils import YTDLSource
import asyncio

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue()
        self.current = None

    async def play_next(self, ctx):
        if self.queue.empty():
            self.current = None
            return

        self.current = await self.queue.get()
        ctx.voice_client.play(self.current, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))
        await ctx.send(f'Now playing: {self.current.title}')

    @commands.command()
    async def play(self, ctx, *, url):
        async with ctx.typing():
            print(f"DEBUG: Processing play command for: {url}")
            try:
                # 1. Connect to voice channel if not already connected
                if not ctx.voice_client:
                    if ctx.author.voice:
                        print(f"DEBUG: Connecting to {ctx.author.voice.channel.name}")
                        await ctx.author.voice.channel.connect()
                    else:
                        print("DEBUG: User not in voice channel")
                        return await ctx.send("You are not connected to a voice channel.")

                # 2. Extract audio data via yt-dlp
                print("DEBUG: Extracting audio stream via yt-dlp...")
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                print(f"DEBUG: Successfully extracted: {player.title}")

                # 3. Add to queue or play immediately
                if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                    await self.queue.put(player)
                    await ctx.send(f'Added to queue: {player.title}')
                    print(f"DEBUG: Added to queue: {player.title}")
                else:
                    self.current = player
                    ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))
                    await ctx.send(f'Now playing: {player.title}')
                    print(f"DEBUG: Started playback for: {player.title}")
            except Exception as e:
                print(f"ERROR: Exception in play command: {e}")
                await ctx.send(f"An error occurred: {e}")

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Paused.")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Skipped.")

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue = asyncio.Queue() # Clear queue
            await ctx.send("Left voice channel.")

async def setup(bot):
    await bot.add_cog(Music(bot))
