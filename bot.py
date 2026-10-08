import discord, os, threading, json, asyncio
from flask import Flask
from discord import app_commands

# Traduttore senza limiti - usa MyMemory + fallback
from deep_translator import MyMemoryTranslator, LingueeTranslator

TOKEN = os.getenv("DISCORD_TOKEN")

def traduci_sicuro(testo):
    # Prova MyMemory (gratis, 1000+ al giorno, no limite 5/sec)
    try:
        # MyMemory ha limite 5000 caratteri, spezziamo se serve
        if len(testo) > 4000:
            testo = testo[:4000]
        result = MyMemoryTranslator(source='en-US', target='it-IT').translate(testo)
        if result and "MYMEMORY WARNING" not in result and "QUERY LENGTH LIMIT" not in result:
            return result
    except Exception as e:
        print(f"MyMemory fallito: {e}")

    # Fallback 2: prova Google ma con delay
    try:
        from deep_translator import GoogleTranslator
        import time
        time.sleep(1.2)  # rispetta limite Google
        return GoogleTranslator(source='auto', target='it').translate(testo[:4000])
    except Exception as e:
        print(f"Google fallback fallito: {e}")
        return testo  # se tutto fallisce, ritorna originale

FILE_CANALE = "canali_auto.json"

def carica_canali():
    if os.path.exists(FILE_CANALE):
        try:
            with open(FILE_CANALE, "r") as file:
                return set(json.load(file))
        except:
            return set()
    return set()

def salva_canali(canali):
    with open(FILE_CANALE, "w") as file:
        json.dump(list(canali), file)

canali_auto = carica_canali()

app = Flask('')
@app.route('/')
def home():
    return "BLACKOUT Translator Online"

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
    print(f"Bot online come {bot.user} - Auto attivi: {canali_auto}")
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizzati {len(synced)} comandi")
    except Exception as e:
        print(f"Errore sync: {e}")

async def crea_embed_tradotto(testo_originale, channel_name, embed_orig=None):
    tradotto_text = traduci_sicuro(testo_originale)
    titolo = tradotto_text.split("\n\n")[0][:256] if "\n\n" in tradotto_text else tradotto_text[:256]

    nuovo_embed = discord.Embed(
        title=titolo,
        description=tradotto_text,
        color=0x00D9FF
    )
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
    print(f"Auto attivato in {interaction.channel.name}")

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
            await interaction.followup.send(f"✅ Auto-traduzione **ATTIVATA** in {interaction.channel.mention}! Da ora traduco tutto automaticamente qui. Usa `/traduci_stop` per fermare.")
            return

        embeds = await crea_embed_tradotto(testo_originale, interaction.channel.name, embed_orig)
        await interaction.followup.send(content=f"✅ Auto-traduzione **ATTIVATA** in {interaction.channel.mention}! Ora è automatico qui.", embeds=embeds)

    except Exception as e:
        print(f"Errore /traduci: {e}")
        await interaction.followup.send(f"✅ Auto attivata, ma errore traduzione: {e}")

@bot.tree.command(name="traduci_stop", description="Disattiva traduzione automatica in questo canale")
async def traduci_stop(interaction: discord.Interaction):
    if interaction.channel.id in canali_auto:
        canali_auto.remove(interaction.channel.id)
        salva_canali(canali_auto)
        await interaction.response.send_message(f"🛑 Auto **DISATTIVATA** in {interaction.channel.mention}.")
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
        # Piccolo delay per non spammare Google
        await asyncio.sleep(0.5)
        embeds = await crea_embed_tradotto(testo_originale, message.channel.name, embed_orig)
        await message.channel.send(embeds=embeds)
    except Exception as e:
        print(f"Errore auto: {e}")

bot.run(TOKEN)
