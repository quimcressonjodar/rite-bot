import asyncio
import random
import time
import uuid

import discord

import state
from config import PET_SHOP, PET_RARITIES, PET_LOOT_PROBABILITIES, ADVENTURE_LOOT, ADVENTURE_EVENTS, FOOD_ITEMS
from database import eco_col, pets_col
from utils.economy import get_user_data, get_wallet, update_wallet
from utils.pets import get_current_hunger, get_pet_state


async def run_adventure(interaction: discord.Interaction, ctx, selected_pet: dict) -> None:
    # Aplazar inmediatamente para evitar que expire la interacción
    await interaction.response.defer()
    
    try:
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        cooldown = 1800
        now = time.time()
        last_adventure = user_data.get("last_adventure", 0)

        if now - last_adventure < cooldown:
            next_adv_ts = int(last_adventure + cooldown)
            return await interaction.followup.send(
                f"⏳ Tus mascotas están descansando. Inténtalo de nuevo <t:{next_adv_ts}:R>.", ephemeral=True
            )

        # Normalizar el tipo de mascota para las búsquedas
        pet_type = selected_pet["type"].lower()
        rarity = PET_RARITIES.get(pet_type, "basic")
        chances = PET_LOOT_PROBABILITIES.get(
            pet_type, {"common": 80, "rare": 15, "epic": 4, "legendary": 1}
        )

        roll = random.randint(1, 100)
        cumulative = 0
        loot_rarity = "common"
        for r, chance in chances.items():
            cumulative += chance
            if roll <= cumulative:
                loot_rarity = r
                break

        item_name, item_value = random.choice(ADVENTURE_LOOT[loot_rarity])

        bonus_multiplier = {"basic": 1, "rare": 1.5, "epic": 2, "legendary": 4}
        final_value = int(item_value * bonus_multiplier[rarity])
        
        _, penalties = get_pet_state(selected_pet)
        if penalties.get("xp_penalty"):
            final_value = int(final_value * (1 - penalties["xp_penalty"]))

        # ADVENTURE_EVENTS es una lista de dicts
        event = random.choice(ADVENTURE_EVENTS)
        event_text = event["text"]
        
        rarity_colors = {
            "common": 0x95A5A6,
            "rare": 0x3498DB,
            "epic": 0x9B59B6,
            "legendary": 0xF1C40F,
            "godly": 0xFF00FF,
        }
        
        pet_emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
        next_adv_ts = int(now + cooldown)

        embed = discord.Embed(title="🌍 Aventura de Mascota", color=rarity_colors.get(loot_rarity, 0x95A5A6))
        embed.description = (
            f"{pet_emoji} Tu **{pet_type.capitalize()}** {event_text}...\n\n"
            f"🎁 Descubrió:\n"
            f"## {item_name}\n\n"
            f"💰 Vendido por: 🪙 **{final_value:,}**\n\n"
            f"🌍 Tu mascota puede aventurarse de nuevo <t:{next_adv_ts}:R>."
        )
        embed.add_field(name="✨ Rareza del Botín", value=loot_rarity.capitalize())
        embed.add_field(name="🐾 Rareza de la Mascota", value=rarity.capitalize())

        # Actualizar la BD solo después de la generación exitosa
        eco_col.update_one(
            {"_id": user_id},
            {
                "$push": {"inventory": {"name": item_name, "value": final_value, "rarity": loot_rarity}},
                "$set": {"last_adventure": now},
            },
            upsert=True,
        )

        # Rastrear progreso de misión ADVENTURER
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(ctx.bot, user_id, "ADVENTURER", 1)

        await interaction.edit_original_response(content=None, embed=embed, view=None)
        
    except Exception as e:
        import logging
        logging.getLogger("weekly-xp-bot").error(f"ERROR DE AVENTURA: {e}", exc_info=True)
        try:
            await interaction.followup.send(f"❌ Ocurrió un error durante la aventura: {str(e)}", ephemeral=True)
        except:
            pass


