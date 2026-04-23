import discord
import yt_dlp
import asyncio

def parse_duration(duration):
    """Formats a duration from seconds into a string (e.g. 125 -> 02:05)."""
    if duration is None:
        return "00:00"
    
    try:
        duration = int(float(duration))
    except (TypeError, ValueError):
        return "00:00"

    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False, # Allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = parse_duration(data.get('duration', 0))

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first entry for non-playlist calls
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @classmethod
    async def extract_metadata(cls, url, *, loop=None):
        """Ultra-fast extraction of metadata (URLs/IDs) for playlists or single tracks."""
        loop = loop or asyncio.get_event_loop()
        
        is_url = url.startswith(('http://', 'https://'))
        
        # Always use extract_flat=True for initial enqueuing to prevent hanging
        ytdl_opts = {**ytdl_format_options, 'extract_flat': True if is_url else False}
        ytdl_instance = yt_dlp.YoutubeDL(ytdl_opts)
        
        data = await loop.run_in_executor(None, lambda: ytdl_instance.extract_info(url, download=False))
        
        if 'entries' in data:
            return [{
                'url': entry.get('webpage_url') or entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                'title': entry.get('title') or entry.get('id'), # Might be ID for SoundCloud flat
                'duration': parse_duration(entry.get('duration', 0)),
                'is_resolved': True if entry.get('title') else False
            } for entry in data['entries'] if entry]
        
        return [{
            'url': data.get('webpage_url') or data.get('url'),
            'title': data.get('title') or "Unknown Title",
            'duration': parse_duration(data.get('duration', 0)),
            'is_resolved': True
        }]

    @classmethod
    async def resolve_track_metadata(cls, track, *, loop=None):
        """Fetches full metadata for a single track if it only has an ID/URL."""
        if track.get('is_resolved'):
            return track
            
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(track['url'], download=False))
        
        track['title'] = data.get('title') or track['title']
        track['duration'] = parse_duration(data.get('duration', 0))
        track['is_resolved'] = True
        return track
