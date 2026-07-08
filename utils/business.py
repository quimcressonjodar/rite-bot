"""
Sistema de negocios — lógica central y operaciones de base de datos.
Completamente independiente del sistema del mercado de acciones.
Para añadir un nuevo tipo de negocio: añade una clave a BUSINESS_TYPES más abajo.
"""
import random
import string
import time
from database import db

businesses_col = db["businesses"]

# ─────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────

COLLECTION_INTERVAL = 3600          # 1 hora en segundos
MAX_ACCUMULATION_HOURS = 24         # límite de acumulación de ingresos

# XP necesario para alcanzar el siguiente nivel (índice = nivel actual)
XP_PER_LEVEL = [0, 100, 250, 500, 900, 1_500, 2_500, 4_000, 6_500, 10_000]

# Multiplicador de ingresos por nivel (índice = nivel, nivel máximo 10)
LEVEL_INCOME_MULT = [1.0, 1.0, 1.15, 1.30, 1.50, 1.75, 2.10, 2.55, 3.10, 3.80, 4.60]

WORKER_NAMES = [
  "Alex", "Sam", "Jamie", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
  "Quinn", "Avery", "Blake", "Drew", "Hayden", "Logan", "Peyton", "Reese",
  "Skyler", "Sage", "Charlie", "Frankie", "Dakota", "Emery", "Finley", "Harper",
  "Indigo", "Jules", "Kendall", "Lane", "Marlowe", "Nova", "Oakley", "Parker",
]


def reputation_multiplier(rep: int) -> float:
  """reputación 0-100 -> multiplicador de ingresos 0.5-1.5"""
  return 0.5 + (rep / 100.0)


