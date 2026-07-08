"""
Cog de Negocios - Interfaz de Discord para el Sistema de Negocios completo.
Comandos agrupados bajo /business (híbrido: slash + prefijo).
"""
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import time as _time
from database import pets_col, eco_col
from utils.economy import get_wallet, update_wallet
from utils.pets import get_current_hunger
from utils.business import (
  BUSINESS_TYPES,
  get_business, get_owner_businesses,
  compute_income, collect_income,
  buy_business, apply_upgrade,
  hire_worker, fire_worker,
  sell_business, rename_business,
  visit_business, increment_visits,
  get_leaderboard, get_xp_for_next_level,
  XP_PER_LEVEL, businesses_col,
)


# ─────────────────────────────────────────────────────────
# VISTAS
# ─────────────────────────────────────────────────────────

class BusinessListView(discord.ui.View):
  """Embed paginado que muestra todos los negocios de un usuario."""
  PER_PAGE = 4

  def __init__(self, ctx: commands.Context, businesses: list[dict]):
      super().__init__(timeout=60)
      self.ctx        = ctx
      self.businesses = businesses
      self.page       = 0
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(view=None)
          except Exception:
              pass

  def max_pages(self) -> int:
      return max(1, (len(self.businesses) + self.PER_PAGE - 1) // self.PER_PAGE)

  def build_embed(self) -> discord.Embed:
      embed = discord.Embed(
          title=f"\U0001f3e2 Negocios de {self.ctx.author.display_name}",
          color=0x2ECC71,
      )
      start = self.page * self.PER_PAGE
      for b in self.businesses[start : start + self.PER_PAGE]:
          btype = BUSINESS_TYPES[b["type"]]
          info  = compute_income(b)
          embed.add_field(
              name=f'{btype["emoji"]} {b["name"]} (Nv.{b["level"]})',
              value=(
                  f'\U0001f194 `{b["_id"]}`\n'
                  f'\U0001f4c8 Pendiente: \U0001fa99 **{info["net"]:,}** ({info["hours_pending"]:.1f}h)\n'
                  f'\u2b50 Rep: {b.get("reputation", 50)}/100  '
                  f'\U0001f477 Trabajadores: {len(b["workers"])}/{btype["max_workers"]}'
              ),
              inline=False,
          )
      embed.set_footer(text=f'Página {self.page+1}/{self.max_pages()} \u2022 /business info <id> para detalles completos')
      return embed

  async def _guard(self, interaction: discord.Interaction) -> bool:
      if str(interaction.user.id) != str(self.ctx.author.id):
          await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
          return False
      return True

  @discord.ui.button(label="\u25c4", style=discord.ButtonStyle.secondary)
  async def prev_page(self, interaction: discord.Interaction, _: discord.ui.Button):
      if not await self._guard(interaction):
          return
      self.page = max(0, self.page - 1)
      await interaction.response.edit_message(embed=self.build_embed(), view=self)

  @discord.ui.button(label="\u25ba", style=discord.ButtonStyle.secondary)
  async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button):
      if not await self._guard(interaction):
          return
      self.page = min(self.max_pages() - 1, self.page + 1)
      await interaction.response.edit_message(embed=self.build_embed(), view=self)


class SellConfirmView(discord.ui.View):
  def __init__(self, ctx: commands.Context, business_id: str, sell_price: int, name: str):
      super().__init__(timeout=30)
      self.ctx         = ctx
      self.business_id = business_id
      self.sell_price  = sell_price
      self.name        = name
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ Esta confirmación ha expirado.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.button(label="\u2705 Confirmar Venta", style=discord.ButtonStyle.danger)
  async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
      result = sell_business(self.business_id)
      if "error" in result:
          return await interaction.response.edit_message(content=f'\u274c {result["error"]}', view=None, embed=None)
      update_wallet(str(interaction.user.id), result["sell_price"])
      embed = discord.Embed(
          title="\U0001f4b0 ¡Negocio Vendido!",
          description=f'Vendiste **{result["name"]}** por \U0001fa99 **{result["sell_price"]:,}**.\nFondos añadidos a tu cartera.',
          color=0xE74C3C,
      )
      await interaction.response.edit_message(embed=embed, view=None)

  @discord.ui.button(label="\u274c Cancelar", style=discord.ButtonStyle.secondary)
  async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
      await interaction.response.edit_message(content="Venta cancelada.", embed=None, view=None)


