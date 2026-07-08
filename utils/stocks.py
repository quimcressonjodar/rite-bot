import random
import time
import os
from zoneinfo import ZoneInfo
import matplotlib
# Usar backend Agg para entornos sin pantalla como Render
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import io
import discord
from config import STOCKS, STOCK_HISTORY_LIMIT, STOCK_FEE
from pymongo import MongoClient

# Configuración de MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["protox_bot"]
stocks_col = db["stocks_history"]
user_stocks_col = db["user_stocks"]
stock_alerts_col = db["stock_alerts"]
autosell_col = db["stock_autosells"]
ipo_col = db["ipo_stocks"]


# ---------------------------------------------------------------------------
# IPO – cargar acciones personalizadas persistidas en el diccionario STOCKS al iniciar
# ---------------------------------------------------------------------------

def load_ipo_stocks():
    """Carga las acciones IPO personalizadas desde MongoDB y las inyecta en STOCKS."""
    for doc in ipo_col.find():
        symbol = doc["symbol"]
        if symbol not in STOCKS:
            STOCKS[symbol] = {
                "name": doc["name"],
                "sector": doc.get("sector", "IPO"),
                "volatility": doc.get("volatility", 0.10),
                "initial_price": doc.get("initial_price", 500),
                "description": doc.get("description", "Una nueva empresa en el mercado."),
            }


def add_ipo_stock(symbol: str, data: dict) -> str | None:
    """
    Añade una nueva acción IPO al mercado y elimina la de peor rendimiento.
    Devuelve el símbolo de la empresa eliminada (o None si el mercado estaba vacío).
    """
    worst_symbol = None
    worst_performance = float("inf")
    for s in list(STOCKS.keys()):
        try:
            price = get_current_price(s)
        except Exception:
            price = STOCKS[s]["initial_price"]
        initial = STOCKS[s].get("initial_price", 500)
        # Rendimiento = % de cambio respecto al precio inicial (menor = peor)
        performance = (price - initial) / initial if initial else 0
        if performance < worst_performance:
            worst_performance = performance
            worst_symbol = s

    # Eliminar la peor del diccionario activo, historial de precios y registro IPO
    if worst_symbol:
        STOCKS.pop(worst_symbol, None)
        stocks_col.delete_one({"symbol": worst_symbol})
        ipo_col.delete_one({"symbol": worst_symbol})

    # Añadir nueva acción al diccionario activo
    STOCKS[symbol] = data

    # Persistir en la colección IPO para que sobreviva a reinicios del bot
    ipo_col.update_one(
        {"symbol": symbol},
        {"$set": {"symbol": symbol, **data}},
        upsert=True,
    )

    # Inicializar historial de precios con dos puntos idénticos (el gráfico necesita >= 2)
    stocks_col.delete_one({"symbol": symbol})
    stocks_col.insert_one({
        "symbol": symbol,
        "prices": [
            {"price": data["initial_price"], "timestamp": time.time() - 60},
            {"price": data["initial_price"], "timestamp": time.time()},
        ],
    })

    return worst_symbol


# ---------------------------------------------------------------------------
# Helpers de precio
# ---------------------------------------------------------------------------

