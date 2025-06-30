import os
import discord
from discord.ext import commands
import aiohttp
import asyncio
import time
from flask import Flask, render_template_string, request
import threading

TOKEN = os.getenv('TOKEN')
DEFAULT_CHANNEL_ID = 123456789012345678  # Fallback channel ID

# Define the categories you want to monitor
CATEGORIES = ['gear-seeds', 'shop-seeds', 'gear', 'eggs', 'honey']

# Will be filled dynamically with user preferences per category
watched_items = {category: [] for category in CATEGORIES}
watched_channel_id = DEFAULT_CHANNEL_ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask web dashboard
app = Flask(__name__)
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Grow a Garden Bot Dashboard</title>
</head>
<body>
    <h1>Tracked Items</h1>
    <form method="POST">
        <label for="channel_id">Discord Channel ID:</label>
        <input type="text" name="channel_id" value="{{ channel_id }}"><br><br>
        {% for category, items in all_items.items() %}
            <h3>{{ category }}</h3>
            {% for item in items %}
                <input type="checkbox" name="{{ category }}" value="{{ item }}" {% if item in watched_items[category] %}checked{% endif %}> {{ item }}<br>
            {% endfor %}
        {% endfor %}
        <br><input type="submit" value="Save">
    </form>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    global watched_items, watched_channel_id

    all_items = {cat: [] for cat in CATEGORIES}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def gather_items():
        async with aiohttp.ClientSession() as session:
            for category in CATEGORIES:
                ts = int(time.time() * 1000)
                url = f'https://growagardenstock.com/api/stock?type={category}&ts={ts}'
                async with session.get(url) as resp:
                    data = await resp.json()
                    all_items[category] = list(data.keys())

    loop.run_until_complete(gather_items())

    if request.method == 'POST':
        watched_channel_id = int(request.form.get('channel_id', DEFAULT_CHANNEL_ID))
        for category in CATEGORIES:
            watched_items[category] = request.form.getlist(category)

    return render_template_string(TEMPLATE, all_items=all_items, watched_items=watched_items, channel_id=watched_channel_id)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    bot.loop.create_task(monitor_stock())

async def fetch_stock(category):
    ts = int(time.time() * 1000)
    url = f'https://growagardenstock.com/api/stock?type={category}&ts={ts}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def monitor_stock():
    await bot.wait_until_ready()

    while not bot.is_closed():
        for category in CATEGORIES:
            if not watched_items[category]:
                continue

            try:
                data = await fetch_stock(category)
                channel = bot.get_channel(watched_channel_id)
                for item_name in watched_items[category]:
                    item_info = data.get(item_name)
                    if item_info and item_info['stock'] > 1:
                        await channel.send(f"🔔 **{item_name}** is in stock in `{category}`! ({item_info['stock']} available)")
            except Exception as e:
                print(f"Error checking {category}: {e}")

        await asyncio.sleep(300)  # 5 minutes

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Start Flask app in a separate thread
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

bot.run(TOKEN)
