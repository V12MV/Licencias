import os
import discord
import re
import aiohttp
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive # <--- INYECTADO AQUÍ

load_dotenv()

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

        print(f'[ESPIA] Iniciando MODO PRODUCCIÓN (CON AUTO-MATCHER).')
        
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

        texto_limpio = message.content.lower().replace('*', '').replace('+', '').strip()
        
        patron_normal = r'(buy|buying)\s+(\d+[kmb]?)\s+(\w+)'
        patron_invertido = r'(buy|buying)\s+(\w+)\s+(\d+[kmb]?)'
        
        match_normal = re.search(patron_normal, texto_limpio, re.IGNORECASE)
        match_invertido = re.search(patron_invertido, texto_limpio, re.IGNORECASE)

        if match_normal:
            accion = "Buy"
            cantidad = match_normal.group(2).upper()
            servidor_rsps = match_normal.group(3).capitalize()
        elif match_invertido:
            accion = "Buy"
            servidor_rsps = match_invertido.group(2).capitalize()
            cantidad = match_invertido.group(3).upper()
        else:
            return 
            
        print(f"\n🔔 [NUEVA DEMANDA] {cantidad} de {servidor_rsps} | De: {message.guild.name}")
        
        stock_disponible = await self.consultar_baserow(servidor_rsps)
        
        await self.enviar_webhook_privado(accion, cantidad, servidor_rsps, message, stock_disponible)
        await self.enviar_webhook_publico(cantidad, servidor_rsps)

    async def consultar_baserow(self, servidor_buscado):
        url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
        headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}
        
        vendedores_match = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    filas = data.get('results', [])
                    
                    for fila in filas:
                        status = fila.get('Status', {})
                        status_val = status.get('value') if isinstance(status, dict) else status
                        
                        if status_val == 'Activo' and fila.get('RSPS', '').lower() == servidor_buscado.lower():
                            vendedores_match.append(fila)
        return vendedores_match

    async def enviar_webhook_privado(self, accion, cantidad, servidor_rsps, message, stock_disponible):
        webhook_url = os.getenv('WEBHOOK_URL')
        if not webhook_url: return

        # Diseño Premium: Colores y Títulos
        if stock_disponible:
            color = 0xf1c40f # Dorado
            titulo = f"🎉 ¡MATCH ENCONTRADO! Demanda de {servidor_rsps}"
            
            # Formateo como bloque de código para los vendedores
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

        # Embed Principal Profesional
        payload = {
            "embeds": [{
                "author": {
                    "name": f"Alerta de Mercado • {message.guild.name}",
                    "icon_url": "https://i.imgur.com/eOMD93t.png" # Tu logo aquí
                },
                "title": titulo,
                "description": f"El usuario **{message.author.name}** está Comprando comprar en el canal `#{message.channel.name}`.\n\n"
                               f"**Detalles de la Operación:**\n"
                               f"```yaml\n"
                               f"Acción  : {accion}\n"
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
                    "url": "https://i.imgur.com/eOMD93t.png" # Tu logo también como miniatura
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

        # Anuncio público estilizado
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
            "avatar_url": "https://i.imgur.com/eOMD93t.png" # Tu logo en el publicador
        }

        async with aiohttp.ClientSession() as session:
            await session.post(webhook_publico, json=payload)
            print("   -> 📢 Anuncio público publicado en tu servidor.")

    async def borrar_mensaje_webhook(self, webhook_url, id_mensaje, segundos):
        await asyncio.sleep(segundos)
        async with aiohttp.ClientSession() as session:
            await session.delete(f"{webhook_url}/messages/{id_mensaje}")

cliente_espia = SpyClient()

# Encendemos el servidor web miniatura para Render
keep_alive()

cliente_espia.run(os.getenv('USER_TOKEN'), log_handler=None)
