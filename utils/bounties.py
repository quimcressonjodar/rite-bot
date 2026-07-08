import time
import random
import discord
from database import db

bounties_col = db.get_collection("bounties_col")

BOUNTY_TYPES = {
    "WORKER": {
        "name": "El Trabajador Incansable",
        "description": "Sé el primero en usar `!work` {goal} veces.",
        "goal": 5,
        "reward": 150000
    },
    "GAMBLER": {
        "name": "El Apostador Afortunado",
        "description": "Sé el primero en ganar {goal} monedas en cualquier juego de casino.",
        "goal": 200000,
        "reward": 300000
    },
    "TRADER": {
        "name": "El Tiburón de Wall Street",
        "description": "Sé el primero en obtener {goal} monedas de ganancia en una sola venta de acciones.",
        "goal": 100000,
        "reward": 250000
    },
    "ROBBER": {
        "name": "El Ladrón Maestro",
        "description": "Sé el primero en robar exitosamente a {goal} jugadores diferentes.",
        "goal": 3,
        "reward": 200000
    },
    "HUNTER": {
        "name": "El Cazarrecompensas",
        "description": "Sé el primero en atrapar a {goal} criminales buscados.",
        "goal": 2,
        "reward": 300000
    },
    "PET_LOVER": {
        "name": "El Cuidador de Mascotas",
        "description": "Sé el primero en alimentar a tus mascotas {goal} veces.",
        "goal": 10,
        "reward": 100000
    },
    "DAILY_CLAIMER": {
        "name": "El Ciudadano Constante",
        "description": "Sé el primero en reclamar tu recompensa `!daily`.",
        "goal": 1,
        "reward": 50000
    },
    "LOAN_PAYER": {
        "name": "El Deudor Responsable",
        "description": "Sé el primero en pagar {goal} monedas de tu deuda.",
        "goal": 100000,
        "reward": 150000
    },
    "STREAK_GAMBLER": {
        "name": "El Apostador Imparable",
        "description": "Sé el primero en ganar {goal} juegos de casino seguidos.",
        "goal": 3,
        "reward": 400000
    },
    "BIG_SPENDER": {
        "name": "El Gran Gastador",
        "description": "Sé el primero en gastar {goal} monedas en la tienda (Mascotas/Roles/Comida).",
        "goal": 500000,
        "reward": 250000
    },
    "BREEDER": {
        "name": "El Criador Maestro",
        "description": "Sé el primero en criar exitosamente {goal} mascotas.",
        "goal": 2,
        "reward": 350000
    },
    "ADVENTURER": {
        "name": "El Aventurero Valiente",
        "description": "Sé el primero en completar {goal} aventuras exitosas.",
        "goal": 5,
        "reward": 200000
    }
}

def get_active_bounties():
    """Obtiene todas las recompensas actualmente activas de la base de datos."""
    return list(bounties_col.find({"status": "active"}))

def spawn_new_bounty():
    """Selecciona un tipo de recompensa aleatorio que no esté activo y lo activa."""
    active_keys = {b["key"] for b in bounties_col.find({"status": "active"})}
    available = [k for k in BOUNTY_TYPES if k not in active_keys]
    if not available:
        available = list(BOUNTY_TYPES.keys())  # todas activas — permitir repetición como alternativa
    b_key = random.choice(available)
    b_data = BOUNTY_TYPES[b_key].copy()

    new_bounty = {
        "key": b_key,
        "name": b_data["name"],
        "description": b_data["description"].format(goal=f"{b_data['goal']:,}"),
        "goal": b_data["goal"],
        "reward": b_data["reward"],
        "status": "active",
        "start_time": time.time(),
        "participants": {}  # {user_id: progreso_actual}
    }

    bounties_col.insert_one(new_bounty)
    return new_bounty

async def track_bounty_progress(bot, user_id, bounty_key, increment):
    """Actualiza el progreso de un tipo de recompensa específico para un usuario."""
    user_id = str(user_id)
    active_bounties = bounties_col.find({"key": bounty_key, "status": "active"})

    for bounty in active_bounties:
        current_progress = bounty.get("participants", {}).get(user_id, 0)
        new_progress = current_progress + increment

        if new_progress >= bounty["goal"]:
            # ¡Recompensa completada!
            bounties_col.update_one(
                {"_id": bounty["_id"]},
                {
                    "$set": {
                        "status": "completed",
                        "winner": user_id,
                        "completion_time": time.time(),
                        f"participants.{user_id}": new_progress
                    }
                }
            )

            # Pagar la recompensa
            from utils.economy import update_wallet
            update_wallet(user_id, bounty["reward"])

            # Anunciar en Discord
            from config import WELCOME_CHANNEL_ID
            STOCK_NEWS_CHANNEL_ID = 1206197908399980575
            channel = bot.get_channel(STOCK_NEWS_CHANNEL_ID)
            if channel:
                user = await bot.fetch_user(int(user_id))
                embed = discord.Embed(
                    title="🎉 ¡CONTRATO COMPLETADO!",
                    description=f"{user.mention} ha completado el contrato **{bounty['name']}**!",
                    color=0x2ECC71
                )
                embed.add_field(name="💰 Recompensa", value=f"🪙 {bounty['reward']:,}")
                embed.set_footer(text="¡Pronto se publicará un nuevo contrato!")
                await channel.send(embed=embed)
        else:
            # Actualizar progreso
            bounties_col.update_one(
                {"_id": bounty["_id"]},
                {"$set": {f"participants.{user_id}": new_progress}}
            )
