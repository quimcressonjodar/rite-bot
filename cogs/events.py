import random
import time
import logging

import discord
from discord.ext import commands, tasks

import state
from config import WELCOME_CHANNEL_ID, ADVENTURE_LOOT, ANNOUNCEMENTS_CHANNEL_ID
from database import eco_col

logger = logging.getLogger("weekly-xp-bot")

GLOBAL_DROP_CHANNEL_ID = ANNOUNCEMENTS_CHANNEL_ID
GLOBAL_DROP_COIN_REWARDS = [50000, 75000, 100000, 125000, 150000, 200000]


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info(f"EVENTS COG CARGADO {id(self)}")
        self.spawn_global_drop.start()
        self.process_interests.start()

    def cog_unload(self):
        self.spawn_global_drop.cancel()
        self.process_interests.cancel()

    def _should_process_member_event(self, event_name: str, member_id: int, cooldown: float = 5.0) -> bool:
        key = (event_name, member_id)
        now = time.monotonic()
        last = state.recent_member_events.get(key)
        if last and now - last < cooldown:
            return False
        state.recent_member_events[key] = now
        return True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("join", member.id):
            return
        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return
        embed = discord.Embed(
            title=f"¡Bienvenido al servidor, {member.name}! \U0001f389",
            description=(
                f"¡Hola {member.mention}, nos alegra tenerte aquí!\n\n"
                f"\U0001f4dc **Primer Paso:** Por favor, lee las reglas en <#1206222685143826485>\n"
                f"\u2694\ufe0f **¿Quieres unirte?** Si quieres solicitar ingreso al clan, ve a <#1206198139686617088>\n\n"
                f"¡Disfruta tu estancia!"
            ),
            color=0x2B2D31,
        )
        embed.set_image(url="https://i.ibb.co/d4r7Z6f8/248-AB2-AF-21-F0-4384-A53-D-404328353301.png")
        await channel.send(content=f"¡Bienvenido {member.mention}!", embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("leave", member.id):
            return
        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return
        embed = discord.Embed(
            title="¡Hasta luego! \U0001f44b",
            description=f"**{member.name}** ha abandonado el servidor. ¡Te echaremos de menos!",
            color=0xFF2A2A,
        )
        await channel.send(embed=embed)

    @tasks.loop(hours=9)
    async def spawn_global_drop(self):
        channel = self.bot.get_channel(GLOBAL_DROP_CHANNEL_ID)
        if not channel:
            return

        drop_type = random.choice(["coins", "coins", "coins", "item", "item"])

        if drop_type == "coins":
            reward = random.choice(GLOBAL_DROP_COIN_REWARDS)
            state.active_global_drop = {"type": "coins", "reward": reward}
            embed = discord.Embed(
                title="\U0001f320 DROP GLOBAL",
                description=(
                    "\U0001f4b8 ¡Apareció un ENORME tesoro!\n¡La primera persona en reclamarlo gana!\n"
                    "¡Usa `!claimdrop` primero!"
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="\U0001f4b0 Recompensa en Monedas", value=f"\U0001fa99 {reward:,}")
        else:
            rarity_roll = random.randint(1, 100)
            if rarity_roll <= 50:
                rarity = "common"
            elif rarity_roll <= 80:
                rarity = "rare"
            elif rarity_roll <= 94:
                rarity = "epic"
            elif rarity_roll <= 99:
                rarity = "legendary"
            else:
                rarity = "godly"

            item_name, item_value = random.choice(ADVENTURE_LOOT[rarity])
            rarity_colors = {
                "common": 0x95A5A6, "rare": 0x3498DB, "epic": 0x9B59B6,
                "legendary": 0xF1C40F, "godly": 0xFF00FF,
            }
            embed = discord.Embed(
                title="\U0001f320 DROP GLOBAL DE ÍTEM",
                description="¡Apareció un ítem misterioso desde el cielo!\n\n¡Usa `!claimdrop` primero!",
                color=rarity_colors[rarity],
            )
            embed.add_field(name="\U0001f381 Ítem", value=item_name)
            embed.add_field(name="\u2728 Rareza", value=rarity.capitalize())
            state.active_global_drop = {
                "type": "item",
                "item": {"name": item_name, "value": item_value, "rarity": rarity},
            }

        if drop_type == "item" and rarity in ("godly", "legendary"):
            hype = (
                "\U0001f30c ¡¡¡Apareció un ítem DIVINO!!! ¡¡¡EL UNIVERSO TIEMBLA!!!"
                if rarity == "godly"
                else "\U0001f30c ¡¡¡Apareció un ítem LEGENDARIO!!!"
            )
            await channel.send(hype)
        await channel.send(embed=embed)

    @spawn_global_drop.before_loop
    async def before_spawn_global_drop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def process_interests(self):
        """Aplica un 2% de interés diario prorrateado a los préstamos activos."""
        now = time.time()
        users_with_loans = eco_col.find({"loan_amount": {"$gt": 0}})

        for user_data in users_with_loans:
            user_id   = user_data["_id"]
            last_calc = user_data.get("last_interest_calc", now)
            time_diff = now - last_calc

            if time_diff >= 3600:
                loan_amount = user_data.get("loan_amount", 0)
                interest    = int(loan_amount * 0.02 * (time_diff / 86400))

                if interest > 0:
                    eco_col.update_one(
                        {"_id": user_id},
                        {
                            "$inc": {"interest_accrued": interest},
                            "$set": {"last_interest_calc": now},
                        },
                    )
                    logger.info(f"Se aplicaron {interest} de interés al usuario {user_id} por {time_diff/3600:.2f} horas")
                elif time_diff >= 86400:
                    eco_col.update_one({"_id": user_id}, {"$set": {"last_interest_calc": now}})

    @process_interests.before_loop
    async def before_process_interests(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        from utils.economy import JailCheckError
        if isinstance(error, JailCheckError):
            return

        logger.error(f"Error en el comando {ctx.command}: {error}", exc_info=error)

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("\u274c No tienes permiso para usar este comando.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("\u274c No tengo permiso para hacer eso.", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            next_ts = int(time.time() + error.retry_after)
            await ctx.send(f"\u23f3 Este comando está en cooldown. Inténtalo de nuevo <t:{next_ts}:R>.", ephemeral=True)
        else:
            await ctx.send(f"\u274c Ocurrió un error: {str(error)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
