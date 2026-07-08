import random
import re
import discord
from discord.ext import commands

from config import OWNER_IDS

# ── Transformación UwU ────────────────────────────────────────────────────────

CUTE_REPLACEMENTS = {
    "no": "nyo",
    "you": "chu",
    "love": "wuv",
    "what": "wat",
    "the": "da",
    "that": "dat",
    "this": "dis",
    "is": "ish",
    "are": "awe",
    "was": "waz",
    "sad": "saaad",
    "bad": "baad",
    "mad": "maaad",
    "hi": "hewwo",
    "hello": "hewwo",
    "ok": "owkay",
    "okay": "owkay",
    "please": "pwease",
    "friend": "fwend",
    "cool": "kewl",
    "cute": "kawaii",
    "good": "gweat",
    "sorry": "sowwy",
    "thanks": "thankies",
    "thank you": "thankies",
    "yes": "yesh",
    "nice": "nyice",
    "wow": "wowie",
    "really": "weawwy",
    "right": "wight",
    "little": "wittle",
    "beautiful": "bewwiful",
    "stupid": "stoopid",
    "stop": "stahp",
    "come": "come hewe",
    "bro": "bwoo",
    "dude": "duude",
    "lol": "lolol",
    "lmao": "wmaoo",
    "omg": "owmg",
    "wtf": "wtheck",
    "because": "becuz",
    "when": "wen",
    "why": "wai",
    "how": "howw",
    "just": "juwst",
    "but": "buwt",
    "so": "soo",
    "not": "nwot",
    "my": "mwy",
    "me": "mwe",
    "its": "itz",
    "it": "eet",
    "he": "hee",
    "she": "shee",
    "they": "dey",
    "we": "wee",
    "do": "doo",
    "can": "cwan",
    "will": "wiww",
    "got": "got >w<",
    "going": "goinggg",
    "idk": "idkk uwu",
    "ngl": "ngl bestie",
    "fr": "fwr",
    "bruh": "bwuh",
    "man": "myan",
    "guys": "guyyys",
}

TROLL_EMOJIS = ["🥺", "✨", "😭", "💖", "😳", "🌸", "💕", "🥹", "🫶", "😚", "🐾", "💫"]

UWU_FACES = ["OwO", "UwU", ":3", "^w^", ";;w;;", "uwu", ">w<", "^-^", "x3", "(◡ ω ◡)"]

ROLEPLAY_ACTIONS = [
    "***blushes***", "***screams***", "***sweats***", "***cries***",
    "***runs away***", "***looks at you***", "***screeches***",
    "***whispers to self***", "***wags my tail***", "***boops your nose***",
    "***huggles tightly***", "***nuzzles your necky wecky***",
    "***pounces on you***", "***walks away nervously***", "***smirks smugly***",
]

EXCLAMATION_REPLACEMENTS = {
    "!":  ["!", "!!", "!!!",  "!!11", "!!1!"],
    "?":  ["?", "??", "???", "?!", "?!?1", "?!?!"],
}

TYPO_SWAPS = {
    "a": "aa", "e": "ee", "i": "ii", "o": "oo",
    "s": "ss", "t": "tt", "l": "ll", "n": "nn",
}

# Regex para detectar tokens de Discord que no deben transformarse
_PROTECT_RE = re.compile(
    r'(@everyone|@here)'          # menciones globales
    r'|(<[@#!&][^>]+>)'           # menciones de usuario/canal/rol
    r'|(<a?:[a-zA-Z0-9_]+:\d+>)' # emoji personalizado
    r'|(https?://\S+)'            # URLs
)


