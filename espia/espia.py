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
# 🔥 BLOQUE DE SEGURIDAD (MANTENER PARA RENDER)
# =========================================================
class MockFriendFlags:
    none = 0
    def __init__(self, value): self.value = value
    @classmethod
    def _from_value(cls, value): return value
    @classmethod
    def _from_dict(cls, data): return 0 if data is None else data
enums.FriendFlags = MockFriendFlags

original_settings_init = Settings.__init__
def patched_settings_init(self, *args, **kwargs):
    if 'data' in kwargs and kwargs['data'] is not None:
        if kwargs['data'].get('friend_source_flags') is None:
            kwargs['data']['friend_source_flags'] = {'all': True}
    original_settings_init(self, *args, **kwargs)
Settings.__init__ = patched_settings_init
# =========================================================

load_dotenv()
keep_alive()

class SpyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        canales_str = os.getenv('TARGET_CHANNELS', '')
        self.canales_ids = [int(cid.strip()) for cid in canales_str.split(',') if cid.strip().isdigit()]

    async def on_ready(self):
        print(f'\n[ESPIA] 🟢 Conectado exitosamente como {self.user}!')
        if not self.canales_ids:
            print("[ERROR] No hay canales configurados en TARGET_CHANNELS (.env)")
            return

        print(f'[ESPIA] Iniciando MODO PRODUCCIÓN (CON MOTOR INTELIGENTE).')
        
        canales_exitosos = 0
        for canal_id in self.canales_ids:
            canal = self.get_channel(canal_id)
            if canal is None:
                try:
                    canal = await self.fetch_channel(canal_id)
                except Exception:
                    pass
            if canal:
                print(f"   ✅ Monitoreando: {canal.guild.name} -> #{canal.name}")
                canales_exitosos += 1

        print(f'\n[ESPIA] 🎧 Escuchando en {canales_exitosos} canales...')
        print("-" * 50)

    async def on_message(self, message):
        if message.author.id == self.user.id: return
        if message.channel.id not in self.canales_ids: return
        await self.procesar_mensaje(message)

    async def procesar_mensaje(self, message):
        if message.embeds: return 

        # 1. Separar por líneas (Mucha gente manda listas enteras en un solo mensaje)
        lineas = message.content.split('\n')
        matches_encontrados = [] # Para no repetir alertas del mismo server en un mensaje
        
        for linea in lineas:
            linea = linea.lower().strip()
            
            # Filtro rápido: si la línea no tiene "buy" o "buying", la saltamos
            if not re.search(r'\b(buy|buying)\b', linea):
                continue
                
            # 2. Limpieza extrema: Quitar pings (@), emojis raros y dejar lo esencial
            texto_limpio = re.sub(r'<@&?\d+>', '', linea) # Quita @Roles y @Usuarios
            texto_limpio = texto_limpio.replace('@everyone', '').replace('@here', '')
            # Dejar solo letras, números, espacios y caracteres útiles (., -, +, /)
            texto_limpio = re.sub(r'[^\w\s\.\-\+/]', '', texto_limpio).strip()
            
            # 3. Partir el texto justo después de "buy" o "buying"
            partes = re.split(r'\b(?:buy|buying)\b', texto_limpio, maxsplit=1)
            if len(partes) < 2: continue
            
            resto = partes[1].strip()
            
            # 4. Eliminar "palabras basura" que usan los traders y confunden la búsqueda
            palabras_basura = ['asap', 'bulk', 'with account', 'for good price', 'for', 'good', 'price', 'all rsps', 'and selling', 'selling', 'and']
            for pb in palabras_basura:
                resto = re.sub(rf'\b{pb}\b', '', resto).strip()
                
            if not resto or resto == '': continue
            
            cantidad = "Cant. Variable / A Consultar"
            servidor_rsps = resto
            
            # 5. Inteligencia de Extracción (Detectar rangos como 1-5M, 500B-800B, 25t+)
            # Comprueba si el texto arranca con números, letras de medida, guiones o símbolos +
            match_cantidad = re.match(r'^([0-9\.\-\+kmbqtKMBQT]+)\s+(.*)$', resto)
            if match_cantidad:
                cantidad = match_cantidad.group(1).upper()
                servidor_rsps = match_cantidad.group(2).strip()
            else:
                # Buscar si lo escribieron al revés (Ej: "Lost City 10m")
                match_inv = re.match(r'^(.*)\s+([0-9\.\-\+kmbqtKMBQT]+)$', resto)
                if match_inv:
                    servidor_rsps = match_inv.group(1).strip()
                    cantidad = match_inv.group(2).upper()

            # 6. Múltiples Servidores: Separar si usan "/" (Ej: Roatz / Lost City)
            servidores = [s.strip().title() for s in servidor_rsps.split('/') if s.strip()]
            
            for serv in servidores:
                # Evitar alertas basura si detecta palabras muy cortas o si dicen "All"
                if len(serv) < 2 or serv.lower() in ['all', 'all rsps']: 
                    continue 
                    
                if serv in matches_encontrados: 
                    continue # Evita doble notificación si repiten el nombre
                    
                matches_encontrados.append(serv)
                
                print(f"\n🔔 [NUEVA DEMANDA] {cantidad} de {serv} | De: {message.guild.name}")
                stock_disponible = await self.consultar_baserow(serv)
                
                await self.enviar_webhook_privado("Buy", cantidad, serv, message, stock_disponible)
                await self.enviar_webhook_publico(cantidad, serv)

    async def consultar_baserow(self, servidor_buscado):
        url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
        headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}
        
        vendedores_match = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        filas = data.get('results', [])
                        for fila in filas:
                            status = fila.get('Status', {})
                            status_val = status.get('value') if isinstance(status, dict) else status
                            if status_val == 'Activo' and str(fila.get('RSPS', '')).lower() == servidor_buscado.lower():
                                vendedores_match.append(fila)
        except Exception as e:
            print(f"⚠️ Error Baserow: {e}")
        return vendedores_match

    async def enviar_webhook_privado(self, accion, cantidad, servidor_rsps, message, stock_disponible):
        webhook_url = os.getenv('WEBHOOK_URL')
        if not webhook_url: return

        if stock_disponible:
            color = 0xf1c40f # Dorado
            titulo = f"🎉 ¡MATCH ENCONTRADO! Demanda de {servidor_rsps}"
            texto_stock = "```yaml\n"
            for v in stock_disponible:
                texto_stock += f"Vendedor : {v.get('DiscordName')}\n"
                texto_stock += f"Cantidad : {v.get('Quantity')}\n"
                texto_stock += f"WhatsApp : {v.get('Whatsapp')}\n"
                texto_stock += "-" * 20 + "\n"
            texto_stock += "```"
            estado_match = "✅ Oportunidad de venta detectada"
        else:
            color = 0x2ecc71 # Verde Esmeralda
            titulo = f"🛒 Nuevo Comprador Detectado: {servidor_rsps}"
            texto_stock = "```diff\n- No hay stock activo en la base de datos.\n```"
            estado_match = "❌ Sin vendedores disponibles"

        payload = {
            "embeds": [{
                "author": {
                    "name": f"Alerta de Mercado • {message.guild.name}",
                    "icon_url": "https://i.imgur.com/eOMD93t.png"
                },
                "title": titulo,
                "description": f"El usuario **{message.author.name}** está Comprando en el canal `#{message.channel.name}`.\n\n"
                               f"**Detalles de la Operación:**\n"
                               f"```yaml\n"
                               f"Acción   : {accion}\n"
                               f"Servidor: {servidor_rsps}\n"
                               f"Cantidad: {cantidad}\n"
                               f"```\n"
                               f"**🔍 Resultado del Auto-Matcher:**\n"
                               f"{estado_match}\n{texto_stock}",
                "color": color,
                "fields": [
                    {"name": "👤 Discord ID", "value": f"`{message.author.id}`", "inline": True},
                    {"name": "📞 Contacto", "value": f"{message.author.mention}", "inline": True},
                    {"name": "🌐 Enlace Directo", "value": f"[➡️ Ir al mensaje original]({message.jump_url})", "inline": False}
                ],
                "footer": {
                    "text": "⏳ Este mensaje se auto-eliminará en 1 hora por limpieza."
                },
                "thumbnail": {
                    "url": "https://i.imgur.com/eOMD93t.png"
                },
                "timestamp": message.created_at.isoformat()
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{webhook_url}?wait=true", json=payload) as response:
                if response.status in [200, 204]:
                    datos = await response.json()
                    id_msg = datos.get("id")
                    if id_msg: asyncio.create_task(self.borrar_mensaje_webhook(webhook_url, id_msg, 3600))

    async def enviar_webhook_publico(self, cantidad, servidor_rsps):
        webhook_publico = os.getenv('WEBHOOK_PUBLIC_URL')
        ticket_link = os.getenv('TICKET_CHANNEL_LINK')
        if not webhook_publico or not ticket_link: return

        mensaje_publico = (
            f"@everyone\n\n"
            f"📢 **COMPRANDO {servidor_rsps} YA** 📢\n"
            f"```yaml\n"
            f"Comprando: {cantidad.upper()} {servidor_rsps.upper()}\n"
            f"```\n"
            f"👉 **Abre tu ticket ya en:** {ticket_link}"
        )

        payload = {
            "content": mensaje_publico,
            "username": "BlessedGold Pedidos", 
            "avatar_url": "https://i.imgur.com/eOMD93t.png"
        }

        async with aiohttp.ClientSession() as session:
            await session.post(webhook_publico, json=payload)

    async def borrar_mensaje_webhook(self, webhook_url, id_mensaje, segundos):
        await asyncio.sleep(segundos)
        try:
            async with aiohttp.ClientSession() as session:
                await session.delete(f"{webhook_url}/messages/{id_mensaje}")
        except: pass

cliente_espia = SpyClient()
cliente_espia.run(os.getenv('USER_TOKEN'))
