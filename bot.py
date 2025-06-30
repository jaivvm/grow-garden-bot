import os
import discord
from discord.ext import commands
import aiohttp
import asyncio
from flask import Flask, render_template_string, request
import threading

TOKEN = os.getenv("TOKEN")
DEFAULT_CHANNEL_ID = 123456789012345678

API_BASE_URL = "https://growagardenapi.just3itx.repl.co"

CATEGORIES = ["seeds", "gear", "eggs", "honey"]

watched_items = {category: [] for category in CATEGORIES}
watched_channel_id = DEFAULT_CHANNEL_ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__)
TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Grow a Garden Bot Dashboard</title></head>
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

@app.route("/", methods=["GET", "POST"])
def index():
    global watched_items, watched_channel_id
    all_items = {cat: [] for cat in CATEGORIES}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def gather_items():
        async with aiohttp.ClientSession() as session:
            for cat in CATEGORIES:
                async with session.get(f"{API_BASE_URL}/{cat}") as resp:
                    data = await resp.json()
                    all_items[cat] = list(data.keys())

    loop.run_until_complete(gather_items())

    if request.method == "POST":
        watched_channel_id = int(request.form.get("channel_id", DEFAULT_CHANNEL_ID))
        for category in CATEGORIES:
            watched_items[category] = request.form.getlist(category)

    return render_template_string(TEMPLATE, all_items=all_items, watched_items=watched_items, channel_id=watched_channel_id)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(monitor_stock())

async def fetch_category_stock(category):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE_URL}/{category}") as resp:
            return await resp.json()

async def monitor_stock():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for category in CATEGORIES:
            try:
                data = await fetch_category_stock(category)
                channel = bot.get_channel(watched_channel_id)
                for item in watched_items[category]:
                    stock = data.get(item, {}).get("stock", 0)
                    if stock > 1:
                        await channel.send(f"🔔 **{item}** is in stock in `{category}`! ({stock} available)")
            except Exception as e:
                print(f"Error checking {category}: {e}")
        await asyncio.sleep(300)

def run_flask():
    app.run(host="0.0.0.0", port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

bot.run(TOKEN)
