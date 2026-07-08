from datetime import timedelta

import discord
from discord.ext import commands

from database import warns_col


OWNER_ID = 1436417791615045785

def is_admin(ctx: commands.Context) -> bool:
    """Comprueba si el autor del contexto es el propietario del bot."""
    return ctx.author.id == OWNER_ID


def parse_duration(duration_str: str) -> timedelta | None:
    """Convierte una cadena de duración (ej. '10m', '2h', '1d') en un objeto timedelta.

    Devuelve None si el formato no es válido.
    """
    try:
        if duration_str.endswith("m"):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        else:
            return timedelta(minutes=int(duration_str))
    except ValueError:
        return None


def load_warns() -> dict:
    """Carga todos los avisos almacenados en la base de datos."""
    doc = warns_col.find_one({"_id": "all_warns"})
    return doc["data"] if doc else {}


def save_warns(data: dict) -> None:
    """Guarda el diccionario de avisos en la base de datos."""
    warns_col.update_one({"_id": "all_warns"}, {"$set": {"data": data}}, upsert=True)
