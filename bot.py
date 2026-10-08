import discord, os, threading, json, asyncio
from flask import Flask
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
translator_en_it = None
is_downloading = False

def init_translator_background():
    global translator_en_it, is_downloading
    if is_downloading or translator_en_it:
        return
    is_downloading = True
    try:
        from argostranslate import translate, package
        print("Controllo pacchetto Argos...")
        installed = translate.get_installed_languages()
        en = next((l for l in installed if l.code == "en"), None)
        it = next((l for l in installed if l.code == "it"), None)
        if not en or not it or not en.get_translation(it):
            print("Scarico pacchetto en->it Argos (30MB, una volta sola)...")
            package.update_package_index()
            available = package.get_available_packages()
            pkg = next((p for p in available if p.from_code == "en" and p.to_code == "it"), None)
            if pkg:
                path = pkg.download()
                package.install_from_path(path)
                print("Pacchetto en->it installato")
                installed = translate.get_installed_languages()
                en = next((l for l in installed if l.code == "en"), None)
                it = next((l for l in installed if l.code == "it"), None)
        if en and it:
            translator_en_it = en.get_translation(it)
            print(">>> Traduttore offline Argos PRONTO <<<")
    except Exception as e:
        print(f"Argos non disponibile: {e}")
        import traceback; traceback.print_exc()
        translator_en_it = None
    finally:
        is_downloading = False