class HireConfirmView(discord.ui.View):
  def __init__(self, ctx: commands.Context, business_id: str, worker: dict, hire_cost: int):
      super().__init__(timeout=30)
      self.ctx         = ctx
      self.business_id = business_id
      self.worker      = worker
      self.hire_cost   = hire_cost
      self._confirmed  = False
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ Esta confirmación ha expirado.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.button(label="\u2705 Contratar", style=discord.ButtonStyle.green)
  async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
      self._confirmed = True
      w = self.worker
      update_wallet(str(interaction.user.id), -self.hire_cost)
      embed = discord.Embed(
          title="\U0001f477 ¡Trabajador Contratado!",
          description=(
              f'**{w["name"]}** ({w["role"]}) se unió a tu negocio!\n\n'
              f'\U0001fa99 Salario: {w["salary"]:,}/h\n'
              f'\u2699\ufe0f Eficiencia: {w["efficiency"]:.2f}x\n'
              f'\U0001fa99 Tasa de contratación deducida: **{self.hire_cost:,}**'
          ),
          color=0x2ECC71,
      )
      await interaction.response.edit_message(embed=embed, view=None)

  @discord.ui.button(label="\u274c Cancelar", style=discord.ButtonStyle.secondary)
  async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
      if not self._confirmed:
          b = get_business(self.business_id)
          if b and b.get("workers"):
              workers = b["workers"]
              workers.pop()
              businesses_col.update_one({"_id": self.business_id}, {"$set": {"workers": workers}})
      await interaction.response.edit_message(content="Contratación cancelada.", embed=None, view=None)


