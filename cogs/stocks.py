import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
from config import STOCKS, STOCK_UPDATE_INTERVAL, STOCK_FEE, OWNER_IDS
from utils.stocks import (
    update_stock_prices, generate_stock_chart, get_current_price,
    get_user_portfolio, buy_stock, sell_stock, process_dividends,
    load_ipo_stocks, add_ipo_stock,
    add_price_alert, get_user_alerts, remove_alert_by_seq, check_price_alerts,
    add_autosell, get_user_autosells, remove_autosell_by_seq, check_autosells,
    stock_alerts_col, user_stocks_col,
)
from utils.stock_news import get_random_news
from utils.economy import get_wallet, update_wallet, get_bank, get_prestige_level
from utils.helpers import is_admin


class StockView(discord.ui.View):
    def __init__(self, ctx, symbol):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.symbol = symbol
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    @discord.ui.button(label="Comprar 1", style=discord.ButtonStyle.green)
    async def buy_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "buy")

    @discord.ui.button(label="Comprar 10", style=discord.ButtonStyle.green)
    async def buy_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 10, "buy")

    @discord.ui.button(label="Vender 1", style=discord.ButtonStyle.red)
    async def sell_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "sell")

    @discord.ui.button(label="Vender Todo", style=discord.ButtonStyle.red)
    async def sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        portfolio = get_user_portfolio(str(interaction.user.id))
        quantity = portfolio.get(self.symbol, {}).get("quantity", 0)
        if quantity <= 0:
            return await interaction.response.send_message("❌ No tienes acciones de esta empresa.", ephemeral=True)
        await self.process_trade(interaction, quantity, "sell")

    async def process_trade(self, interaction, quantity, side):
        if str(interaction.user.id) != str(self.ctx.author.id):
            return await interaction.response.send_message("❌ Este menú no es tuyo.", ephemeral=True)
        await self.process_trade_direct(interaction, quantity, side)

    async def process_trade_direct(self, target, quantity, side):
        is_interaction = isinstance(target, discord.Interaction)
        user = target.user if is_interaction else target.author
        user_id = str(user.id)

        price = get_current_price(self.symbol)
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)

        fee_multiplier = max(0, 1 - (level * 0.15))
        current_fee = STOCK_FEE * fee_multiplier

        if side == "buy":
            total_cost = int(price * quantity * (1 + current_fee))
            if wallet < total_cost:
                msg = f"❌ Necesitas 🪙 {total_cost:,} para comprar {quantity} acciones (incluidas comisiones)."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)

            update_wallet(user_id, -total_cost)
            buy_stock(user_id, self.symbol, quantity, price)
            msg = f"✅ Compraste {quantity} acciones de **{self.symbol}** por 🪙 {total_cost:,}!"
            return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)
        else:
            total_gain = int(price * quantity * (1 - current_fee))
            portfolio = get_user_portfolio(user_id)
            avg_price = portfolio.get(self.symbol, {}).get("avg_price", 0)
            profit = int((price - avg_price) * quantity)

            if sell_stock(user_id, self.symbol, quantity):
                update_wallet(user_id, total_gain)

                if profit > 0:
                    from utils.bounties import track_bounty_progress
                    bot = self.ctx.bot if hasattr(self.ctx, "bot") else self.ctx
                    await track_bounty_progress(bot, user_id, "TRADER", profit)

                if profit > 0:
                    result_line = f"📈 **+🪙 {profit:,}** de beneficio"
                    color = 0x2ECC71
                    title = "✅ Venta completada — Beneficio"
                elif profit < 0:
                    result_line = f"📉 **-🪙 {abs(profit):,}** de pérdida"
                    color = 0xE74C3C
                    title = "✅ Venta completada — Pérdida"
                else:
                    result_line = "➡️ Sin ganancia ni pérdida (vendido al precio medio)"
                    color = 0x95A5A6
                    title = "✅ Venta completada"

                fee_paid = int(price * quantity * current_fee)
                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="📦 Acciones vendidas", value=f"**{quantity}x {self.symbol}**", inline=True)
                embed.add_field(name="💰 Recibido", value=f"🪙 {total_gain:,}", inline=True)
                embed.add_field(
                    name="📊 Venta vs precio medio de compra",
                    value=f"🪙 {price:,} → media 🪙 {int(avg_price):,}",
                    inline=False,
                )
                embed.add_field(name="📈 Resultado", value=result_line, inline=False)
                if fee_paid > 0:
                    embed.set_footer(text=f"Comisión aplicada: 🪙 {fee_paid:,}")

                return await target.response.send_message(embed=embed, ephemeral=True) if is_interaction else await target.send(embed=embed)
            else:
                msg = "❌ No tienes suficientes acciones para vender."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)


