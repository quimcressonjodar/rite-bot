import time
import platform
import discord
from discord import app_commands
from discord.ext import commands

from database import tutorial_col


# ---------------------------------------------------------------------------
# Definición de pasos del tutorial
# Cada paso:
#   watch    — nombre del comando que el bot espera (coincidencia exacta, sin prefijo)
#   embed_fn — función() -> discord.Embed enviado como instrucción "hazlo ahora"
# ---------------------------------------------------------------------------

def _e(title: str, desc: str, color: int, fields: list[tuple]) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    for name, value in fields:
        e.add_field(name=name, value=value, inline=False)
    return e


STEPS: list[dict] = [
    # ── Paso 0 ──────────────────────────────────────────────────────────────
    {
        "watch": "daily",
        "embed": lambda: _e(
            "📅 Paso 1 — Reclama tus monedas diarias",
            (
                "Cada día puedes reclamar monedas gratis solo por aparecer.\n\n"
                "Ve al servidor y escribe:"
            ),
            0x2ECC71,
            [
                ("Comando", "`!daily`"),
                ("Qué hace", "Te da ~1,000 🪙 una vez cada 24 horas. Nunca te lo saltes."),
                ("⏳ Esperando…", "¡Lo detectaré automáticamente y continuaré cuando lo hayas hecho!"),
            ],
        ),
    },
    # ── Paso 1 ──────────────────────────────────────────────────────────────
    {
        "watch": "balance",
        "embed": lambda: _e(
            "💰 Paso 2 — Consulta tu saldo",
            "¡Genial! Ya tienes monedas. Vamos a verlas.",
            0xF1C40F,
            [
                ("Comando", "`!balance`"),
                ("Qué hace", "Muestra tu cartera, banco, patrimonio neto total y nivel de prestigio."),
                ("💡 Consejo", "Cartera = monedas que llevas (pueden robarte). Banco = almacenamiento seguro."),
                ("⏳ Esperando…", "¡Adelante — escribe `!balance` en el servidor!"),
            ],
        ),
    },
    # ── Paso 2 ──────────────────────────────────────────────────────────────
    {
        "watch": "work",
        "embed": lambda: _e(
            "🔨 Paso 3 — Ve a trabajar",
            "Puedes ganar monedas extra trabajando. Tiene un cooldown, pero es 100% seguro — sin riesgo.",
            0xE67E22,
            [
                ("Comando", "`!work`"),
                ("Qué hace", "Elige un trabajo aleatorio y te paga monedas. Ingreso seguro y constante."),
                ("⏳ Esperando…", "¡Escribe `!work` en el servidor!"),
            ],
        ),
    },
    # ── Paso 3 ──────────────────────────────────────────────────────────────
    {
        "watch": "deposit",
        "embed": lambda: _e(
            "🏦 Paso 4 — Deposita tus monedas",
            (
                "Tu cartera está expuesta — cualquiera puede robarte si estás en BUSCADO. "
                "El banco es seguro. Vamos a mover tus monedas allí."
            ),
            0x3498DB,
            [
                ("Comando", "`!deposit all`"),
                ("Qué hace", "Mueve todo desde tu cartera al banco."),
                ("💡 Hazlo siempre", "Después de cada `!work`, `!daily` o gran ganancia — deposita de inmediato."),
                ("⏳ Esperando…", "¡Escribe `!deposit all` en el servidor!"),
            ],
        ),
    },
    # ── Paso 4 ──────────────────────────────────────────────────────────────
    {
        "watch": "bounties",
        "embed": lambda: _e(
            "🎯 Paso 5 — Consulta tus contratos de recompensa",
            (
                "Las recompensas son desafíos a largo plazo que te premian por jugar naturalmente. "
                "Probablemente ya avanzaste en algunos ahora mismo."
            ),
            0xE74C3C,
            [
                ("Comando", "`!bounties`"),
                ("Qué hace", (
                    "Muestra todos los contratos activos y tu progreso personal.\n"
                    "Ejemplos: *trabajar 10 veces*, *atrapar a un criminal*, *ganar en el casino*."
                )),
                ("⚙️ Seguimiento automático", "El progreso se cuenta automáticamente — solo juega normalmente."),
                ("⏳ Esperando…", "¡Escribe `!bounties` en el servidor!"),
            ],
        ),
    },
    # ── Paso 5 ──────────────────────────────────────────────────────────────
    {
        "watch": "stocks",
        "embed": lambda: _e(
            "📈 Paso 6 — Mira el mercado de acciones",
            (
                "Una vez que tengas monedas de sobra, el mercado de acciones es una de las mejores formas "
                "de hacerlas crecer. Los precios se actualizan cada pocos minutos y ganas dividendos diarios."
            ),
            0x1ABC9C,
            [
                ("Comando", "`!stocks`"),
                ("Qué hace", "Lista todas las empresas, su precio actual y variación diaria en %."),
                ("🛒 Para comprar", "`!sbuy <SÍMBOLO> <cantidad>` — ej. `!sbuy PROTOX 10`"),
                ("💼 Tus posiciones", "`!portfolio` — ve tus posiciones y ganancia/pérdida total."),
                ("⏳ Esperando…", "¡Escribe `!stocks` en el servidor para echar un vistazo!"),
            ],
        ),
    },
]

