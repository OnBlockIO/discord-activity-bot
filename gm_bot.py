import asyncio
import discord
import os
import requests
import threading
import time
import urllib3

from discord.ext import commands

urllib3.disable_warnings()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_TO_POST = int(os.environ.get("CHANNEL_ID"))
CHAIN_FILTER = os.environ.get("CHAIN_FILTER", "")
COLLECTION_FILTER = os.environ.get("COLLECTION_FILTER", "")
GM_SALES_URL = "https://api.ghostmarket.io/api/v2/events?page=1&size=100&DateFrom={}&DateTill={}&orderBy=date&orderDirection=desc&getTotal=true&localCurrency=USD&chain=&grouping=true&eventKind=orderfilled&onlyVerified=false&showBurned=false&nftName=&showBlacklisted=false&showNsfw=false&chain={}&collection={}"
GM_OFFERS_URL = "https://api.ghostmarket.io/api/v2/events?page=1&size=100&DateFrom={}&DateTill={}&orderBy=date&orderDirection=desc&getTotal=true&localCurrency=USD&chain=&grouping=true&eventKind=offercreated&onlyVerified=false&showBurned=false&nftName=&showBlacklisted=false&showNsfw=false&chain={}&collection={}"
GM_BIDS_URL = "https://api.ghostmarket.io/api/v2/events?page=1&size=100&DateFrom={}&DateTill={}&orderBy=date&orderDirection=desc&getTotal=true&localCurrency=USD&chain=&grouping=true&eventKind=orderbid&onlyVerified=false&showBurned=false&nftName=&showBlacklisted=false&showNsfw=false&chain={}&collection={}"
GM_LISTINGS_URL = "https://api.ghostmarket.io/api/v2/events?page=1&size=100&DateFrom={}&DateTill={}&orderBy=date&orderDirection=desc&getTotal=true&localCurrency=USD&chain=&grouping=true&eventKind=ordercreated&onlyVerified=false&showBurned=false&nftName=&showBlacklisted=false&showNsfw=false&chain={}&collection={}"
GM_ASSETS_URL = "https://api.ghostmarket.io/api/v2/assets?Chain={}&Contract={}&TokenIds[]={}"
GM_ATTR_URL = "https://api.ghostmarket.io/api/v2/asset/{}/attributes?page=1&size={}"
CHAIN_MAPPING = {
    "pha": "Phantasma",
    "bsc": "BSC",
    "n3": "N3",
    "polygon": "Polygon",
    "avalanche": "Avalanche",
    "eth": "Ethereum"
}
DECIMALS_MAPPING = {
    "BNB": 18,
    "WBNB": 18,
    "MATIC": 18,
    "WMATIC": 18,
    "BUSD": 18,
    "SOUL": 8,
    "GAS": 8,
    "KCAL": 10,
    "GOATI": 3,
    "ETH": 18,
    "WETH": 18,
    "NEO": 0,
    "DYT": 18,
    "DANK": 18,
    "USDC": 6,
    "SWTH": 8,
    "CAKE": 18,
    "DAI": 18,
    "BNEO": 8,
    "AVAX": 18,
    "WAVAX": 18,
    "FLM": 8,
    "GM": 8,
    "O3": 18,
    "NUDES": 8,
    "APE": 18,
    "SOM": 8,
    "FUSDT": 6,
    "FUSD": 8,
    "NEX": 8,
    "NEP": 8
}
ATTRIBUTES_TO_SHOW = 6

intents = discord.Intents.default()
description = "A bot for GhostMarket activity"
bot = commands.Bot(command_prefix='??', description=description, intents=intents)

last_sales_time = int(time.time())
last_bids_time = int(time.time())
last_offers_time = int(time.time())
last_listings_time = int(time.time())


def _get_asset_id(chain, contract, token_id):
    url = GM_ASSETS_URL.format(chain, contract, token_id)
    res = requests.get(url, verify=False).json()
    return res["assets"][0]["nftId"]


def _get_asset_attributes(asset_id):
    url = GM_ATTR_URL.format(asset_id, ATTRIBUTES_TO_SHOW)
    res = requests.get(url, verify=False).json()
    res = [x for x in res["attributes"] if x['key'].get('displayName')]
    return res


