import discord
import asyncio
from pyVinted import Vinted
import sqlite3
import time
from discord.ext import commands
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',filename='vinted_bot.log')
#

TOKEN = '' #TOKEN du bot discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents) 


FILTERS = []
conn = sqlite3.connect('vinted_bot.db')  # Créez la DB 
cursor = conn.cursor()

# Créez une table pour stocker les IDs des articles déjà envoyés
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sent_items (
        item_id TEXT PRIMARY KEY,
        timestamp INTEGER
    )
''')
conn.commit()

@bot.event
async def on_ready():
    global vinted
    logging.info(f'Logged in as {bot.user.name}')
    vinted = Vinted()
    await check_vinted()  # Lancement de la boucle main

@bot.event
async def on_error(event, *args, **kwargs):
    error_message = f'An error occurred: {event}'
    logging.error(error_message)

def is_valid_link(link):
    try:
        items = vinted.items.search(link)
        if items:
            return True
        else:
            return False
    except Exception as e:
        error_message = f'An error occurred while checking the link: {str(e)}'
        logging.error(error_message)
        return False




# ------------------- Fonctions de la DB -------------------

# Vérification si l'article a déjà été envoyé en consultant la DB
def is_item_sent(item_id):
    cursor.execute('SELECT item_id FROM sent_items WHERE item_id = ?', (item_id,))
    return cursor.fetchone() is not None

# Ajout de l'ID de l'article à la DB
def mark_item_as_sent(item_id):
    timestamp = int(time.time())
    cursor.execute('INSERT INTO sent_items (item_id, timestamp) VALUES (?, ?)', (item_id, timestamp))
    conn.commit()

def cleanup_database():
    cursor.execute('SELECT COUNT(*) FROM sent_items')
    total_items = cursor.fetchone()[0]
    if total_items >= 2000:
        # Supprimer les 1500 articles les plus anciens
        cursor.execute('DELETE FROM sent_items WHERE item_id IN (SELECT item_id FROM sent_items ORDER BY timestamp ASC LIMIT 1500)')
        conn.commit()


# ------------------- Commandes Discord -------------------

@bot.command()
async def add_filter(ctx, search_text):
    global FILTERS
    if is_valid_link(search_text):
        FILTERS.append((search_text, ctx.channel.id))
        await ctx.send(f'Filtre ajouté : {search_text}', suppress_embeds=True)
    else:
        await ctx.send(f'Le filtre {search_text} n\'est pas valide.')

@bot.command()
async def list_filters(ctx):
    message = 'Liste des filtres :\n'
    for i, filter in enumerate(FILTERS):
        message += f'{i + 1}. [filtre {i+1}]({filter[0]})\n'
    await ctx.send(message, suppress_embeds=True)

@bot.command()
async def remove_filter(ctx, filter_number: int):
    if 1 <= filter_number <= len(FILTERS):
        removed_filter = FILTERS.pop(filter_number - 1)
        await ctx.send(f'Filtre {filter_number} supprimé : {removed_filter[0]}', suppress_embeds=True)
    else:
        await ctx.send(f'Numéro de filtre invalide. Veuillez entrer un numéro entre 1 et {len(FILTERS)}.')

@bot.command()
async def help_cmd(ctx):
    await ctx.send('```Commandes disponibles :\n\n!add_filter <lien_vinted> : ajoute un filtre dans le channel où la commande est appelée\n\n!remove_filter <numéro_filtre> : supprime un filtre par son numéro\n\n!list_filters : liste les filtres actifs```')

async def check_vinted():
    while True:
        for filter_text in FILTERS:
            try:
                items = vinted.items.search(filter_text[0], json=True)

                if items:
                    for item in items[:10]:
                        item_id = item['id']
                        if not is_item_sent(item_id):
                            mark_item_as_sent(item_id)
                            embed = discord.Embed(title=f"{item['title']}", url=f"{item['url']}", color=0x11d44c)
                            embed.set_image(url=f"{item['photo']['url']}")
                            embed.add_field(name="Prix avec frais", value=f"{item['total_item_price']}", inline=True)
                            embed.add_field(name="Taille", value=f"{item['size_title']}", inline=True)
                            embed.add_field(name="Marque", value=f"{item['brand_title']}", inline=True)
                            embed.add_field(name="État", value=f"{item['status']}", inline=True)
                            embed.set_footer(text=f"Vinted Bot - {time.strftime('%H:%M:%S')}")

                            await bot.get_channel(filter_text[1]).send(embed=embed)
                cleanup_database()  # Nettoyer la DB
            except Exception as e:
                error_message = f'An error occurred while checking Vinted: {str(e)}'
                logging.error(error_message)
            await asyncio.sleep(5)  # Attendre 5 sec pour ne pas spammer les requêtes

if __name__ == '__main__':
    bot.run(TOKEN)
conn.close()