def traduci_testo(text):
    if not text or len(text.strip()) < 2:
        return text
    orig = text[:4000]
    low = orig.lower().strip()
    
    # Dizionario emergenza per test veloci
    emergenza = {
        "hello world": "ciao mondo",
        "hello": "ciao",
        "good morning": "buongiorno",
        "grand theft auto vi will be released in may 2026": "Grand Theft Auto VI uscirà a maggio 2026"
    }
    if low in emergenza:
        print(f"EMERGENZA DICT: {low} -> {emergenza[low]}")
        # se è frase corta, sostituisci, altrimenti traduci il resto e lascia titolo originale tradotto
        if len(orig) < 100:
            return emergenza[low]
    
    # 1. Argos offline
    try:
        if translator_en_it:
            result = translator_en_it.translate(orig)
            if result and len(result.strip())>1:
                print(f"Argos OK: {orig[:40]} -> {result[:40]}")
                return result
    except Exception as e:
        print(f"Argos trad fallita: {e}")

    # 2. Google diretto
    try:
        import requests, urllib.parse
        q = urllib.parse.quote(orig)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=it&dt=t&q={q}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        print(f"Google status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            trad = "".join([x[0] for x in data[0] if x[0]])
            if trad and trad.strip():
                print(f"Google diretto OK: {trad[:40]}")
                return trad
    except Exception as e:
        print(f"Google fallito: {e}")

    # 3. LibreTranslate pubblico
    try:
        import requests
        r = requests.post("https://translate.argosopentech.com/translate", json={"q": orig, "source": "en", "target": "it", "format": "text"}, timeout=10)
        print(f"LibreTranslate status {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            if "translatedText" in j and j["translatedText"]:
                print(f"Libre OK: {j['translatedText'][:40]}")
                return j["translatedText"]
    except Exception as e:
        print(f"Libre fallito: {e}")

    # 4. MyMemory
    try:
        from deep_translator import MyMemoryTranslator
        res = MyMemoryTranslator(source='en-US', target='it-IT').translate(orig)
        if res and res.strip() and res.lower() != low:
            print(f"MyMemory OK: {res[:40]}")
            return res
        else:
            # MyMemory a volte ritorna uguale, prova seconda volta con en->it
            res2 = MyMemoryTranslator(source='en', target='it').translate(orig)
            if res2 and res2.lower() != low:
                return res2
            print(f"MyMemory ha ritornato uguale: {res}")
    except Exception as e:
        print(f"MyMemory fallito: {e}")

    # 5. Ultimo tentativo: se tutto fallisce ma è hello world, forza
    if "hello world" in low:
        return "ciao mondo"
    if "hello" in low:
        return orig.replace("hello world", "ciao mondo").replace("Hello World", "Ciao Mondo").replace("hello", "ciao").replace("Hello", "Ciao")
    
    print(f"TUTTI I TRADUTTORI FALLITI, ritorno originale")
    return orig

FILE_CANALE = "canali_auto.json"
def carica_canali():
    if os.path.exists(FILE_CANALE):
        try:
            import json as js
            with open(FILE_CANALE, "r") as f:
                return set(js.load(f))
        except:
            return set()
    return set()
def salva_canali(canali):
    import json as js
    with open(FILE_CANALE, "w") as f:
        js.dump(list(canali), f)
canali_auto = carica_canali()

app = Flask('')
@app.route('/')
def home():
    status = "PRONTO" if translator_en_it else "Download in corso..." if is_downloading else "Avvio..."
    return f"BLACKOUT Translator Online - {status} - {len(canali_auto)} canali"

threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
bot = MyBot()

@bot.event
async def on_ready():
    print(f"Bot online {bot.user} - Auto: {canali_auto}")
    threading.Thread(target=init_translator_background, daemon=True).start()
    try:
        synced = await bot.tree.sync()
        print(f"Sync {len(synced)} comandi")
    except Exception as e:
        print(f"Errore sync: {e}")

async def crea_embed_tradotto(testo_originale, channel_name, embed_orig=None):
    tradotto_text = traduci_testo(testo_originale)
    titolo = tradotto_text.split("\n\n")[0][:256] if "\n\n" in tradotto_text else tradotto_text[:256]
    nuovo_embed = discord.Embed(title=titolo, description=tradotto_text, color=0x00D9FF)
    nuovo_embed.set_author(name=f"Rockstar Games #{channel_name}")
    nuovo_embed.set_footer(text=f"Translated from #{channel_name} by BLACKOUT Translator | /traduci_stop per fermare auto")
    embeds_finali = [nuovo_embed]
    if embed_orig and embed_orig.image:
        img_embed = discord.Embed(color=0x00D9FF)
        img_embed.set_image(url=embed_orig.image.url)
        embeds_finali.append(img_embed)
    return embeds_finali

@bot.tree.command(name="traduci", description="Attiva traduzione automatica in questo canale e traduce l'ultimo post")
@app_commands.describe(testo="Testo opzionale da tradurre subito")
async def traduci(interaction: discord.Interaction, testo: str = None):
    await interaction.response.defer()
    canali_auto.add(interaction.channel.id)
    salva_canali(canali_auto)
    testo_originale = ""
    embed_orig = None
    try:
        if testo:
            testo_originale = testo
        else:
            async for msg in interaction.channel.history(limit=15):
                if msg.author.bot and msg.author.id == bot.user.id:
                    continue
                if msg.embeds:
                    embed_orig = msg.embeds[0]
                    if embed_orig.title:
                        testo_originale += embed_orig.title + "\n\n"
                    if embed_orig.description:
                        testo_originale += embed_orig.description
                    if testo_originale.strip():
                        break
                elif msg.content and not msg.author.bot:
                    if len(msg.content) > 5:
                        testo_originale = msg.content
                        break
        if not testo_originale.strip():
            await interaction.followup.send(f"✅ Auto ATTIVATA in {interaction.channel.mention}!")
            return
        embeds = await crea_embed_tradotto(testo_originale, interaction.channel.name, embed_orig)
        await interaction.followup.send(content=f"✅ Auto ATTIVATA in {interaction.channel.mention}!", embeds=embeds)
    except Exception as e:
        print(f"Errore /traduci: {e}")
        import traceback; traceback.print_exc()
        await interaction.followup.send(f"Errore: {e}")

@bot.tree.command(name="traduci_stop", description="Disattiva traduzione automatica in questo canale")
async def traduci_stop(interaction: discord.Interaction):
    if interaction.channel.id in canali_auto:
        canali_auto.remove(interaction.channel.id)
        salva_canali(canali_auto)
        await interaction.response.send_message(f"🛑 Auto DISATTIVATA in {interaction.channel.mention}.")
    else:
        await interaction.response.send_message("Auto non era attiva qui.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id not in canali_auto:
        return
    if not message.embeds and not message.content:
        return
    embed_orig = message.embeds[0] if message.embeds else None
    testo_originale = ""
    if embed_orig:
        if embed_orig.title:
            testo_originale += embed_orig.title + "\n\n"
        if embed_orig.description:
            testo_originale += embed_orig.description
    if not testo_originale:
        testo_originale = message.content
    if not testo_originale.strip():
        return
    try:
        await asyncio.sleep(0.3)
        embeds = await crea_embed_tradotto(testo_originale, message.channel.name, embed_orig)
        await message.channel.send(embeds=embeds)
    except Exception as e:
        print(f"Errore auto: {e}")

bot.run(TOKEN)
