import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive # <--- INYECTADO AQUÍ

load_dotenv()

class BotOficial(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()
        print(f"[BOT] Comandos Slash sincronizados.")

bot = BotOficial()

# ==========================================
# LÓGICA DE BASEROW 
# ==========================================
async def guardar_en_baserow(ticket_id, discord_name, whatsapp, rsps, cantidad):
    url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
    headers = {
        "Authorization": f"Token {os.getenv('BASEROW_TOKEN')}",
        "Content-Type": "application/json"
    }
    data = {
        "TicketID": str(ticket_id),
        "DiscordName": str(discord_name),
        "Whatsapp": str(whatsapp),
        "RSPS": str(rsps).lower(),
        "Quantity": str(cantidad),
        "Status": "Activo"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            return response.status == 200

# ==========================================
# EL FORMULARIO (MODAL)
# ==========================================
class VentaModal(discord.ui.Modal, title='Formulario de Venta RSPS'):
    whatsapp = discord.ui.TextInput(label='Número de WhatsApp Vigente', placeholder='+58 412 1234567', max_length=20)
    rsps = discord.ui.TextInput(label='¿Qué RSPS vendes?', placeholder='Ej: Roatpkz, Alora, Impact...', max_length=50)
    cantidad = discord.ui.TextInput(label='Cantidad que vendes', placeholder='Ej: 10m, 2b, 500k', max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        categoria_tickets = discord.utils.get(guild.categories, name="TICKETS") 
        
        if not categoria_tickets:
            categoria_tickets = await guild.create_category("TICKETS")

        # Permisos del canal (Solo lo ve el usuario y los admins)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
        }
        
        nombre_canal = f"venta-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(nombre_canal, category=categoria_tickets, overwrites=overwrites)

        # Guardamos en Baserow pasando el ID del canal (ticket_channel.id)
        exito_db = await guardar_en_baserow(
            ticket_id=ticket_channel.id,
            discord_name=interaction.user.name,
            whatsapp=self.whatsapp.value,
            rsps=self.rsps.value,
            cantidad=self.cantidad.value
        )

        # Mensaje de bienvenida DENTRO del ticket
        embed_ticket = discord.Embed(
            title="Ticket de Venta Creado 🛒", 
            description=f"Hola {interaction.user.mention}, un administrador te atenderá pronto.\nPara cerrar este ticket y borrar el stock, usa el comando `/cerrar`.",
            color=0x2ecc71
        )
        embed_ticket.add_field(name="📱 WhatsApp", value=f"`{self.whatsapp.value}`", inline=True)
        embed_ticket.add_field(name="🎮 RSPS", value=f"`{self.rsps.value}`", inline=True)
        embed_ticket.add_field(name="⚖️ Cantidad", value=f"`{self.cantidad.value}`", inline=True)
        
        await ticket_channel.send(f"{interaction.user.mention}", embed=embed_ticket)
        
        if exito_db:
            await interaction.followup.send(f"✅ ¡Tu ticket ha sido creado! Ve a {ticket_channel.mention}", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Ticket creado en {ticket_channel.mention}, pero hubo un error guardando en BD.", ephemeral=True)

# ==========================================
# LOS BOTONES DEL PANEL PRINCIPAL
# ==========================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    # Botón Rojo (Abre el Modal)
    @discord.ui.button(label="Vender RSPS", style=discord.ButtonStyle.danger, custom_id="btn_vender", emoji="🎟️")
    async def btn_vender_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VentaModal())

    # Botón Azul (Quejas)
    @discord.ui.button(label="Quejas Del Personal", style=discord.ButtonStyle.blurple, custom_id="btn_quejas", emoji="⚙️")
    async def btn_quejas_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Si tienes algún problema, envíale un mensaje directo a un Administrador.", ephemeral=True)

# ==========================================
# COMANDOS SLASH
# ==========================================
@bot.tree.command(name="panel", description="Genera el panel profesional de tickets")
@app_commands.checks.has_permissions(administrator=True) 
async def panel_command(interaction: discord.Interaction):
    
    descripcion = (
        "Hola Bienvenido a **BlessedGold** 💸\n\n"
        "Por favor, si eres tan amable deja los siguientes datos al abrir tu ticket:\n\n"
        "✅ **Qué Servidor vendes**\n"
        "✅ **Qué Cantidad vendes**\n"
        "✅ **Número de WhatsApp vigente**\n\n"
        "**Los precios de los RSPS están acá:**\n"
        "👉 <#1261850103967121480> \n\n" 
        "**Nuestras Redes:**\n"
        "📱 **Grupo de WhatsApp:** [Haz clic aquí](https://chat.whatsapp.com/FMGPgKU0DYwBPKl428VloZ?mode=gi_t )\n"
        "**Agentes Autorizados para atender Ventas:**\n"
        "👑 <@&1426600389733781579>\n" 
        "💎 <@&1426623451250032851>"  
    )

    embed = discord.Embed(title="Sala De Tickets", description=descripcion, color=0x2b2d31)
    
    embed.set_thumbnail(url="https://i.imgur.com/SCDBVvg.png") 
    embed.set_footer(text="BlessedGold • Sistema Automatizado", icon_url="https://i.imgur.com/SCDBVvg.png")
    
    view = PanelView()
    await interaction.response.send_message("Panel generado:", ephemeral=True) 
    await interaction.channel.send(embed=embed, view=view) 

@bot.tree.command(name="cerrar", description="Cierra el ticket y elimina el stock de la base de datos")
async def cerrar_command(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("venta-"):
        await interaction.response.send_message("❌ Este comando solo funciona dentro de un canal de ticket.", ephemeral=True)
        return

    await interaction.response.send_message("🔒 **Cerrando ticket...**", ephemeral=False)

    url_get = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
    headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url_get, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                filas = data.get('results', [])
                
                row_id_a_borrar = None
                for fila in filas:
                    if fila.get('TicketID') == str(interaction.channel.id):
                        row_id_a_borrar = fila.get('id')
                        break
                
                if row_id_a_borrar:
                    url_delete = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/{row_id_a_borrar}/"
                    await session.delete(url_delete, headers=headers)
                    print(f"[BASEROW] Stock eliminado correctamente (Row ID: {row_id_a_borrar})")

    await asyncio.sleep(3)
    await interaction.channel.delete(reason="Ticket cerrado y stock limpiado.")

@bot.tree.command(name="stock", description="Consulta el stock actual de vendedores")
async def stock_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    
    url = f"https://api.baserow.io/api/database/rows/table/{os.getenv('BASEROW_TABLE_ID')}/?user_field_names=true"
    headers = {"Authorization": f"Token {os.getenv('BASEROW_TOKEN')}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                filas = data.get('results', [])
                
                activos = [f for f in filas if f.get('Status', {}).get('value') == 'Activo' or f.get('Status') == 'Activo']
                
                if not activos:
                    await interaction.followup.send("❌ No hay stock registrado actualmente.")
                    return
                
                mensaje = "**📦 STOCK ACTUAL REGISTRADO:**\n\n"
                for idx, fila in enumerate(activos, 1):
                    mensaje += f"`{idx}.` **{fila.get('RSPS', 'N/A').capitalize()}**: {fila.get('Quantity', '0')} | Vendedor: {fila.get('DiscordName', 'Desconocido')} | 📱 {fila.get('Whatsapp', '')}\n"
                
                await interaction.followup.send(mensaje)
            else:
                await interaction.followup.send(f"Error consultando la base de datos (Código: {response.status}).")

# ==========================================
# INICIO DEL BOT
# ==========================================
@bot.event
async def on_ready():
    print(f'[BOT OFICIAL] 🟢 Conectado exitosamente como {bot.user}')
    print(f'[BOT OFICIAL] Listo para recibir tickets y comandos Slash.')

# Encendemos el servidor web miniatura para Render
keep_alive()

bot.run(os.getenv('BOT_TOKEN'))
