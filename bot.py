
import discord
from discord import app_commands
import asyncio
import os
import json
import threading
from flask import Flask
import requests

app = Flask(__name__)
@app.route('/')
def home():
    try:
        with open('auto_channels.json','r') as f:
            data=json.load(f)
            count=len(data)
    except:
        count=0
    try:
        from argos_translate import translate
        stato = "PRONTO"
    except:
        stato = "PRONTO" if os.path.exists('/tmp/argos_done') else "Download in corso..."
    return f"BLACKOUT Translator Online - {stato} - {count} canali"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()

EMERGENZA = {
    "hello world": "ciao mondo",
    "hello": "ciao",
}

def traduci_testo_sync(texto: str) -> str:
    if not texto or not texto.strip():
        return texto
    low = texto.strip().lower()
    if low in EMERGENZA:
        return EMERGENZA[low]
    if len(texto) < 100:
        for k,v in EMERGENZA.items():
            if k in low:
                return texto.lower().replace(k, v)
    try:
        from argos_translate import translate
        tr = translate.translate(texto, "en", "it")
        if tr and tr.strip() != texto.strip():
            return tr
    except Exception as e:
        print(f"Argos skip: {e}")
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": texto, "langpair": "en|it"}, timeout=8)
        t = r.json().get("responseData", {}).get("translatedText")
        if t and "MYMEMORY WARNING" not in t:
            return t
    except Exception as e:
        print(f"MyMemory fail: {e}")
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='en', target='it').translate(texto)
    except Exception as e:
        print(f"Google fail: {e}")
        return texto

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

AUTO_FILE = "auto_channels.json"
def load_auto():
    try:
        with open(AUTO_FILE, 'r') as f:
            return set(json.load(f))
    except:
        return set()
def save_auto(channels):
    with open(AUTO_FILE, 'w') as f:
        json.dump(list(channels), f)
auto_channels = load_auto()

@client.event
async def on_ready():
    print(f"Bot online {client.user}")
    def dl():
        try:
            from argos_translate import package
            av = package.get_available_packages()
            en_it = [p for p in av if p.from_code=='en' and p.to_code=='it']
            if en_it:
                en_it[0].install()
                open('/tmp/argos_done','w').write('ok')
                print("Argos OK")
        except Exception as e:
            print(f"Argos dl err {e}")
    threading.Thread(target=dl, daemon=True).start()
    try:
        await tree.sync()
    except: pass

@client.event
async def on_message(message):
    if message.author.bot: return
    if message.channel.id in auto_channels:
        if "Translated from" in message.content: return
        if not message.content.strip(): return
        try:
            orig = message.content
            if len(orig) > 900:
                chunks = [orig[i:i+900] for i in range(0, len(orig), 900)]
                trad = "\n".join([traduci_testo_sync(c) for c in chunks])
            else:
                trad = await asyncio.to_thread(traduci_testo_sync, orig)
            if trad.strip().lower() != orig.strip().lower():
                emb = discord.Embed(title=f"Rockstar Games # | chat", description=f"**{trad[:3500]}**\n\n{orig[:500]}", color=0x00ffcc)
                emb.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT Translator | /traduci_stop per fermare auto")
                await message.channel.send(embed=emb)
        except Exception as e:
            print(e)

@tree.command(name="traduci", description="Traduci o attiva auto")
@app_commands.describe(testo="Testo da tradurre (vuoto=attiva auto)")
async def traduci(interaction: discord.Interaction, testo: str = None):
    await interaction.response.defer(thinking=True)
    try:
        if not testo:
            auto_channels.add(interaction.channel.id)
            save_auto(auto_channels)
            await interaction.followup.send(f"✅ Auto ATTIVATA in <#{interaction.channel.id}>!")
            return
        else:
            if len(testo) > 900:
                chunks = [testo[i:i+900] for i in range(0, len(testo), 900)]
                tradotti = []
                for c in chunks:
                    tradotti.append(await asyncio.to_thread(traduci_testo_sync, c))
                finale = "\n".join(tradotti)
            else:
                finale = await asyncio.to_thread(traduci_testo_sync, testo)
            await interaction.followup.send(f"**{finale[:3500]}**")
    except Exception as e:
        print(e)
        try: await interaction.followup.send(f"Errore {e}", ephemeral=True)
        except: pass

@tree.command(name="traduci_stop", description="Ferma auto")
async def traduci_stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    auto_channels.discard(interaction.channel.id)
    save_auto(auto_channels)
    await interaction.followup.send(f"🛑 Auto DISATTIVATA in <#{interaction.channel.id}>", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