def get_current_price(symbol):
    """Obtiene el último precio de un símbolo de acción."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or not history.get("prices"):
        return STOCKS[symbol]["initial_price"]
    return history["prices"][-1]["price"]


def update_stock_prices(news_impact=None):
    """Actualiza los precios de todas las acciones usando lógica de Movimiento Browniano Geométrico."""
    if news_impact is None:
        news_impact = {}

    for symbol, config in STOCKS.items():
        multiplier = news_impact.get(symbol, 1.0) * news_impact.get("ALL", 1.0)
        history = stocks_col.find_one({"symbol": symbol})
        if not history:
            prices = [{"price": config["initial_price"], "timestamp": time.time()}]
            stocks_col.insert_one({"symbol": symbol, "prices": prices})
            continue

        current_prices = history.get("prices", [])
        last_price = current_prices[-1]["price"]

        drift = 0.005
        volatility = config["volatility"]
        amplified_multiplier = 1.0 + (multiplier - 1.0) * 1.5

        change = random.normalvariate(drift, volatility)
        new_price = max(50, int(last_price * (1 + change) * amplified_multiplier))

        new_entry = {"price": new_price, "timestamp": time.time()}
        current_prices.append(new_entry)

        if len(current_prices) > STOCK_HISTORY_LIMIT:
            current_prices = current_prices[-STOCK_HISTORY_LIMIT:]

        stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": current_prices}})


# ---------------------------------------------------------------------------
# Generación de gráficos
# ---------------------------------------------------------------------------

def generate_stock_chart(symbol):
    """Genera un gráfico PNG de las últimas 24h para un símbolo y lo devuelve como discord.File."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or len(history.get("prices", [])) < 2:
        return None

    # Conservar solo los datos de las últimas 24 horas; usar los últimos 2 puntos si no hay suficientes
    cutoff = time.time() - 86400
    all_prices = history["prices"]
    recent = [p for p in all_prices if p["timestamp"] >= cutoff]
    if len(recent) < 2:
        recent = all_prices[-2:]

    spain_tz = ZoneInfo("Europe/Madrid")
    prices = [p["price"] for p in recent]
    timestamps = [
        pd.to_datetime(p["timestamp"], unit='s', utc=True).tz_convert(spain_tz)
        for p in recent
    ]

    df = pd.DataFrame({"timestamp": timestamps, "price": prices})

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))

    for i in range(len(prices) - 1):
        segment_color = '#2ecc71' if prices[i + 1] >= prices[i] else '#e74c3c'
        ax.plot(df['timestamp'][i:i + 2], df['price'][i:i + 2], color=segment_color, linewidth=2)

    trend_color = '#2ecc71' if prices[-1] >= prices[0] else '#e74c3c'
    ax.fill_between(df['timestamp'], df['price'], alpha=0.1, color=trend_color)

    ax.set_title(f"{STOCKS[symbol]['name']} ({symbol})", fontsize=16, color='white', pad=20)
    ax.set_ylabel("Precio (Monedas)", color='white')
    ax.grid(True, alpha=0.2)

    time_range = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    if time_range > 86400:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M', tz=spain_tz))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=spain_tz))
    fig.autofmt_xdate(rotation=45)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)

    return discord.File(fp=buf, filename=f"{symbol}_chart.png")


# ---------------------------------------------------------------------------
# Helpers de cartera
# ---------------------------------------------------------------------------

def get_user_portfolio(user_id):
    portfolio = user_stocks_col.find_one({"_id": user_id})
    return portfolio.get("stocks", {}) if portfolio else {}


def buy_stock(user_id, symbol, quantity, price):
    # Asegurarse de que el documento del usuario existe
    user_stocks_col.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"stocks": {}}},
        upsert=True,
    )

    # Leer solo los datos del símbolo actual para calcular el nuevo avg_price
    portfolio = user_stocks_col.find_one({"_id": user_id})
    current = portfolio.get("stocks", {}).get(symbol, {"quantity": 0, "avg_price": 0})

    new_quantity = current["quantity"] + quantity
    new_avg_price = (
        (current["quantity"] * current["avg_price"]) + (quantity * price)
    ) / new_quantity

    # Usar $set con notación de punto para escribir SOLO los campos de este símbolo,
    # sin tocar ningún otro símbolo de la cartera del usuario.
    user_stocks_col.update_one(
        {"_id": user_id},
        {"$set": {
            f"stocks.{symbol}.quantity": new_quantity,
            f"stocks.{symbol}.avg_price": new_avg_price,
        }},
    )


