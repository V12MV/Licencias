import os
import discord
import re
import aiohttp
import asyncio
from discord import enums
from discord.settings import Settings
from dotenv import load_dotenv
from keep_alive import keep_alive

# =========================================================
# 🔥 EL "SANTO GRIAL" DE LOS FIXES PARA RENDER
# =========================================================

# 1. Parche para Enums (Lo que ya arreglamos)
class MockFriendFlags:
    none = 0
    def __init__(self, value): self.value = value
    @classmethod
    def _from_value(cls, value): return value
    @classmethod
    def _from_dict(cls, data):
        return 0 if data is None else data
enums.FriendFlags = MockFriendFlags

# 2. Parche para Settings (Arregla el Error 'NoneType')
original_settings_init = Settings.__init__
def patched_settings_init(self, *args, **kwargs):
    if 'data' in kwargs and kwargs['data'] is not None:
        # Si Discord no envía estos datos, los inventamos para que no explote
        if kwargs['data'].get('friend_source_flags') is None:
            kwargs['data']['friend_source_flags'] = {'all': True}
    original_settings_init(self, *args, **kwargs)

Settings.__init__ = patched_settings_init
print("✅ Parche V4 (Anti-NoneType) aplicado con éxito.")
# =========================================================

load_dotenv()
keep_alive()

USER_TOKEN = os.getenv('USER_TOKEN')

class SpyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        canales_str = os.getenv('TARGET_CHANNELS', '')
        self.canales_ids = [int(cid.strip()) for cid in canales_str.split(',') if cid.strip().isdigit()]

    async def on_ready(self):
        print(f'\n[ESPIA] 🟢 BOT ONLINE: {self.user}')
        print(f'[ESPIA] Monitoreando {len(self.canales_ids)} canales.')
        print("-" * 50)

    async def on_message(self, message):
        if message.author.id == self.user.id: return
        if message.channel.id not in self.canales_ids: return
        
        texto = message.content.lower().replace('*', '').replace('+', '').strip()
        patrones = [r'(buy|buying)\s+(\d+[kmb]?)\s+(\w+)', r'(buy|buying)\s+(\w+)\s+(\d+[kmb]?)']
        
        for p in patrones:
            match = re.search(p, texto, re.IGNORECASE)
            if match:
                try:
                    g2, g3 = match.group(2), match.group(3)
                    if any(c in g2.lower() for c in ['k','m','b']) or g2.isdigit():
                        cant, serv = g2.upper(), g3.capitalize()
                    else:
                        serv, cant = g2.capitalize(), g3.upper()
                    
                    print(f"🔔 Detectado: {cant} en {serv}")
                    stock = await self.consultar_baserow(serv)
                    await self.enviar_webhooks(cant, serv, message, stock)
                except: pass
                break

    async def consultar_baserow(self, serv_buscado):
        url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
        headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return [f for f in data.get('results', []) if str(f.get('RSPS','')).lower() == serv_buscado.lower() and (isinstance(f.get('Status'), dict) and f.get('Status').get('value') == 'Activo' or f.get('Status') == 'Activo')]
        except: pass
        return []

    async def enviar_webhooks(self, cant, serv, msg, stock):
        priv = os.getenv('WEBHOOK_URL')
        pub = os.getenv('WEBHOOK_PUBLIC_URL')
        
        async with aiohttp.ClientSession() as session:
            if priv:
                res = "```yaml\n"
                if stock:
                    for v in stock: res += f"Vendedor: {v.get('DiscordName')}\nCant: {v.get('Quantity')}\n---\n"
                else: res += "Sin stock activo.\n"
                res += "```"
                
                payload = {"embeds": [{"title": f"Compra: {serv}", "description": f"Cant: {cant}\n{res}", "color": 0xf1c40f, "fields": [{"name":"Link","value":msg.jump_url}]}]}
                await session.post(priv, json=payload)
            
            if pub:
                ticket = os.getenv('TICKET_CHANNEL_LINK', '#')
                payload_pub = {"content": "@everyone", "embeds": [{"title": f"📢 COMPRANDO {serv.upper()}", "description": f"Cantidad: **{cant}**\n[Vende aquí]({ticket})", "color": 0x00ff00}]}
                await session.post(pub, json=payload_pub)

# RUN
client = SpyClient()
try:
    client.run(USER_TOKEN)
except Exception as e:
    print(f"❌ Error en el run: {e}")