class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stocks.start()
        self.distribute_dividends.start()

    def cog_unload(self):
        self.update_stocks.cancel()
        self.distribute_dividends.cancel()

    # ------------------------------------------------------------------
    # Tareas en segundo plano
    # ------------------------------------------------------------------

    @tasks.loop(minutes=STOCK_UPDATE_INTERVAL)
    async def update_stocks(self):
        try:
            news_impact = {}
            if random.random() < 0.50:
                symbol, message, multiplier = get_random_news()
                news_impact[symbol] = multiplier

                STOCK_NEWS_CHANNEL_ID = 1513755454029959239
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(title="🗞️ Alerta de Noticias del Mercado", description=message, color=0xF1C40F)
                    if symbol != "ALL":
                        embed.set_footer(text=f"Impacto: {symbol}")
                    await channel.send(embed=embed)

            update_stock_prices(news_impact)

            # Comprobar alertas de precio y órdenes de venta automática tras cada actualización
            await check_price_alerts(self.bot)
            await check_autosells(self.bot)

        except Exception as e:
            print(f"ERROR AL ACTUALIZAR ACCIONES: {e}")

    @tasks.loop(hours=24)
    async def distribute_dividends(self):
        try:
            users, total, rates = process_dividends()
            if users > 0:
                STOCK_NEWS_CHANNEL_ID = 1513755454029959239
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    # Ordenar acciones por tasa de dividendo para mostrar mejores y peores pagadores
                    sorted_rates = sorted(
                        rates.items(), key=lambda x: x[1]["rate"], reverse=True
                    )
                    top = sorted_rates[:3]
                    bottom = sorted_rates[-3:]

                    def fmt(symbol, info):
                        perf = info["performance"]
                        arrow = "📈" if perf >= 0 else "📉"
                        sign = "+" if perf >= 0 else ""
                        return f"**{symbol}** {arrow} {sign}{perf:.1%} → tasa {info['rate']:.2%}"

                    top_lines = "\n".join(fmt(s, i) for s, i in top)
                    bottom_lines = "\n".join(fmt(s, i) for s, i in bottom)

                    embed = discord.Embed(
                        title="💰 Dividendos Diarios Distribuidos",
                        description=f"🪙 **{total:,}** monedas pagadas a **{users}** accionistas!",
                        color=0x2ECC71,
                    )
                    embed.add_field(name="🏆 Mejores pagadores", value=top_lines, inline=False)
                    embed.add_field(name="📉 Peores pagadores", value=bottom_lines, inline=False)
                    embed.set_footer(text="Tasa de dividendo = 0,3% base ± rendimiento 24h. Rango: 0,05% – 2%")
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"ERROR DE DIVIDENDOS: {e}")

    @update_stocks.before_loop
    async def before_update_stocks(self):
        await self.bot.wait_until_ready()
        # Cargar acciones IPO persistidas en el diccionario STOCKS activo
        load_ipo_stocks()
        # Asegurarse de que cada acción tiene al menos 2 puntos de datos para que los gráficos se rendericen.
        # Se inicializa cada acción individualmente en lugar de llamar a update_stock_prices()
        # una vez (que solo añadiría 1 punto y fallaría en la primera acción encontrada).
        from utils.stocks import stocks_col
        import time as _time
        needs_seed = []
        for symbol in STOCKS:
            history = stocks_col.find_one({"symbol": symbol})
            if not history or len(history.get("prices", [])) < 2:
                needs_seed.append(symbol)

        for symbol in needs_seed:
            initial_price = STOCKS[symbol].get("initial_price", 500)
            history = stocks_col.find_one({"symbol": symbol})
            existing = history.get("prices", []) if history else []
            # Construir una lista con al menos 2 puntos
            if len(existing) == 0:
                seed = [
                    {"price": initial_price, "timestamp": _time.time() - 120},
                    {"price": initial_price, "timestamp": _time.time() - 60},
                ]
            else:
                # Tiene exactamente 1 punto — añadir un segundo justo antes
                seed = [
                    {"price": existing[0]["price"], "timestamp": existing[0]["timestamp"] - 60},
                ] + existing
            if history:
                stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": seed}})
            else:
                stocks_col.insert_one({"symbol": symbol, "prices": seed})

        # Ejecutar una actualización completa de precios para que todas las acciones reciban un tick inicial
        if needs_seed:
            update_stock_prices()

    # ------------------------------------------------------------------
    # Comandos de trading
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="sbuy", description="Compra acciones del mercado")
    @app_commands.describe(symbol="Símbolo de la acción (ej. VRTX)", quantity="Cantidad a comprar ('all', 'max', o un número)")
    async def sbuy(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Símbolo de acción **{symbol}** no encontrado.", ephemeral=True)

        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        price = get_current_price(symbol)

        level = get_prestige_level(wallet + get_bank(user_id))
        fee_multiplier = 1.0 + (STOCK_FEE * (1 - (level / 7.0)))
        cost_per_share = price * fee_multiplier

        if quantity.lower() in ["all", "max"]:
            if cost_per_share > wallet:
                return await ctx.send(
                    f"❌ No puedes permitirte ninguna acción de {symbol}. Necesitas al menos 🪙 {int(cost_per_share):,}.",
                    ephemeral=True,
                )
            parsed_quantity = int(wallet // cost_per_share)
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Cantidad inválida. Usa un número o 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ La cantidad debe ser positiva.", ephemeral=True)

        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "buy")

    @commands.hybrid_command(name="ssell", description="Vende acciones al mercado")
    @app_commands.describe(symbol="Símbolo de la acción (ej. VRTX)", quantity="Cantidad a vender ('all', 'max', o un número)")
    async def ssell(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Símbolo de acción **{symbol}** no encontrado.", ephemeral=True)

        user_id = str(ctx.author.id)
        portfolio = get_user_portfolio(user_id)
        user_shares = portfolio.get(symbol, {}).get("quantity", 0)

        if quantity.lower() in ["all", "max"]:
            parsed_quantity = user_shares
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Cantidad inválida. Usa un número o 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ La cantidad debe ser positiva.", ephemeral=True)

        if parsed_quantity > user_shares:
            return await ctx.send(f"❌ Solo tienes {user_shares} acciones de {symbol}.", ephemeral=True)

        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "sell")

    @commands.hybrid_command(name="stocks", aliases=["socks", "stock", "st"], description="Ver el mercado de acciones")
    async def stocks(self, ctx: commands.Context, symbol: str = None):
        await ctx.defer()

        if not symbol:
            embed = discord.Embed(title="📈 Mercado de Acciones Global", color=0x2B2D31)
            description = "Usa `!stocks <símbolo>` para ver gráficos detallados y operar.\n\n"
            for s, cfg in STOCKS.items():
                try:
                    price = get_current_price(s)
                    description += f"**{s}** - {cfg['name']}\nPrecio: 🪙 {price:,}\n\n"
                except Exception:
                    description += f"**{s}** - {cfg['name']}\nPrecio: *Calculando...*\n\n"
            embed.description = description
            return await ctx.send(embed=embed)

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Símbolo de acción **{symbol}** no encontrado.", ephemeral=True)

        try:
            price = get_current_price(symbol)
            embed = discord.Embed(
                title=f"📊 {STOCKS[symbol]['name']} ({symbol})",
                description=f"{STOCKS[symbol]['description']}\n\n**Precio Actual:** 🪙 {price:,}",
                color=0x3498DB,
            )

            chart = None
            try:
                chart = generate_stock_chart(symbol)
            except Exception as chart_err:
                print(f"ERROR AL GENERAR GRÁFICO para {symbol}: {chart_err}")

            if chart:
                embed.set_image(url=f"attachment://{symbol}_chart.png")
                view = StockView(ctx, symbol)
                view.message = await ctx.send(embed=embed, file=chart, view=view)
            else:
                view = StockView(ctx, symbol)
                view.message = await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(f"ERROR EN COMANDO STOCKS: {e}")
            await ctx.send(f"❌ Ocurrió un error al obtener datos de {symbol}. Por favor, inténtalo más tarde.")

    @commands.hybrid_command(name="portfolio", aliases=["pfol"], description="Ver tu cartera de acciones")
    async def portfolio(self, ctx: commands.Context):
        await ctx.defer()
        try:
            user_id = str(ctx.author.id)
            stocks_data = get_user_portfolio(user_id)

            if not stocks_data:
                return await ctx.send("💼 Tu cartera está vacía. ¡Empieza a operar con `!stocks`!")

            embed = discord.Embed(title=f"💼 Cartera de {ctx.author.display_name}", color=0x2ECC71)
            total_value = 0
            total_profit = 0

            for symbol, data in stocks_data.items():
                try:
                    current_price = get_current_price(symbol)
                    qty = data["quantity"]
                    avg = data["avg_price"]
                    value = qty * current_price
                    profit = (current_price - avg) * qty
                    total_value += value
                    total_profit += profit
                    p_text = f"+🪙 {profit:,.0f}" if profit >= 0 else f"-🪙 {abs(profit):,.0f}"
                    embed.add_field(
                        name=f"{symbol} ({qty} acciones)",
                        value=f"Valor: 🪙 {value:,}\nBeneficio: **{p_text}**\nCoste Medio: 🪙 {avg:,.0f}",
                        inline=True,
                    )
                except Exception as e:
                    print(f"ERROR procesando acción {symbol} en cartera: {e}")
                    continue

            embed.description = (
                f"**Valor Total de la Cartera:** 🪙 {total_value:,}\n"
                f"**Beneficio/Pérdida Total:** 🪙 {total_profit:,.0f}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"ERROR EN COMANDO PORTFOLIO: {e}")
            await ctx.send("❌ Ocurrió un error al obtener tu cartera. Por favor, inténtalo más tarde.")

    # ------------------------------------------------------------------
    # Comandos de alertas de precio
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="alert", description="Crea una alerta de precio — recibe un MD cuando una acción llegue a tu objetivo")
    @app_commands.describe(symbol="Símbolo de la acción (ej. CRPT)", price="Precio objetivo en monedas")
    async def alert(self, ctx: commands.Context, symbol: str, price: int):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(
                f"❌ Acción **{symbol}** no encontrada. Consulta `!stocks` para ver los símbolos disponibles.", ephemeral=True
            )
        if price <= 0:
            return await ctx.send("❌ El precio objetivo debe ser mayor que 0.", ephemeral=True)

        current_price = get_current_price(symbol)
        if current_price == price:
            return await ctx.send(
                "❌ El precio objetivo es igual al precio actual. Elige un valor diferente.", ephemeral=True
            )

        user_id = str(ctx.author.id)
        existing = get_user_alerts(user_id)
        if len(existing) >= 5:
            return await ctx.send(
                "❌ Ya tienes 5 alertas activas (máximo). Cancela una con `!cancelalert` antes de añadir otra.",
                ephemeral=True,
            )

        direction = "above" if price > current_price else "below"
        alert_id = add_price_alert(user_id, symbol, price)

        arrow = "📈" if direction == "above" else "📉"
        verb = "sube a" if direction == "above" else "baja a"

        embed = discord.Embed(
            title="🔔 Alerta de precio creada",
            description=(
                f"{arrow} Te enviaré un MD cuando **{symbol}** {verb} 🪙 **{price:,}**\n\n"
                f"💹 Precio actual: 🪙 **{current_price:,}**"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"ID: {alert_id} • Cancelar con: !cancelalert {alert_id}")
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="myalerts", description="Ver tus alertas de precio activas")
    async def myalerts(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        alerts = get_user_alerts(user_id)

        if not alerts:
            return await ctx.send(
                "📭 No tienes alertas activas. Crea una con `!alert <símbolo> <precio>`."
            )

        embed = discord.Embed(title="🔔 Tus alertas de precio activas", color=0x3498DB)
        for a in alerts:
            symbol = a["symbol"]
            target = a["target_price"]
            direction = a["direction"]
            arrow = "📈" if direction == "above" else "📉"
            verb = "≥" if direction == "above" else "≤"
            try:
                current = get_current_price(symbol)
                current_text = f"Precio actual: 🪙 {current:,}"
            except Exception:
                current_text = "Precio actual: desconocido"
            embed.add_field(
                name=f"{arrow} {symbol} {verb} 🪙 {target:,}",
                value=f"{current_text}\n`!cancelalert {a['seq']}`",
                inline=False,
            )

        embed.set_footer(text="Usa !cancelalert <id> para eliminar una alerta")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cancelalert", description="Cancelar una alerta de precio activa")
    @app_commands.describe(alert_id="Número de alerta mostrado en !myalerts (ej. 1, 2, 3)")
    async def cancelalert(self, ctx: commands.Context, alert_id: str):
        user_id = str(ctx.author.id)
        try:
            seq = int(alert_id)
        except ValueError:
            return await ctx.send("❌ ID inválido — usa el número mostrado en `!myalerts` (ej. `!cancelalert 1`).", ephemeral=True)

        alert = remove_alert_by_seq(user_id, seq)
        if not alert:
            return await ctx.send("❌ Alerta no encontrada. Consulta tus IDs con `!myalerts`.", ephemeral=True)

        embed = discord.Embed(
            title="✅ Alerta cancelada",
            description=f"La alerta para **{alert['symbol']}** a 🪙 {alert['target_price']:,} ha sido eliminada.",
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Comandos de venta automática
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="autosell", description="Establece una orden de venta automática cuando una acción alcance tu precio objetivo")
    @app_commands.describe(
        symbol="Símbolo de la acción (ej. VRTX)",
        quantity="Acciones a vender: un número, 'all' o 'half'",
        target_price="Precio (en monedas) al que se ejecutará la venta",
    )
    async def autosell(self, ctx: commands.Context, symbol: str, quantity: str, target_price: int):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Símbolo de acción **{symbol}** no encontrado.", ephemeral=True)
        if target_price <= 0:
            return await ctx.send("❌ El precio objetivo debe ser mayor que 0.", ephemeral=True)

        user_id = str(ctx.author.id)
        portfolio = get_user_portfolio(user_id)
        owned = portfolio.get(symbol, {}).get("quantity", 0)
        if owned <= 0:
            return await ctx.send(f"❌ No tienes acciones de **{symbol}**.", ephemeral=True)

        q_lower = quantity.lower().strip()
        if q_lower in ("all", "max"):
            parsed_quantity = owned
        elif q_lower == "half":
            parsed_quantity = max(1, owned // 2)
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Cantidad inválida. Usa un número, **all** o **half**.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ La cantidad debe ser mayor que 0.", ephemeral=True)
        if parsed_quantity > owned:
            return await ctx.send(
                f"❌ Solo tienes **{owned}** acciones de {symbol}, pero intentaste programar una venta de **{parsed_quantity}**.",
                ephemeral=True,
            )

        current_price = get_current_price(symbol)
        if target_price <= current_price:
            return await ctx.send(
                f"❌ El precio objetivo 🪙 {target_price:,} debe estar **por encima** del precio actual de 🪙 {current_price:,}.\n"
                f"Usa `!ssell` para vender inmediatamente al precio de mercado.",
                ephemeral=True,
            )

        existing = get_user_autosells(user_id)
        if len(existing) >= 5:
            return await ctx.send(
                "❌ Ya tienes 5 órdenes de venta automática activas (máximo). Cancela una con `!cancelautosell` primero.",
                ephemeral=True,
            )

        order_id = add_autosell(user_id, symbol, parsed_quantity, target_price)

        embed = discord.Embed(
            title="📤 Orden de venta automática creada",
            description=(
                f"📈 Venderé automáticamente **{parsed_quantity}x {symbol}** cuando el precio llegue a 🪙 **{target_price:,}**\n\n"
                f"💹 Precio actual: 🪙 **{current_price:,}**\n"
                f"🎯 Precio objetivo: 🪙 **{target_price:,}** (+{((target_price - current_price) / current_price * 100):.1f}%)"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"ID: {order_id} • Cancelar con: !cancelautosell {order_id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="myautosells", description="Ver tus órdenes de venta automática activas")
    async def myautosells(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        orders = get_user_autosells(user_id)

        if not orders:
            return await ctx.send(
                "📭 No tienes órdenes de venta automática activas. Crea una con `!autosell <símbolo> <cantidad> <precio_objetivo>`."
            )

        embed = discord.Embed(title="📤 Tus órdenes de venta automática activas", color=0x3498DB)
        for o in orders:
            symbol = o["symbol"]
            try:
                current = get_current_price(symbol)
                pct = ((o["target_price"] - current) / current) * 100
                current_text = f"Actual: 🪙 {current:,} ({pct:+.1f}% al objetivo)"
            except Exception:
                current_text = "Precio actual: desconocido"
            embed.add_field(
                name=f"📈 {symbol} — {o['quantity']} acciones @ 🪙 {o['target_price']:,}",
                value=f"{current_text}\n`!cancelautosell {o['seq']}`",
                inline=False,
            )

        embed.set_footer(text="Usa !cancelautosell <id> para eliminar una orden")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cancelautosell", description="Cancelar una orden de venta automática activa")
    @app_commands.describe(order_id="Número de orden mostrado en !myautosells (ej. 1, 2, 3)")
    async def cancelautosell(self, ctx: commands.Context, order_id: str):
        user_id = str(ctx.author.id)
        try:
            seq = int(order_id)
        except ValueError:
            return await ctx.send(
                "❌ ID inválido — usa el número mostrado en `!myautosells` (ej. `!cancelautosell 1`).", ephemeral=True
            )

        order = remove_autosell_by_seq(user_id, seq)
        if not order:
            return await ctx.send("❌ Orden no encontrada. Consulta tus IDs con `!myautosells`.", ephemeral=True)

        embed = discord.Embed(
            title="✅ Orden de venta automática cancelada",
            description=(
                f"La orden de venta automática de **{order['quantity']}x {order['symbol']}** "
                f"a 🪙 {order['target_price']:,} ha sido eliminada."
            ),
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Comando IPO (solo admin — completamente automático)
    # ------------------------------------------------------------------

    # Pool de empresas candidatas para IPOs automáticas.
    # El bot elige una al azar que no esté ya listada.
    IPO_POOL = {
        "NOVA": {"name": "Nova Systems",          "sector": "Technology",      "volatility": 0.12, "initial_price": 480,  "description": "Hardware de microchips y interfaces neurales de nueva generación."},
        "QNTM": {"name": "Quantum Leap Computing","sector": "Technology",      "volatility": 0.18, "initial_price": 620,  "description": "Pioneros en computación cuántica estable y cifrado."},
        "NXUS": {"name": "Nexus Networks",        "sector": "Telecom",         "volatility": 0.11, "initial_price": 450,  "description": "Proveedor global de infraestructura 7G e internet por satélite."},
        "ZRTH": {"name": "Zeroth AI",             "sector": "AI",              "volatility": 0.16, "initial_price": 550,  "description": "Modelos de lenguaje avanzados y sistemas autónomos de vanguardia."},
        "SOLX": {"name": "SolarX",                "sector": "Energy",          "volatility": 0.13, "initial_price": 390,  "description": "Paneles solares de máxima eficiencia y granjas solares flotantes."},
        "HYDR": {"name": "HydroGen Power",        "sector": "Energy",          "volatility": 0.14, "initial_price": 420,  "description": "Producción de hidrógeno verde y cadenas de suministro de carga."},
        "CARB": {"name": "CarbonZero",            "sector": "Environment",     "volatility": 0.12, "initial_price": 360,  "description": "Captura directa de carbono del aire y comercio global de créditos."},
        "BRVK": {"name": "BraveBank",             "sector": "Finance",         "volatility": 0.14, "initial_price": 500,  "description": "Banco digital sin comisiones con asesores financieros de IA."},
        "PYDE": {"name": "PyDex Exchange",        "sector": "Crypto/DeFi",     "volatility": 0.20, "initial_price": 340,  "description": "Exchange descentralizado regulado y socio piloto de CBDC."},
        "GNTX": {"name": "Genetix Corp",          "sector": "Biotech",         "volatility": 0.17, "initial_price": 580,  "description": "Terapia génica CRISPR y secuenciación del genoma a escala."},
        "MNDR": {"name": "MindRise",              "sector": "Neurotech",       "volatility": 0.19, "initial_price": 610,  "description": "Implantes cerebrales no invasivos y tecnología de mejora neurológica."},
        "DRFT": {"name": "Drift Motors",          "sector": "Automotive",      "volatility": 0.13, "initial_price": 470,  "description": "Vehículos eléctricos de alto rendimiento y conducción autónoma."},
        "SKYW": {"name": "SkyWay Airlines",       "sector": "Aviation",        "volatility": 0.11, "initial_price": 410,  "description": "Aerolínea global pionera en aviones propulsados por hidrógeno."},
        "XPRS": {"name": "Xpress Logistics",      "sector": "Logistics",       "volatility": 0.10, "initial_price": 380,  "description": "Entrega autónoma por drones y redes de almacenes robotizados."},
        "VRTL": {"name": "VirtualWorld",          "sector": "Gaming/Metaverse","volatility": 0.15, "initial_price": 520,  "description": "Metaverso VR inmersivo y publisher líder de esports."},
        "PLSR": {"name": "Pulsar Entertainment", "sector": "Entertainment",    "volatility": 0.12, "initial_price": 460,  "description": "Estudio de cine, plataforma de streaming y sello musical."},
        "NUTX": {"name": "NutriX",               "sector": "Food & Consumer",  "volatility": 0.10, "initial_price": 350,  "description": "Carne cultivada en laboratorio y suscripciones de nutrición personalizada."},
        "ARMX": {"name": "ArmX Defense",         "sector": "Defense",          "volatility": 0.14, "initial_price": 540,  "description": "Drones de combate autónomos y sistemas de ciberguerra para la OTAN."},
        "BRKR": {"name": "BrickRock Properties", "sector": "Real Estate",      "volatility": 0.09, "initial_price": 430,  "description": "Desarrollos de lujo y comunidades residenciales inteligentes."},
    }

    @commands.hybrid_command(
        name="ipo",
        description="Lista aleatoriamente una nueva empresa en el mercado, eliminando la de peor rendimiento (Solo Admin)",
    )
    @app_commands.default_permissions(administrator=True)
    async def ipo(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Solo administradores.", ephemeral=True)

        # Elegir un candidato al azar que no esté ya listado
        available = [s for s in self.IPO_POOL if s not in STOCKS]
        if not available:
            return await ctx.send(
                "❌ Todos los candidatos a IPO ya están listados en el mercado.", ephemeral=True
            )

        symbol = random.choice(available)
        data = self.IPO_POOL[symbol]

        # ── Pre-calcular qué acción será deslistada y su último precio ──────
        worst_symbol = None
        worst_performance = float("inf")
        for s in list(STOCKS.keys()):
            try:
                price = get_current_price(s)
            except Exception:
                price = STOCKS[s]["initial_price"]
            initial = STOCKS[s].get("initial_price", 500)
            performance = (price - initial) / initial if initial else 0
            if performance < worst_performance:
                worst_performance = performance
                worst_symbol = s

        # Obtener el último precio y todos los tenedores ANTES de que se elimine la acción
        delisted_price = 0
        holders = []  # lista de (user_id, quantity)
        if worst_symbol:
            try:
                delisted_price = get_current_price(worst_symbol)
            except Exception:
                delisted_price = STOCKS[worst_symbol].get("initial_price", 0)

            for doc in user_stocks_col.find({f"stocks.{worst_symbol}": {"$exists": True}}):
                qty = doc.get("stocks", {}).get(worst_symbol, {}).get("quantity", 0)
                if qty > 0:
                    holders.append((doc["_id"], qty))

        # ── Ejecutar la IPO / deslistado ───────────────────────────────────────
        removed = add_ipo_stock(symbol, data)

        # ── Pagar y limpiar tenedores de la acción deslistada ─────────────────
        paid_out = 0
        if removed and holders:
            from utils.economy import update_wallet
            for user_id, qty in holders:
                payout = delisted_price * qty
                if payout > 0:
                    update_wallet(user_id, payout)
                    paid_out += 1
                # Eliminar la acción deslistada de la cartera del usuario
                user_stocks_col.update_one(
                    {"_id": user_id},
                    {"$unset": {f"stocks.{removed}": ""}},
                )
                # Enviar MD al usuario
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    dm_embed = discord.Embed(
                        title="📉 Tu acción ha sido deslistada",
                        description=(
                            f"**{removed}** era la empresa con peor rendimiento del mercado "
                            f"y ha sido eliminada tras una nueva IPO.\n\n"
                            f"Tus **{qty}** acción(es) han sido liquidadas automáticamente "
                            f"al último precio conocido de 🪙 **{delisted_price:,}** por acción.\n\n"
                            f"💰 Recibiste: 🪙 **{delisted_price * qty:,}**"
                        ),
                        color=0xE74C3C,
                    )
                    dm_embed.set_footer(text="Los fondos han sido añadidos a tu cartera.")
                    await user.send(embed=dm_embed)
                except Exception:
                    pass  # MD cerrados o usuario no encontrado

        # ── También cancelar alertas y ventas automáticas de la acción deslistada ─────────
        if removed:
            stock_alerts_col.delete_many({"symbol": removed})
            from utils.stocks import autosell_col
            autosell_col.delete_many({"symbol": removed})

        # ── Anuncio ──────────────────────────────────────────────────────────
        embed = discord.Embed(title="🏦 ¡Nueva empresa listada en el mercado!", color=0xF1C40F)
        embed.add_field(name="🆕 Nuevo listado", value=f"**{symbol}** — {data['name']}", inline=False)
        embed.add_field(name="🏭 Sector", value=data["sector"], inline=True)
        embed.add_field(name="💹 Precio inicial", value=f"🪙 {data['initial_price']:,}", inline=True)
        embed.add_field(name="📊 Volatilidad", value=f"{data['volatility']:.0%}", inline=True)
        embed.add_field(name="📝 Acerca de", value=data["description"], inline=False)
        if removed:
            holder_note = f"\n👥 {paid_out} tenedor(es) fueron pagados automáticamente y notificados." if holders else ""
            embed.add_field(
                name="📉 Deslistada (peor rendimiento)",
                value=f"**{removed}** ha sido eliminada del mercado.{holder_note}",
                inline=False,
            )
        embed.set_footer(text="Las noticias del mercado ya pueden afectar a esta empresa.")

        STOCK_NEWS_CHANNEL_ID = 1513755454029959239
        channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
        if channel and channel.id != ctx.channel.id:
            await channel.send(embed=embed)

        await ctx.send(embed=embed)


    # ── !raise ────────────────────────────────────────────────────────────────

    @commands.command(name="raise", hidden=True)
    async def stock_raise(self, ctx: commands.Context, symbol: str, amount: int):
        """Solo propietario: sube manualmente el precio de una acción en <amount>."""
        if ctx.author.id not in OWNER_IDS:
            return

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Acción desconocida `{symbol}`.", delete_after=5)

        from utils.stocks import stocks_col
        history = stocks_col.find_one({"symbol": symbol})
        if not history or not history.get("prices"):
            return await ctx.send(f"❌ Sin historial de precios para `{symbol}`.", delete_after=5)

        current = history["prices"][-1]["price"]
        new_price = max(50, current + amount)
        new_entry = {"price": new_price, "timestamp": time.time()}

        prices = history["prices"] + [new_entry]
        stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": prices}})

        direction = "📈" if amount >= 0 else "📉"
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass
        await ctx.send(
            f"{direction} **{symbol}** {current:,} → **{new_price:,}** ({'+' if amount >= 0 else ''}{amount:,})",
            delete_after=10,
        )

        # Verificar ventas automáticas inmediatamente para que las órdenes se ejecuten en subidas manuales también
        try:
            await check_autosells(self.bot)
        except Exception as e:
            print(f"[raise] error en check_autosells: {e}")


async def setup(bot):
    await bot.add_cog(Stocks(bot))
