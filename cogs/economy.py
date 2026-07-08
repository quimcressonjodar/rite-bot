import random
import time
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import state
from config import ROLE_SHOP
from database import eco_col
from utils.economy import (
    get_user_data,
    get_wallet,
    get_bank,
    update_wallet,
    update_bank,
    parse_economy_amount,
    get_debt,
    update_loan,
    update_interest,
    apply_amortization,
)
from views.economy_views import SellView


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Consulta tu perfil de economía")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        wallet = get_wallet(str(target.id))
        bank = get_bank(str(target.id))
        total = wallet + bank
        embed = discord.Embed(title=f"💳 Economía de {target.display_name}", color=0x2B2D31)
        embed.add_field(name="💵 Billetera", value=f"🪙 {wallet:,}", inline=True)
        from utils.economy import get_prestige_level
        from config import PRESTIGE_LEVELS
        level = get_prestige_level(total)
        p_name = PRESTIGE_LEVELS[level]["name"] if level > 0 else "Ninguno"

        embed.add_field(name="🏦 Banco", value=f"🪙 {bank:,}", inline=True)
        embed.add_field(name="📈 Patrimonio Total", value=f"🪙 {total:,}", inline=False)
        embed.add_field(name="🏆 Prestigio", value=f"**{p_name}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deposit", aliases=["dep"], description="Deposita monedas en tu banco")
    @app_commands.describe(amount="La cantidad a depositar ('all', 'half' o un número)")
    async def deposit(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        parsed_amount = parse_economy_amount(amount, wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Cantidad inválida. Por favor especifica un número positivo, 'all' o 'half'.", ephemeral=True)
        if parsed_amount > wallet:
            return await ctx.send(f"❌ No tienes suficientes monedas. Solo tienes 🪙 {wallet:,}.", ephemeral=True)
        update_wallet(user_id, -parsed_amount)
        update_bank(user_id, parsed_amount)
        embed = discord.Embed(
            title="🏦 Depósito Exitoso",
            description=f"Depositaste 🪙 {parsed_amount:,} monedas en tu banco.",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="withdraw", aliases=["with"], description="Retira monedas de tu banco")
    @app_commands.describe(amount="La cantidad a retirar ('all', 'half' o un número)")
    async def withdraw(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        bank = get_bank(user_id)
        parsed_amount = parse_economy_amount(amount, bank)
        if parsed_amount <= 0:
            return await ctx.send("❌ Cantidad inválida. Por favor especifica un número positivo, 'all' o 'half'.", ephemeral=True)
        if parsed_amount > bank:
            return await ctx.send(f"❌ No tienes suficientes monedas en el banco. Solo tienes 🪙 {bank:,} en el banco.", ephemeral=True)
        update_bank(user_id, -parsed_amount)
        update_wallet(user_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Retiro Exitoso",
            description=f"Retiraste 🪙 {parsed_amount:,} monedas de tu banco.",
            color=0x3498DB,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Reclama tus monedas diarias gratuitas")
    async def daily(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        last_daily = user_data.get("last_daily")
        already_claimed = False

        if isinstance(last_daily, str):
            already_claimed = last_daily == today_str
        elif isinstance(last_daily, (int, float)):
            last_date = datetime.fromtimestamp(last_daily, tz=timezone.utc)
            already_claimed = last_date.strftime("%Y-%m-%d") == today_str
        elif hasattr(last_daily, "strftime"):
            already_claimed = last_daily.strftime("%Y-%m-%d") == today_str

        if already_claimed:
            next_midnight = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
            return await ctx.send(
                f"❌ ¡Ya reclamaste tu recompensa diaria! Espera hasta <t:{int(next_midnight.timestamp())}:R>.",
                ephemeral=True,
            )

        base_amount = 1000
        amount = apply_amortization(user_id, base_amount)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_daily": today_str}},
            upsert=True,
        )
        
        # Seguimiento de misiones
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "DAILY_CLAIMER", 1)
        
        msg = f"📆 ¡Reclamaste tu recompensa diaria de 🪙 {base_amount:,} monedas!"
        if amount < base_amount:
            msg += f"\n📉 🪙 {base_amount - amount:,} monedas fueron usadas automáticamente para pagar tu deuda."
        await ctx.send(msg)

    @commands.hybrid_command(name="weekly", description="Reclama tu enorme recompensa semanal")
    async def weekly(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        week_str = f"{now.year}-W{now.isocalendar()[1]}"
        last_weekly = user_data.get("last_weekly")
        already_claimed = False

        if isinstance(last_weekly, str):
            already_claimed = last_weekly == week_str
        elif isinstance(last_weekly, (int, float)):
            last_date = datetime.fromtimestamp(last_weekly, tz=timezone.utc)
            saved_week = f"{last_date.year}-W{last_date.isocalendar()[1]}"
            already_claimed = saved_week == week_str
        elif hasattr(last_weekly, "isocalendar"):
            saved_week = f"{last_weekly.year}-W{last_weekly.isocalendar()[1]}"
            already_claimed = saved_week == week_str

        if already_claimed:
            days_until_next_monday = 7 - now.weekday()
            next_monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=days_until_next_monday)
            return await ctx.send(
                f"❌ ¡Ya reclamaste tu recompensa semanal! Espera hasta <t:{int(next_monday.timestamp())}:R>.",
                ephemeral=True,
            )

        base_amount = 25000
        amount = apply_amortization(user_id, base_amount)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_weekly": week_str}},
            upsert=True,
        )
        
        # Seguimiento de misiones
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "DAILY_CLAIMER", 1)
        
        msg = f"✨ ¡Reclamaste tu recompensa semanal de 🪙 {base_amount:,} monedas!"
        if amount < base_amount:
            msg += f"\n📉 🪙 {base_amount - amount:,} monedas usadas para pagar la deuda."
        await ctx.send(msg)

    @commands.hybrid_command(name="claim", description="Reclama recompensas de tus roles")
    async def claim(self, ctx: commands.Context):
        await ctx.defer()
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        last_claim = user_data.get("last_claim")

        if last_claim:
            if isinstance(last_claim, str):
                last_claim = datetime.fromisoformat(last_claim)
            elapsed = (now - last_claim).total_seconds()
            if elapsed < 3600:
                remaining = int(3600 - elapsed)
                next_claim_ts = int((now + timedelta(seconds=remaining)).timestamp())
                return await ctx.send(
                    f"❌ Ya reclamaste tus recompensas. Vuelve <t:{next_claim_ts}:R>.",
                    ephemeral=True,
                )

        total = 0
        breakdown = []
        for key, data in ROLE_SHOP.items():
            role_id = data.get("role_id")
            if not role_id:
                continue
            role = ctx.guild.get_role(int(role_id))
            if role and role in ctx.author.roles:
                reward = data["claim"]
                total += reward
                breakdown.append(f"✨ **{role.name}** → 🪙 {reward:,}")

        if total == 0:
            return await ctx.send("❌ No tienes ningún rol de recompensa.")

        actual_total = apply_amortization(user_id, total)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": actual_total}, "$set": {"last_claim": now.isoformat()}},
            upsert=True,
        )
        next_claim_ts = int(now.timestamp() + 3600)
        
        desc = "\n".join(breakdown)
        if actual_total < total:
            desc += f"\n\n📉 🪙 {total - actual_total:,} monedas usadas para pagar la deuda."
        desc += f"\n\nVuelve <t:{next_claim_ts}:R> para más recompensas."
        
        embed = discord.Embed(
            title="💰 Recompensas Reclamadas", 
            description=desc, 
            color=0x00FF99
        )
        embed.add_field(name="Total Recibido", value=f"🪙 {actual_total:,}", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pay", description="Envía monedas a otro miembro")
    @app_commands.describe(member="El miembro al que enviar monedas", amount="Cantidad ('all', 'half' o número)")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: str):
        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)
        if member.bot:
            return await ctx.send("❌ No puedes enviar monedas a bots.", ephemeral=True)
        if sender_id == receiver_id:
            return await ctx.send("❌ No puedes pagarte a ti mismo.", ephemeral=True)
        sender_wallet = get_wallet(sender_id)
        parsed_amount = parse_economy_amount(amount, sender_wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Cantidad inválida. Por favor usa un número positivo, 'all' o 'half'.", ephemeral=True)
        if sender_wallet < parsed_amount:
            return await ctx.send(f"❌ Solo tienes 🪙 {sender_wallet:,} en tu billetera.", ephemeral=True)
        update_wallet(sender_id, -parsed_amount)
        update_wallet(receiver_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Pago Enviado",
            description=f"{ctx.author.mention} envió 🪙 **{parsed_amount:,}** monedas a {member.mention}.",
            color=0x00FF99,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Muestra los miembros más ricos")
    async def leaderboard(self, ctx: commands.Context):
        users = sorted(
            eco_col.find(),
            key=lambda u: u.get("wallet", 0) + u.get("bank", 0),
            reverse=True,
        )[:10]

        embed = discord.Embed(title="🏆 Clasificación Global de Economía", color=0xFFD700)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        description = ""
        for index, user_data in enumerate(users, start=1):
            user_id = int(user_data["_id"])
            total = user_data.get("wallet", 0) + user_data.get("bank", 0)
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Usuario Desconocido ({user_id})"
            medal = medals.get(index, f"`#{index}`")
            description += f"{medal} **{name}** — 🪙 {total:,}\n"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="work", description="Trabaja para ganar monedas")
    async def work(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        cooldown = 2700
        last_work = user_data.get("last_work", 0)
        now = time.time()
        if now - last_work < cooldown:
            next_work_ts = int(last_work + cooldown)
            return await ctx.send(f"⏳ ¡Estás demasiado cansado! Vuelve a trabajar <t:{next_work_ts}:R>.", ephemeral=True)

        base_earnings = random.randint(250, 800)
        earnings = apply_amortization(user_id, base_earnings)
        
        jobs = [
            "desarrollaste un bot de Discord futurista para un multimillonario", "ganaste un torneo de póker de madrugada",
            "reparaste un dron militar para una agencia secreta", "hackeaste una bóveda de cripto abandonada",
            "trabajaste horas extra en un club nocturno cyberpunk", "entregaste tacos espaciales ilegales por toda la galaxia",
            "transmitiste videojuegos durante 14 horas seguidas", "vendiste huevos de dragón raros en el mercado negro",
            "trabajaste como guardaespaldas de un jefe de la mafia", "encontraste un tesoro antiguo oculto bajo tierra",
            "completaste peligrosas misiones de cazarrecompensas", "administraste un casino clandestino",
            "trabajaste en un laboratorio de IA futurista", "ayudaste a un millonario a recuperar su cripto perdido",
            "participaste en carreras callejeras ilegales", "vendiste armas encantadas a mercaderes viajeros",
            "trabajaste como mercenario durante guerras de clanes", "creaste memes virales que explotaron en internet",
            "encontraste dinero escondido detrás de una máquina expendedora", "trabajaste de noche en un hotel embrujado",
            "hackeaste el mainframe de una megacorp rival", "pasaste de contrabando artefactos alienígenas raros por la aduana",
            "ganaste un torneo de carreras subterráneo de alto riesgo", "domaste un cyber-dragón salvaje para un excéntrico adinerado",
            "reparaste el hiperpropulsor de un crucero espacial varado", "desactivaste una bomba a punto de explotar en la plaza de la ciudad",
            "ganaste una legendaria batalla de rap contra una IA",
        ]
        reason = random.choice(jobs)
        next_work_ts = int(now + cooldown)
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_work": now}}, upsert=True)
        
        # Seguimiento de misiones
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "WORKER", 1)
        
        desc = f"Has {reason} y ganaste 🪙 **{earnings:,}** monedas."
        if earnings < base_earnings:
            desc += f"\n📉 🪙 {base_earnings - earnings:,} monedas fueron usadas automáticamente para pagar tu deuda."
        desc += f"\n\nVuelve <t:{next_work_ts}:R> para otro turno."
        
        embed = discord.Embed(
            title="💼 Trabajo Completado",
            description=desc,
            color=0x00FF99,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="crime", description="¡Comete un crimen por mucho dinero, pero arriesgate a que te atrapen!")
    async def crime(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        wallet = user_data.get("wallet", 0)
        cooldown = 7200
        last_crime = user_data.get("last_crime", 0)
        now = time.time()
        if now - last_crime < cooldown:
            next_crime_ts = int(last_crime + cooldown)
            return await ctx.send(
                f"⏳ ¡El ambiente está muy caliente! Mantén un perfil bajo <t:{next_crime_ts}:R> antes de cometer otro crimen.",
                ephemeral=True,
            )
        if wallet < 1000:
            return await ctx.send("❌ Necesitas al menos 🪙 1,000 en tu billetera para cometer un crimen (por si acaso hay que sobornar a los policías).", ephemeral=True)

        success = random.choice([True, False])
        if success:
            base_earnings = random.randint(2000, 6500)
            earnings = apply_amortization(user_id, base_earnings)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "robaste un casino clandestino", "hackeaste la cuenta bancaria de un multimillonario",
                "robaste un auto deportivo cibernético", "pasaste de contrabando artefactos alienígenas raros",
                "vendiste skins falsas de Protox en el mercado negro",
            ])
            
            desc = f"Has {msg} y te escapaste con 🪙 **{base_earnings:,}** monedas!"
            if earnings < base_earnings:
                desc += f"\n📉 🪙 {base_earnings - earnings:,} monedas usadas para pagar la deuda."
            eco_col.update_one({"_id": user_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            desc += "\n\n🚨 **¡Ahora estás BUSCADO** durante 45 minutos. ¡Cuida tu espalda!"

            # Seguimiento de misiones
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, user_id, "GAMBLER", base_earnings)

            embed = discord.Embed(title="🦹 Crimen Exitoso", description=desc, color=0x2ECC71)
        else:
            fine = random.randint(1000, min(3500, wallet))
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": -fine}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "tropezaste con un cubo de basura huyendo de la policía", "dejaste tu identificación en la escena del crimen",
                "intentaste hackear un servidor del gobierno pero olvidaste activar tu VPN",
                "te atrapó un perro guardián cibernético", "tu conductor de huida te traicionó",
            ])
            eco_col.update_one({"_id": user_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            embed = discord.Embed(title="🚔 ¡ATRAPADO!", description=f"Has {msg}.\n\nTe multaron con 🪙 **{fine:,}** monedas.\n\n🚨 **¡Ahora estás BUSCADO** durante 45 minutos!", color=0xE74C3C)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rob", description="Intenta robarle a otro miembro")
    async def rob(self, ctx: commands.Context, member: discord.Member):
        thief_id = str(ctx.author.id)
        target_id = str(member.id)
        user_data = get_user_data(thief_id)
        target_data = get_user_data(target_id)
        cooldown = 3600
        last_rob = user_data.get("last_rob", 0)
        now = time.time()
        if now - last_rob < cooldown:
            next_rob_ts = int(last_rob + cooldown)
            return await ctx.send(f"⏳ ¡La policía todavía te está buscando! Mantén un perfil bajo <t:{next_rob_ts}:R>.", ephemeral=True)
        if thief_id == target_id:
            return await ctx.send("❌ No puedes robarte a ti mismo.", ephemeral=True)
        if target_data.get("wallet", 0) < 300:
            return await ctx.send("❌ Este usuario no tiene suficientes monedas en su billetera para robar.", ephemeral=True)

        success = random.choice([True, False])
        if success:
            base_stolen = random.randint(150, int(target_data.get("wallet", 0) * 0.30))
            stolen = apply_amortization(thief_id, base_stolen)
            eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": stolen}, "$set": {"last_rob": now}}, upsert=True)
            eco_col.update_one({"_id": target_id}, {"$inc": {"wallet": -base_stolen}}, upsert=True)
            msg = random.choice([
                "saltaste por una ventana como ladrón de película", "le hiciste el bolsillo en un concierto abarrotado",
                "usaste credenciales de seguridad falsas para acceder a su bóveda", "escapaste por los tejados tras el robo",
                "ejecutaste la misión sigilosa perfecta", "usaste granadas de humo y escapaste sin ser visto",
                "hackeaste su billetera cripto de forma remota", "sobornaste a los guardias y saliste por la puerta principal",
                "usaste un teletransportador para arrebatar su billetera", "los distrajiste con un holograma y agarraste el efectivo",
                "te disfrazaste de repartidor de pizzas y saqueaste el lugar",
            ])
            
            desc = f"Has {msg}.\n\nRobaste 🪙 **{base_stolen:,}** a {member.mention}."
            if stolen < base_stolen:
                desc += f"\n📉 🪙 {base_stolen - stolen:,} monedas usadas para pagar la deuda."
            eco_col.update_one({"_id": thief_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            desc += "\n\n🚨 **¡Ahora estás BUSCADO** durante 45 minutos. ¡Cuida tu espalda!"

            # Seguimiento de misiones
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, thief_id, "ROBBER", 1)
            await track_bounty_progress(self.bot, thief_id, "GAMBLER", base_stolen)

            embed = discord.Embed(title="🥷 Robo Exitoso", description=desc, color=0x00FF00)
        else:
            fine = random.randint(150, 500)
            eco_col.update_one(
                {"_id": thief_id},
                {"$inc": {"wallet": -fine}, "$set": {"last_rob": now, "wanted_until": int(now + 2700)}},
                upsert=True,
            )
            msg = random.choice([
                "activaste la alarma", "te atraparon las cámaras de seguridad",
                "robaste accidentalmente a un policía", "dejaste huellas por todos lados",
                "activaste las defensas láser", "tu conductor de huida te traicionó",
                "te derribaron los guardaespaldas", "te engañó una caja fuerte señuelo",
                "te persiguió un perro guardián cibernético", "tiraste el botín intentando escapar sobre una valla",
                "estornudaste fuerte mientras estabas escondido en el armario",
            ])
            embed = discord.Embed(
                title="🚨 Robo Fallido",
                description=(
                    f"Has {msg}.\n\n"
                    f"Pagaste una multa de 🪙 **{fine:,}**.\n\n"
                    "🚨 **¡Ahora estás BUSCADO** durante 45 minutos. ¡Cuida tu espalda!"
                ),
                color=0xFF0000,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="catch", description="Atrapa a un criminal buscado y reclama una recompensa")
    @commands.cooldown(1, 900, commands.BucketType.user)
    @app_commands.describe(member="El criminal buscado a atrapar")
    async def catch(self, ctx: commands.Context, member: discord.Member):
        catcher_id = str(ctx.author.id)
        target_id = str(member.id)

        if catcher_id == target_id:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ ¡No puedes atraparte a ti mismo!", ephemeral=True)

        target_data = get_user_data(target_id)
        now = time.time()
        wanted_until = target_data.get("wanted_until", 0)

        if wanted_until < now:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ **{member.display_name}** no está buscado en este momento.", ephemeral=True)

        # 50% de probabilidad de que el criminal escape
        if random.random() < 0.50:
            escape_msg = random.choice([
                "desapareció entre la multitud antes de que pudieras reaccionar",
                "sobornó a un transeúnte para bloquearte el paso",
                "saltó a una moto de huida y desapareció",
                "se metió por un callejón y te dio esquinazo",
                "lanzó una bomba de humo y salió corriendo",
                "se disfrazó en el último segundo",
                "te vio venir y se escapó antes de que te acercaras",
            ])
            embed = discord.Embed(
                title="💨 ¡Se escaparon!",
                description=(
                    f"**{member.display_name}** {escape_msg}.\n\n"
                    "Mejor suerte la próxima vez — ¡siguen BUSCADOS! 🚨"
                ),
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        # Éxito — limpiar estado de buscado, encarcelar al criminal, recompensar al cazador
        from utils.economy import set_jail
        from utils.bounties import track_bounty_progress

        reward = random.randint(500, 2000)
        release_ts = set_jail(target_id)
        eco_col.update_one({"_id": target_id}, {"$set": {"wanted_until": 0}}, upsert=True)
        update_wallet(catcher_id, reward)

        await track_bounty_progress(self.bot, catcher_id, "HUNTER", 1)

        remaining = int(wanted_until - now)
        embed = discord.Embed(
            title="🚔 ¡Criminal Atrapado!",
            description=(
                f"¡Atrapaste a **{member.display_name}** y lo entregaste!\n"
                f"Le quedaban **{remaining // 60}m {remaining % 60}s** en su temporizador de buscado.\n\n"
                f"💰 Recompensa: 🪙 **{reward:,}** monedas\n\n"
                f"🔒 **{member.display_name}** fue enviado a la cárcel hasta <t:{release_ts}:t> "
                f"(<t:{release_ts}:R>) y no puede usar ningún comando."
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"Tu nueva billetera: 🪙 {get_wallet(catcher_id):,}")
        await ctx.send(embed=embed)

        # DM al jugador encarcelado
        try:
            jail_embed = discord.Embed(
                title="🔒 ¡Te han enviado a la cárcel!",
                description=(
                    f"**{ctx.author.display_name}** te atrapó y te entregó.\n\n"
                    f"No puedes usar ningún comando del bot hasta <t:{release_ts}:t> (<t:{release_ts}:R>)."
                ),
                color=0xE74C3C,
            )
            await member.send(embed=jail_embed)
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="sell", description="Vende un objeto de tu inventario")
    async def sell(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Tu inventario está vacío.")
        embed = discord.Embed(title="💰 Vender Objeto", description="Elige un objeto para vender.", color=0xE67E22)
        _sell_view = SellView(ctx, inventory)
        _sell_view.message = await ctx.send(embed=embed, view=_sell_view)

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="Ve tu inventario")
    async def inventory(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Tu inventario está vacío.")
        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "godly": "🌌",
        }
        embed = discord.Embed(title=f"🎒 Inventario de {ctx.author.name}", color=0x2ECC71)
        total_value = 0
        text = ""
        for item in inventory[:25]:
            rarity = item["rarity"]
            emoji = rarity_emojis.get(rarity, "⚪")
            text += f"{emoji} {item['name']} • 🪙 {item['value']:,}\n"
            total_value += item["value"]
        embed.description = text
        embed.add_field(name="💰 Valor Total del Inventario", value=f"🪙 {total_value:,}", inline=False)
        embed.set_footer(text=f"{len(inventory)} objetos almacenados")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="claimdrop", description="Reclama el drop global activo")
    async def claimdrop(self, ctx: commands.Context):
        # Tomar y limpiar el drop de forma atómica (antes de cualquier await) para evitar condiciones de carrera
        drop = state.active_global_drop
        if not drop:
            return await ctx.send("❌ No hay ningún drop global activo.")
        state.active_global_drop = None  # reclamado — nadie más puede tomarlo ahora
        user_id = str(ctx.author.id)
        if drop["type"] == "coins":
            base_reward = drop["reward"]
            reward = apply_amortization(user_id, base_reward)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": reward}}, upsert=True)
            msg = f"🌠 {ctx.author.mention} reclamó el drop y recibió 🪙 {reward:,}!"
            if reward < base_reward:
                msg += f"\n📉 🪙 {base_reward - reward:,} monedas fueron usadas automáticamente para pagar tu deuda."
            await ctx.send(msg)
        else:
            item = drop["item"]
            eco_col.update_one({"_id": user_id}, {"$push": {"inventory": item}}, upsert=True)
            await ctx.send(
                f"🌠 {ctx.author.mention} reclamó:\n\n{item['name']} • {item['rarity'].capitalize()}!"
            )

    @commands.hybrid_command(name="loan", description="Solicita un préstamo del banco del clan")
    @app_commands.describe(amount="Cantidad a pedir prestada (ej. 1000 o 'max')")
    async def loan(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        
        user_data = get_user_data(user_id)
        wallet = user_data.get("wallet", 0)
        bank = user_data.get("bank", 0)
        net_worth = max(0, wallet + bank)
        
        from utils.economy import get_prestige_level
        level = get_prestige_level(net_worth)
        
        # Límite de crédito basado en el prestigio y el patrimonio neto (MUY AGRESIVO)
        ratios = {
            0: 1.0,   # Ninguno: 100%
            1: 1.0,   # Bronce: 100%
            2: 2.0,   # Plata: 200%
            3: 5.0,   # Oro: 500%
            4: 10.0,  # Platino: 1,000%
            5: 20.0,  # Esmeralda: 2,000%
            6: 50.0,  # Diamante: 5,000%
            7: 100.0  # Maestro: 10,000%
        }
        ratio = ratios.get(level, 1.0)
        # Límite mínimo de 50,000 para jugadores nuevos/pobres, de lo contrario usar el ratio agresivo
        limit = max(50000, int(net_worth * ratio))

        # Analizar la cantidad
        if amount.lower() in ["max", "all"]:
            parsed_amount = limit
        else:
            try:
                parsed_amount = int(amount.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Cantidad inválida. Por favor usa un número o 'max'.", ephemeral=True)

        # Validación de entrada
        if parsed_amount <= 0:
            if limit <= 0:
                return await ctx.send("❌ Tu límite de crédito es 0 porque no tienes patrimonio neto.", ephemeral=True)
            return await ctx.send("❌ Por favor especifica una cantidad positiva.", ephemeral=True)
            
        if parsed_amount > 1000000000000: # Límite técnico
            return await ctx.send("❌ ¡Esa cantidad es demasiado alta incluso para nuestro banco!", ephemeral=True)

        current_debt = get_debt(user_id)
        if current_debt > 0:
            return await ctx.send(f"❌ Ya tienes una deuda activa de 🪙 {current_debt:,}. ¡Págala primero!", ephemeral=True)
            
        if parsed_amount > limit:
            return await ctx.send(f"❌ Tu límite de crédito es 🪙 {limit:,} según tu patrimonio neto y prestigio.", ephemeral=True)
            
        # Operación atómica para evitar duplicación
        now = time.time()
        result = eco_col.update_one(
            {"_id": user_id, "$or": [{"loan_amount": {"$exists": False}}, {"loan_amount": {"$lte": 0}}]},
            {
                "$inc": {"loan_amount": parsed_amount, "wallet": parsed_amount},
                "$set": {"last_interest_calc": now, "loan_start_time": now}
            }
        )
        
        if result.modified_count == 0:
            return await ctx.send("❌ No se pudo procesar el préstamo. Puede que ya tengas uno o se produjo un error.", ephemeral=True)
        
        embed = discord.Embed(
            title="🏦 Préstamo Aprobado",
            description=f"Pediste prestado 🪙 **{parsed_amount:,}** monedas.\n\n⚠️ **Nota:** Se aplicará un interés del 2% cada 24 horas. El 30% de tus ganancias futuras se usará automáticamente para pagar este préstamo.",
            color=0xF1C40F
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="repay", description="Paga tu préstamo activo")
    @app_commands.describe(amount="Cantidad a pagar ('all', 'half' o número)")
    async def repay(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        debt = get_debt(user_id)
        
        if debt <= 0:
            return await ctx.send("✅ No tienes ningún préstamo activo que pagar.", ephemeral=True)
            
        wallet = get_wallet(user_id)
        parsed_amount = parse_economy_amount(amount, min(wallet, debt))
        
        if parsed_amount <= 0:
            return await ctx.send("❌ Cantidad inválida. Por favor especifica un número positivo, 'all' o 'half'.", ephemeral=True)
            
        if wallet < parsed_amount:
            return await ctx.send(f"❌ No tienes suficientes monedas en tu billetera. Necesitas 🪙 {parsed_amount:,}.", ephemeral=True)
            
        user_data = get_user_data(user_id)
        interest = user_data.get("interest_accrued", 0)
        
        # Pagar primero los intereses, luego el capital, todo en una única actualización atómica
        if parsed_amount <= interest:
            eco_col.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "interest_accrued": -parsed_amount,
                        "wallet": -parsed_amount
                    }
                }
            )
        else:
            remaining = parsed_amount - interest
            eco_col.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "interest_accrued": -interest,
                        "loan_amount": -remaining,
                        "wallet": -parsed_amount
                    }
                }
            )
        
        new_debt = get_debt(user_id)
        
        # Seguimiento de misiones
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "LOAN_PAYER", parsed_amount)
        
        embed = discord.Embed(
            title="🏦 Pago del Préstamo",
            description=f"Pagaste 🪙 **{parsed_amount:,}** monedas.\n\n**Deuda Restante:** 🪙 {new_debt:,}",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="debt", description="Consulta el estado de tu deuda actual")
    async def debt(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        loan = user_data.get("loan_amount", 0)
        
        if loan <= 0 and user_data.get("interest_accrued", 0) <= 0:
            return await ctx.send("✅ ¡Estás libre de deudas! Felicidades.")

        # Usar get_debt para obtener el total calculado dinámicamente incluyendo intereses pendientes
        total = get_debt(user_id)
        interest = total - loan
        
        last_calc = user_data.get("last_interest_calc", time.time())
        # El próximo cálculo es en 1 hora (ya que process_interests se ejecuta cada hora)
        next_calc = int(last_calc + 3600)
        
        embed = discord.Embed(title="📉 Informe de Deuda Financiera", color=0xFF2A2A)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        desc = (
            f"### 🏦 Saldo Pendiente\n"
            f"> **Total a Pagar:** 🪙 `{total:,}`\n\n"
            f"**Detalles:**\n"
            f"💵 **Capital:** 🪙 `{loan:,}`\n"
            f"📈 **Intereses Acumulados:** 🪙 `{interest:,}`\n\n"
            f"--- \n"
            f"📊 **Tasa de Interés:** `2% diario` (Calculado cada hora)\n"
            f"⏳ **Próxima Actualización:** <t:{next_calc}:R>\n"
            f"📉 **Pago Automático:** `30%` de todas las ganancias futuras"
        )
        embed.description = desc
        embed.set_footer(text="Paga tu préstamo con !repay para evitar más intereses.")
        
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="prestige", description="Consulta tus hitos de prestigio de riqueza")
    async def prestige(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        net_worth = wallet + bank
        
        from utils.economy import get_prestige_level
        from config import PRESTIGE_LEVELS
        
        current_level = get_prestige_level(net_worth)
        
        embed = discord.Embed(title="🏆 Hitos de Prestigio de Riqueza", color=0xFFD700)
        embed.description = f"Tu Patrimonio Neto: **🪙 {net_worth:,}**\n\n"
        
        for level, data in PRESTIGE_LEVELS.items():
            indicator = "✅" if level <= current_level else "🔒"
            text = (
                f"{indicator} **{data['name']}**\n"
                f"• Requerido: 🪙 {data['threshold']:,}\n"
                f"• Descuento en Tienda: {data['discount']*100}%\n"
            )
            embed.add_field(name="\u200b", value=text, inline=False)
            
        embed.set_footer(text="¡Alcanza mayor riqueza para desbloquear descuentos permanentes!")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
