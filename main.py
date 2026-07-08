import asyncio
import logging

import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

from config import DISCORD_TOKEN, GUILD_ID

logger = logging.getLogger("weekly-xp-bot")

app = Flask("")


@app.route("/")
def home():
    return "Bot activo"


def _run_flask():
    import os
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()


COGS = [
    "cogs.admin",
    "cogs.economy",
    "cogs.pets",
    "cogs.games",
    "cogs.utility",
    "cogs.events",
    "cogs.fake_admin_ai",
    "cogs.starboard",
    "cogs.stocks",
    "cogs.bounties",
    "cogs.business",
    "cogs.troll",
]


class YSLBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="Grinding for YSL"),
            help_command=None,
        )

    async def setup_hook(self) -> None:
        logger.info("Iniciando setup_hook...")
        for cog in COGS:
            logger.info(f"Cargando extensión {cog}...")
            await self.load_extension(cog)
            logger.info(f"Cargado {cog}")
        logger.info("Sincronizando árbol de comandos...")
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info("Comandos slash sincronizados")

        # Verificación global de cárcel — bloquea todos los comandos para usuarios encarcelados
        async def jail_check(ctx: commands.Context) -> bool:
            from utils.economy import is_jailed, JailCheckError
            try:
                release = is_jailed(str(ctx.author.id))
            except Exception:
                # Si la base de datos no está disponible, dejar pasar el comando
                return True
            if release:
                await ctx.send(
                    f"🔒 Estás en la cárcel y no puedes usar comandos hasta <t:{release}:t> (<t:{release}:R>).",
                    ephemeral=True,
                )
                raise JailCheckError("jailed")
            return True

        self.add_check(jail_check)

    async def on_ready(self):
        logger.info(f"✅ Bot conectado como {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Grinding for YSL"),
        )
        print(f"LISTO: {self.user} | {id(self)}")


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Falta la variable de entorno requerida: DISCORD_TOKEN")


async def run_bot() -> None:
    """Inicia el bot, reintentando con retroceso exponencial si Discord devuelve un 429 al iniciar sesión.

    Sin esto, un 429 en el momento del inicio de sesión bloquea el proceso, el host (p. ej. Render)
    lo reinicia inmediatamente, y el nuevo intento vuelve a golpear el endpoint de inicio de sesión
    de inmediato — convirtiendo un bloqueo temporal en un bucle de saturación que mantiene
    el bloqueo activo.
    """
    max_attempts = 6
    base_delay = 60  # segundos

    for attempt in range(1, max_attempts + 1):
        bot = YSLBot()
        try:
            await bot.start(DISCORD_TOKEN)
            return
        except discord.HTTPException as e:
            if e.status != 429:
                await bot.close()
                raise

            retry_after = base_delay * (2 ** (attempt - 1))
            try:
                header_val = e.response.headers.get("Retry-After")
                if header_val:
                    retry_after = max(retry_after, float(header_val))
            except (TypeError, ValueError, AttributeError):
                pass
            retry_after = min(retry_after, 900)

            await bot.close()

            if attempt == max_attempts:
                logger.critical(
                    "Discord sigue limitando los inicios de sesión después de %s intentos. "
                    "Esto suele ser un bloqueo a nivel de IP en las IPs compartidas del proveedor de hosting "
                    "(común en el nivel gratuito de Render), no algo que controle el código del bot. "
                    "Abandonando por ahora — inténtalo más tarde o migra a un host con IP dedicada.",
                    max_attempts,
                )
                raise

            logger.error(
                "Límite de velocidad global de Discord al iniciar sesión (intento %s/%s). Esperando %.0fs antes de reintentar...",
                attempt, max_attempts, retry_after,
            )
            await asyncio.sleep(retry_after)


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    asyncio.run(run_bot())
