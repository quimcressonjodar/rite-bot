import asyncio
import random
import secrets
import time

import discord
from discord import app_commands
from discord.ext import commands

from config import ROULETTE_RED, VALID_BETS
from database import eco_col
from utils.economy import get_user_data, get_wallet, update_wallet, parse_economy_amount, apply_amortization
from views.game_views import BlackjackView


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="roulette", aliases=["r"], description="Apuesta en la ruleta del casino")
    @app_commands.describe(
        bet_amount="Cantidad ('all', 'half' o número)",
        bet_on="¿En qué estás apostando?",
        number="Número al que apostar (si elegiste número específico)",
    )
    @app_commands.choices(bet_on=[
        app_commands.Choice(name="🔴 Rojo (x2)", value="red"),
        app_commands.Choice(name="⚫ Negro (x2)", value="black"),
        app_commands.Choice(name="🔢 Par (x2)", value="even"),
        app_commands.Choice(name="🔢 Impar (x2)", value="odd"),
        app_commands.Choice(name="🥇 1ra docena (1-12) (x3)", value="1st"),
        app_commands.Choice(name="🥈 2da docena (13-24) (x3)", value="2nd"),
        app_commands.Choice(name="🥉 3ra docena (25-36) (x3)", value="3rd"),
        app_commands.Choice(name="🎯 Número Específico (x36)", value="specific_number"),
    ])
    async def roulette(self, ctx: commands.Context, bet_amount: str, bet_on: str, number: int = None):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        bet = parse_economy_amount(bet_amount, user_data["wallet"])

        if bet <= 0:
            return await ctx.send("❌ Apuesta inválida. Por favor especifica un número positivo, 'all' o 'half'.", ephemeral=True)
        if user_data["wallet"] < bet:
            return await ctx.send(f"❌ No tienes suficientes monedas. Tu saldo es 🪙 {user_data['wallet']:,}.", ephemeral=True)

        bet_aliases = {
            "number": "specific_number", "num": "specific_number", "n": "specific_number",
            "red": "red", "black": "black", "even": "even", "odd": "odd",
        }
        bet_on = bet_aliases.get(bet_on.lower(), bet_on.lower())

        if bet_on not in VALID_BETS:
            return await ctx.send(
                "❌ Tipo de apuesta inválido.\nApuestas válidas: red, black, even, odd, number, 1st, 2nd, 3rd",
                ephemeral=True,
            )

        if bet_on == "specific_number" and (number is None or not (0 <= number <= 36)):
            return await ctx.send("❌ Por favor ingresa un número válido entre 0 y 36.", ephemeral=True)

        spin_msg = await ctx.send("🎰 **Lanzando la bola...** 🔄\n`[          ] 0%`")
        animation_frames = [
            "🎰 **Girando...** 🔴 14\n`[▬▬        ] 25%`",
            "🎰 **Girando...** ⬛ 22\n`[▬▬▬▬▬     ] 50%`",
            "🎰 **Desacelerando...** 🟢 0\n`[▬▬▬▬▬▬▬   ] 75%`",
            "🎰 **Casi listo...** 🔴 7\n`[▬▬▬▬▬▬▬▬▬ ] 99%`",
        ]
        for frame in animation_frames:
            await asyncio.sleep(0.8)
            await spin_msg.edit(content=frame)

        winning_number = secrets.randbelow(37)

        is_red = winning_number in ROULETTE_RED
        is_black = winning_number != 0 and not is_red
        color_emoji = "🟩" if winning_number == 0 else ("🟥" if is_red else "⬛")
        color_text = "Verde" if winning_number == 0 else ("Rojo" if is_red else "Negro")

        win = False
        multiplier = 0
        if bet_on == "red" and is_red:
            win, multiplier = True, 2
        elif bet_on == "black" and is_black:
            win, multiplier = True, 2
        elif bet_on == "even" and winning_number != 0 and winning_number % 2 == 0:
            win, multiplier = True, 2
        elif bet_on == "odd" and winning_number % 2 != 0:
            win, multiplier = True, 2
        elif bet_on == "specific_number" and number == winning_number:
            win, multiplier = True, 36
        elif bet_on == "1st" and 1 <= winning_number <= 12:
            win, multiplier = True, 3
        elif bet_on == "2nd" and 13 <= winning_number <= 24:
            win, multiplier = True, 3
        elif bet_on == "3rd" and 25 <= winning_number <= 36:
            win, multiplier = True, 3

        bet_target_display = {
            "red": "Rojo", "black": "Negro", "even": "Par", "odd": "Impar",
            "1st": "1ra docena (1-12)", "2nd": "2da docena (13-24)", "3rd": "3ra docena (25-36)",
        }.get(bet_on, bet_on.capitalize())
        if bet_on == "specific_number":
            bet_target_display = f"Número {number}"

        embed = discord.Embed(title="🎰 Ruleta del Casino", color=0x00FF00 if win else 0xFF0000)
        embed.set_author(name=f"Tirada de {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="📝 Detalles de la Apuesta", value=f"**Cantidad:** 🪙 {bet:,}\n**Apuesta en:** {bet_target_display}", inline=True)
        embed.add_field(name="🎯 La Tirada", value=f"**Cayó en:**\n{color_emoji} **{color_text} {winning_number}**", inline=True)

        if win:
            winnings = bet * multiplier
            profit = winnings - bet
            
            # Aplicar amortización a las ganancias
            actual_profit = apply_amortization(user_id, profit)
            update_wallet(user_id, actual_profit)
            
            # Seguimiento de misiones
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, user_id, "GAMBLER", profit)
            await track_bounty_progress(self.bot, user_id, "STREAK_GAMBLER", 1)
            
            outcome_text = f"**¡GANASTE!** (multiplicador x{multiplier})\n¡Ganaste 🪙 **{winnings:,}**!"
            if actual_profit < profit:
                outcome_text += f"\n📉 🪙 {profit - actual_profit:,} monedas fueron usadas automáticamente para pagar tu deuda."
            
            embed.add_field(name="🎉 Resultado", value=outcome_text, inline=False)
        else:
            update_wallet(user_id, -bet)
            embed.add_field(name="💀 Resultado", value=f"**¡PERDISTE!**\nPerdiste 🪙 **{bet:,}**.", inline=False)

        embed.set_footer(text=f"Nuevo Saldo de Billetera: 🪙 {get_wallet(user_id):,}")
        await asyncio.sleep(0.8)
        await spin_msg.edit(content="🛑 **¡La ruleta se detuvo!**", embed=embed)

    @commands.hybrid_command(name="blackjack", aliases=["bj"], description="Juega una mano realista de blackjack")
    @app_commands.describe(bet_amount="Cantidad ('all', 'half' o número)")
    async def blackjack(self, ctx: commands.Context, bet_amount: str):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        bet = parse_economy_amount(bet_amount, user_data["wallet"])
        if bet <= 0:
            return await ctx.send("❌ Apuesta inválida. Por favor especifica un número positivo, 'all' o 'half'.")
        if user_data["wallet"] < bet:
            return await ctx.send(f"❌ No tienes suficientes monedas. Tu saldo es 🪙 {user_data['wallet']:,}.")
        view = BlackjackView(ctx, bet)
        msg = await ctx.send(embed=view.create_embed(), view=view)
        view.message = msg
        
        # Verificar blackjack natural
        if view._calculate_score(view.player_hand) == 21:
            await asyncio.sleep(1)
            p_score = 21
            d_score = view._calculate_score(view.dealer_hand)
            
            view.finished = True
            view.hit_button.disabled = True
            view.stand_button.disabled = True
            
            if d_score == 21:
                result_text = "¡Ambos tienen Blackjack! ¡Empate!"
                win_amount = 0
            else:
                win_amount = int(bet * 1.5)
                actual_win = apply_amortization(user_id, win_amount)
                update_wallet(user_id, actual_win)
                
                # Seguimiento de misiones
                from utils.bounties import track_bounty_progress
                await track_bounty_progress(self.bot, user_id, "GAMBLER", win_amount)
                await track_bounty_progress(self.bot, user_id, "STREAK_GAMBLER", 1)
                
                result_text = "¡Blackjack! ¡Ganaste!"
                if actual_win < win_amount:
                    result_text += f"\n📉 🪙 {win_amount - actual_win:,} monedas usadas para pagar la deuda."
                
            embed = view.create_embed(result_text)
            if isinstance(msg, discord.Interaction):
                await msg.edit_original_response(embed=embed, view=view)
            else:
                await msg.edit(embed=embed, view=view)

    @commands.hybrid_command(name="dice", description="Tira dos dados contra la casa")
    @app_commands.describe(bet_amount="Cantidad ('all', 'half' o número)")
    async def dice(self, ctx: commands.Context, bet_amount: str):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        
        # Verificación de cooldown
        cooldown = 900
        last_dice = user_data.get("last_dice", 0)
        now = time.time()
        if now - last_dice < cooldown:
            next_dice_ts = int(last_dice + cooldown)
            return await ctx.send(f"⏳ Debes esperar <t:{next_dice_ts}:R> antes de volver a tirar los dados.", ephemeral=True)

        bet = parse_economy_amount(bet_amount, user_data["wallet"])

        if bet <= 0:
            return await ctx.send("❌ Apuesta inválida. Por favor especifica un número positivo, 'all' o 'half'.", ephemeral=True)
        if user_data["wallet"] < bet:
            return await ctx.send(f"❌ No tienes suficientes monedas. Tu saldo es 🪙 {user_data['wallet']:,}.", ephemeral=True)

        # Tirar dados usando secrets para mayor equidad
        p_dice1 = secrets.randbelow(6) + 1
        p_dice2 = secrets.randbelow(6) + 1
        p_total = p_dice1 + p_dice2

        h_dice1 = secrets.randbelow(6) + 1
        h_dice2 = secrets.randbelow(6) + 1
        h_total = h_dice1 + h_dice2

        username = ctx.author.name.lower()
        content = f"🎲 {username} apuesta **{bet:,}** 🪙 y lanza sus dados..."
        msg = await ctx.send(content)
        await asyncio.sleep(1.2)

        content += f"\n🎲 {username} saca **{p_dice1}** y **{p_dice2}**..."
        await msg.edit(content=content)
        await asyncio.sleep(1.2)

        content += f"\n🎲 {username}, tu oponente lanza sus dados... y saca **{h_dice1}** y **{h_dice2}**..."
        await msg.edit(content=content)
        await asyncio.sleep(1.2)

        if p_total > h_total:
            multiplier = 1
            bonus_text = ""
            if p_dice1 == p_dice2:
                if p_dice1 == 6:
                    multiplier = 3
                    bonus_text = " **(¡DOBLE 6! ¡MULTIPLICADOR x3)**"
                else:
                    multiplier = 2
                    bonus_text = " **(¡DOBLE! ¡MULTIPLICADOR x2)**"
            
            base_winnings = bet * multiplier
            profit = base_winnings - bet
            winnings = apply_amortization(user_id, base_winnings)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": winnings}, "$set": {"last_dice": now}}, upsert=True)
            
            # Seguimiento de misiones
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, user_id, "GAMBLER", profit)
            await track_bounty_progress(self.bot, user_id, "STREAK_GAMBLER", 1)
            
            result = f"**ganaste** **{base_winnings:,}** 🪙{bonus_text}"
            if winnings < base_winnings:
                result += f"\n📉 🪙 {base_winnings - winnings:,} monedas usadas para pagar la deuda."
        elif p_total < h_total:
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": -bet}, "$set": {"last_dice": now}}, upsert=True)
            result = f"**perdiste** **{bet:,}** 🪙"
        else:
            result = f"**empataste**, **{bet:,}** 🪙 devueltas"

        content += f"\n🎲 {username}, {result}"
        await msg.edit(content=content)

    @commands.hybrid_command(name="8ball", description="Hazle una pregunta a la mágica bola 8")
    @app_commands.describe(question="La pregunta que quieres hacer")
    async def eight_ball(self, ctx: commands.Context, question: str):
        responses = [
            "Es seguro.", "Definitivamente sí.", "Sin ninguna duda.",
            "Sí, definitivamente.", "Puedes contar con ello.", "A mi modo de ver, sí.",
            "Lo más probable.", "El panorama es bueno.", "Sí.", "Las señales apuntan a que sí.",
            "La respuesta es confusa, inténtalo de nuevo.", "Pregunta más tarde.", "Mejor no decírtelo ahora.",
            "No puedo predecirlo ahora.", "Concéntrate y pregunta de nuevo.",
            "No cuentes con ello.", "Mi respuesta es no.", "Mis fuentes dicen que no.",
            "El panorama no es muy bueno.", "Muy dudoso.",
        ]
        embed = discord.Embed(color=0x2B2D31)
        embed.description = (
            f"🎱 **{ctx.author.display_name} pregunta:** {question}\n"
            f"💬 **Respuesta:** {random.choice(responses)}"
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
