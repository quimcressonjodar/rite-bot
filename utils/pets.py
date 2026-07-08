import time

def get_current_hunger(pet):
    """Calcula el nivel de hambre actual de una mascota en función del tiempo transcurrido desde la última alimentación."""
    last_fed = pet.get("last_fed", time.time())
    hunger_at_last_fed = pet.get("hunger", 100)
    elapsed = time.time() - last_fed
    decay = (elapsed / 86400) * 10  # -10 de hambre cada 24 horas
    return max(0, hunger_at_last_fed - decay)

def get_pet_state(pet):
    """Devuelve el estado actual de la mascota y las penalizaciones asociadas según su nivel de hambre."""
    hunger = get_current_hunger(pet)
    if hunger >= 70:
        return "Bien Alimentada", {}
    elif hunger >= 30:
        return "Hambrienta", {"xp_penalty": 0.25, "damage_penalty": 0.25}
    elif hunger > 0:
        return "Desnutrida", {"blocked": True}
    else:
        return "Muriendo de Hambre", {"blocked": True}

def is_pet_dead(pet):
    """Determina si una mascota ha muerto por inanición (sin comida durante 7 días)."""
    last_fed = pet.get("last_fed", time.time())
    hunger_at_last_fed = pet.get("hunger", 100)

    # Si el hambre ya era 0, starvation_since debe estar definido
    starvation_since = pet.get("starvation_since")

    if hunger_at_last_fed > 0:
        # Tiempo que tardó en llegar a 0
        time_to_zero = (hunger_at_last_fed / 10) * 86400
        reached_zero_at = last_fed + time_to_zero
    else:
        reached_zero_at = starvation_since or last_fed

    now = time.time()
    if now > reached_zero_at and (now - reached_zero_at) >= (7 * 86400):
        return True
    return False
