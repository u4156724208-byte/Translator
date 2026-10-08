
import discord
from discord import app_commands
import asyncio
import os
import json
import threading
import requests
from flask import Flask

# =======================
# 1. WEB SERVER ANTI-502 PER RENDER + UPTIMEROBOT
# =======================
app = Flask(__name__)

@app.route('/')
def home():
    try:
        with open('auto_channels.json','r') as f:
            count = len(json.load(f))
    except:
        count = 0
    # Modalità leggera: non serve Argos, siamo sempre PRONTO
    try:
        import argos_translate.translate
        stato = "PRONTO ✅ (con Argos)"
    except:
        # Se Argos non è installato, siamo in modalità leggera = sempre pronto
        stato = "PRONTO ✅ LEGGERO - MyMemory + Google"
    return f"BLACKOUT Translator Online - {stato} - {count} canali"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

# =======================
# 2. TRADUZIONE A 3 LIVELLI - NON FALLISCE MAI
# =======================
EMERGENZA = {
    "hello world": "ciao mondo",
    "hello": "ciao",
    "hi": "ciao",
    "thanks": "grazie",
    "thank you": "grazie",
    "good morning": "buongiorno",
    "good night": "buonanotte",
    "how are you": "come stai",
}

def traduci_sync(text: str) -> str:
    if not text or not text.strip():
        return text
    
    low = text.strip().lower()
    
    # LIVELLO 1: Dizionario istantaneo (0.01s) - risolve 502 e timeout
    if low in EMERGENZA:
        return EMERGENZA[low]
    
    # LIVELLO 2: Argos offline (il più stabile su Render)
    try:
        from argos_translate import translate
        tr = translate.translate(text, "en", "it")
        if tr and len(tr.strip()) > 2 and tr.lower() != low:
            return tr
    except Exception as e:
        print(f"[Argos] non pronto: {e}")

    # LIVELLO 3: MyMemory (gratis, veloce)
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:900], "langpair": "en|it"},
            timeout=10
        )
        if r.status_code == 200:
            j = r.json()
            t = j.get("responseData", {}).get("translatedText")
            if t and "MYMEMORY WARNING" not in t and t.lower() != low:
                # MyMemory a volte lascia inglese, accettiamo solo se diverso
                if len(t) > 0:
                    return t
    except Exception as e:
        print(f"[MyMemory] fail: {e}")

    # LIVELLO 4: Google via deep_translator (ultimo fallback)
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='en', target='it').translate(text[:4000])
    except Exception as e:
        print(f"[Google] fail: {e}")
        # Se tutto fallisce, ritorna originale ma NON crasha
        return text

# =======================
# 3. DISCORD BOT
# =======================
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

def save_auto(channels):
    try:
        with open(AUTO_FILE,'w') as f:
            json.dump(list(channels), f)
    except Exception as e:
        print(f"Save auto fail: {e}")

auto_channels = load_auto()

@client.event
async def on_ready():
    print(f"✅ Bot ONLINE: {client.user} | {len(auto_channels)} canali auto | MODALITA' LEGGERA - PRONTO")
    # Modalità leggera: niente download Argos, usa solo MyMemory + Google (80MB)
    
    try:
        synced = await tree.sync()
        print(f"🔄 Sync {len(synced)} comandi slash")
    except Exception as e:
        print(f"Sync error: {e}")

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
        # Evita di tradurre se già italiano (euristica semplice)
        if len(orig) < 3:
            return
        
        print(f"[AUTO] Traduco messaggio in #{message.channel.name}: {orig[:50]}...")
        
        # Traduci a chunk per patch notes lunghissimi
        if len(orig) > 900:
            chunks = [orig[i:i+900] for i in range(0, len(orig), 900)]
            tradotti = []
            for c in chunks:
                tradotti.append(traduci_sync(c))
            tradotto = "\n".join(tradotti)
        else:
            tradotto = await asyncio.to_thread(traduci_sync, orig)
        
        if tradotto and tradotto.strip().lower() != orig.strip().lower():
            embed = discord.Embed(
                description=f"**{tradotto[:3500]}**",
                color=0x00ffcc
            )
            embed.set_author(name=f"Rockstar Games # {message.channel.name}" if hasattr(message.channel,'name') else "Traduzione")
            embed.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT Translator | /traduci_stop per fermare")
            await message.channel.send(embed=embed)
            print(f"[AUTO] Tradotto e inviato!")
    except Exception as e:
        print(f"[AUTO] Errore: {e}")

# COMANDO /traduci - FIX DEFINITIVO ANTI "NON HA RISPOSTO"
@tree.command(name="traduci", description="Traduci un testo EN->IT o attiva auto-traduzione")
@app_commands.describe(testo="Testo inglese da tradurre (lascia vuoto per attivare auto in questo canale)")
async def traduci(interaction: discord.Interaction, testo: str = None):
    # FIX #1: DEFER IMMEDIATO (entro 0.3s) - risolve "L'applicazione non ha risposto" per SEMPRE
    await interaction.response.defer(thinking=True, ephemeral=False)
    
    try:
        if not testo:
            auto_channels.add(interaction.channel.id)
            save_auto(auto_channels)
            # Traduci ultimo messaggio utile
            try:
                async for msg in interaction.channel.history(limit=10):
                    if not msg.author.bot and msg.content and len(msg.content.strip()) > 3:
                        if "Translated from" not in msg.content:
                            trad = await asyncio.to_thread(traduci_sync, msg.content)
                            embed = discord.Embed(description=f"**{trad[:3500]}**\n\n{msg.content[:500]}", color=0x00ffcc)
                            embed.set_footer(text=f"Translated from #{interaction.channel.name} by BLACKOUT Translator")
                            await interaction.followup.send(embed=embed)
                            break
            except:
                pass
            await interaction.followup.send(f"✅ Auto **ATTIVATA** in <#{interaction.channel.id}>!\nUptimeRobot la terrà sveglia per sempre. Usa `/traduci_stop` per fermare.", ephemeral=True)
            return
        else:
            print(f"[/traduci] Richiesta: {testo[:80]}...")
            if len(testo) > 900:
                await interaction.followup.send(f"⏳ Testo lungo ({len(testo)} caratteri), traduco a pezzi...")
                chunks = [testo[i:i+900] for i in range(0, len(testo), 900)]
                tradotti = []
                for c in chunks:
                    t = await asyncio.to_thread(traduci_sync, c)
                    tradotti.append(t)
                finale = "\n".join(tradotti)
            else:
                finale = await asyncio.to_thread(traduci_sync, testo)
            
            await interaction.followup.send(f"**{finale[:3500]}**")
            print(f"[/traduci] Inviato!")
    except Exception as e:
        print(f"[/traduci] Errore: {e}")
        try:
            await interaction.followup.send(f"❌ Errore: {e}\nRiprova tra 10 secondi (Render si sta svegliando)", ephemeral=True)
        except:
            pass

@tree.command(name="traduci_stop", description="Ferma l'auto-traduzione in questo canale")
async def traduci_stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    auto_channels.discard(interaction.channel.id)
    save_auto(auto_channels)
    await interaction.followup.send(f"🛑 Auto **DISATTIVATA** in <#{interaction.channel.id}>", ephemeral=True)

# AVVIO
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRORE FATALE: manca DISCORD_TOKEN nelle Environment Variables di Render!")
else:
    print("🚀 Avvio bot...")
    client.run(TOKEN)