async def start_pet_battle(channel, battle_id: str) -> None:
    battle = state.active_battles[battle_id]
    challenger = battle["challenger"]
    opponent = battle["opponent"]
    user_id = str(challenger.id)
    opp_id = str(opponent.id)
    user_pet = battle["challenger_pet"]
    opp_pet = battle["opponent_pet"]

    battle_msg = await channel.send(
        f"⚔️ **¡BATALLA INICIADA!**\n"
        f"{challenger.mention} ({user_pet['type']}) VS {opponent.mention} ({opp_pet['type']})"
    )

    animation_frames = [
        f"⚔️ **¡PELEANDO!**\n{user_pet['type'].capitalize()} se lanza hacia adelante...\n`[▬▬▬       ] 30%`",
        f"⚔️ **¡PELEANDO!**\n{opp_pet['type'].capitalize()} contraataca con fuerza!\n`[▬▬▬▬▬▬    ] 60%`",
        f"⚔️ **¡CHOCANDO!**\nHay polvo por todas partes...\n`[▬▬▬▬▬▬▬▬▬ ] 99%`",
    ]
    for frame in animation_frames:
        await asyncio.sleep(1.2)
        await battle_msg.edit(content=frame)

    # Aplicar penalizaciones
    _, c_penalties = get_pet_state(user_pet)
    _, o_penalties = get_pet_state(opp_pet)

    user_damage = user_pet["damage"]
    if c_penalties.get("damage_penalty"):
        user_damage = int(user_damage * (1 - c_penalties["damage_penalty"]))

    opp_damage = opp_pet["damage"]
    if o_penalties.get("damage_penalty"):
        opp_damage = int(opp_damage * (1 - o_penalties["damage_penalty"]))

    user_power = user_pet["hp"] + user_damage + random.randint(1, 50)
    opp_power = opp_pet["hp"] + opp_damage + random.randint(1, 50)
    bet_amount = random.randint(15000, 30000)

    if user_power >= opp_power:
        winner, loser = challenger, opponent
        winner_id, loser_id = user_id, opp_id
        winner_pet, loser_pet = user_pet, opp_pet
    else:
        winner, loser = opponent, challenger
        winner_id, loser_id = opp_id, user_id
        winner_pet, loser_pet = opp_pet, user_pet

    from utils.economy import update_loan, update_interest
    
    eco_col.update_one({"_id": winner_id}, {"$inc": {"wallet": bet_amount}}, upsert=True)
    
    # Verificar si la billetera quedará en negativo
    from utils.economy import get_user_data as _get
    loser_data_before = _get(loser_id)
    current_wallet = loser_data_before.get("wallet", 0)
    
    if current_wallet < bet_amount:
        debt_incurred = bet_amount - current_wallet
        eco_col.update_one({"_id": loser_id}, {"$set": {"wallet": 0}}, upsert=True)
        update_loan(loser_id, debt_incurred)
        # Establecer último cálculo de intereses si no está definido
        if "last_interest_calc" not in loser_data_before:
            eco_col.update_one({"_id": loser_id}, {"$set": {"last_interest_calc": time.time()}})
    else:
        eco_col.update_one({"_id": loser_id}, {"$inc": {"wallet": -bet_amount}}, upsert=True)

    winner_data = _get(winner_id)
    loser_data = _get(loser_id)

    # Seguimiento de misiones
    from utils.bounties import track_bounty_progress
    bot = channel.guild.me._state._get_client() # Truco para obtener la instancia del bot
    await track_bounty_progress(bot, winner_id, "PET_MASTER", 1)

    embed = discord.Embed(
        title="🏆 RESULTADOS DE LA BATALLA",
        description="El polvo se asienta, y surge un vencedor...",
        color=0xFFD700,
    )
    embed.add_field(
        name=f"👑 GANADOR: {winner.display_name}",
        value=(
            f"**Mascota:** {winner_pet['type'].capitalize()}\n"
            f"**Ganó:** 🪙 {bet_amount:,}\n"
            f"**Nuevo Saldo:** 🪙 {winner_data['wallet']:,}"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"💀 PERDEDOR: {loser.display_name}",
        value=(
            f"**Mascota:** {loser_pet['type'].capitalize()}\n"
            f"**Perdió:** 🪙 {bet_amount:,}\n"
            f"**Nuevo Saldo:** 🪙 {loser_data['wallet']:,}"
        ),
        inline=False,
    )
    from utils.economy import get_debt
    if get_debt(loser_id) > 0:
        embed.set_footer(text="📉 ¡En bancarrota! El perdedor está ahora en deuda y debe pagarla con intereses.")

    await asyncio.sleep(1)
    await battle_msg.edit(content="🛑 **¡La batalla ha terminado!**", embed=embed)
    del state.active_battles[battle_id]


class AdventurePetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        self.ctx = ctx
        self.pets = pets

        options = []
        for index, pet in enumerate(pets):
            pet_type = pet["type"]
            emoji = PET_SHOP[pet_type]["emoji"]
            rarity = PET_RARITIES.get(pet_type, "basic").capitalize()
            # Usar el índice como valor para evitar duplicados cuando el usuario
            # tiene varias mascotas del mismo tipo (Discord rechaza valores repetidos).
            options.append(
                discord.SelectOption(
                    label=f"{pet_type.capitalize()} (#{index + 1})",
                    description=f"Mascota {rarity}",
                    emoji=emoji,
                    value=str(index),
                )
            )

        super().__init__(
            placeholder="Elige una mascota para la aventura...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_pet = self.pets[selected_index]
        
        hunger = get_current_hunger(selected_pet)
        if hunger < 30:
            return await interaction.response.send_message("😿 Tu mascota está demasiado débil y necesita comida antes de poder participar.", ephemeral=True)
            
        await run_adventure(interaction, self.ctx, selected_pet)


class AdventureView(discord.ui.View):
    def __init__(self, ctx, pets):
        super().__init__(timeout=60)
        self.message: discord.Message | None = None
        self.add_item(AdventurePetSelect(ctx, pets))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Menú de aventura expirado.", view=None, embed=None)
            except Exception:
                pass


class PetBattleSelect(discord.ui.Select):
    def __init__(self, user, pets, battle_id: str, role: str):
        self.user = user
        self.pets = pets
        self.battle_id = battle_id
        self.role = role

        options = []
        for index, pet in enumerate(pets):
            pet_type = pet["type"]
            emoji = PET_SHOP[pet_type]["emoji"]
            # Usar el índice como valor para evitar duplicados cuando el usuario
            # tiene varias mascotas del mismo tipo (Discord rechaza valores repetidos).
            options.append(
                discord.SelectOption(
                    label=f"{pet_type.capitalize()} (#{index + 1})",
                    emoji=emoji,
                    value=str(index),
                )
            )

        super().__init__(
            placeholder="Elige tu mascota...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Esta selección no es para ti.", ephemeral=True
            )

        selected_pet = self.pets[int(self.values[0])]
        
        hunger = get_current_hunger(selected_pet)
        if hunger < 30:
            return await interaction.response.send_message("😿 Tu mascota está demasiado débil y necesita comida antes de poder participar.", ephemeral=True)

        battle = state.active_battles[self.battle_id]
        battle[self.role] = selected_pet

        await interaction.response.send_message(
            f"✅ ¡Seleccionaste {selected_pet['type'].capitalize()}!", ephemeral=True
        )

        if battle["challenger_pet"] and battle["opponent_pet"]:
            await start_pet_battle(interaction.channel, self.battle_id)


class PetBattleSelectView(discord.ui.View):
    def __init__(self, ctx, opponent, challenger_pets, opponent_pets, battle_id: str):
        super().__init__(timeout=60)
        self.message: discord.Message | None = None
        self.add_item(PetBattleSelect(ctx.author, challenger_pets, battle_id, "challenger_pet"))
        self.add_item(PetBattleSelect(opponent, opponent_pets, battle_id, "opponent_pet"))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Selección de batalla expirada.", view=None, embed=None)
            except Exception:
                pass


class BattleRequestView(discord.ui.View):
    def __init__(self, ctx, opponent):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.opponent = opponent
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Solicitud de batalla expirada.", view=None, embed=None)
            except Exception:
                pass

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ Esta solicitud de batalla no es para ti.", ephemeral=True
            )

        challenger_pets = pets_col.find_one({"_id": str(self.ctx.author.id)})["pets"]
        opponent_pets = pets_col.find_one({"_id": str(self.opponent.id)})["pets"]
        battle_id = f"{self.ctx.author.id}-{self.opponent.id}"

        state.active_battles[battle_id] = {
            "challenger": self.ctx.author,
            "opponent": self.opponent,
            "challenger_pet": None,
            "opponent_pet": None,
        }

        view = PetBattleSelectView(
            self.ctx, self.opponent, challenger_pets, opponent_pets, battle_id
        )
        embed = discord.Embed(
            title="🐾 Elige tus Mascotas de Batalla",
            description=(
                f"{self.ctx.author.mention} y {self.opponent.mention}\n\n"
                "Ambos jugadores deben elegir una mascota."
            ),
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ Esta solicitud de batalla no es para ti.", ephemeral=True
            )
        await interaction.response.edit_message(content="❌ Batalla rechazada.", embed=None, view=None)


class ShopView(discord.ui.View):
    def __init__(self, ctx, pet_shop):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pet_shop = pet_shop
        self.page = "pets"  # "pets" o "food"
        self.pet_subpage = 0
        self.pets_per_page = 15
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Tienda cerrada.", view=None, embed=None)
            except Exception:
                pass

    def _get_discount(self):
        from utils.economy import get_wallet, get_bank, get_prestige_level
        from config import PRESTIGE_LEVELS
        user_id = str(self.ctx.author.id)
        w = get_wallet(user_id)
        b = get_bank(user_id)
        level = get_prestige_level(w + b)
        return PRESTIGE_LEVELS[level]["discount"] if level > 0 else 0.0

    def _build_embed(self, guild):
        discount = self._get_discount()
        
        if self.page == "pets":
            embed = discord.Embed(
                title="🏪 Tienda de Mascotas",
                description=f"🐾 ¡Compra mascotas para batallas y aventuras!\n✨ Tu Descuento de Prestigio: **{discount*100}%**",
                color=0x3498DB
            )
            
            pet_items = sorted(self.pet_shop.items(), key=lambda x: x[1]['price'])
            start = self.pet_subpage * self.pets_per_page
            end = start + self.pets_per_page
            current_pets = pet_items[start:end]
            
            total_subpages = (len(pet_items) - 1) // self.pets_per_page + 1
            embed.set_author(name=f"Página {self.pet_subpage + 1} de {total_subpages}")

            pet_fields = []
            current_field = ""
            for name, stats in current_pets:
                price = int(stats['price'] * (1 - discount))
                entry = f"{stats['emoji']} **{name.capitalize()}**\n🪙 {price:,} | ❤️ {stats['hp']} | ⚔️ {stats['damage']}\n\n"
                if len(current_field) + len(entry) > 1024:
                    pet_fields.append(current_field)
                    current_field = entry
                else:
                    current_field += entry
            if current_field:
                pet_fields.append(current_field)

            for i, field_content in enumerate(pet_fields):
                name = "🐾 Mascotas" if i == 0 else "\u200b"
                embed.add_field(name=name, value=field_content, inline=False)

        elif self.page == "food":
            embed = discord.Embed(
                title="🍖 Tienda de Comida",
                description=f"😋 ¡Mantén a tus mascotas sanas y fuertes!\n✨ Tu Descuento de Prestigio: **{discount*100}%**",
                color=0x2ECC71
            )
            from config import FOOD_ITEMS
            food_text = ""
            for key, data in FOOD_ITEMS.items():
                price = int(data['price'] * (1 - discount))
                food_text += f"{data['emoji']} **{data['name']}**\n🪙 {price:,} | 🍖 +{data['hunger']} Hambre\n\n"
            
            embed.add_field(name="🍖 Objetos de Comida", value=food_text, inline=False)
            
        return embed

    @discord.ui.button(label="Mascotas", style=discord.ButtonStyle.primary, row=0)
    async def show_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "pets"
        self.pet_subpage = 0
        await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="Comida", style=discord.ButtonStyle.primary, row=0)
    async def show_food(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "food"
        await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page == "pets" and self.pet_subpage > 0:
            self.pet_subpage -= 1
            await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page == "pets":
            pet_items = list(self.pet_shop.items())
            total_subpages = (len(pet_items) - 1) // self.pets_per_page + 1
            if self.pet_subpage < total_subpages - 1:
                self.pet_subpage += 1
                await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)
            else:
                await interaction.response.defer()
        else:
            await interaction.response.defer()


class SellPetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        self.ctx = ctx
        self.pets = pets
        options = []
        for index, pet in enumerate(pets):
            pet_type = pet["type"]
            price = PET_SHOP.get(pet_type, {}).get("price", 0)
            sell_price = price // 2
            emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
            options.append(
                discord.SelectOption(
                    label=f"{pet_type.capitalize()} (ID: {pet['pet_id'][:8]})",
                    description=f"Vender por 🪙 {sell_price:,}",
                    emoji=emoji,
                    value=str(index)
                )
            )
        super().__init__(placeholder="Elige una mascota para vender...", options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(self.ctx.author.id)
        selected_index = int(self.values[0])
        pet_data = pets_col.find_one({"_id": user_id})
        pets = pet_data.get("pets", [])
        
        if selected_index >= len(pets):
            return await interaction.response.send_message("❌ La mascota ya no existe.", ephemeral=True)
            
        pet = pets.pop(selected_index)
        shop_price = PET_SHOP.get(pet["type"], {}).get("price", 0)
        sell_price = shop_price // 2
        
        pets_col.update_one({"_id": user_id}, {"$set": {"pets": pets}})
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": sell_price}}, upsert=True)
        
        embed = discord.Embed(title="💰 Mascota Vendida", color=0x2ECC71)
        embed.description = f"Vendiste tu **{pet['type'].capitalize()}**\n\nRecibiste: 🪙 **{sell_price:,}**"
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class FeedPetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        options = []
        for pet in pets:
            hunger = get_current_hunger(pet)
            pet_type = pet["type"]
            emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    description=f"Hambre: {int(hunger)}/100",
                    emoji=emoji,
                    value=pet["pet_id"],
                )
            )
        super().__init__(placeholder="Selecciona una mascota para alimentar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_pet_id = self.values[0]
        await interaction.response.defer()


class FeedFoodSelect(discord.ui.Select):
    def __init__(self, food_items):
        options = []
        food_counts = {}
        for item in food_items:
            key = item["key"]
            food_counts[key] = food_counts.get(key, 0) + 1

        for key, count in food_counts.items():
            food_data = FOOD_ITEMS[key]
            options.append(
                discord.SelectOption(
                    label=f"{food_data['name']} (x{count})",
                    description=f"+{food_data['hunger']} Hambre",
                    emoji=food_data["emoji"],
                    value=key,
                )
            )
        super().__init__(placeholder="Selecciona comida...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_food_key = self.values[0]
        await self.view.process_feed(interaction)


class FeedView(discord.ui.View):
    def __init__(self, ctx, pets, food_items):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pets = pets
        self.food_items = food_items
        self.selected_pet_id = None
        self.selected_food_key = None
        self.message: discord.Message | None = None

        self.add_item(FeedPetSelect(ctx, pets))
        self.add_item(FeedFoodSelect(food_items))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Menú de alimentación expirado.", view=None, embed=None)
            except Exception:
                pass

    async def process_feed(self, interaction: discord.Interaction):
        if not self.selected_pet_id:
            return await interaction.followup.send("❌ ¡Por favor selecciona una mascota primero!", ephemeral=True)

        user_id = str(self.ctx.author.id)
        pet_index = next(
            (i for i, p in enumerate(self.pets) if p["pet_id"] == self.selected_pet_id), None
        )
        if pet_index is None:
            return await interaction.followup.send("❌ Mascota no encontrada.", ephemeral=True)

        pet = self.pets[pet_index]
        current_hunger = get_current_hunger(pet)
        food_data = FOOD_ITEMS[self.selected_food_key]
        new_hunger = min(100, current_hunger + food_data["hunger"])

        self.pets[pet_index]["hunger"] = new_hunger
        self.pets[pet_index]["last_fed"] = time.time()
        self.pets[pet_index]["starvation_since"] = None

        pets_col.update_one({"_id": user_id}, {"$set": {"pets": self.pets}})

        user_data = eco_col.find_one({"_id": user_id})
        inventory = user_data.get("inventory", []) if user_data else []

        for i, item in enumerate(inventory):
            if item.get("type") == "food" and item.get("key") == self.selected_food_key:
                inventory.pop(i)
                break

        eco_col.update_one({"_id": user_id}, {"$set": {"inventory": inventory}})
        
        # Seguimiento de misiones
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.ctx.bot, user_id, "PET_LOVER", 1)
        
        embed = discord.Embed(
            title="🍖 Mascota Alimentada",
            description=(
                f"Le diste a tu **{pet['type'].capitalize()}** {food_data['emoji']} **{food_data['name']}**.\n\n"
                f"🍖 Hambre: {int(current_hunger)} → **{int(new_hunger)}**/100"
            ),
            color=0x00FF00,
        )
        await interaction.message.edit(content=None, embed=embed, view=None)


class SellPetView(discord.ui.View):
    def __init__(self, ctx, pets):
        super().__init__(timeout=60)
        self.message: discord.Message | None = None
        self.add_item(SellPetSelect(ctx, pets))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Menú de venta expirado.", view=None, embed=None)
            except Exception:
                pass


class BreedSelect(discord.ui.Select):
    def __init__(self, pets, placeholder, custom_id):
        options = []
        for p in pets:
            pet_type = p["type"]
            emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
            options.append(discord.SelectOption(
                label=f"{pet_type.capitalize()} (ID: {p['pet_id'][:8]})",
                emoji=emoji,
                value=p["pet_id"]
            ))
        super().__init__(placeholder=placeholder, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class BreedView(discord.ui.View):
    def __init__(self, ctx, pets):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pets = pets
        self.message: discord.Message | None = None
        self.add_item(BreedSelect(pets, "Selecciona el primer padre...", "parent1"))
        self.add_item(BreedSelect(pets, "Selecciona el segundo padre...", "parent2"))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Menú de cría expirado.", view=None, embed=None)
            except Exception:
                pass

    @discord.ui.button(label="Iniciar Cría", style=discord.ButtonStyle.green)
    async def start_breed(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Primero, aplazar la interacción porque las operaciones de BD pueden tardar
            await interaction.response.defer()

            # Encontrar los componentes select para obtener sus valores
            p1_id = None
            p2_id = None
            for child in self.children:
                if isinstance(child, BreedSelect):
                    if child.custom_id == "parent1" and child.values:
                        p1_id = child.values[0]
                    elif child.custom_id == "parent2" and child.values:
                        p2_id = child.values[0]

            if not p1_id or not p2_id:
                return await interaction.followup.send("❌ Por favor selecciona ambos padres de los menús.", ephemeral=True)
            
            if p1_id == p2_id:
                return await interaction.followup.send("❌ No puedes criar una mascota consigo misma.", ephemeral=True)

            user_id = str(self.ctx.author.id)
            p1 = next((p for p in self.pets if p["pet_id"] == p1_id), None)
            p2 = next((p for p in self.pets if p["pet_id"] == p2_id), None)

            if not p1 or not p2:
                return await interaction.followup.send("❌ Una de las mascotas seleccionadas no se encontró en tu colección.", ephemeral=True)

            from config import PET_SHOP, BREEDING_COST_RATIO, BREEDING_SUCCESS_CHANCE, BREEDING_RISK_CHANCE
            v1 = PET_SHOP.get(p1["type"], {}).get("price", 0)
            v2 = PET_SHOP.get(p2["type"], {}).get("price", 0)
            combined_value = v1 + v2
            cost = int(combined_value * BREEDING_COST_RATIO)

            wallet = get_wallet(user_id)
            if wallet < cost:
                return await interaction.followup.send(f"❌ Necesitas 🪙 {cost:,} para criar estas mascotas.", ephemeral=True)

            # Actualización atómica de la billetera
            update_wallet(user_id, -cost)
            
            # Seguimiento de misiones
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.ctx.bot, user_id, "BREEDER", 1)
            
            # Lógica de cría: Encontrar una mascota en PET_SHOP que sea más cara que el valor combinado
            available_pets = sorted(PET_SHOP.items(), key=lambda x: x[1]['price'])
            possible_evolutions = [name for name, stats in available_pets if stats['price'] > combined_value]
            
            success = random.randint(1, 100) <= BREEDING_SUCCESS_CHANCE
            if success and possible_evolutions:
                # Obtener la siguiente
                new_type = possible_evolutions[0] 
                new_pet = {
                    "pet_id": str(uuid.uuid4()),
                    "type": new_type,
                    "hp": PET_SHOP[new_type]["hp"],
                    "damage": PET_SHOP[new_type]["damage"],
                    "hunger": 100,
                    "last_fed": time.time(),
                }
                pets_col.update_one({"_id": user_id}, {"$push": {"pets": new_pet}})
                embed = discord.Embed(
                    title="💖 ¡Evolución Exitosa!", 
                    description=f"¡Tus mascotas se unieron y evolucionaron en un(a) **{new_type.capitalize()}**!", 
                    color=0xFF69B4
                )
                embed.add_field(name="Valor de la Nueva Mascota", value=f"🪙 {PET_SHOP[new_type]['price']:,}")
            else:
                risk = random.randint(1, 100) <= BREEDING_RISK_CHANCE
                if risk:
                    # Eliminar un padre
                    lost_id = random.choice([p1_id, p2_id])
                    lost_type = p1["type"] if lost_id == p1_id else p2["type"]
                    pets_col.update_one({"_id": user_id}, {"$pull": {"pets": {"pet_id": lost_id}}})
                    embed = discord.Embed(title="💔 Cría Fallida", description=f"La cría falló y tu **{lost_type.capitalize()}** huyó en la confusión...", color=0xFF0000)
                else:
                    embed = discord.Embed(title="💨 Cría Fallida", description="Las mascotas no se unieron. Perdiste las monedas pero conservaste tus mascotas.", color=0x95A5A6)

            await interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            print(f"ERROR DE CRÍA: {e}")
            try:
                await interaction.followup.send(f"❌ Ocurrió un error interno: {e}", ephemeral=True)
            except:
                pass
