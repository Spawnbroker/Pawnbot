import discord
from discord.ext import commands, tasks
import googleapiclient.discovery
from datetime import datetime
import os
import feedparser
from replit import db
from keep_alive import keep_alive

# Load environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID')
DISCORD_VIDEO_CHANNEL_ID = int(os.getenv('DISCORD_VIDEO_CHANNEL_ID'))
DISCORD_SUBSTACK_CHANNEL_ID = int(os.getenv('DISCORD_SUBSTACK_CHANNEL_ID'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))  # Default: check every hour
SUBSTACK_URL = os.getenv('SUBSTACK_URL')

# Set up the YouTube API client
youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Initialize the Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    check_youtube_videos.start()
    check_substack_articles.start()

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
            channel = bot.get_channel(DISCORD_VIDEO_CHANNEL_ID)
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

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_substack_articles():
    latest_article_url = load_last_article()
    print(f"Checking for new Substack articles at {datetime.now()}")
    
    try:
        # Create the RSS feed URL from the Substack URL
        # Remove any trailing slash and /archive if present
        base_url = SUBSTACK_URL.rstrip('/')
        if base_url.endswith('/archive'):
            base_url = base_url[:-8]
        
        rss_url = f"{base_url}/feed"
        print(f"Fetching RSS feed from: {rss_url}")
        
        # Parse the RSS feed
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print("No articles found in the RSS feed.")
            return
        
        # Get the latest article
        latest_entry = feed.entries[0]
        article_url = latest_entry.link
        article_title = latest_entry.title
        
        # Get publication name from feed title
        publication_name = feed.feed.title if hasattr(feed.feed, 'title') else "Substack"
        
        # Get publication date if available
        pub_date = ""
        if hasattr(latest_entry, 'published'):
            try:
                # Format the date nicely if possible
                pub_date = f"Published: {datetime.strptime(latest_entry.published, '%a, %d %b %Y %H:%M:%S %Z').strftime('%B %d, %Y')}\n"
            except:
                # If date parsing fails, just use the raw date string
                pub_date = f"Published: {latest_entry.published}\n"
        
        # Get summary/excerpt if available
        summary = ""
        if hasattr(latest_entry, 'summary'):
            # Strip HTML tags and limit to a reasonable length
            from html import unescape
            import re
            
            # Remove HTML tags and unescape HTML entities
            cleaned_summary = re.sub(r'<[^>]+>', '', latest_entry.summary)
            cleaned_summary = unescape(cleaned_summary)
            
            # Limit to ~200 characters and add ellipsis if truncated
            if len(cleaned_summary) > 200:
                summary = f"{cleaned_summary[:200].strip()}...\n\n"
            else:
                summary = f"{cleaned_summary.strip()}\n\n"
        
        if article_url != latest_article_url and article_url:
            # This is a new article! Post it to Discord
            channel = bot.get_channel(DISCORD_SUBSTACK_CHANNEL_ID)
            if channel:                
                await channel.send(
                    f"📝 **New Article from {publication_name}!**\n"
                    f"**{article_title}**\n"
                    f"{pub_date}"
                    f"{summary}"
                    f"{article_url}"
                )
                save_last_article(article_url)
                print(f"Posted new Substack article: {article_title}")
    except Exception as e:
        print(f"Error checking Substack articles: {e}")

def load_last_article():
    #Loads the last posted article URL from Replit's database
    return db.get("last_article_url")

def delete_article_file():
    # Deletes the article file from Replit's database
    if "last_article_url" in db:
        del db["last_article_url"]
    return None

def save_last_article(article_url):
    # Saves the last posted article URL to Replit's database
    db["last_article_url"] = article_url

def load_last_video():
    # Loads the last posted video ID from Replit's database
    return db.get("last_video_id")

def save_last_video(video_id):
    # Saves the last posted video ID to Replit's database
    db["last_video_id"] = video_id

def delete_video_file():
    # Deletes the video file from Replit's database
    if "last_video_id" in db:
        del db["last_video_id"]
    return None

@bot.command(name='forcescan')
@commands.has_permissions(send_messages=True)
async def force_scan(ctx):
    """Clear and Force an immediate scan for new videos"""
    await ctx.send("Clearing latest video and forcing a scan for new videos...")
    delete_video_file()
    delete_article_file()
    await check_youtube_videos()
    await check_substack_articles()
    await ctx.send("Scan complete!")

@bot.command(name='forcesubstack')
@commands.has_permissions(send_messages=True)
async def force_substack(ctx):
    """Clear and Force a Substack scan only"""
    await ctx.send("Clearing latest article and forcing a scan for new articles...")
    delete_article_file()
    await check_substack_articles()
    await ctx.send("Substack scan complete!")

@bot.command(name='forceyoutube')
@commands.has_permissions(send_messages=True)
async def force_youtube(ctx):
    """Clear and Force a YouTube scan only"""
    await ctx.send("Clearing latest video and forcing a scan for new videos...")
    delete_video_file()
    await check_youtube_videos()
    await ctx.send("YouTube scan complete!")

keep_alive()

# Run the bot
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)