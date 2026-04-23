import discord
from discord.ext import commands
from music_utils import YTDLSource
import asyncio
import random

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = [] # Using a list for easier shuffling and queue viewing
        self.current = None
        self.idle_timer = None

    async def idle_leave(self, ctx):
        """Task that waits 60 seconds and then leaves the voice channel if no music is playing."""
        await asyncio.sleep(60)
        if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.voice_client.disconnect()
            self.queue = []
            embed = discord.Embed(
                description="No tracks have been playing. Leaving the call 👋",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    def cancel_idle_timer(self):
        if self.idle_timer:
            self.idle_timer.cancel()
            self.idle_timer = None

    async def resolve_queue_metadata(self):
        """Background task to resolve metadata for the first 10 items in the queue."""
        for track in self.queue[:10]:
            if not track.get('is_resolved'):
                try:
                    await YTDLSource.resolve_track_metadata(track, loop=self.bot.loop)
                except Exception as e:
                    print(f"DEBUG: Failed to resolve metadata for {track['url']}: {e}")

    async def play_next(self, ctx):
        if len(self.queue) == 0:
            self.current = None
            embed = discord.Embed(
                description="The track list is empty.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            # Start idle timer
            self.cancel_idle_timer()
            self.idle_timer = self.bot.loop.create_task(self.idle_leave(ctx))
            return

        self.cancel_idle_timer()
        metadata = self.queue.pop(0)
        
        # Trigger resolution for the new top items in background
        self.bot.loop.create_task(self.resolve_queue_metadata())
        
        try:
            # Full extraction happens here automatically in YTDLSource.from_url
            player = await YTDLSource.from_url(metadata['url'], loop=self.bot.loop, stream=True)
            self.current = player
            
            ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))
            
            embed = discord.Embed(
                title="Started playing",
                description=f"[{player.title}]({metadata['url']})",
                color=discord.Color.green()
            )
            embed.add_field(name="Length", value=player.duration)
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"ERROR: Failed to play track: {e}")
            await ctx.send(embed=discord.Embed(description=f"Error playing track: {e}", color=discord.Color.red()))
            await self.play_next(ctx)

    @commands.command()
    async def play(self, ctx, *, query):
        async with ctx.typing():
            try:
                # 1. Connect to voice channel if not already connected
                if not ctx.voice_client:
                    if ctx.author.voice:
                        await ctx.author.voice.channel.connect()
                    else:
                        return await ctx.send(embed=discord.Embed(description="You are not connected to a voice channel.", color=discord.Color.red()))

                # 2. Fast Extract metadata (flat, supports playlists)
                tracks = await YTDLSource.extract_metadata(query, loop=self.bot.loop)
                
                # 3. Add tracks to queue
                for track in tracks:
                    track['requester'] = ctx.author
                    self.queue.append(track)

                # 4. Background resolve for the first 10
                self.bot.loop.create_task(self.resolve_queue_metadata())

                # 5. Handle messaging and playback start
                if len(tracks) > 1:
                    embed = discord.Embed(
                        description=f"Added **{len(tracks)}** songs to queue.",
                        color=discord.Color.blue()
                    )
                    await ctx.send(embed=embed)
                else:
                    embed = discord.Embed(
                        description=f"Added to queue: **{tracks[0]['title']}**",
                        color=discord.Color.blue()
                    )
                    await ctx.send(embed=embed)

                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await self.play_next(ctx)
                    
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"An error occurred: {e}", color=discord.Color.red()))

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(embed=discord.Embed(description="Paused.", color=discord.Color.blue()))

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            title = self.current.title if self.current else "Current song"
            ctx.voice_client.stop()
            embed = discord.Embed(
                description=f"**{title}** has been skipped by {ctx.author.mention}",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def queue(self, ctx):
        if not self.queue and not self.current:
            return await ctx.send(embed=discord.Embed(description="The track list is empty.", color=discord.Color.orange()))

        # Trigger resolution check for what we are about to show
        await self.resolve_queue_metadata()

        embed = discord.Embed(title="Current Queue", color=discord.Color.blue())
        
        queue_text = ""
        if self.current:
            queue_text += f"**Now Playing:** {self.current.title}\n\n"
        
        for i, track in enumerate(self.queue[:10], start=1):
            title = track['title'] if track.get('is_resolved') else f"*{track['title']} (Loading...)*"
            queue_text += f"{i}. {title} ({track['duration']})\n"
        
        if len(self.queue) > 10:
            queue_text += f"\n*...and {len(self.queue) - 10} more*"
            
        embed.description = queue_text
        await ctx.send(embed=embed)

    @commands.command()
    async def shuffle(self, ctx):
        if not self.queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.red()))
            
        random.shuffle(self.queue)
        embed = discord.Embed(
            description="[Shuffling the queue!] 🎲🎲",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def clear(self, ctx):
        """Clears all songs currently in the queue."""
        self.queue = []
        embed = discord.Embed(
            description="The queue has been cleared. 🧹",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue = []
            self.cancel_idle_timer()
            await ctx.send(embed=discord.Embed(description="Left voice channel.", color=discord.Color.blue()))

async def setup(bot):
    await bot.add_cog(Music(bot))
