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
    # MyMemory - limite 500 chars, usiamo 400 per sicurezza
    try:
        q = text[:400]  # FIX: prima era 900, MyMemory max 500
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": q, "langpair": "en|it"}, timeout=10)
        if r.status_code == 200:
            j = r.json()
            t = j.get("responseData", {}).get("translatedText")
            # Filtra errori MyMemory
            if t:
                upper = t.upper()
                if "QUERY LENGTH LIMIT EXCEEDED" in upper or "MAX ALLOWED QUERY" in upper or "MYMEMORY WARNING" in upper:
                    print(f"MyMemory limite superato, passo a Google")
                elif t.strip() and t.lower() != low:
                    return t
    except Exception as e:
        print(f"MyMemory fail: {e}")
    # Google fallback - gestisce testi lunghi fino a 4000
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
    
    # Estrae testo da content + embeds (per patch notes di DbD ecc)
    orig = ""
    if message.content and message.content.strip():
        orig = message.content.strip()
    elif message.embeds:
        # Prendi titolo + descrizione + fields dagli embed
        parts = []
        for emb in message.embeds:
            if emb.title:
                parts.append(emb.title)
            if emb.description:
                parts.append(emb.description)
            for f in emb.fields:
                if f.name:
                    parts.append(f.name)
                if f.value:
                    parts.append(f.value)
        orig = "\n".join(parts).strip()
    
    if not orig or len(orig) < 2:
        return
    
    try:
        print(f"[AUTO] Traduco in #{message.channel.name}: {orig[:80]}...")
        if len(orig) > 400:
            chunks = [orig[i:i+400] for i in range(0, len(orig), 400)]
            # Traduci ogni chunk e unisci
            trad_parts = []
            for c in chunks:
                trad_parts.append(traduci_sync(c))
            trad = "\n".join(trad_parts)
        else:
            trad = await asyncio.to_thread(traduci_sync, orig)
        
        if trad and trad.lower().strip() != orig.lower().strip():
            # Taglia per limite embed Discord 4096
            if len(trad) > 3500:
                trad = trad[:3500] + "..."
            emb = discord.Embed(description=f"**{trad}**", color=0x00ffcc)
            emb.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT | /traduci_stop per fermare")
            await message.channel.send(embed=emb)
            print(f"[AUTO] Tradotto!")
    except Exception as e:
        print(f"[AUTO] Errore: {e}")

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
        if len(testo) > 400:
            chunks = [testo[i:i+400] for i in range(0, len(testo), 400)]
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

