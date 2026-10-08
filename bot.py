import 【entity-discord¦canonical_name=discord】, os, threading
from flask import Flask
from googletrans import Translator

TOKEN = os.getenv("DISCORD_TOKEN")
translator = Translator()

app = Flask('')
@app.route('/')
def home():
    return "BLACKOUT Translator Online"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()

intents = 【entity-discord¦canonical_name=discord】.Intents.default()
intents.message_content = True
bot = 【entity-【entity-discord¦canonical_name=discord】¦canonical_name=【entity-discord¦canonical_name=discord】】.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online come {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
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
        tradotto = await translator.translate(testo_originale, dest="it")
        nuovo_embed = discord.Embed(
            title=tradotto.text.split("\n\n")[0][:256],
            description=tradotto.text,
            color=0x00D9FF
        )
        nuovo_embed.set_author(name=f"【entity-Rockstar Games¦canonical_name=Rockstar Games】 #{message.channel.name}")
        nuovo_embed.set_footer(text=f"Translated from #{message.channel.name} by BLACKOUT Translator")
        embeds_finali = [nuovo_embed]
        if embed_orig and embed_orig.image:
            img_embed = 【entity-discord¦canonical_name=discord】.Embed(color=0x00D9FF)
            img_embed.set_image(url=embed_orig.image.url)
            embeds_finali.append(img_embed)
        await message.channel.send(embeds=embeds_finali)
    except Exception as e:
        print(f"Errore: {e}")

bot.run(TOKEN)
