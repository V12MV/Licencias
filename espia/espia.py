import os
import discord
import re
import aiohttp
import asyncio
from discord import enums
from dotenv import load_dotenv
from keep_alive import keep_alive

# =========================================================
# 🔥 PARCHE DE EMERGENCIA V3 (BYPASS TOTAL DE ENUMMETA)
# =========================================================
# Creamos una versión "falsa" pero funcional de la clase que da problemas
class MockFriendFlags:
    none = 0
    def __init__(self, value): self.value = value
    @classmethod
    def _from_value(cls, value): return value
    @classmethod
    def _from_dict(cls, data):
        if data is None: return 0
        return data

# Inyectamos el parche directamente en el módulo de la librería
enums.FriendFlags = MockFriendFlags
print("✅ Parche V3 aplicado: FriendFlags emulado con éxito.")
# =========================================================

load_dotenv()

# Iniciar servidor Flask para Render
keep_alive()

# Validación de Token
USER_TOKEN = os.getenv('USER_TOKEN')
if not USER_TOKEN:
    print("❌ ERROR: Falta USER_TOKEN en Environment Variables.")

class SpyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        canales_str = os.getenv('TARGET_CHANNELS', '')
        self.canales_ids = [int(cid.strip()) for cid in canales_str.split(',') if cid.strip().isdigit()]

    async def on_ready(self):
        print(f'\n[ESPIA] 🟢 Sesión iniciada como: {self.user}')
        if not self.canales_ids:
            print("[⚠️] No hay canales en TARGET_CHANNELS.")
            return

        for canal_id in self.canales_ids:
            try:
                canal = self.get_channel(canal_id) or await self.fetch_channel(canal_id)
                if canal:
                    print(f"    ✅ Monitoreando: {canal.guild.name} -> #{canal.name}")
            except Exception:
                print(f"    ❌ Error accediendo al canal: {canal_id}")
        print("-" * 50)

    async def on_message(self, message):
        if message.author.id == self.user.id: return
        if message.channel.id not in self.canales_ids: return
        
        # Limpieza básica de texto
        texto = message.content.lower().replace('*', '').replace('+', '').strip()
        
        # Lógica de detección (Buy/Buying)
        patrones = [r'(buy|buying)\s+(\d+[kmb]?)\s+(\w+)', r'(buy|buying)\s+(\w+)\s+(\d+[kmb]?)']
        match = None
        for p in patrones:
            match = re.search(p, texto, re.IGNORECASE)
            if match: break

        if match:
            try:
                # Determinar cuál grupo es la cantidad y cuál el servidor
                g2, g3 = match.group(2), match.group(3)
                if any(c in g2.lower() for c in ['k','m','b']) or g2.isdigit():
                    cantidad, servidor = g2.upper(), g3.capitalize()
                else:
                    servidor, cantidad = g2.capitalize(), g3.upper()
                
                print(f"🔔 Match encontrado: {cantidad} en {servidor}")
                stock = await self.consultar_baserow(servidor)
                await self.enviar_webhooks(cantidad, servidor, message, stock)
            except Exception as e:
                print(f"❌ Error al procesar match: {e}")

    async def consultar_baserow(self, servidor_buscado):
        url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
        headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}
        matches = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for fila in data.get('results', []):
                            status_data = fila.get('Status', {})
                            val = status_data.get('value') if isinstance(status_data, dict) else status_data
                            if val == 'Activo' and str(fila.get('RSPS', '')).lower() == servidor_buscado.lower():
                                matches.append(fila)
        except Exception as e:
            print(f"⚠️ Error Baserow: {e}")
        return matches

    async def enviar_webhooks(self, cantidad, servidor, message, stock):
        # 1. Webhook Privado con Matcher
        priv_url = os.getenv('WEBHOOK_URL')
        if priv_url:
            res_matcher = "```yaml\n"
            if stock:
                for v in stock:
                    res_matcher += f"Vendedor: {v.get('DiscordName')}\nCant: {v.get('Quantity')}\nWS: {v.get('Whatsapp')}\n---\n"
            else:
                res_matcher += "No hay stock activo.\n"
            res_matcher += "```"

            payload_priv = {
                "embeds": [{
                    "title": f"{'🎉 MATCH!' if stock else '🛒'} Compra de {servidor}",
                    "description": f"Buscando: **{cantidad} {servidor}**\n\n**🔍 Stock:**\n{res_matcher}",
                    "color": 0xf1c40f if stock else 0x2ecc71,
                    "fields": [
                        {"name": "Usuario", "value": message.author.mention, "inline": True},
                        {"name": "Link", "value": f"[Ir al mensaje]({message.jump_url})", "inline": True}
                    ]
                }]
            }
            async with aiohttp.ClientSession() as session:
                await session.post(priv_url, json=payload_priv)

        # 2. Webhook Público
        pub_url = os.getenv('WEBHOOK_PUBLIC_URL')
        if pub_url:
            ticket = os.getenv('TICKET_CHANNEL_LINK', '#')
            payload_pub = {
                "content": "@everyone",
                "embeds": [{
                    "title": f"📢 ¡ESTAMOS COMPRANDO {servidor.upper()}!",
                    "description": f"Cantidad: **{cantidad}**\n\nVende aquí: [SOPORTE]({ticket})",
                    "color": 0x00ff00
                }]
            }
            async with aiohttp.ClientSession() as session:
                await session.post(pub_url, json=payload_pub)

# Ejecución
client = SpyClient()
try:
    client.run(USER_TOKEN)
except Exception as e:
    print(f"❌ Error fatal: {e}")