def sell_stock(user_id, symbol, quantity):
    portfolio = user_stocks_col.find_one({"_id": user_id})
    if not portfolio or symbol not in portfolio.get("stocks", {}):
        return False

    current_qty = portfolio["stocks"][symbol]["quantity"]
    if current_qty < quantity:
        return False

    new_qty = current_qty - quantity
    if new_qty == 0:
        # Eliminar el símbolo completamente usando $unset
        user_stocks_col.update_one(
            {"_id": user_id},
            {"$unset": {f"stocks.{symbol}": ""}},
        )
    else:
        user_stocks_col.update_one(
            {"_id": user_id},
            {"$set": {f"stocks.{symbol}.quantity": new_qty}},
        )
    return True


def get_dividend_rate(symbol: str) -> tuple[float, float]:
    """
    Calcula la tasa de dividendo de una acción basada en su rendimiento de precio en 24h.
    Devuelve (tasa, rendimiento_pct) donde la tasa está entre 0.0005 y 0.02.

    Fórmula: tasa = clamp(0.003 + rendimiento * 0.10, 0.0005, 0.02)
    Ejemplos:
      +10% ganancia  → 0.003 + 0.10*0.10 = 1.3%
      plano          → 0.3%
      -10% pérdida   → limitado a 0.05% (mínimo)
    """
    history = stocks_col.find_one({"symbol": symbol})
    if not history or len(history.get("prices", [])) < 2:
        return 0.003, 0.0  # tasa base por defecto si no hay historial

    prices = history["prices"]
    current_price = prices[-1]["price"]
    cutoff = time.time() - 86400  # hace 24 horas

    # Encontrar el precio más antiguo dentro de las últimas 24h; usar el más antiguo disponible como respaldo
    price_24h_ago = None
    for entry in prices:
        if entry["timestamp"] >= cutoff:
            price_24h_ago = entry["price"]
            break
    if price_24h_ago is None:
        price_24h_ago = prices[0]["price"]

    if price_24h_ago == 0:
        return 0.003, 0.0

    performance = (current_price - price_24h_ago) / price_24h_ago
    rate = max(0.0005, min(0.02, 0.003 + performance * 0.10))
    return rate, performance


def process_dividends():
    """
    Paga dividendos proporcionales a todos los accionistas.
    La tasa de cada acción depende de su rendimiento en 24h (0,05% – 2%).
    Devuelve (usuarios_pagados, total_distribuido, tasas_por_símbolo).
    """
    from utils.economy import update_wallet

    # Pre-calcular tasas para cada acción listada
    rates = {}
    for symbol in STOCKS:
        rate, perf = get_dividend_rate(symbol)
        rates[symbol] = {"rate": rate, "performance": perf}

    all_portfolios = user_stocks_col.find()
    total_distributed = 0
    users_paid = 0

    for portfolio in all_portfolios:
        user_id = portfolio["_id"]
        stocks_data = portfolio.get("stocks", {})
        user_total_dividend = 0

        for symbol, data in stocks_data.items():
            if symbol not in STOCKS:
                continue
            current_price = get_current_price(symbol)
            rate = rates[symbol]["rate"]
            dividend = int(current_price * data["quantity"] * rate)
            user_total_dividend += dividend

        if user_total_dividend > 0:
            update_wallet(user_id, user_total_dividend)
            total_distributed += user_total_dividend
            users_paid += 1

    return users_paid, total_distributed, rates


# ---------------------------------------------------------------------------
# Sistema de Alertas de Precio
# ---------------------------------------------------------------------------

def add_price_alert(user_id: str, symbol: str, target_price: int) -> int:
    """
    Guarda una alerta de precio. La dirección se infiere del precio actual vs objetivo.
    Devuelve el ID secuencial corto (1, 2, 3, ...) específico para este usuario.
    """
    current_price = get_current_price(symbol)
    direction = "above" if target_price > current_price else "below"
    # Calcular el siguiente ID corto para este usuario
    existing = list(stock_alerts_col.find({"user_id": user_id}, {"seq": 1}))
    used_seqs = [a.get("seq", 0) for a in existing]
    seq = 1
    while seq in used_seqs:
        seq += 1
    stock_alerts_col.insert_one({
        "user_id": user_id,
        "seq": seq,
        "symbol": symbol,
        "target_price": target_price,
        "direction": direction,
        "created_at": time.time(),
    })
    return seq