def _apply_uwu(text: str) -> str:
    original = text
    # 0. Dividir en tokens protegidos y texto normal para nunca alterar
    #    menciones, emojis personalizados ni URLs.
    parts = []       # lista de (es_protegido, fragmento)
    last = 0
    for m in _PROTECT_RE.finditer(text):
        if m.start() > last:
            parts.append((False, text[last:m.start()]))
        parts.append((True, m.group()))
        last = m.end()
    if last < len(text):
        parts.append((False, text[last:]))

    transformed = []
    for protected, chunk in parts:
        if protected:
            transformed.append(chunk)
            continue

        # 1. Reemplazos de palabras graciosas
        for word, replacement in CUTE_REPLACEMENTS.items():
            chunk = re.sub(rf'\b{re.escape(word)}\b', replacement, chunk, flags=re.IGNORECASE)

        # 2. r / l  →  w  (~85 % de las ocurrencias)
        def maybe_w(mo):
            return ('W' if mo.group().isupper() else 'w') if random.random() < 0.85 else mo.group()
        chunk = re.sub(r'[Rr]', maybe_w, chunk)
        chunk = re.sub(r'[Ll]', maybe_w, chunk)

        # 3. v antes de vocal → w  ("very" → "wery")
        chunk = re.sub(r'[Vv]([aeiouAEIOU])', lambda mo: ('W' if mo.group(0)[0].isupper() else 'w') + mo.group(1), chunk)

        # 4. Sustituciones comunes de patrones de letras (de uwuipy)
        chunk = re.sub(r'ove\b', 'uv', chunk, flags=re.IGNORECASE)
        chunk = re.sub(r'ose\b', 'owse', chunk, flags=re.IGNORECASE)
        chunk = re.sub(r'([Oo])h\b', r'\1wh', chunk)
        chunk = re.sub(r'([Nn])([aeiouAEIOU])', lambda mo: mo.group(1) + 'y' + mo.group(2) if random.random() < 0.5 else mo.group(), chunk)

        # 5. Multiplicación de signos de exclamación
        def multi_exclaim(mo):
            return random.choice(EXCLAMATION_REPLACEMENTS[mo.group()])
        chunk = re.sub(r'[!?]', multi_exclaim, chunk)

        # 6. Errores tipográficos de letras dobles (~55 % de probabilidad por palabra >3 chars)
        words = chunk.split(' ')
        for i, word in enumerate(words):
            if len(word) > 3 and random.random() < 0.55:
                ci = random.randint(0, len(word) - 1)
                c = word[ci].lower()
                if c in TYPO_SWAPS:
                    words[i] = word[:ci] + TYPO_SWAPS[c] + word[ci + 1:]
        chunk = ' '.join(words)

        transformed.append(chunk)

    text = ''.join(transformed)

    # 7. Tartamudeo en la primera palabra real (~25 % de los mensajes)
    if random.random() < 0.25:
        text = re.sub(r'\b([a-zA-Z])([a-zA-Z]{2,})', lambda mo: f'{mo.group(1)}-{mo.group()}', text, count=1)

    # 8. Añadir una cara o emoji al final (85 % cara, 55 % emoji, independientemente)
    suffix = ''
    if random.random() < 0.85:
        suffix += ' ' + random.choice(UWU_FACES)
    if random.random() < 0.55:
        suffix += ' ' + random.choice(TROLL_EMOJIS)
    text = text.rstrip() + suffix

    # 9. Agregar acción de roleplay al inicio (~15 % de los mensajes)
    if random.random() < 0.15:
        text = random.choice(ROLEPLAY_ACTIONS) + ' ' + text

    # 10. Respaldo — si nada cambió, forzar una cara UwU + emoji para que siempre sea visible
    if text.strip() == original.strip():
        text = text.rstrip() + ' ' + random.choice(UWU_FACES) + ' ' + random.choice(TROLL_EMOJIS)

    return text


# ── Cog ───────────────────────────────────────────────────────────────────────

class TrollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Conjunto de IDs de usuarios actualmente en modo impostor
        self.impostor_users: set[int] = set()
        # Caché: channel_id → webhook
        self._webhook_cache: dict[int, discord.Webhook] = {}

    def _is_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id in OWNER_IDS

    # ── Comando !impostor ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="impostor", description="Activa/desactiva el modo impostor para un usuario (solo Owner)")
    @app_commands.describe(member="El miembro al que aplicar el modo impostor")
    async def impostor(self, ctx: commands.Context, member: discord.Member):
        if not self._is_owner(ctx):
            return  # Ignorar silenciosamente — no revelar que el comando existe

        if ctx.interaction is not None:
            await ctx.interaction.response.send_message("✅", ephemeral=True)
        else:
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

        if member.id in self.impostor_users:
            self.impostor_users.discard(member.id)
        else:
            self.impostor_users.add(member.id)

    # ── Función auxiliar de Webhook ─────────────────────────────────────────────

    async def _get_webhook(self, channel: discord.TextChannel) -> discord.Webhook | None:
        """Devuelve un webhook propio del bot para el canal, creándolo si es necesario."""
        cached = self._webhook_cache.get(channel.id)
        if cached is not None:
            return cached
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name == "Logger" and wh.user and wh.user.id == self.bot.user.id:
                    self._webhook_cache[channel.id] = wh
                    return wh
            # No se encontró ninguno — crear uno
            wh = await channel.create_webhook(name="Logger")
            self._webhook_cache[channel.id] = wh
            return wh
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _send_via_webhook(
        self,
        channel: discord.TextChannel,
        content: str,
        username: str,
        avatar_url: str,
        files: list[discord.File] | None = None,
    ) -> bool:
        """Intenta enviar mediante webhook; reintenta una vez si el hook en caché está obsoleto."""
        for attempt in range(2):
            webhook = await self._get_webhook(channel)
            if webhook is None:
                return False
            try:
                await webhook.send(
                    content=content or None,
                    username=username,
                    avatar_url=avatar_url,
                    files=files or [],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return True
            except discord.NotFound:
                self._webhook_cache.pop(channel.id, None)
                # Re-descargar archivos para reintento (ya fueron consumidos)
                if files:
                    return False
            except discord.HTTPException:
                return False
        return False

    # ── Listener de mensajes ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar bots, DMs y usuarios que no están en modo impostor
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if message.author.id not in self.impostor_users:
            return
        # El owner siempre puede usar comandos del bot incluso en modo impostor
        if message.author.id in OWNER_IDS and message.content.startswith("!"):
            return
        # Saltar si no hay nada que reenviar (sin texto ni archivos adjuntos)
        has_text = bool(message.content.strip())
        has_files = bool(message.attachments)
        if not has_text and not has_files:
            return

        transformed = _apply_uwu(message.content) if has_text else ""
        username = message.author.display_name
        avatar_url = message.author.display_avatar.url

        # Descargar archivos adjuntos para resubirlos mediante webhook
        files: list[discord.File] = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        # Enviar PRIMERO — solo eliminar el original si el relay tuvo éxito para evitar pérdida de datos
        sent = await self._send_via_webhook(message.channel, transformed, username, avatar_url, files)
        if sent:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TrollCog(bot))
