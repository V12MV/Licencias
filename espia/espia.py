import os
import discord
import re
import aiohttp
import asyncio
from discord import enums
from dotenv import load_dotenv
from keep_alive import keep_alive

# =========================================================
# 🔥 FIX CRÍTICO PARA RENDER (BYPASS DE ENUMS INMUTABLES)
# =========================================================
def _patch_from_dict(cls, data):
    if data is None:
        return cls.none
    return cls._from_value(data)

# Forzamos la inyección del método saltando la restricción de la librería
try:
    object.__setattr__(enums.FriendFlags, '_from_dict', classmethod(_patch_from_dict))
    print("✅ Parche de Enums (FriendFlags) aplicado con éxito.")
except Exception as e:
    print(f"⚠️ Error al aplicar parche: {e}")
# =========================================================

load_dotenv()

# Iniciar servidor Flask para evitar que Render mate el proceso
keep_alive()

# Validación de Token
USER_TOKEN = os.getenv('USER_TOKEN')
if not USER_TOKEN:
    print("❌ ERROR CRÍTICO: No se encontró USER_TOKEN en las variables de entorno.")

# ==========================================
# 🕵️ CLASE DEL ESPÍA
# ==========================================
class SpyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        canales_str = os.getenv('TARGET_CHANNELS', '')
        self.canales_ids = [int(cid.strip()) for cid in canales_str.split(',') if cid.strip().isdigit()]

    async def on_ready(self):
        print(f'\n[ESPIA] 🟢 Conectado exitosamente como {self.user}!')
        if not self.canales_ids:
            print("[⚠️] No hay canales configurados en TARGET_CHANNELS.")
            return

        print(f'[ESPIA] Modo Producción Activo.')
        for canal_id in self.canales_ids:
            try:
                canal = self.get_channel(canal_id) or await self.fetch_channel(canal_id)
                if canal:
                    print(f"    ✅ Monitoreando: {canal.guild.name} -> #{canal.name}")
            except:
                print(f"    ❌ No se pudo acceder al canal ID: {canal_id}")

        print(f'\n[ESPIA] 🎧 Escuchando en {len(self.canales_ids)} canales...')
        print("-" * 50)

    async def on_message(self, message):
        if message.author.id == self.user.id: return
        if message.channel.id not in self.canales_ids: return
        await self.procesar_mensaje(message)

    async def procesar_mensaje(self, message):
        if message.embeds: return 
        texto = message.content.lower().replace('*', '').replace('+', '').strip()
        
        patrones = [r'(buy|buying)\s+(\d+[kmb]?)\s+(\w+)', r'(buy|buying)\s+(\w+)\s+(\d+[kmb]?)']
        match = None
        for p in patrones:
            match = re.search(p, texto, re.IGNORECASE)
            if match: break

        if not match: return

        # Extraer datos según el patrón que hizo match
        try:
            if match.group(2).replace('k','').replace('m','').replace('b','').isdigit():
                cantidad, servidor = match.group(2).upper(), match.group(3).capitalize()
            else:
                servidor, cantidad = match.group(2).capitalize(), match.group(3).upper()
            
            print(f"🔔 [DEMANDA] {cantidad} {servidor} en {message.guild.name}")
            stock = await self.consultar_baserow(servidor)
            await self.enviar_webhook_privado(cantidad, servidor, message, stock)
            await self.enviar_webhook_publico(cantidad, servidor)
        except Exception as e:
            print(f"❌ Error procesando match: {e}")

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
                            st = fila.get('Status', {})
                            st_val = st.get('value') if isinstance(st, dict) else st
                            if st_val == 'Activo' and str(fila.get('RSPS', '')).lower() == servidor_buscado.lower():
                                matches.append(fila)
        except Exception as e:
            print(f"⚠️ Error en Baserow: {e}")
        return matches

    async def enviar_webhook_privado(self, cantidad, servidor, message, stock):
        webhook_url = os.getenv('WEBHOOK_URL')
        if not webhook_url: return
        
        color = 0xf1c40f if stock else 0x2ecc71
        res_matcher = "```yaml\n"
        if stock:
            for v in stock: 
                res_matcher += f"Vendedor: {v.get('DiscordName')}\nCant: {v.get('Quantity')}\nWS: {v.get('Whatsapp')}\n---\n"
        else:
            res_matcher += "No hay stock activo en la base de datos.\n"
        res_matcher += "```"

        payload = {
            "embeds": [{
                "author": {"name": f"Alerta de Mercado • {message.guild.name}", "icon_url": "https://i.imgur.com/eOMD93t.png"},
                "title": f"{'🎉 MATCH!' if stock else '🛒'} Compra de {servidor}",
                "description": f"Buscando: **{cantidad} {servidor}**\n\n**🔍 Resultado del Auto-Matcher:**\n{res_matcher}",
                "color": color,
                "fields": [
                    {"name": "Contacto", "value": message.author.mention, "inline": True},
                    {"name": "Link", "value": f"[Ir al mensaje]({message.jump_url})", "inline": True}
                ],
                "thumbnail": {"url": "https://i.imgur.com/eOMD93t.png"}
            }]
        }
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json=payload)

    async def enviar_webhook_publico(self, cantidad, servidor):
        web_pub = os.getenv('WEBHOOK_PUBLIC_URL')
        ticket_link = os.getenv('TICKET_CHANNEL_LINK', '#')
        if not web_pub: return
        
        payload = {
            "content": "@everyone",
            "embeds": [{
                "title": f"📢 ¡ESTAMOS COMPRANDO {servidor.upper()}!",
                "description": f"Se busca: **{cantidad}**\n\nSi tienes stock disponible, abre un ticket aquí:\n👉 [SOPORTE / TICKETS]({ticket_link})",
                "color": 0x00ff00,
                "footer": {"text": "Transacciones rápidas y seguras"}
            }]
        }
        async with aiohttp.ClientSession() as session:
            await session.post(web_pub, json=payload)

# ==========================================
# EJECUCIÓN
# ==========================================
client = SpyClient()
try:
    client.run(USER_TOKEN)
except Exception as e:
    print(f"❌ Error al iniciar el cliente: {e}")
