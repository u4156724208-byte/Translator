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
    return f"BLACKOUT Translator Online - OFFLINE MODE - {count} canali - OK"

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

# --- TRADUTTORE OFFLINE (Argos) ---
argos_ready = False
argos_from_en_to_it = None

def init_argos():
    global argos_ready, argos_from_en_to_it
    try:
        from argostranslate import package, translate
        from_code, to_code = "en", "it"
        # Controlla se già installato
        installed = package.get_installed_packages()
        has_en_it = any(p.from_code == from_code and p.to_code == to_code for p in installed)
        if not has_en_it:
            print("📥 Scarico modello Argos en->it (80MB) una tantum...")
            available = package.get_available_packages()
            avail = [p for p in available if p.from_code == from_code and p.to_code == to_code]
            if avail:
                pkg = avail[0]
                path = pkg.download()
                package.install_from_path(path)
                print("✅ Modello Argos installato")
        # Carica traduttore
        from argostranslate.translate import get_translation_from_codes
        argos_from_en_to_it = get_translation_from_codes(from_code, to_code)
        argos_ready = True
        print("✅ Argos OFFLINE pronto")
    except Exception as e:
        print(f"⚠️ Argos non pronto: {e}")
        argos_ready = False

# Prova a inizializzare all'avvio in background
def init_argos_thread():
    try:
        init_argos()
    except Exception as e:
        print(f"Argos thread fail {e}")

threading.Thread(target=init_argos_thread, daemon=True).start()

def chunk_smart(text, max_len=380):
    chunks = []
    while len(text) > max_len:
        cut = text.rfind(' ', 0, max_len)
        if cut == -1:
            cut = text.rfind('\n', 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks

def google_free_translate(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "it", "dt": "t", "q": text}
        r = requests.get(url, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data[0], list):
                translated = "".join([item[0] for item in data[0] if item and len(item)>0 and item[0]])
                if translated and translated.strip():
                    return translated
    except Exception as e:
        print(f"[GoogleFree fail] {e}")
    return None

def traduci_sync(text: str) -> str:
    if not text or not text.strip():
        return text
    low = text.strip().lower()
    if low in EMERGENZA:
        return EMERGENZA[low]

    # 1. OFFLINE Argos (garantito, no rate limit)
    if argos_ready and argos_from_en_to_it:
        try:
            res = argos_from_en_to_it.translate(text)
            if res and res.strip() and res.lower() != low:
                return res
        except Exception as e:
            print(f"[Argos fail] {e}")

    # 2. Google diretto
    res = google_free_translate(text[:3500])
    if res and res.strip() and res.lower() != low:
        if res.lower().strip() != text.lower().strip():
            return res

    # 3. MyMemory
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:380], "langpair": "en|it", "de": "blackout@translator.com"},
                         timeout=10)
        if r.status_code == 200:
            j = r.json()
            t = j.get("responseData", {}).get("translatedText")
            if t and "QUERY LENGTH" not in t.upper() and "MYMEMORY WARNING" not in t.upper():
                if t.strip().lower() != low:
                    return t
    except Exception as e:
        print(f"[MyMemory fail] {e}")

    # 4. deep_translator
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='en', target='it').translate(text[:3500])
        if result and result.strip().lower() != low:
            return result
    except:
        pass

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
    print(f"Bot ONLINE {client.user} | {len(auto_channels)} canali | Argos={argos_ready}")
    try:
        synced = await tree.sync()
        print(f"Sync {len(synced)} comandi")
    except Exception as e:
        print(f"Sync error {e}")

@client.event
async def on_message(message):
    try:
        if client.user and message.author.id == client.user.id:
            return
    except:
        pass
    if "Translated from" in (message.content or ""):
        return
    if message.embeds:
        for em in message.embeds:
            if em.footer and em.footer.text and "BLACKOUT" in em.footer.text:
                return
    if message.channel.id not in auto_channels:
        return

    parts = []
    if message.content and message.content.strip():
        txt = message.content.strip()
        if "will now receive notifications for" not in txt and "will no longer receive" not in txt:
            parts.append(txt)
    
    if message.embeds:
        for emb in message.embeds:
            if emb.title:
                parts.append(emb.title)
            if emb.description:
                parts.append(emb.description)
            for f in emb.fields:
                if f.value:
                    parts.append(f.value)
    
    orig = "\n".join(parts).strip()
    if not orig or len(orig) < 3:
        return
    if "will now receive notifications for" in orig.lower() and len(orig) < 300:
        embed_only = []
        for emb in message.embeds:
            if emb.title:
                embed_only.append(emb.title)
            if emb.description:
                embed_only.append(emb.description)
        if embed_only:
            orig = "\n".join(embed_only).strip()
        else:
            return

    try:
        if len(orig) > 380:
            chunks = chunk_smart(orig, 380)
            trad_parts = [traduci_sync(c) for c in chunks]
            trad = "\n".join(trad_parts)
        else:
            trad = await asyncio.to_thread(traduci_sync, orig)
        
        if trad and trad.strip() and trad.lower().strip() != orig.lower().strip():
            if len(trad) > 3500:
                trad = trad[:3500] + "..."
            emb = discord.Embed(description=f"**{trad}**", color=0x00ffcc)
            emb.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT | /traduci_stop per fermare")
            await message.channel.send(embed=emb)
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
        if len(testo) > 380:
            chunks = chunk_smart(testo, 380)
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
    print("❌ Manca DISCORD_TOKEN!")
    import time
    while True:
        time.sleep(3600)
else:
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import time
        while True:
            time.sleep(3600)