def get_user_alerts(user_id: str) -> list:
    alerts = list(stock_alerts_col.find({"user_id": user_id}))
    # Rellenar seq para alertas antiguas creadas antes de que existiera el campo seq
    used_seqs = {a["seq"] for a in alerts if "seq" in a}
    next_seq = 1
    for a in alerts:
        if "seq" not in a:
            while next_seq in used_seqs:
                next_seq += 1
            stock_alerts_col.update_one({"_id": a["_id"]}, {"$set": {"seq": next_seq}})
            a["seq"] = next_seq
            used_seqs.add(next_seq)
            next_seq += 1
    return sorted(alerts, key=lambda a: a["seq"])


def remove_alert_by_seq(user_id: str, seq: int) -> dict | None:
    """Elimina la alerta por ID corto. Devuelve el documento si se encuentra, o None."""
    alert = stock_alerts_col.find_one({"user_id": user_id, "seq": seq})
    if alert:
        stock_alerts_col.delete_one({"_id": alert["_id"]})
    return alert


async def check_price_alerts(bot):
    """
    Se llama tras cada actualización de precio de acciones.
    Envía un MD a los usuarios cuya alerta de precio se ha activado y luego la elimina.
    """
    alerts = list(stock_alerts_col.find())
    for alert in alerts:
        symbol = alert["symbol"]
        if symbol not in STOCKS:
            continue
        try:
            current_price = get_current_price(symbol)
        except Exception:
            continue

        triggered = (
            (alert["direction"] == "above" and current_price >= alert["target_price"]) or
            (alert["direction"] == "below" and current_price <= alert["target_price"])
        )
        if not triggered:
            continue

        try:
            user = await bot.fetch_user(int(alert["user_id"]))
            arrow = "📈" if alert["direction"] == "above" else "📉"
            verb = "alcanzó" if alert["direction"] == "above" else "bajó a"
            color = 0x2ECC71 if alert["direction"] == "above" else 0xE74C3C
            embed = discord.Embed(
                title="🔔 ¡Alerta de precio activada!",
                description=(
                    f"{arrow} **{symbol}** ha {verb} tu objetivo de 🪙 **{alert['target_price']:,}**\n\n"
                    f"💹 Precio actual: 🪙 **{current_price:,}**"
                ),
                color=color,
            )
            embed.set_footer(text="Esta alerta ha sido eliminada automáticamente.")
            await user.send(embed=embed)
        except Exception:
            pass  # MD cerrados o usuario no encontrado

        stock_alerts_col.delete_one({"_id": alert["_id"]})


# ---------------------------------------------------------------------------
# Sistema de Órdenes de Venta Automática
# ---------------------------------------------------------------------------

def add_autosell(user_id: str, symbol: str, quantity: int, target_price: int) -> int:
    """
    Guarda una orden de venta automática. Se activa cuando precio >= target_price.
    Devuelve el ID secuencial corto específico para este usuario.
    """
    existing = list(autosell_col.find({"user_id": user_id}, {"seq": 1}))
    used_seqs = [a.get("seq", 0) for a in existing]
    seq = 1
    while seq in used_seqs:
        seq += 1
    autosell_col.insert_one({
        "user_id": user_id,
        "seq": seq,
        "symbol": symbol,
        "quantity": quantity,
        "target_price": target_price,
        "created_at": time.time(),
    })
    return seq


def get_user_autosells(user_id: str) -> list:
    orders = list(autosell_col.find({"user_id": user_id}))
    return sorted(orders, key=lambda a: a["seq"])


