from datetime import datetime, timezone
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import is_admin, parse_duration, load_warns, save_warns
from database import eco_col, pets_col
from config import STOCKS
from utils.stocks import stocks_col, user_stocks_col, stock_alerts_col, ipo_col
from utils.bounties import bounties_col


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ban", description="Banea a un miembro del servidor (solo Admin)")
    @app_commands.describe(member="El miembro a banear", reason="La razón del ban")
    @app_commands.default_permissions(administrator=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, reason: str = "Sin razón especificada"):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        try:
            await member.send(f"🔨 Has sido **baneado** de **{ctx.guild.name}**.\n**Razón:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🔨 **{member.name}** ha sido baneado permanentemente. Razón: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Error al banear al usuario: {e}", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Desbanea a un usuario por su ID de Discord (solo Admin)")
    @app_commands.describe(user_id="El ID único del usuario a desbanear")
    @app_commands.default_permissions(administrator=True)
    async def unban(self, ctx: commands.Context, user_id: str):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user)
            await ctx.send(f"✅ Se desbaneó exitosamente a **{user.name}** del servidor.")
        except Exception as e:
            await ctx.send(f"❌ Error al desbanear al usuario. Asegúrate de que el ID sea correcto: {e}", ephemeral=True)

    @commands.hybrid_command(name="kick", description="Expulsa a un miembro del servidor (solo Admin)")
    @app_commands.describe(member="El miembro a expulsar", reason="La razón de la expulsión")
    @app_commands.default_permissions(administrator=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = "Sin razón especificada"):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        try:
            await member.send(f"👢 Has sido **expulsado** de **{ctx.guild.name}**.\n**Razón:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 **{member.name}** ha sido expulsado del servidor. Razón: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Error al expulsar al usuario: {e}", ephemeral=True)

    @commands.hybrid_command(name="timeout", description="Silencia a un miembro temporalmente (solo Admin)")
    @app_commands.describe(member="El miembro", duration="Duración (ej. 10m, 2h, 1d)", reason="Razón del silencio")
    @app_commands.default_permissions(administrator=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, reason: str = "Sin razón especificada"):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        time_delta = parse_duration(duration)
        if not time_delta:
            return await ctx.send(
                "❌ ¡Formato de duración inválido! Usa formatos como `10m` (minutos), `2h` (horas) o `1d` (días).",
                ephemeral=True,
            )
        try:
            await member.send(f"🔇 Has sido **silenciado** en **{ctx.guild.name}** por `{duration}`.\n**Razón:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.timeout(time_delta, reason=reason)
            await ctx.send(f"🔇 **{member.name}** ha sido silenciado por `{duration}`. Razón: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Error al aplicar el silencio: {e}", ephemeral=True)

    @commands.hybrid_command(name="untimeout", description="Elimina el silencio de un miembro (solo Admin)")
    @app_commands.describe(member="El miembro al que quitar el silencio")
    @app_commands.default_permissions(administrator=True)
    async def untimeout(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        try:
            await member.timeout(None)
            await ctx.send(f"🔊 Silencio eliminado. **{member.name}** puede hablar de nuevo.")
        except Exception as e:
            await ctx.send(f"❌ Error al eliminar el silencio: {e}", ephemeral=True)

    @commands.hybrid_command(name="purge", description="Elimina una cantidad de mensajes del canal (solo Admin)")
    @app_commands.describe(amount="Cantidad de mensajes a eliminar")
    @app_commands.default_permissions(administrator=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("Por favor especifica un número mayor a 0.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        try:
            # Si es comando con prefijo, también hay que eliminar el mensaje del comando en sí
            limit = amount if ctx.interaction else amount + 1
            deleted = await ctx.channel.purge(limit=limit)
            
            # El conteo excluye el mensaje del comando si fue un comando con prefijo
            count = len(deleted) if ctx.interaction else len(deleted) - 1
            
            msg = await ctx.send(f"🧹 Se eliminaron **{count}** mensajes exitosamente.", ephemeral=True)
            
            # Auto-eliminar el mensaje de éxito para comandos con prefijo
            if not ctx.interaction:
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
        except Exception as e:
            await ctx.send(f"❌ Error al purgar mensajes: {e}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="Emite una advertencia a un miembro (solo Admin)")
    @app_commands.describe(member="El miembro a advertir", reason="La razón de la advertencia")
    @app_commands.default_permissions(administrator=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, reason: str):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        if user_id not in warns_data:
            warns_data[user_id] = []
        warn_id = str(len(warns_data[user_id]) + 1)
        new_warn = {
            "id": warn_id,
            "reason": reason,
            "moderator": ctx.author.name,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
        warns_data[user_id].append(new_warn)
        save_warns(warns_data)
        try:
            await member.send(
                f"⚠️ Recibiste una **advertencia** en **{ctx.guild.name}**.\n"
                f"**Razón:** {reason}\n*Ahora tienes {len(warns_data[user_id])} advertencias.*"
            )
        except discord.Forbidden:
            pass
        embed = discord.Embed(
            title="⚠️ Miembro Advertido",
            description=f"**Usuario:** {member.mention}\n**Razón:** {reason}\n**Total de Advertencias:** {len(warns_data[user_id])}",
            color=0xFFAA00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="warns", description="Consulta el historial de advertencias de un miembro (solo Admin)")
    @app_commands.describe(member="El miembro a consultar")
    @app_commands.default_permissions(administrator=True)
    async def check_warns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        if not user_warns:
            return await ctx.send(f"✅ **{member.name}** tiene un historial limpio (0 advertencias).")
        embed = discord.Embed(title=f"⚠️ Registro de Advertencias: {member.name}", color=0xFFAA00)
        for w in user_warns:
            embed.add_field(
                name=f"ID: {w['id']} | {w['date']}",
                value=f"**Razón:** {w['reason']}\n**Staff:** {w['moderator']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="delwarn", description="Elimina una advertencia específica de un miembro (solo Admin)")
    @app_commands.describe(member="El miembro", warn_id="El ID de la advertencia a eliminar")
    @app_commands.default_permissions(administrator=True)
    async def delwarn(self, ctx: commands.Context, member: discord.Member, warn_id: str):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        updated_warns = [w for w in user_warns if w["id"] != warn_id]
        if len(updated_warns) == len(user_warns):
            return await ctx.send("❌ ID de advertencia no encontrado para este usuario.", ephemeral=True)
        for idx, w in enumerate(updated_warns):
            w["id"] = str(idx + 1)
        warns_data[user_id] = updated_warns
        save_warns(warns_data)
        await ctx.send(f"✅ Se eliminó exitosamente la advertencia ID `{warn_id}` de **{member.name}**.")

    @commands.hybrid_command(name="clearwarns", description="Borra todas las advertencias de un miembro (solo Admin)")
    @app_commands.describe(member="El miembro a limpiar")
    @app_commands.default_permissions(administrator=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        if user_id in warns_data:
            del warns_data[user_id]
            save_warns(warns_data)
        await ctx.send(f"✅ Se borraron todas las advertencias de **{member.name}**.")

    @commands.hybrid_command(name="say", description="Hace que el bot diga algo (solo Owner)")
    @app_commands.describe(message="El mensaje que quieres que repita el bot")
    async def say(self, ctx: commands.Context, *, message: str):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(message)
        else:
            await ctx.send("¡Mensaje enviado!", ephemeral=True)
            await ctx.channel.send(message)

    @commands.hybrid_command(name="sayembed", description="Envía un mensaje embed personalizado (solo Owner)")
    @app_commands.describe(
        title="Título del embed",
        description="El texto principal del embed",
        color="Código de color hexadecimal (ej. 2b2d31 o ff0000)",
    )
    async def sayembed(self, ctx: commands.Context, title: str, description: str, color: str = "2b2d31"):
        if not is_admin(ctx):
            return await ctx.send("Comando solo para admins.", ephemeral=True)
        try:
            color_int = int(color.lstrip("#"), 16)
        except ValueError:
            color_int = 0x2B2D31
        embed = discord.Embed(title=title, description=description, color=color_int)
        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(embed=embed)
        else:
            await ctx.send("¡Embed enviado!", ephemeral=True)
            await ctx.channel.send(embed=embed)

    @commands.hybrid_command(name="add", description="Agrega monedas a un usuario (solo Admin)")
    @app_commands.describe(member="El miembro al que darle monedas", amount="Cantidad de monedas a agregar")
    @app_commands.default_permissions(administrator=True)
    async def add(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not is_admin(ctx):
            return await ctx.send("❌ Comando solo para admins.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        from utils.economy import update_wallet, get_wallet
        update_wallet(str(member.id), amount)
        wallet = get_wallet(str(member.id))
        embed = discord.Embed(
            title="💰 Monedas Agregadas",
            description=f"Se agregaron 🪙 **{amount:,}** a {member.mention}\n\nNuevo Saldo en Cartera: 🪙 **{wallet:,}**",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="remove", description="Quita monedas de la cartera de un usuario (solo Admin)")
    @app_commands.describe(member="El miembro al que quitarle monedas", amount="Cantidad de monedas a quitar")
    @app_commands.default_permissions(administrator=True)
    async def remove(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not is_admin(ctx):
            return await ctx.send("❌ Comando solo para admins.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        from utils.economy import update_wallet, get_wallet
        current = get_wallet(str(member.id))
        deduct = min(amount, current)
        update_wallet(str(member.id), -deduct)
        wallet = get_wallet(str(member.id))
        embed = discord.Embed(
            title="💸 Monedas Eliminadas",
            description=f"Se quitaron 🪙 **{deduct:,}** de {member.mention}\n\nNuevo Saldo en Cartera: 🪙 **{wallet:,}**",
            color=0xFF4444,
        )
        if deduct < amount:
            embed.set_footer(text=f"Nota: el usuario solo tenía {current:,} monedas — se le quitaron todas.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="reset_economy", description="REINICIA TODO: monedas, mascotas, ítems y roles (solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def reset_economy(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Comando solo para admins.", ephemeral=True)

        await ctx.defer()

        # 1. Limpiar monedas, inventario y todos los cooldowns en eco_col para todos los usuarios
        eco_col.update_many(
            {},
            {
                "$set": {"wallet": 0, "bank": 0, "inventory": []},
                "$unset": {
                    "last_daily": "",
                    "last_weekly": "",
                    "last_claim": "",
                    "last_work": "",
                    "last_crime": "",
                    "last_rob": "",
                    "last_adventure": "",
                    "balance": ""
                }
            }
        )

        # 2. Limpiar mascotas en pets_col para todos los usuarios
        pets_col.update_many({}, {"$set": {"pets": []}})

        # 3. Limpiar todos los datos relacionados con acciones
        user_stocks_col.delete_many({})   # portafolios de usuarios
        stocks_col.delete_many({})        # historial de precios y gráficos
        stock_alerts_col.delete_many({})  # alertas de precios
        ipo_col.delete_many({})           # empresas de IPO persistidas

        # También eliminar acciones de IPO del diccionario STOCKS en vivo
        # (las acciones base definidas en config.py se conservan al reiniciar)
        from config import STOCKS as _base_stocks_check
        base_symbols = set(_base_stocks_check.keys())
        for sym in list(STOCKS.keys()):
            if sym not in base_symbols:
                STOCKS.pop(sym, None)

        # 4. Limpiar recompensas
        bounties_col.delete_many({})

        embed = discord.Embed(
            title="🧨 Reinicio de Economía Completo",
            description=(
                "¡La economía ha sido reiniciada completamente!\n\n"
                "✅ Todas las carteras y bancos establecidos en 🪙 0\n"
                "✅ Todos los inventarios y cooldowns limpiados\n"
                "✅ Todas las mascotas eliminadas\n"
                "✅ Todos los portafolios de acciones borrados\n"
                "✅ Todo el historial de precios de acciones limpiado\n"
                "✅ Todas las alertas de precios eliminadas\n"
                "✅ Todas las empresas de IPO deslistadas\n"
                "✅ Todas las recompensas borradas"
            ),
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
