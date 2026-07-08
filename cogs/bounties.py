import discord
from discord.ext import commands, tasks
import time
from utils.bounties import get_active_bounties, spawn_new_bounty
from database import db

class Bounties(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bounty_spawner.start()

    def cog_unload(self):
        self.bounty_spawner.cancel()

    @tasks.loop(hours=12)
    async def bounty_spawner(self):
        """Asegura que siempre haya 3 recompensas activas en el tablero."""
        active = get_active_bounties()
        needed = 3 - len(active)
        
        if needed <= 0:
            return

        STOCK_NEWS_CHANNEL_ID = 1206197908399980575
        channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
        
        for _ in range(needed):
            new_b = spawn_new_bounty()
            if not new_b:
                continue
                
            # Anunciar cada nueva recompensa
            if channel:
                embed = discord.Embed(
                    title="🎯 NUEVA RECOMPENSA PUBLICADA",
                    description=f"¡Hay un nuevo contrato disponible en el tablero!\n\n**{new_b['name']}**\n{new_b['description']}",
                    color=0xE67E22
                )
                embed.add_field(name="💰 Recompensa", value=f"🪙 {new_b['reward']:,}")
                embed.set_footer(text="Usa !bounties para ver todos los contratos activos.")
                await channel.send(embed=embed)

    @bounty_spawner.before_loop
    async def before_bounty_spawner(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="bounties", description="Ver contratos de recompensa activos")
    async def bounties(self, ctx: commands.Context):
        active = get_active_bounties()
        
        if not active:
            return await ctx.send("📋 El tablero de recompensas está vacío por ahora. ¡Vuelve más tarde!")

        embed = discord.Embed(title="🎯 Tablero de Recompensas Activas", color=0xE67E22)
        
        for b in active:
            user_progress = b.get("participants", {}).get(str(ctx.author.id), 0)
            progress_bar = f"Progreso: `{user_progress:,} / {b['goal']:,}`"
            
            embed.add_field(
                name=f"📜 {b['name']}",
                value=f"{b['description']}\n💰 Recompensa: 🪙 {b['reward']:,}\n📊 {progress_bar}",
                inline=False
            )
            
        embed.set_footer(text="¡Sé el primero en completar el objetivo para reclamar la recompensa!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Bounties(bot))