def remove_autosell_by_seq(user_id: str, seq: int) -> dict | None:
    """Elimina la orden de venta automática por ID corto. Devuelve el documento si se encuentra, o None."""
    order = autosell_col.find_one({"user_id": user_id, "seq": seq})
    if order:
        autosell_col.delete_one({"_id": order["_id"]})
    return order


async def check_autosells(bot):
    """
    Se llama tras cada actualización de precio de acciones.
    Ejecuta las órdenes de venta automática pendientes cuyo precio objetivo ha sido alcanzado,
    acredita la cartera del usuario y envía un MD de confirmación.
    """
    from utils.economy import update_wallet, get_wallet, get_bank, get_prestige_level

    orders = list(autosell_col.find())
    for order in orders:
        symbol = order["symbol"]
        if symbol not in STOCKS:
            continue
        try:
            current_price = get_current_price(symbol)
        except Exception:
            continue

        if current_price < order["target_price"]:
            continue

        # El precio ha alcanzado el objetivo — ejecutar la venta
        user_id = order["user_id"]
        quantity = order["quantity"]

        portfolio = get_user_portfolio(user_id)
        owned = portfolio.get(symbol, {}).get("quantity", 0)
        avg_price = portfolio.get(symbol, {}).get("avg_price", 0)

        sell_qty = min(quantity, owned)
        if sell_qty <= 0:
            # El usuario ya no tiene acciones — eliminar la orden obsoleta silenciosamente
            autosell_col.delete_one({"_id": order["_id"]})
            continue

        # Aplicar la misma lógica de comisión que en las ventas manuales
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)
        fee_multiplier = max(0, 1 - (level * 0.15))
        current_fee = STOCK_FEE * fee_multiplier

        total_gain = int(current_price * sell_qty * (1 - current_fee))
        profit = int((current_price - avg_price) * sell_qty)
        fee_paid = int(current_price * sell_qty * current_fee)

        try:
            sold = sell_stock(user_id, symbol, sell_qty)
        except Exception as e:
            print(f"[autosell] error en sell_stock para {user_id} {symbol}: {e}")
            continue

        if sold:
            update_wallet(user_id, total_gain)

            try:
                user = await bot.fetch_user(int(user_id))

                if profit > 0:
                    result_line = f"📈 **+🪙 {profit:,}** de beneficio"
                    color = 0x2ECC71
                    title = "✅ Venta automática ejecutada — Beneficio"
                elif profit < 0:
                    result_line = f"📉 **-🪙 {abs(profit):,}** de pérdida"
                    color = 0xE74C3C
                    title = "✅ Venta automática ejecutada — Pérdida"
                else:
                    result_line = "➡️ Sin ganancia ni pérdida"
                    color = 0x95A5A6
                    title = "✅ Venta automática ejecutada"

                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="📦 Acciones vendidas", value=f"**{sell_qty}x {symbol}**", inline=True)
                embed.add_field(name="💰 Recibido", value=f"🪙 {total_gain:,}", inline=True)
                embed.add_field(
                    name="📊 Venta vs precio medio de compra",
                    value=f"🪙 {current_price:,} → media 🪙 {int(avg_price):,}",
                    inline=False,
                )
                embed.add_field(name="📈 Resultado", value=result_line, inline=False)
                footer = f"Objetivo: 🪙 {order['target_price']:,}"
                if fee_paid > 0:
                    footer += f" • Comisión aplicada: 🪙 {fee_paid:,}"
                embed.set_footer(text=footer)
                await user.send(embed=embed)
            except Exception as e:
                print(f"[autosell] error al enviar MD a {user_id}: {e}")

            # Solo eliminar la orden tras una venta confirmada exitosa
            autosell_col.delete_one({"_id": order["_id"]})
        else:
            print(f"[autosell] sell_stock devolvió False para {user_id} {symbol} qty={sell_qty} owned={owned}")