# ─────────────────────────────────────────────────────────
# CATÁLOGO DE NEGOCIOS
# Para añadir un nuevo tipo: copia cualquier entrada y personalízala.
# ─────────────────────────────────────────────────────────
BUSINESS_TYPES: dict[str, dict] = {
  "restaurant": {
      "name": "Restaurante", "emoji": "\U0001f37d\ufe0f",
      "description": "Un popular restaurante que sirve a clientes hambrientos día y noche.",
      "base_cost": 50_000,
      "base_income_per_hour": 800,
      "base_maintenance_per_hour": 120,
      "max_workers": 8,
      "sell_multiplier": 0.60,
      "worker_roles": ["Chef", "Camarero", "Cajero", "Gerente"],
      "worker_base_salary": 180,
      "entry_fee": 500,
      "visit_benefit": {"type": "feed_pets", "value": 30},
      "visit_description": "\U0001f35c ¡Tus mascotas disfrutaron de una deliciosa comida! Su hambre fue restaurada en **+30**.",
      "upgrades": {
          "better_kitchen":  {"name": "Cocina Mejorada",   "emoji": "\U0001f373", "cost": 20_000,  "income_bonus": 0.15, "req_level": 1},
          "outdoor_seating": {"name": "Terraza Exterior",  "emoji": "\U0001fa91", "cost": 35_000,  "income_bonus": 0.20, "req_level": 3},
          "vip_area":        {"name": "Sala VIP",          "emoji": "\U0001f48e", "cost": 60_000,  "income_bonus": 0.25, "req_level": 5},
          "michelin_star":   {"name": "Estrella Michelin", "emoji": "\u2b50",     "cost": 150_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "cinema": {
      "name": "Cine", "emoji": "\U0001f3ac",
      "description": "Un cine con los últimos éxitos de taquilla.",
      "base_cost": 75_000,
      "base_income_per_hour": 1_100,
      "base_maintenance_per_hour": 200,
      "max_workers": 6,
      "sell_multiplier": 0.60,
      "worker_roles": ["Proyeccionista", "Taquillero", "Acomodador", "Gerente"],
      "worker_base_salary": 220,
      "entry_fee": 800,
      "visit_benefit": {"type": "coins", "value": 400},
      "visit_description": "\U0001f3ac Viste una película increíble y ganaste un sorteo. ¡Recibiste \U0001fa99 **400**!",
      "upgrades": {
          "new_projectors": {"name": "Nuevos Proyectores", "emoji": "\U0001f4fd\ufe0f", "cost": 30_000,  "income_bonus": 0.15, "req_level": 1},
          "vip_seats":      {"name": "Butacas VIP",        "emoji": "\U0001f6cb\ufe0f","cost": 50_000,  "income_bonus": 0.20, "req_level": 3},
          "imax_screen":    {"name": "Pantalla IMAX",      "emoji": "\U0001f39e\ufe0f","cost": 100_000, "income_bonus": 0.35, "req_level": 6},
          "food_court":     {"name": "Zona de Comida",     "emoji": "\U0001f37f",       "cost": 80_000,  "income_bonus": 0.25, "req_level": 5},
      },
  },
  "store": {
      "name": "Tienda", "emoji": "\U0001f3ea",
      "description": "Una tienda de artículos variados en una calle muy transitada.",
      "base_cost": 30_000,
      "base_income_per_hour": 500,
      "base_maintenance_per_hour": 80,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Cajero", "Reponedor", "Seguridad", "Gerente"],
      "worker_base_salary": 130,
      "entry_fee": 300,
      "visit_benefit": {"type": "coins", "value": 150},
      "visit_description": "\U0001f6d2 ¡Encontraste una gran oferta y obtuviste un reembolso de \U0001fa99 **150**!",
      "upgrades": {
          "self_checkout":   {"name": "Autopago",          "emoji": "\U0001f916",     "cost": 15_000,  "income_bonus": 0.15, "req_level": 1},
          "loyalty_program": {"name": "Programa Fidelidad","emoji": "\U0001f3ab",     "cost": 25_000,  "income_bonus": 0.20, "req_level": 3},
          "second_floor":    {"name": "Segunda Planta",    "emoji": "\U0001f3d7\ufe0f","cost": 60_000, "income_bonus": 0.30, "req_level": 5},
          "brand_deal":      {"name": "Acuerdo de Marca",  "emoji": "\U0001f91d",     "cost": 100_000, "income_bonus": 0.35, "req_level": 8},
      },
  },
  "waterpark": {
      "name": "Parque Acuático", "emoji": "\U0001f30a",
      "description": "Diversión acuática para familias y amantes de la adrenalina.",
      "base_cost": 200_000,
      "base_income_per_hour": 2_500,
      "base_maintenance_per_hour": 600,
      "max_workers": 15,
      "sell_multiplier": 0.60,
      "worker_roles": ["Socorrista", "Operador de Atracción", "Taquillero", "Limpiador", "Gerente"],
      "worker_base_salary": 280,
      "entry_fee": 1_500,
      "visit_benefit": {"type": "feed_pets", "value": 25},
      "visit_description": "\U0001f30a ¡Tus mascotas se mojaron y lo pasaron genial! Su hambre fue restaurada en **+25**.",
      "upgrades": {
          "wave_pool":    {"name": "Piscina de Olas",  "emoji": "\U0001f3c4",     "cost": 80_000,  "income_bonus": 0.20, "req_level": 2},
          "lazy_river":   {"name": "Río Lento",        "emoji": "\U0001f6f6",     "cost": 120_000, "income_bonus": 0.25, "req_level": 4},
          "speed_slides": {"name": "Toboganes Rápidos","emoji": "\U0001f3a2",     "cost": 200_000, "income_bonus": 0.35, "req_level": 6},
          "vip_cabanas":  {"name": "Cabañas VIP",      "emoji": "\U0001f3d6\ufe0f","cost": 300_000,"income_bonus": 0.40, "req_level": 8},
      },
  },
  "museum": {
      "name": "Museo", "emoji": "\U0001f3db\ufe0f",
      "description": "Una prestigiosa institución que exhibe arte e historia.",
      "base_cost": 120_000,
      "base_income_per_hour": 1_400,
      "base_maintenance_per_hour": 300,
      "max_workers": 10,
      "sell_multiplier": 0.60,
      "worker_roles": ["Curador", "Guía", "Guardia de Seguridad", "Restaurador", "Gerente"],
      "worker_base_salary": 250,
      "entry_fee": 1_000,
      "visit_benefit": {"type": "coins", "value": 500},
      "visit_description": "\U0001f3db\ufe0f ¡Una visita cultural! Encontraste un artefacto raro en la tienda de regalos por \U0001fa99 **500**.",
      "upgrades": {
          "digital_exhibits": {"name": "Exposiciones Digitales","emoji": "\U0001f4f1",     "cost": 50_000,  "income_bonus": 0.20, "req_level": 2},
          "gift_shop":        {"name": "Tienda de Regalos",     "emoji": "\U0001f381",     "cost": 30_000,  "income_bonus": 0.15, "req_level": 1},
          "night_tours":      {"name": "Visitas Nocturnas",     "emoji": "\U0001f319",     "cost": 70_000,  "income_bonus": 0.25, "req_level": 5},
          "world_tour_art":   {"name": "Arte Itinerante",       "emoji": "\U0001f5bc\ufe0f","cost": 150_000,"income_bonus": 0.35, "req_level": 7},
      },
  },
  "hotel": {
      "name": "Hotel", "emoji": "\U0001f3e8",
      "description": "Una estancia de lujo para viajeros de todo el mundo.",
      "base_cost": 180_000,
      "base_income_per_hour": 2_200,
      "base_maintenance_per_hour": 500,
      "max_workers": 12,
      "sell_multiplier": 0.60,
      "worker_roles": ["Recepcionista", "Camarero de Piso", "Botones", "Chef", "Gerente"],
      "worker_base_salary": 270,
      "entry_fee": 2_000,
      "visit_benefit": {"type": "feed_pets", "value": 100},
      "visit_description": "\U0001f3e8 ¡Estancia de lujo! Tus mascotas fueron completamente mimadas — hambre **restaurada al 100**!",
      "upgrades": {
          "spa":             {"name": "Spa y Bienestar",  "emoji": "\U0001f9d6", "cost": 80_000,  "income_bonus": 0.20, "req_level": 2},
          "rooftop_pool":    {"name": "Piscina en la Azotea","emoji": "\U0001f3ca", "cost": 150_000, "income_bonus": 0.25, "req_level": 4},
          "conference_hall": {"name": "Sala de Conferencias","emoji": "\U0001f935", "cost": 100_000, "income_bonus": 0.20, "req_level": 3},
          "five_stars":      {"name": "Clasificación 5 Estrellas","emoji": "\u2b50","cost": 250_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "gym": {
      "name": "Gimnasio", "emoji": "\U0001f3cb\ufe0f",
      "description": "Un centro de fitness de última generación para el máximo rendimiento.",
      "base_cost": 40_000,
      "base_income_per_hour": 600,
      "base_maintenance_per_hour": 100,
      "max_workers": 6,
      "sell_multiplier": 0.60,
      "worker_roles": ["Entrenador", "Recepcionista", "Limpiador", "Gerente"],
      "worker_base_salary": 160,
      "entry_fee": 400,
      "visit_benefit": {"type": "strength", "value": 50},
      "visit_description": "\U0001f4aa ¡Gran entrenamiento! Ganaste **+50 XP de Fuerza**. ¡Sigue entrenando!",
      "upgrades": {
          "new_equipment":     {"name": "Nuevo Equipamiento",     "emoji": "\U0001f3c3",                       "cost": 20_000, "income_bonus": 0.20, "req_level": 1},
          "sauna":             {"name": "Sala de Sauna",          "emoji": "\u2668\ufe0f",                    "cost": 35_000, "income_bonus": 0.20, "req_level": 3},
          "juice_bar":         {"name": "Bar de Zumos",           "emoji": "\U0001f964",                       "cost": 25_000, "income_bonus": 0.15, "req_level": 2},
          "personal_training": {"name": "Entrenamiento Personal", "emoji": "\U0001f9d1\u200d\U0001f3eb",    "cost": 60_000, "income_bonus": 0.30, "req_level": 6},
      },
  },
  "cafe": {
      "name": "Caf\u00e9", "emoji": "\u2615",
      "description": "Un encantador rincón del café amado por la clientela matutina.",
      "base_cost": 25_000,
      "base_income_per_hour": 420,
      "base_maintenance_per_hour": 60,
      "max_workers": 4,
      "sell_multiplier": 0.60,
      "worker_roles": ["Barista", "Cajero", "Panadero", "Gerente"],
      "worker_base_salary": 110,
      "entry_fee": 200,
      "visit_benefit": {"type": "feed_pets", "value": 15},
      "visit_description": "\u2615 ¡Tus mascotas disfrutaron de un snack acogedor en el café! Su hambre fue restaurada en **+15**.",
      "upgrades": {
          "espresso_machine": {"name": "Espresso Premium",   "emoji": "\u2615",     "cost": 12_000, "income_bonus": 0.15, "req_level": 1},
          "coworking_space":  {"name": "Espacio Coworking",  "emoji": "\U0001f4bb", "cost": 20_000, "income_bonus": 0.20, "req_level": 2},
          "pastry_display":   {"name": "Vitrina de Pasteles","emoji": "\U0001f950", "cost": 15_000, "income_bonus": 0.15, "req_level": 2},
          "franchise_deal":   {"name": "Acuerdo de Franquicia","emoji": "\U0001f30d", "cost": 80_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
  "bakery": {
      "name": "Panadería", "emoji": "\U0001f956",
      "description": "Pan fresco y pasteles horneados desde cero cada mañana.",
      "base_cost": 22_000,
      "base_income_per_hour": 380,
      "base_maintenance_per_hour": 55,
      "max_workers": 4,
      "sell_multiplier": 0.60,
      "worker_roles": ["Panadero", "Cajero", "Repartidor", "Gerente"],
      "worker_base_salary": 100,
      "entry_fee": 200,
      "visit_benefit": {"type": "feed_pets", "value": 20},
      "visit_description": "\U0001f956 ¡Pasteles frescos compartidos con tus mascotas! Su hambre fue restaurada en **+20**.",
      "upgrades": {
          "brick_oven":       {"name": "Horno de Leña",       "emoji": "\U0001f525", "cost": 10_000, "income_bonus": 0.15, "req_level": 1},
          "custom_cakes":     {"name": "Tartas Personalizadas","emoji": "\U0001f382", "cost": 18_000, "income_bonus": 0.20, "req_level": 2},
          "delivery_service": {"name": "Servicio a Domicilio", "emoji": "\U0001f6f5", "cost": 25_000, "income_bonus": 0.20, "req_level": 3},
          "artisan_brand":    {"name": "Marca Artesanal",      "emoji": "\U0001f3c5", "cost": 70_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
  "gasstation": {
      "name": "Gasolinera", "emoji": "\u26fd",
      "description": "Repostando vehículos y viajeros las 24 horas.",
      "base_cost": 60_000,
      "base_income_per_hour": 900,
      "base_maintenance_per_hour": 180,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Empleado", "Cajero", "Mecánico", "Gerente"],
      "worker_base_salary": 150,
      "entry_fee": 500,
      "visit_benefit": {"type": "coins", "value": 250},
      "visit_description": "\u26fd ¡Cogiste unos snacks y obtuviste un reembolso de combustible de \U0001fa99 **250**!",
      "upgrades": {
          "car_wash":          {"name": "Lavado de Coches",    "emoji": "\U0001f697", "cost": 25_000,  "income_bonus": 0.20, "req_level": 1},
          "convenience_store": {"name": "Tienda de Conveniencia","emoji": "\U0001f3ea", "cost": 40_000,  "income_bonus": 0.20, "req_level": 3},
          "ev_chargers":       {"name": "Cargadores EV",       "emoji": "\u26a1",     "cost": 70_000,  "income_bonus": 0.25, "req_level": 5},
          "truck_stop":        {"name": "Área de Camiones",    "emoji": "\U0001f69b", "cost": 120_000, "income_bonus": 0.30, "req_level": 7},
      },
  },
  "cardealership": {
      "name": "Concesionario de Coches", "emoji": "\U0001f698",
      "description": "Un reluciente salón de exposición que vende vehículos de lujo y cotidianos.",
      "base_cost": 150_000,
      "base_income_per_hour": 2_000,
      "base_maintenance_per_hour": 450,
      "max_workers": 10,
      "sell_multiplier": 0.60,
      "worker_roles": ["Agente de Ventas", "Mecánico", "Recepcionista", "Asesor Financiero", "Gerente"],
      "worker_base_salary": 300,
      "entry_fee": 2_500,
      "visit_benefit": {"type": "coins", "value": 1_000},
      "visit_description": "\U0001f698 ¡Probaste un coche de lujo y ganaste una bonificación por referido de \U0001fa99 **1.000**!",
      "upgrades": {
          "showroom_upgrade": {"name": "Salón Premium",    "emoji": "\u2728",             "cost": 60_000,  "income_bonus": 0.20, "req_level": 2},
          "luxury_models":    {"name": "Modelos de Lujo",  "emoji": "\U0001f3ce\ufe0f",  "cost": 120_000, "income_bonus": 0.30, "req_level": 4},
          "financing_dept":   {"name": "Dpto. Financiero", "emoji": "\U0001f4b3",         "cost": 80_000,  "income_bonus": 0.20, "req_level": 3},
          "auction_house":    {"name": "Casa de Subastas", "emoji": "\U0001f528",         "cost": 200_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "factory": {
      "name": "Fábrica", "emoji": "\U0001f3ed",
      "description": "Una potencia industrial que produce bienes a escala.",
      "base_cost": 250_000,
      "base_income_per_hour": 3_500,
      "base_maintenance_per_hour": 900,
      "max_workers": 20,
      "sell_multiplier": 0.60,
      "worker_roles": ["Operario", "Ingeniero", "Control de Calidad", "Capataz", "Gerente"],
      "worker_base_salary": 350,
      "entry_fee": 3_000,
      "visit_benefit": {"type": "coins", "value": 1_500},
      "visit_description": "\U0001f3ed ¡Hiciste una visita guiada y negociaste un acuerdo lateral por \U0001fa99 **1.500**!",
      "upgrades": {
          "automation":    {"name": "Línea de Automatización","emoji": "\U0001f916",     "cost": 100_000, "income_bonus": 0.25, "req_level": 2},
          "solar_panels":  {"name": "Paneles Solares",        "emoji": "\u2600\ufe0f",  "cost": 80_000,  "income_bonus": 0.15, "req_level": 1},
          "r_and_d_lab":   {"name": "Laboratorio I+D",        "emoji": "\U0001f52c",     "cost": 150_000, "income_bonus": 0.25, "req_level": 5},
          "global_export": {"name": "Exportación Global",     "emoji": "\U0001f30d",     "cost": 300_000, "income_bonus": 0.45, "req_level": 9},
      },
  },
  "arcade": {
      "name": "Salón de Juegos", "emoji": "\U0001f579\ufe0f",
      "description": "Un paraíso de juegos retro-futurista repleto de fichas y diversión.",
      "base_cost": 45_000,
      "base_income_per_hour": 700,
      "base_maintenance_per_hour": 130,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Técnico", "Cajero", "Seguridad", "Gerente"],
      "worker_base_salary": 145,
      "entry_fee": 500,
      "visit_benefit": {"type": "coins", "value": 300},
      "visit_description": "\U0001f579\ufe0f ¡Rompiste el récord y canjeaste tus tickets por \U0001fa99 **300**!",
      "upgrades": {
          "vr_zone":          {"name": "Zona VR",            "emoji": "\U0001f97d", "cost": 30_000,  "income_bonus": 0.20, "req_level": 1},
          "tournament_stage": {"name": "Escenario de Torneo","emoji": "\U0001f3c6", "cost": 45_000,  "income_bonus": 0.20, "req_level": 3},
          "prize_counter":    {"name": "Mostrador de Premios","emoji": "\U0001f381", "cost": 25_000,  "income_bonus": 0.15, "req_level": 2},
          "esports_arena":    {"name": "Arena de eSports",   "emoji": "\U0001f3ae", "cost": 120_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
}


# ─────────────────────────────────────────────────────────
# HELPERS DE BASE DE DATOS
# ─────────────────────────────────────────────────────────

def get_business(business_id: str) -> dict | None:
  return businesses_col.find_one({"_id": business_id})


def get_owner_businesses(owner_id: str) -> list[dict]:
  return list(businesses_col.find({"owner_id": owner_id}))


def get_xp_for_next_level(level: int) -> int:
  if level >= len(XP_PER_LEVEL):
      return 999_999_999
  return XP_PER_LEVEL[level]


# ─────────────────────────────────────────────────────────
# MOTOR DE INGRESOS
# ─────────────────────────────────────────────────────────

def compute_income(business: dict) -> dict:
  """
  Calcula los ingresos/gastos pendientes de un negocio SIN escribir en la base de datos.
  Devuelve: hours_pending, gross_income, maintenance, worker_salaries, net, xp_earned
  """
  btype         = BUSINESS_TYPES[business["type"]]
  now           = time.time()
  last          = business.get("last_collected", now)
  elapsed_hours = min((now - last) / 3600.0, MAX_ACCUMULATION_HOURS)

  level    = business.get("level", 1)
  rep      = business.get("reputation", 50)
  upgrades = business.get("upgrades", [])
  workers  = business.get("workers", [])

  base    = btype["base_income_per_hour"] * elapsed_hours
  lv_mult = LEVEL_INCOME_MULT[min(level, len(LEVEL_INCOME_MULT) - 1)]

  # Las mejoras se acumulan de forma aditiva
  upgrade_bonus = 1.0
  for upg_id in upgrades:
      upg = btype["upgrades"].get(upg_id)
      if upg:
          upgrade_bonus += upg["income_bonus"]

  # Cada trabajador aporta un 15% de su (eficiencia - 1.0)
  worker_bonus = 1.0
  for w in workers:
      worker_bonus += (w.get("efficiency", 1.0) - 1.0) * 0.15

  rep_mult = reputation_multiplier(rep)
  gross    = int(base * lv_mult * upgrade_bonus * worker_bonus * rep_mult)

  maintenance     = int(btype["base_maintenance_per_hour"] * elapsed_hours)
  worker_salaries = int(sum(w.get("salary", 0) for w in workers) * elapsed_hours)
  net             = gross - maintenance - worker_salaries
  xp_earned       = max(1, int(elapsed_hours * level * 10))

  return {
      "hours_pending":   round(elapsed_hours, 2),
      "gross_income":    gross,
      "maintenance":     maintenance,
      "worker_salaries": worker_salaries,
      "net":             net,
      "xp_earned":       xp_earned,
  }


def collect_income(business_id: str) -> dict:
  """Recoge ingresos pendientes, aplica XP/subida de nivel y actualiza la reputación."""
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}

  result = compute_income(business)
  now    = time.time()

  new_xp     = business.get("xp", 0) + result["xp_earned"]
  new_level  = business.get("level", 1)
  leveled_up = False

  while new_level < len(XP_PER_LEVEL) and new_xp >= XP_PER_LEVEL[new_level]:
      new_xp    -= XP_PER_LEVEL[new_level]
      new_level += 1
      leveled_up = True

  new_rep = min(100, business.get("reputation", 50) + 2)

  businesses_col.update_one(
      {"_id": business_id},
      {
          "$set": {
              "last_collected": now,
              "xp":             new_xp,
              "level":          new_level,
              "reputation":     new_rep,
          },
          "$inc": {
              "total_earned": max(0, result["net"]),
              "total_spent":  result["maintenance"] + result["worker_salaries"],
          },
      },
  )

  result["leveled_up"] = leveled_up
  result["new_level"]  = new_level
  result["new_rep"]    = new_rep
  return result


# ─────────────────────────────────────────────────────────
# OPERACIONES DE NEGOCIO
# ─────────────────────────────────────────────────────────

def buy_business(owner_id: str, btype_key: str, name: str) -> dict:
  if btype_key not in BUSINESS_TYPES:
      return {"error": f"Tipo de negocio desconocido '{btype_key}'."}
  now         = time.time()
  short_id    = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
  business_id = f"{btype_key[:3].upper()}-{short_id}"
  doc = {
      "_id":            business_id,
      "owner_id":       owner_id,
      "type":           btype_key,
      "name":           name,
      "level":          1,
      "xp":             0,
      "reputation":     50,
      "workers":        [],
      "upgrades":       [],
      "last_collected": now,
      "founded_at":     now,
      "total_earned":   0,
      "total_spent":    0,
      "visits":         0,
  }
  businesses_col.insert_one(doc)
  return {"business_id": business_id, "doc": doc}


def apply_upgrade(business_id: str, upgrade_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}
  btype   = BUSINESS_TYPES[business["type"]]
  upgrade = btype["upgrades"].get(upgrade_id)
  if not upgrade:
      return {"error": "ID de mejora inválido."}
  if business.get("level", 1) < upgrade["req_level"]:
      return {"error": f'Requiere Nivel de Negocio {upgrade["req_level"]}.'}
  if upgrade_id in business.get("upgrades", []):
      return {"error": "Mejora ya comprada."}
  businesses_col.update_one({"_id": business_id}, {"$push": {"upgrades": upgrade_id}})
  return {"ok": True, "upgrade": upgrade}


def hire_worker(business_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}
  btype   = BUSINESS_TYPES[business["type"]]
  workers = business.get("workers", [])
  if len(workers) >= btype["max_workers"]:
      return {"error": f'Máximo de trabajadores ({btype["max_workers"]}) ya alcanzado.'}

  name       = random.choice(WORKER_NAMES)
  role       = random.choice(btype["worker_roles"])
  base_sal   = btype["worker_base_salary"]
  salary     = int(base_sal * random.uniform(0.80, 1.20))
  efficiency = round(random.uniform(0.80, 1.30), 2)
  worker     = {
      "name":       name,
      "role":       role,
      "salary":     salary,
      "efficiency": efficiency,
      "level":      1,
      "xp":         0,
      "hired_at":   int(time.time()),
  }
  hire_cost = salary * 5
  businesses_col.update_one({"_id": business_id}, {"$push": {"workers": worker}})
  return {"ok": True, "worker": worker, "hire_cost": hire_cost}


def fire_worker(business_id: str, worker_index: int) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}
  workers = business.get("workers", [])
  if worker_index < 0 or worker_index >= len(workers):
      return {"error": "Índice de trabajador inválido."}
  fired = workers[worker_index]
  workers.pop(worker_index)
  businesses_col.update_one({"_id": business_id}, {"$set": {"workers": workers}})
  return {"ok": True, "fired": fired}


def sell_business(business_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}
  btype          = BUSINESS_TYPES[business["type"]]
  upgrades_owned = business.get("upgrades", [])
  upgrade_value  = sum(btype["upgrades"][u]["cost"] for u in upgrades_owned if u in btype["upgrades"])
  level          = business.get("level", 1)
  sell_price     = int(
      (btype["base_cost"] + upgrade_value)
      * btype["sell_multiplier"]
      * (1 + (level - 1) * 0.05)
  )
  businesses_col.delete_one({"_id": business_id})
  return {"ok": True, "sell_price": sell_price, "name": business["name"]}


def rename_business(business_id: str, new_name: str) -> dict:
  if not get_business(business_id):
      return {"error": "Negocio no encontrado."}
  businesses_col.update_one({"_id": business_id}, {"$set": {"name": new_name}})
  return {"ok": True}



def visit_business(visitor_id: str, business_id: str) -> dict:
  """El visitante paga la tarifa de entrada; el dueño la recibe. Devuelve los detalles de la transacción incluyendo la especificación del beneficio."""
  business = get_business(business_id)
  if not business:
      return {"error": "Negocio no encontrado."}
  btype = BUSINESS_TYPES[business["type"]]
  fee     = btype.get("entry_fee", 0)
  desc    = btype.get("visit_description", "Visitaste el negocio.")
  benefit = btype.get("visit_benefit", {"type": "none", "value": 0})
  businesses_col.update_one({"_id": business_id}, {"$inc": {"visits": 1}})
  return {
      "ok":                True,
      "fee":               fee,
      "owner_id":          business["owner_id"],
      "btype_name":        btype["name"],
      "btype_emoji":       btype["emoji"],
      "visit_description": desc,
      "visit_benefit":     benefit,
  }


def increment_visits(business_id: str) -> None:
  businesses_col.update_one({"_id": business_id}, {"$inc": {"visits": 1}})


def get_leaderboard(limit: int = 10) -> list[dict]:
  return list(businesses_col.find({}, sort=[("total_earned", -1)]).limit(limit))