class VisitView(discord.ui.View):
  """Menú de selección para visitar el negocio de otro jugador y pagar la tarifa de entrada."""

  def __init__(self, ctx: commands.Context, owner: discord.Member, businesses: list[dict]):
      super().__init__(timeout=60)
      self.ctx   = ctx
      self.owner = owner
      self.message: discord.Message | None = None
      options = []
      for b in businesses[:25]:
          btype = BUSINESS_TYPES[b["type"]]
          fee   = btype.get("entry_fee", 0)
          options.append(discord.SelectOption(
              label=f'{b["name"][:50]} (Nv.{b["level"]})',
              description=f'{btype["name"]} \u2022 Entrada: \U0001fa99 {fee:,}',
              value=b["_id"],
              emoji=btype["emoji"],
          ))
      self.select.options = options

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ Este menú de visita ha expirado.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.select(placeholder="Elige un negocio para visitar\u2026", min_values=1, max_values=1)
  async def select(self, interaction: discord.Interaction, sel: discord.ui.Select):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Este menú no es tuyo.", ephemeral=True)
      await interaction.response.defer()
      business_id = sel.values[0]
      b = get_business(business_id)
      if not b:
          return await interaction.followup.send("\u274c Negocio no encontrado.", ephemeral=True)
      btype    = BUSINESS_TYPES[b["type"]]
      fee      = btype.get("entry_fee", 0)
      visitor  = str(interaction.user.id)
      owner_id = b["owner_id"]
      if visitor == owner_id:
          return await interaction.followup.send("\u274c Ese es tu propio negocio.", ephemeral=True)
      wallet = get_wallet(visitor)
      if wallet < fee:
          return await interaction.followup.send(
              f"\u274c Necesitas \U0001fa99 **{fee:,}** y tienes \U0001fa99 {wallet:,}.",
              ephemeral=True,
          )
      result = visit_business(visitor, business_id)
      if "error" in result:
          return await interaction.followup.send(f'\u274c {result["error"]}', ephemeral=True)

      # ── Descontar tarifa de entrada y pagar al dueño ──────────────────────
      update_wallet(visitor,  -fee)
      update_wallet(owner_id,  fee)

      # ── Aplicar beneficio del visitante ─────────────────────────────────
      benefit      = result.get("visit_benefit", {"type": "none", "value": 0})
      benefit_type = benefit.get("type", "none")
      benefit_val  = benefit.get("value", 0)
      benefit_line = ""

      if benefit_type == "feed_pets":
          # Alimentar todas las mascotas del visitante
          owner_data = pets_col.find_one({"_id": visitor})
          if owner_data and owner_data.get("pets"):
              pets = owner_data["pets"]
              now  = _time.time()
              fed_count = 0
              for pet in pets:
                  current_hunger = get_current_hunger(pet)
                  new_hunger     = min(100, current_hunger + benefit_val)
                  pet["hunger"]   = new_hunger
                  pet["last_fed"] = now
                  fed_count += 1
              pets_col.update_one({"_id": visitor}, {"$set": {"pets": pets}})
              benefit_line = f"\U0001f43e **Mascotas alimentadas:** {fed_count} mascota(s) +{benefit_val} de hambre"
          else:
              benefit_line = "\U0001f43e Sin mascotas que alimentar — ¡consigue una mascota para disfrutar este beneficio!"

      elif benefit_type == "coins":
          update_wallet(visitor, benefit_val)
          benefit_line = f"\U0001fa99 **Bonus obtenido:** {benefit_val:,} monedas"

      elif benefit_type == "strength":
          eco_col.update_one(
              {"_id": visitor},
              {"$inc": {"strength": benefit_val}},
              upsert=True,
          )
          user_data = eco_col.find_one({"_id": visitor}) or {}
          total_str = user_data.get("strength", benefit_val)
          benefit_line = f"\U0001f4aa **Fuerza ganada:** +{benefit_val} XP (Total: {total_str:,})"

      embed = discord.Embed(
          title=f'{btype["emoji"]} ¡Visita Completada!',
          description=(
              f'{result["visit_description"]}\n\n'
              f'\U0001f3e2 **{b["name"]}** propiedad de {self.owner.display_name}\n'
              f'\U0001f4b8 Pagaste: \U0001fa99 **{fee:,}**\n'
              f'\U0001f464 El dueño recibió: \U0001fa99 **{fee:,}**\n'
              f'{benefit_line}'
          ),
          color=0x2ecc71,
      )
      embed.set_footer(text=f"Visitas totales: {b.get('visits', 0) + 1:,}")
      await interaction.edit_original_response(embed=embed, view=None)


# ─────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────

class BusinessCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
      self.bot = bot

  @commands.hybrid_group(name="business", description="Gestiona tu imperio de negocios")
  async def business(self, ctx: commands.Context):
      if ctx.invoked_subcommand is None:
          await ctx.send("Usa `/business shop` para ver los tipos o `/business help` para todos los comandos.", ephemeral=True)

  # ── /business shop ────────────────────────────────────
  @business.command(name="shop", description="Ver todos los tipos de negocio disponibles")
  async def business_shop(self, ctx: commands.Context):
      await ctx.defer()
      embed = discord.Embed(
          title="\U0001f3ea Mercado de Negocios",
          description="Usa `/business buy <tipo> [nombre]` para abrir uno.",
          color=0xF39C12,
      )
      for key, b in BUSINESS_TYPES.items():
          embed.add_field(
              name=f'{b["emoji"]} {b["name"]}  `{key}`',
              value=(
                  f'\U0001f4b0 Coste: \U0001fa99 **{b["base_cost"]:,}**\n'
                  f'\U0001f4c8 Ingresos: \U0001fa99 **{b["base_income_per_hour"]:,}**/h\n'
                  f'\U0001f527 Mant: \U0001fa99 **{b["base_maintenance_per_hour"]:,}**/h\n'
                  f'\U0001f477 Máx. trabajadores: **{b["max_workers"]}**'
              ),
              inline=True,
          )
      embed.set_footer(text="El beneficio neto depende del nivel, mejoras, trabajadores y reputación.")
      await ctx.send(embed=embed)

  # ── /business buy ─────────────────────────────────────
  @business.command(name="buy", description="Compra un nuevo negocio")
  @app_commands.describe(type="Tipo de negocio (ej. restaurant, cinema, arcade)", name="Nombre personalizado (opcional)")
  async def business_buy(self, ctx: commands.Context, type: str, *, name: str = ""):
      await ctx.defer()
      btype_key = type.lower().replace(" ", "").replace("_", "").replace("-", "")
      if btype_key not in BUSINESS_TYPES:
          keys = ", ".join(f"`{k}`" for k in BUSINESS_TYPES)
          return await ctx.send(f"\u274c Tipo desconocido. Tipos válidos: {keys}", ephemeral=True)

      btype   = BUSINESS_TYPES[btype_key]
      cost    = btype["base_cost"]
      user_id = str(ctx.author.id)
      wallet  = get_wallet(user_id)

      if wallet < cost:
          return await ctx.send(
              f'\u274c Necesitas \U0001fa99 **{cost:,}** para abrir un {btype["name"]}. Tienes \U0001fa99 {wallet:,}.',
              ephemeral=True,
          )

      name = (name or f"{ctx.author.display_name}'s {btype['name']}")[:40]
      update_wallet(user_id, -cost)
      result = buy_business(user_id, btype_key, name)

      embed = discord.Embed(
          title='\U0001f389 ¡Negocio Abierto!',
          description=(
              f'{btype["emoji"]} ¡Ahora eres dueño de **{name}**!\n\n'
              f'\U0001f4b0 Pagado: \U0001fa99 {cost:,}\n'
              f'\U0001f4c8 Ingresos: \U0001fa99 {btype["base_income_per_hour"]:,}/h\n'
              f'\U0001f527 Mantenimiento: \U0001fa99 {btype["base_maintenance_per_hour"]:,}/h\n'
              f'\U0001f477 Máx. trabajadores: {btype["max_workers"]}\n\n'
              f'\U0001f194 ID del negocio: `{result["business_id"]}`\n'
              f'¡Recoge ingresos con `/business collect`!'
          ),
          color=0x2ECC71,
      )
      await ctx.send(embed=embed)

  # ── /business list ────────────────────────────────────
  @business.command(name="list", description="Ver todos los negocios tuyos o de otro jugador")
  @app_commands.describe(member="Jugador a consultar (por defecto: tú)")
  async def business_list(self, ctx: commands.Context, member: discord.Member = None):
      await ctx.defer()
      target     = member or ctx.author
      businesses = get_owner_businesses(str(target.id))
      pronoun    = "No tienes" if not member else f"{target.display_name} no tiene"
      if not businesses:
          return await ctx.send(f"{pronoun} negocios todavía.", ephemeral=True)
      view = BusinessListView(ctx, businesses)
      view.message = await ctx.send(embed=view.build_embed(), view=view)

  # ── /business info ────────────────────────────────────
  @business.command(name="info", description="Estadísticas completas de un negocio específico")
  @app_commands.describe(business_id="El ID del negocio (ver /business list)")
  async def business_info(self, ctx: commands.Context, business_id: str):
      await ctx.defer()
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)

      btype   = BUSINESS_TYPES[b["type"]]
      info    = compute_income(b)
      level   = b.get("level", 1)
      xp      = b.get("xp", 0)
      next_xp = get_xp_for_next_level(level)
      founded = datetime.fromtimestamp(b["founded_at"], tz=timezone.utc).strftime("%Y-%m-%d")

      if str(ctx.author.id) != b["owner_id"]:
          increment_visits(business_id)

      upgrades_owned = b.get("upgrades", [])
      upg_lines = []
      for uid, upg in btype["upgrades"].items():
          if uid in upgrades_owned:
              status = "\u2705 Comprada"
          elif level < upg["req_level"]:
              status = f'\U0001f512 Nv.{upg["req_level"]} requerido'
          else:
              status = f'\U0001f6d2 \U0001fa99 {upg["cost"]:,}'
          upg_lines.append(f'{upg["emoji"]} **{upg["name"]}** \u2014 {status} (+{int(upg["income_bonus"]*100)}%)')

      workers      = b.get("workers", [])
      worker_lines = [
          f'`#{i}` **{w["name"]}** ({w["role"]}) \u2014 \U0001fa99{w["salary"]:,}/h | \u2699\ufe0f{w["efficiency"]:.2f}x | Nv.{w["level"]}'
          for i, w in enumerate(workers)
      ] or ["*Sin trabajadores contratados.*"]

      embed = discord.Embed(
          title=f'{btype["emoji"]} {b["name"]}',
          description=f'*{btype["description"]}*',
          color=0x3498DB,
      )
      embed.add_field(name="\U0001f4ca Resumen", value=(
          f'\U0001f3c6 Nivel: **{level}** \u2014 XP: {xp}/{next_xp}\n'
          f'\u2b50 Reputación: **{b.get("reputation", 50)}/100**\n'
          f'\U0001f4c5 Fundado: {founded}\n'
          f'\U0001f440 Visitas: {b.get("visits", 0):,}'
      ), inline=False)
      embed.add_field(name="\U0001f4b5 Finanzas", value=(
          f'\U0001f4c8 Bruto ({info["hours_pending"]:.1f}h): \U0001fa99 {info["gross_income"]:,}\n'
          f'\U0001f527 Mantenimiento: \U0001fa99 {info["maintenance"]:,}\n'
          f'\U0001f477 Salarios: \U0001fa99 {info["worker_salaries"]:,}\n'
          f'\U0001f4b0 **Beneficio Neto: \U0001fa99 {info["net"]:,}**\n'
          f'\U0001f4e6 Total ganado: \U0001fa99 {b.get("total_earned", 0):,}'
      ), inline=False)
      embed.add_field(
          name=f'\U0001f3d7\ufe0f Mejoras ({len(upgrades_owned)}/{len(btype["upgrades"])})',
          value="\n".join(upg_lines),
          inline=False,
      )
      embed.add_field(
          name=f'\U0001f477 Trabajadores ({len(workers)}/{btype["max_workers"]})',
          value="\n".join(worker_lines)[:1000],
          inline=False,
      )
      embed.set_footer(text=f"ID del negocio: {business_id}")
      await ctx.send(embed=embed)

  # ── /business collect ─────────────────────────────────
  @business.command(name="collect", description="Recoge ingresos de todos o de un negocio específico")
  @commands.cooldown(1, 1800, commands.BucketType.user)
  @app_commands.describe(business_id="Deja en blanco para recoger de TODOS tus negocios")
  async def business_collect(self, ctx: commands.Context, business_id: str = None):
      await ctx.defer()
      user_id = str(ctx.author.id)
      if business_id:
          b = get_business(business_id)
          if not b:
              return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
          if b["owner_id"] != user_id:
              return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)
          businesses = [b]
      else:
          businesses = get_owner_businesses(user_id)
          if not businesses:
              return await ctx.send("\u274c No tienes ningún negocio.", ephemeral=True)

      total_net = 0
      total_xp  = 0
      level_ups = []
      lines     = []

      for b in businesses:
          btype  = BUSINESS_TYPES[b["type"]]
          result = collect_income(b["_id"])
          net    = max(0, result["net"])
          total_net += net
          total_xp  += result["xp_earned"]
          if result.get("leveled_up"):
              level_ups.append(f'{btype["emoji"]} **{b["name"]}** alcanzó el Nivel {result["new_level"]}! \U0001f389')
          lines.append(f'{btype["emoji"]} **{b["name"]}** \u2014 \U0001fa99 {net:,} (+{result["xp_earned"]} XP)')

      if total_net > 0:
          update_wallet(user_id, total_net)

      embed = discord.Embed(
          title="\U0001f4b0 ¡Ingresos Recogidos!",
          description="\n".join(lines) or "Nada que recoger en este momento.",
          color=0xF1C40F,
      )
      embed.add_field(name="\U0001f4b5 Total", value=f"\U0001fa99 **{total_net:,}**", inline=True)
      embed.add_field(name="\u2b50 XP",        value=f"**+{total_xp}**",              inline=True)
      if level_ups:
          embed.add_field(name="\U0001f3c6 ¡Subida de Nivel!", value="\n".join(level_ups), inline=False)
      await ctx.send(embed=embed)

  # ── /business upgrades ────────────────────────────────
  @business.command(name="upgrades", description="Ver todas las mejoras de un negocio")
  @app_commands.describe(business_id="ID del negocio")
  async def business_upgrades(self, ctx: commands.Context, business_id: str):
      await ctx.defer()
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      btype = BUSINESS_TYPES[b["type"]]
      level = b.get("level", 1)
      owned = b.get("upgrades", [])
      embed = discord.Embed(
          title=f'\U0001f3d7\ufe0f Mejoras \u2014 {b["name"]}',
          description=f'Nivel: **{level}**  \u2022  Compra con `/business upgrade {business_id} <id>`',
          color=0x9B59B6,
      )
      for uid, upg in btype["upgrades"].items():
          if uid in owned:
              status = "\u2705 **Comprada**"
          elif level < upg["req_level"]:
              status = f'\U0001f512 Requiere Nivel {upg["req_level"]}'
          else:
              status = f'\U0001f6d2 Comprar por \U0001fa99 {upg["cost"]:,}'
          embed.add_field(
              name=f'{upg["emoji"]} {upg["name"]}  `{uid}`',
              value=f'{status}\n\U0001f4c8 +{int(upg["income_bonus"]*100)}% ingresos',
              inline=True,
          )
      await ctx.send(embed=embed)

  # ── /business upgrade ─────────────────────────────────
  @business.command(name="upgrade", description="Compra una mejora para uno de tus negocios")
  @app_commands.describe(business_id="ID del negocio", upgrade_id="Clave de mejora (ver /business upgrades)")
  async def business_upgrade(self, ctx: commands.Context, business_id: str, upgrade_id: str):
      await ctx.defer()
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)

      btype   = BUSINESS_TYPES[b["type"]]
      upgrade = btype["upgrades"].get(upgrade_id)
      if not upgrade:
          available = ", ".join(f"`{k}`" for k in btype["upgrades"])
          return await ctx.send(f"\u274c Mejora inválida. Disponibles: {available}", ephemeral=True)

      wallet = get_wallet(user_id)
      if wallet < upgrade["cost"]:
          return await ctx.send(
              f'\u274c Necesitas \U0001fa99 **{upgrade["cost"]:,}**. Tienes \U0001fa99 {wallet:,}.', ephemeral=True
          )

      result = apply_upgrade(business_id, upgrade_id)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)

      update_wallet(user_id, -upgrade["cost"])
      embed = discord.Embed(
          title="\U0001f3d7\ufe0f ¡Mejora Aplicada!",
          description=(
              f'{upgrade["emoji"]} **{upgrade["name"]}** instalada en **{b["name"]}**!\n'
              f'\U0001f4c8 Bonus de ingresos: **+{int(upgrade["income_bonus"]*100)}%**\n'
              f'\U0001fa99 Coste: {upgrade["cost"]:,}'
          ),
          color=0x9B59B6,
      )
      await ctx.send(embed=embed)

  # ── /business hire ────────────────────────────────────
  @business.command(name="hire", description="Contrata un trabajador NPC aleatorio para un negocio")
  @app_commands.describe(business_id="ID del negocio")
  async def business_hire(self, ctx: commands.Context, business_id: str):
      await ctx.defer()
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)

      result = hire_worker(business_id)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)

      w, cost = result["worker"], result["hire_cost"]
      wallet  = get_wallet(user_id)
      if wallet < cost:
          b2 = get_business(business_id)
          if b2 and b2.get("workers"):
              workers = b2["workers"]
              workers.pop()
              businesses_col.update_one({"_id": business_id}, {"$set": {"workers": workers}})
          return await ctx.send(
              f'\u274c Necesitas \U0001fa99 **{cost:,}** (tasa de contratación = 5\u00d7 salario por hora). Tienes \U0001fa99 {wallet:,}.',
              ephemeral=True,
          )

      embed = discord.Embed(
          title="\U0001f477 ¡Trabajador Disponible!",
          description=(
              f'**{w["name"]}** quiere unirse como **{w["role"]}**.\n\n'
              f'\U0001fa99 Salario: {w["salary"]:,}/h\n'
              f'\u2699\ufe0f Eficiencia: {w["efficiency"]:.2f}x\n'
              f'\U0001fa99 Tasa de contratación (5\u00d7 salario): **{cost:,}**\n\n'
              f'*El salario se descuenta automáticamente en cada recogida.*'
          ),
          color=0x27AE60,
      )
      view = HireConfirmView(ctx, business_id, w, cost)
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business fire ────────────────────────────────────
  @business.command(name="fire", description="Despide a un trabajador de uno de tus negocios")
  @app_commands.describe(business_id="ID del negocio", worker_index="Número del trabajador (ver /business info)")
  async def business_fire(self, ctx: commands.Context, business_id: str, worker_index: int):
      await ctx.defer()
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)
      result = fire_worker(business_id, worker_index)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)
      w = result["fired"]
      await ctx.send(embed=discord.Embed(
          title="\U0001f534 Trabajador Despedido",
          description=f'**{w["name"]}** ({w["role"]}) ha sido despedido de **{b["name"]}**.',
          color=0xE74C3C,
      ))

  # ── /business sell ────────────────────────────────────
  @business.command(name="sell", description="Vende un negocio y recibe monedas")
  @app_commands.describe(business_id="ID del negocio")
  async def business_sell(self, ctx: commands.Context, business_id: str):
      await ctx.defer()
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)

      btype          = BUSINESS_TYPES[b["type"]]
      upgrades_owned = b.get("upgrades", [])
      upgrade_val    = sum(btype["upgrades"][u]["cost"] for u in upgrades_owned if u in btype["upgrades"])
      level          = b.get("level", 1)
      sell_price     = int((btype["base_cost"] + upgrade_val) * btype["sell_multiplier"] * (1 + (level - 1) * 0.05))

      embed = discord.Embed(
          title="\u26a0\ufe0f ¿Vender Negocio?",
          description=(
              f'¿Vender **{b["name"]}**?\n\n'
              f'\U0001fa99 Recibirás: **{sell_price:,}**\n'
              f'*(60% del coste + mejoras + {(level-1)*5}% de bonus por nivel \u2014 ¡esto no se puede deshacer!)*'
          ),
          color=0xE67E22,
      )
      view = SellConfirmView(ctx, business_id, sell_price, b["name"])
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business rename ──────────────────────────────────
  @business.command(name="rename", description="Dale un nuevo nombre a un negocio")
  @app_commands.describe(business_id="ID del negocio", name="Nuevo nombre (máx. 40 caracteres)")
  async def business_rename(self, ctx: commands.Context, business_id: str, *, name: str):
      await ctx.defer()
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Negocio no encontrado.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c Ese no es tu negocio.", ephemeral=True)
      rename_business(business_id, name[:40])
      await ctx.send(f'\u2705 ¡Renombrado a **{name[:40]}**!', ephemeral=True)

  # ── /business visit ───────────────────────────────────
  @business.command(name="visit", description="Visita el negocio de otro jugador y paga la tarifa de entrada")
  @app_commands.describe(member="El jugador cuyo negocio quieres visitar")
  async def business_visit(self, ctx: commands.Context, member: discord.Member):
      await ctx.defer()
      if member.id == ctx.author.id:
          return await ctx.send("Usa `/business list` para ver tus propios negocios.", ephemeral=True)
      businesses = get_owner_businesses(str(member.id))
      if not businesses:
          return await ctx.send(f"**{member.display_name}** no tiene negocios todavía.", ephemeral=True)

      embed = discord.Embed(
          title=f"\U0001f3e2 Negocios de {member.display_name}",
          description=f"Elige un negocio para visitar. **{member.display_name}** recibirá la tarifa de entrada al instante.",
          color=0x3498DB,
      )
      for b in businesses[:8]:
          btype = BUSINESS_TYPES[b["type"]]
          fee   = btype.get("entry_fee", 0)
          embed.add_field(
              name=f'{btype["emoji"]} {b["name"]} (Nv.{b["level"]})',
              value=(
                  f'\U0001f3ab Entrada: \U0001fa99 **{fee:,}**\n'
                  f'\u2b50 Rep: {b.get("reputation", 50)}/100  '
                  f'\U0001f440 Visitas: {b.get("visits", 0):,}'
              ),
              inline=True,
          )
      embed.set_thumbnail(url=member.display_avatar.url)
      view = VisitView(ctx, member, businesses)
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business leaderboard ─────────────────────────────
  @business.command(name="leaderboard", description="Top 10 negocios por ganancias totales")
  async def business_leaderboard(self, ctx: commands.Context):
      await ctx.defer()
      top    = get_leaderboard(10)
      medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
      embed  = discord.Embed(title="\U0001f3c6 Clasificación de Negocios", color=0xF1C40F)
      for i, b in enumerate(top):
          btype = BUSINESS_TYPES.get(b["type"], {})
          emoji = btype.get("emoji", "\U0001f3e2")
          medal = medals[i] if i < 3 else f"#{i+1}"
          try:
              owner      = await self.bot.fetch_user(int(b["owner_id"]))
              owner_name = owner.display_name
          except Exception:
              owner_name = f'Usuario {b["owner_id"]}'
          embed.add_field(
              name=f'{medal} {emoji} {b["name"]} (Nv.{b.get("level", 1)})',
              value=f'\U0001f464 {owner_name} \u2014 \U0001fa99 {b.get("total_earned", 0):,} ganado',
              inline=False,
          )
      await ctx.send(embed=embed)

  # ── /business help ────────────────────────────────────
  @business.command(name="help", description="Todos los comandos del sistema de negocios explicados")
  async def business_help(self, ctx: commands.Context):
      await ctx.defer()
      embed = discord.Embed(title="\U0001f4d6 Sistema de Negocios \u2014 Comandos", color=0x8E44AD)
      for cmd, desc in [
          ("/business shop",                   "Ver todos los tipos de negocio y precios"),
          ("/business buy <tipo> [nombre]",     "Abrir un nuevo negocio"),
          ("/business list [miembro]",           "Ver tus negocios (o los de alguien)"),
          ("/business info <id>",                "Estadísticas completas: ingresos, trabajadores, mejoras, XP"),
          ("/business collect [id]",             "Recoger ingresos pendientes (todos o uno)"),
          ("/business upgrades <id>",            "Ver todas las mejoras de un negocio"),
          ("/business upgrade <id> <mejora>",    "Comprar una mejora"),
          ("/business hire <id>",                "Contratar un trabajador NPC aleatorio"),
          ("/business fire <id> <#>",            "Despedir a un trabajador por índice"),
          ("/business sell <id>",                "Vender un negocio por monedas"),
          ("/business rename <id> <nombre>",     "Renombrar un negocio"),
          ("/business visit <miembro>",          "Visitar el negocio de otro jugador"),
          ("/business leaderboard",              "Top 10 ganancias globales"),
      ]:
          embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
      embed.set_footer(text="¡Los ingresos se acumulan hasta 24h. Recoge regularmente para ganar XP y reputación!")
      await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
  await bot.add_cog(BusinessCog(bot))