FINAL_EMBED = _e(
    "🎉 ¡Tutorial Completado!",
    (
        "Ya conoces lo básico. Aquí tienes una referencia rápida de todo lo demás:"
    ),
    0xF1C40F,
    [
        ("💸 Más ingresos", "`!weekly` (una vez/semana) • `!claim` (cada hora, si tienes roles)"),
        ("🎰 Casino", "`!blackjack <apuesta>` • `!roulette <apuesta> <elección>` • `!dice <apuesta>`"),
        ("🚨 Crimen", "`!crime` • `!rob @usuario` — arriesgado pero paga más. Estar BUSCADO = otros pueden `!catch` buscarte."),
        ("🐾 Mascotas", "`!shop` → `!buy <mascota>` → `!feed` → `!battle @usuario` → `!adventures <mascota>`"),
        ("🏦 Préstamos", "`!loan <cantidad>` → paga con `!repay <cantidad>` — ¡los intereses crecen con el tiempo!"),
        ("🔔 Alertas de precio", "`!alert <SÍMBOLO> <precio>` — recibe un DM cuando una acción alcance tu objetivo."),
        ("⭐ Prestigio", "Tu rango = tu patrimonio neto total. Mayor prestigio = menores comisiones en acciones."),
        ("📋 Todos los comandos", "Escribe `!help` en cualquier momento para volver a abrir esta referencia."),
    ],
)

