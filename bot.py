import discord
from discord.ext import commands, tasks
import googleapiclient.discovery
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))  # Default: check every hour
LAST_VIDEO_FILE = os.getenv('VIDEO_FILE_NAME')

# Set up the YouTube API client
youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Initialize the Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Start the YouTube check loop
    check_youtube_videos.start()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_youtube_videos():
    latest_video_id = load_last_video()
    
    print(f"Checking for new videos at {datetime.now()}")
    
    try:
        # Get the channel's uploads playlist ID
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=YOUTUBE_CHANNEL_ID
        ).execute()
        
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=1  # Only retrieve the latest video
        ).execute()
        
        video = playlist_response['items'][0]
        video_id = video['snippet']['resourceId']['videoId']
            
        if video_id != latest_video_id:
            # This is a new video! Post it to Discord
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                video_title = video['snippet']['title']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                channel_title = video['snippet']['channelTitle']
                await channel.send(
                    f"📺 **New Video from {channel_title}!**\n"
                    f"**{video_title}**\n"
                    f"{video_url}"
                )
                save_last_video(video_id)
        
    except Exception as e:
        print(f"Error checking YouTube videos: {e}")

def load_last_video():
    """Loads the last posted video ID from a file."""
    if os.path.exists(LAST_VIDEO_FILE):
        with open(LAST_VIDEO_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_video_id")
    return None


def save_last_video(video_id):
    """Saves the last posted video ID to a file."""
    with open(LAST_VIDEO_FILE, "w") as f:
        json.dump({"last_video_id": video_id}, f)

def delete_video_file():
    """Deletes the video file"""
    if os.path.exists(LAST_VIDEO_FILE):
        os.remove(LAST_VIDEO_FILE)
    return None

@bot.command(name='forcescan')
@commands.has_permissions(send_messages=True)
async def force_scan(ctx):
    """Clear and Force an immediate scan for new videos"""
    await ctx.send("Clearing latest video and forcing a scan for new videos...")
    delete_video_file()
    await check_youtube_videos()
    await ctx.send("Scan complete!")

# Run the bot
bot.run(DISCORD_TOKEN)