def get_gm_events_from_last_time(base_url, last_time, event_name, action_name, embed_color):
    events = []
    max_time_to_get = int(time.time()) - 60
    if max_time_to_get <= last_time:
        return events, last_time
    url = base_url.format(last_time, max_time_to_get, CHAIN_FILTER, COLLECTION_FILTER)
    res = requests.get(url, verify=False).json()
    for i, event in enumerate(res["events"] if res["events"] else []):
        if i == 0:
            last_time = event['date'] + 1
        chain = event['contract']['chain']
        chain_name = CHAIN_MAPPING.get(chain, chain)
        collection = event['collection']['name']
        collection_slug = event['collection']['slug']
        if event_name == "sale":
            user = event['toAddress'].get('offchainTitle', event['toAddress'].get('offchainName', event['toAddress'].get('onchainName', event['toAddress']['address'])))
            if len(user) > 20 and user == event['toAddress']['address']:
                user = f"{user[:5]}...{user[-5:]}"
        else:
            user = event['fromAddress'].get('offchainTitle', event['fromAddress'].get('offchainName', event['fromAddress'].get('onchainName', event['fromAddress']['address'])))
            if len(user) > 20 and user == event['fromAddress']['address']:
                user = f"{user[:5]}...{user[-5:]}"
        currency = event['quoteContract']['symbol']
        decimals = DECIMALS_MAPPING.get(currency, 0)
        price = f"{round(int(event['price']) / 10 ** decimals, 4)}"
        price = price[:-2] if price[-2:] == ".0" else price
        price_usd = round(float(event['localPrice']), 2)
        contract = event['contract']['hash']
        if event.get('metadata') is not None:
            token_id = event['tokenId']
            nft_name = event['metadata']['name']
            nft_url = f"https://ghostmarket.io/asset/{chain}/{contract}/{token_id}"
            media_uri = event['metadata'].get('mediaUri', '')
            mint_num = event['metadata']['mintNumber']
            mint_max = event['series']['maxSupply']
            asset_id = _get_asset_id(chain, contract, token_id)
            attributes = _get_asset_attributes(asset_id)
            if attributes:
                if chain == "pha":
                    mint_part = f"{mint_num} of {mint_max}" if mint_max != 0 else f"{mint_num}"
                    description = f"[{nft_name}]({nft_url})\n{action_name} by **{user}**\nFor **{price} {currency}** (${price_usd})\nMint **{mint_part}**\n\n"
                else:
                    description = f"[{nft_name}]({nft_url})\n{action_name} by **{user}**\nFor **{price} {currency}** (${price_usd})\n\n"
            else:
                attributes = []
                if chain == "pha":
                    mint_part = f"{mint_num} of {mint_max}" if mint_max != 0 else f"{mint_num}"
                    description = f"[{nft_name}]({nft_url})\n{action_name} by **{user}**\nFor **{price} {currency}** (${price_usd})\nMint **{mint_part}**"
                else:
                    description = f"[{nft_name}]({nft_url})\n{action_name} by **{user}**\nFor **{price} {currency}** (${price_usd})"
        else:
            nft_name = "Collection offer"
            nft_url = f"https://ghostmarket.io/collection/{collection_slug}"
            media_uri = f"https://cdn.ghostmarket.io/col-avatar/gm/thumb/{collection_slug}.png"
            description = f"[{nft_name}]({nft_url})\n{action_name} by **{user}**\nFor **{price} {currency}** (${price_usd})"
        if media_uri.startswith("ipfs://"):
            media_uri = f"https://cdn.ghostmarket.io/ext-thumbs/{media_uri.replace('ipfs://', '')}"
        embed = discord.Embed(title=f"New {event_name}: {chain_name} {collection} NFT",
                              description=description, color=embed_color)
        if len(media_uri) < 200 and media_uri.startswith("http"):
            embed.set_thumbnail(url=media_uri)
        if event.get('metadata') is not None:
            for attr in attributes:
                embed.add_field(name=attr["key"]["displayName"], value=attr["value"]["value"], inline=True)
        events.append(embed)
    return events, last_time


async def _discord_task(embed):
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_TO_POST)
    await channel.send(embed=embed)


def loop_in_thread(loop):
    print("STARTING DISCORD EVENT LOOP")
    loop.create_task(bot.start(BOT_TOKEN))
    loop.run_forever()


loop = asyncio.get_event_loop()
t = threading.Thread(target=loop_in_thread, args=(loop,))
t.start()


while True:
    try:
        sales, last_sales_time = get_gm_events_from_last_time(GM_SALES_URL, last_sales_time, "sale", "Bought", 0x03fc7b)
        for sale in sales[::-1]:
            bot.loop.create_task(_discord_task(sale))
    except:
        last_sales_time = int(time.time())
        print("Error retrieving last sales")
    try:
        listings, last_listings_time = get_gm_events_from_last_time(GM_LISTINGS_URL, last_listings_time, "listing", "Offered", 0x2596be)
        for listing in listings[::-1]:
            bot.loop.create_task(_discord_task(listing))
    except:
        last_listings_time = int(time.time())
        print("Error retrieving last listings")
    try:
        offers, last_offers_time = get_gm_events_from_last_time(GM_OFFERS_URL, last_offers_time, "offer", "Offer", 0xe4b634)
        for offer in offers[::-1]:
            bot.loop.create_task(_discord_task(offer))
    except:
        last_offers_time = int(time.time())
        print("Error retrieving last offers")
    try:
        bids, last_bids_time = get_gm_events_from_last_time(GM_BIDS_URL, last_bids_time, "bid", "Bid", 0xb54423)
        for bid in bids[::-1]:
            bot.loop.create_task(_discord_task(bid))
    except:
        last_bids_time = int(time.time())
        print("Error retrieving last bids")
    time.sleep(10)
