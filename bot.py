import discord
from discord import app_commands
import asyncio
import os
import json
import threading
import requests
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    try:
        with open('auto_channels.json','r') as f:
            count = len(json.load(f))
    except:
        count = 0
    return f"BLACKOUT Translator Online - PRONTO LEGGERO - {count} canali - OK"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

EMERGENZA = {
    "hello world": "ciao mondo",
    "hello": "ciao",
    "hi": "ciao",
    "thanks": "grazie",
    "thank you": "grazie",
}

def traduci_sync(text: str) -> str:
    if not text or not text.strip():
        return text
    low = text.strip().lower()
    if low in EMERGENZA:
        return EMERGENZA[low]
    # MyMemory
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": text[:900], "langpair": "en|it"}, timeout=10)
        if r.status_code == 200:
            j = r.json()
            t = j.get("responseData", {}).get("translatedText")
            if t and "MYMEMORY WARNING" not in t and t.strip() and t.lower() != low:
                return t
    except Exception as e:
        print(f"MyMemory fail: {e}")
    # Google
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='en', target='it').translate(text[:4000])
    except Exception as e:
        print(f"Google fail: {e}")
        return text

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

AUTO_FILE = "auto_channels.json"
def load_auto():
    try:
        with open(AUTO_FILE,'r') as f:
            return set(json.load(f))
    except:
        return set()
def save_auto(ch):
    try:
        with open(AUTO_FILE,'w') as f:
            json.dump(list(ch), f)
    except:
        pass

auto_channels = load_auto()

@client.event
async def on_ready():
    print(f"Bot ONLINE {client.user} | {len(auto_channels)} canali")
    try:
        synced = await tree.sync()
        print(f"Sync {len(synced)} comandi")
    except Exception as e:
        print(f"Sync error {e}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id not in auto_channels:
        return
    if "Translated from" in message.content:
        return
    if not message.content.strip():
        return
    try:
        orig = message.content
        if len(orig) < 2:
            return
        if len(orig) > 900:
            chunks = [orig[i:i+900] for i in range(0, len(orig), 900)]
            trad = "\n".join([traduci_sync(c) for c in chunks])
        else:
            trad = await asyncio.to_thread(traduci_sync, orig)
        if trad and trad.lower() != orig.lower():
            emb = discord.Embed(description=f"**{trad[:3500]}**", color=0x00ffcc)
            emb.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT")
            await message.channel.send(embed=emb)
    except Exception as e:
        print(f"Auto err {e}")

@tree.command(name="traduci", description="Traduci EN->IT o attiva auto")
@app_commands.describe(testo="Testo da tradurre (vuoto=attiva auto)")
async def traduci(interaction: discord.Interaction, testo: str = None):
    await interaction.response.defer(thinking=True)
    try:
        if not testo:
            auto_channels.add(interaction.channel.id)
            save_auto(auto_channels)
            await interaction.followup.send(f"✅ Auto ATTIVATA in <#{interaction.channel.id}>! Usa /traduci_stop per fermare.", ephemeral=True)
            return
        if len(testo) > 900:
            chunks = [testo[i:i+900] for i in range(0, len(testo), 900)]
            finale = "\n".join([await asyncio.to_thread(traduci_sync, c) for c in chunks])
        else:
            finale = await asyncio.to_thread(traduci_sync, testo)
        await interaction.followup.send(f"**{finale[:3500]}**")
    except Exception as e:
        print(e)
        try:
            await interaction.followup.send(f"Errore {e}", ephemeral=True)
        except:
            pass

@tree.command(name="traduci_stop", description="Ferma auto")
async def traduci_stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    auto_channels.discard(interaction.channel.id)
    save_auto(auto_channels)
    await interaction.followup.send(f"🛑 Auto DISATTIVATA in <#{interaction.channel.id}>", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ Manca DISCORD_TOKEN! Controlla Environment Variables su Render")
    print("⚠️ Flask resta attivo per UptimeRobot, ma bot Discord offline")
    # Tieni vivo il processo per Render
    import time
    while True:
        time.sleep(3600)
else:
    try:
        print(f"🚀 Avvio bot Discord...")
        client.run(TOKEN)
    except Exception as e:
        print(f"❌ ERRORE DISCORD: {e}")
        print("⚠️ Flask resta attivo, ma bot offline - controlla token")
        import time
        while True:
            time.sleep(3600)