# Embed de referencia (mostrado por !help sin flujo de tutorial)
REFERENCE_EMBED = _e(
    "📖 Economía — Guía de Comandos",
    "Cada comando explicado. Usa `!tutorial` para el recorrido interactivo paso a paso.",
    0x2B2D31,
    [
        (
            "💰 Ingresos Gratuitos",
            "`!daily` — ~1,000 🪙 cada 24 h\n"
            "`!weekly` — ~25,000 🪙 una vez por semana\n"
            "`!claim` — bono por hora si tienes roles de ingresos de la tienda",
        ),
        (
            "🏦 Saldo y Banca",
            "`!balance` — cartera, banco, patrimonio neto y nivel de prestigio\n"
            "`!deposit <cantidad|all>` — mover monedas de cartera → banco (a salvo de ladrones)\n"
            "`!withdraw <cantidad|all>` — sacar monedas del banco\n"
            "`!pay @usuario <cantidad>` — enviar monedas directamente a alguien\n"
            "`!leaderboard` — jugadores más ricos ordenados por patrimonio neto",
        ),
        (
            "💼 Trabajo y Crimen",
            "`!work` — trabajo aleatorio, gana monedas con cooldown. 100% seguro.\n"
            "`!crime` — intenta un crimen por 2k–6.5k 🪙. Fallas → multa + BUSCADO 🚨\n"
            "`!rob @usuario` — roba de la cartera de alguien. Fallas → multa + BUSCADO 🚨\n"
            "`!catch @usuario` — atrapa a un jugador BUSCADO por una recompensa (cooldown 15 min)\n"
            "⚠️ BUSCADO = cualquiera puede atraparte y llevarse una recompensa de tu cartera. ¡Deposita rápido!",
        ),
        (
            "🎰 Casino",
            "`!blackjack <apuesta>` — supera al croupier hasta 21. Ganar = 2× tu apuesta\n"
            "`!roulette <apuesta> <rojo/negro/par/impar/número/1ª12/2ª12/3ª12>` — hasta 36× de pago\n"
            "`!dice <apuesta>` — juega contra la casa\n"
            "`!claimdrop` — toma un drop global de monedas/ítem antes que nadie (activado por admin)",
        ),
        (
            "🎯 Recompensas",
            "`!bounties` — ver contratos activos y tu progreso en cada uno\n"
            "El progreso se rastrea automáticamente mientras juegas. Ejemplos: *trabajar 10 veces*, "
            "*atrapar a un criminal*, *ganar al blackjack*. Completar un contrato paga una gran recompensa.",
        ),
        (
            "🐾 Mascotas",
            "`!shop` — explorar mascotas, comida y roles en venta\n"
            "`!buy <mascota>` — comprar una mascota (monedas de cartera)\n"
            "`!pets` — ver todas tus mascotas: HP, daño, hambre, estado\n"
            "`!feed <mascota> <comida>` — restaurar hambre (las mascotas hambrientas pierden estadísticas)\n"
            "`!breed <mascota1> <mascota2>` — combinar dos mascotas en una cría más fuerte\n"
            "`!battle @usuario` — tu mascota más fuerte lucha contra la suya. El ganador gana monedas\n"
            "`!adventures <mascota>` — enviar una mascota a buscar monedas, comida o botín raro\n"
            "`!sell_pet <mascota>` — vender una mascota por el 50% de su precio en tienda",
        ),
        (
            "📈 Acciones",
            "`!stocks` — todas las empresas: precio, variación diaria en %\n"
            "`!stocks <SÍMBOLO>` — vista detallada de una acción\n"
            "`!sbuy <SÍMBOLO> <cantidad|all>` — comprar acciones\n"
            "`!ssell <SÍMBOLO> <cantidad|all>` — vender acciones\n"
            "`!portfolio` — tus posiciones, valor actual, ganancia/pérdida total\n"
            "`!alert <SÍMBOLO> <precio>` — alerta por DM cuando una acción alcance tu objetivo\n"
            "`!myalerts` — ver tus alertas activas (muestra ID 1, 2, 3…)\n"
            "`!cancelalert <id>` — eliminar una alerta por su número corto\n"
            "`!autosell <SÍMBOLO> <cantidad> <objetivo>` — venta automática cuando el precio alcance el objetivo\n"
            "`!myautosells` — ver tus órdenes de venta automática pendientes\n"
            "`!cancelautosell <id>` — cancelar una orden de venta automática\n"
            "📅 Dividendos pagados diariamente: 0.05%–2% según el rendimiento de la empresa",
        ),
        (
            "🏦 Préstamos",
            "`!loan <cantidad>` — pedir prestado monedas al instante (los intereses se acumulan con el tiempo)\n"
            "`!repay <cantidad>` — pagar parte o toda tu deuda\n"
            "`!debt` — consultar tu saldo pendiente e intereses acumulados\n"
            "⚠️ La deuda se compone — solo pide prestado si tienes un plan para devolver.",
        ),
        (
            "🎒 Inventario y Tienda",
            "`!inventory` — ítems que posees: comida, botín, valor de reventa\n"
            "`!sell` — vender un ítem de tu inventario por monedas",
        ),
        (
            "⭐ Prestigio y Estadísticas",
            "`!balance` — muestra tu nivel de prestigio (basado en el patrimonio neto total)\n"
            "Mayor prestigio = menores comisiones de trading en acciones (hasta −90% en rango máximo)\n"
            "`!botstats` — ping del bot, tiempo activo, cantidad de servidores\n"
            "`!tutorial` — reiniciar el recorrido interactivo paso a paso",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Funciones auxiliares de DB
# ---------------------------------------------------------------------------

def get_tutorial_state(user_id: str) -> dict | None:
    return tutorial_col.find_one({"_id": user_id})


def set_tutorial_step(user_id: str, step: int, guild_id: int | None = None):
    update: dict = {"step": step, "active": True}
    if guild_id is not None:
        update["guild_id"] = guild_id
    tutorial_col.update_one({"_id": user_id}, {"$set": update}, upsert=True)


def finish_tutorial(user_id: str):
    tutorial_col.update_one(
        {"_id": user_id},
        {"$set": {"active": False}},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    # ── !tutorial ────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="tutorial",
        description="Inicia el tutorial interactivo de economía — el bot te guía paso a paso",
    )
    async def tutorial_command(self, ctx: commands.Context):
        user_id = str(ctx.author.id)

        # Reiniciar / iniciar tutorial (vinculado a este servidor)
        guild_id = ctx.guild.id if ctx.guild else None
        set_tutorial_step(user_id, 0, guild_id=guild_id)

        # Intentar enviar DM al usuario
        try:
            intro = discord.Embed(
                title="🎮 ¡Bienvenido al Tutorial de Economía!",
                description=(
                    f"¡Hola **{ctx.author.display_name}**! Te guiaré por la economía "
                    f"paso a paso.\n\n"
                    "En cada paso te diré exactamente qué comando usar. "
                    "Una vez que lo ejecutes **en el servidor**, lo detectaré automáticamente "
                    "y te enviaré el siguiente paso aquí.\n\n"
                    "¡Empecemos! 👇"
                ),
                color=0xF1C40F,
            )
            await ctx.author.send(embed=intro)
            await ctx.author.send(embed=STEPS[0]["embed"]())
        except discord.Forbidden:
            await ctx.send(
                "❌ ¡No puedo enviarte un DM! Por favor habilita los DMs de miembros del servidor "
                "(Configuración de Usuario → Privacidad y Seguridad) e intenta `!tutorial` de nuevo.",
                ephemeral=True,
            )
            finish_tutorial(user_id)
            return

        # Confirmar en el canal (efímero para no saturar)
        await ctx.send(
            "📬 ¡Revisa tus DMs! Te guiaré por el tutorial allí.",
            ephemeral=True,
        )

    # ── !help (solo referencia) ───────────────────────────────────────────────

    @commands.hybrid_command(
        name="help",
        description="Referencia rápida de comandos. Usa !tutorial para el recorrido interactivo.",
    )
    async def help_command(self, ctx: commands.Context):
        await ctx.send(embed=REFERENCE_EMBED)

    # ── Listener de completado de comandos ──────────────────────────────────

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        state = get_tutorial_state(user_id)
        if not state or not state.get("active"):
            return

        step_idx = state.get("step", 0)
        if step_idx >= len(STEPS):
            return

        expected_cmd = STEPS[step_idx]["watch"]
        if ctx.command is None or ctx.command.name != expected_cmd:
            return

        # Guardia de servidor — solo avanza desde el mismo servidor donde inició el tutorial
        bound_guild = state.get("guild_id")
        if bound_guild and (ctx.guild is None or ctx.guild.id != bound_guild):
            return

        next_idx = step_idx + 1

        try:
            if next_idx >= len(STEPS):
                # Tutorial terminado — marcar como finalizado ANTES de enviar DMs
                finish_tutorial(user_id)
                done = discord.Embed(
                    title="✅ ¡Buen trabajo!",
                    description=f"Completaste el paso {step_idx + 1} — **`!{expected_cmd}`**. ¡Es el último!",
                    color=0x2ECC71,
                )
                await ctx.author.send(embed=done)
                await ctx.author.send(embed=FINAL_EMBED)
            else:
                # Enviar DMs primero; solo persistir nuevo paso si se entregan correctamente
                confirm = discord.Embed(
                    title=f"✅ ¡Paso {step_idx + 1} completado!",
                    description=f"Usaste **`!{expected_cmd}`** — ¡buen trabajo! Esto es lo que sigue:",
                    color=0x2ECC71,
                )
                await ctx.author.send(embed=confirm)
                await ctx.author.send(embed=STEPS[next_idx]["embed"]())
                # DMs entregados exitosamente — ahora persistir
                set_tutorial_step(user_id, next_idx)
        except discord.Forbidden:
            # El usuario cerró los DMs a mitad del tutorial — desactivar para dejar de rastrear
            finish_tutorial(user_id)

    # ── !botstats ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="botstats", description="Muestra estadísticas de rendimiento del bot: ping, tiempo activo y más")
    async def botstats(self, ctx: commands.Context):
        before = time.perf_counter()
        msg = await ctx.send("📡 Midiendo latencia...")
        after = time.perf_counter()
        rest_ping = round((after - before) * 1000)
        ws_ping = round(self.bot.latency * 1000)

        uptime_seconds = int(time.time() - self.start_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_commands = len([c for c in self.bot.commands if not c.hidden])

        def ping_emoji(ms):
            if ms < 80:
                return "🟢"
            elif ms < 200:
                return "🟡"
            else:
                return "🔴"

        embed = discord.Embed(title="🤖 Estadísticas del Bot", color=0x2B2D31)
        embed.add_field(
            name="📡 Latencia",
            value=(
                f"{ping_emoji(ws_ping)} **WebSocket:** `{ws_ping} ms`\n"
                f"{ping_emoji(rest_ping)} **REST API:** `{rest_ping} ms`"
            ),
            inline=False,
        )
        embed.add_field(name="⏱️ Tiempo Activo", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="🏰 Servidores", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Miembros", value=f"`{total_members:,}`", inline=True)
        embed.add_field(name="⚙️ Comandos", value=f"`{total_commands}`", inline=True)
        embed.add_field(name="🐍 Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.set_footer(text=f"Solicitado por {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await msg.edit(content=None, embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
