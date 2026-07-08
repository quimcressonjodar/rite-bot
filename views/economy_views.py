import discord

from database import eco_col
from utils.economy import get_user_data


class SellSelect(discord.ui.Select):
    def __init__(self, ctx, inventory):
        self.ctx = ctx
        self.inventory = inventory

        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "godly": "🌌",
        }
        options = [
            discord.SelectOption(label="💰 Vender Todos los Objetos", value="all", description="Liquidar todo tu inventario")
        ]
        
        for index, item in enumerate(inventory[:24]):
            rarity = item.get("rarity", "common")
            options.append(
                discord.SelectOption(
                    label=item["name"][:100],
                    description=f"{rarity.capitalize()} • 🪙 {item['value']:,}",
                    emoji=rarity_emojis.get(rarity, "⚪"),
                    value=str(index),
                )
            )

        super().__init__(
            placeholder="Elige un objeto para vender...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Este menú no es para ti.", ephemeral=True)

        user_id = str(self.ctx.author.id)
        user_data = get_user_data(user_id)
        inventory = user_data.get("inventory", [])

        from utils.economy import apply_amortization
        if self.values[0] == "all":
            if not inventory:
                return await interaction.response.send_message("❌ Tu inventario está vacío.", ephemeral=True)
                
            total_value = sum(item["value"] for item in inventory)
            actual_value = apply_amortization(user_id, total_value)
            eco_col.update_one(
                {"_id": user_id},
                {"$inc": {"wallet": actual_value}, "$set": {"inventory": []}},
            )
            embed = discord.Embed(title="💰 Todos los Objetos Vendidos", color=0x2ECC71)
            desc = f"Vendiste **{len(inventory)}** objetos\n\nTotal Ganado: 🪙 **{total_value:,}**"
            if actual_value < total_value:
                desc += f"\n📉 🪙 {total_value - actual_value:,} usados para pagar la deuda."
            embed.description = desc
            return await interaction.response.edit_message(content=None, embed=embed, view=None)

        selected_index = int(self.values[0])
        if selected_index >= len(inventory):
            return await interaction.response.send_message("❌ El objeto ya no existe.", ephemeral=True)

        item = inventory[selected_index]
        inventory.pop(selected_index)
        
        total_value = item["value"]
        actual_value = apply_amortization(user_id, total_value)

        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": actual_value}, "$set": {"inventory": inventory}},
        )

        embed = discord.Embed(title="💰 Objeto Vendido", color=0x2ECC71)
        desc = f"Vendiste {item['name']}\n\nGanaste: 🪙 **{total_value:,}**"
        if actual_value < total_value:
            desc += f"\n📉 🪙 {total_value - actual_value:,} usados para pagar la deuda."
        embed.description = desc
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class SellView(discord.ui.View):
    def __init__(self, ctx, inventory):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.inventory = inventory
        self.message: discord.Message | None = None
        self.add_item(SellSelect(ctx, inventory))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ Este menú expiró.", view=None, embed=None)
            except Exception:
                pass
