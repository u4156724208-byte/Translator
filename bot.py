import discord, os, threading, json, asyncio
from flask import Flask
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
translator_en_it = None
def init_translator():
    global translator_en_it
    try:
        from argostranslate import translate, package
        installed = translate.get_installed_languages()
        en = next((l for l in installed if l.code == "en"), None)
        it = next((l for l in installed if l.code == "it"), None)
        if not en or not it or not en.get_translation(it):
            print("Scarico pacchetto en->it Argos...")
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
            print("Traduttore offline Argos PRONTO")
    except Exception as e:
        print(f"Argos non disponibile: {e}")
        translator_en_it = None

def traduci_testo(text):
    if not text or len(text.strip()) < 2:
        return text
    if len(text) > 4000:
        text = text[:4000]
    try:
        if translator_en_it:
            result = translator_en_it.translate(text)
            if result:
                return result
    except Exception as e:
        print(f"Argos fallita: {e}")
    try:
        import requests, urllib.parse
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=it&dt=t&q={q}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            trad = "".join([x[0] for x in data[0] if x[0]])
            if trad:
                return trad
    except Exception as e:
        print(f"Google fallito: {e}")
    try:
        from deep_translator import MyMemoryTranslator
        return MyMemoryTranslator(source='en', target='it').translate(text)
    except:
        return text

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
    return "BLACKOUT Translator Online - Argos Ready"
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
    init_translator()
    print(f"Bot online {bot.user} - Auto: {canali_auto}")
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
