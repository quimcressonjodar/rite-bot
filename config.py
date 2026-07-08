import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

DEFAULT_WEEKLY_XP_REQUIREMENT = 30_000
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", str(DEFAULT_WEEKLY_XP_REQUIREMENT)))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

WELCOME_CHANNEL_ID = 1206229312743809054
OWNER_IDS = {1436417791615045785}

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
VALID_BETS = {"red", "black", "even", "odd", "specific_number", "1st", "2nd", "3rd"}

CARD_EMOJIS = {
    '♠️': {'2': '🂢', '3': '🂣', '4': '🂤', '5': '🂥', '6': '🂦', '7': '🂧', '8': '🂨', '9': '🂩', '10': '🂪', 'J': '🂫', 'Q': '🂭', 'K': '🂮', 'A': '🂡'},
    '♥️': {'2': '🂲', '3': '🂳', '4': '🂴', '5': '🂵', '6': '🂶', '7': '🂷', '8': '🂸', '9': '🂹', '10': '🂺', 'J': '🂻', 'Q': '🂽', 'K': '🂾', 'A': '🂱'},
    '♦️': {'2': '🃂', '3': '🃃', '4': '🃄', '5': '🃅', '6': '🃆', '7': '🃇', '8': '🃈', '9': '🃉', '10': '🃊', 'J': '🃋', 'Q': '🃍', 'K': '🃎', 'A': '🃁'},
    '♣️': {'2': '🃒', '3': '🃓', '4': '🃔', '5': '🃕', '6': '🃖', '7': '🃗', '8': '🃘', '9': '🃙', '10': '🃚', 'J': '🃛', 'Q': '🃝', 'K': '🃞', 'A': '🃑'},
}
CARD_BACK = "🂠"


PET_LOOT_PROBABILITIES = {
    "slime":    {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "rabbit":   {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "mouse":    {"common": 92, "rare": 6, "epic": 1.5, "legendary": 0.5},
    "bat":      {"common": 88, "rare": 10, "epic": 1.5, "legendary": 0.5},
    "spider":   {"common": 86, "rare": 12, "epic": 1.5, "legendary": 0.5},
    "snake":    {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "frog":     {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "turtle":   {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "parrot":   {"common": 84, "rare": 13, "epic": 2.5, "legendary": 0.5},
    "penguin":  {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "raccoon":  {"common": 82, "rare": 15, "epic": 2.5, "legendary": 0.5},
    "dog":      {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "cat":      {"common": 80, "rare": 17, "epic": 2.5, "legendary": 0.5},
    "owl":      {"common": 78, "rare": 18, "epic": 3.5, "legendary": 0.5},
    "fox":      {"common": 75, "rare": 20, "epic": 4.5, "legendary": 0.5},
    "wolf":     {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "tiger":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "bear":     {"common": 63, "rare": 30, "epic": 6,   "legendary": 1},
    "griffin":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "lynx":     {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "panther":  {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "rhino":    {"common": 68, "rare": 25, "epic": 6,   "legendary": 1},
    "elephant": {"common": 68, "rare": 25, "epic": 6,   "legendary": 1},
    "shark":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "eagle":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "cobra":    {"common": 62, "rare": 30, "epic": 7,   "legendary": 1},
    "hyena":    {"common": 62, "rare": 30, "epic": 7,   "legendary": 1},
    "cheetah":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "gorilla":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "dragon":      {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "golem":       {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "hydra":       {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "pegasus":     {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "unicorn":     {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "manticore":   {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "basilisk":    {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "cerberus":    {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "thunderbird": {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "yeti":        {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "wyvern":      {"common": 48, "rare": 33, "epic": 16,  "legendary": 3},
    "ent":         {"common": 48, "rare": 33, "epic": 16,  "legendary": 3},
    "minotaur":    {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "golem_core":  {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "phoenix":      {"common": 35, "rare": 35, "epic": 25, "legendary": 4.5, "godly": 0.5},
    "chimera":      {"common": 33, "rare": 34, "epic": 27, "legendary": 5.5, "godly": 0.5},
    "kraken":       {"common": 30, "rare": 33, "epic": 30, "legendary": 6,   "godly": 1},
    "leviathan":    {"common": 27, "rare": 30, "epic": 34, "legendary": 8,   "godly": 1},
    "titan":        {"common": 25, "rare": 25, "epic": 37, "legendary": 11,  "godly": 2},
    "bahamut":      {"common": 20, "rare": 20, "epic": 44, "legendary": 14,  "godly": 2},
    "cthulhu":      {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "reaper":       {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "archangel":    {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "demon_lord":   {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "void_dragon":  {"common": 5,  "rare": 5,  "epic": 45, "legendary": 40,  "godly": 5},
}

PET_SHOP = {
    "slime":    {"price": 5_000,       "hp": 50,   "damage": 10,  "emoji": "🧪"},
    "rabbit":   {"price": 3_500,       "hp": 40,   "damage": 8,   "emoji": "🐇"},
    "mouse":    {"price": 2_500,       "hp": 30,   "damage": 12,  "emoji": "🐭"},
    "bat":      {"price": 6_000,       "hp": 45,   "damage": 15,  "emoji": "🦇"},
    "spider":   {"price": 7_500,       "hp": 35,   "damage": 22,  "emoji": "🕷️"},
    "snake":    {"price": 9_000,       "hp": 60,   "damage": 18,  "emoji": "🐍"},
    "frog":     {"price": 4_500,       "hp": 55,   "damage": 10,  "emoji": "🐸"},
    "turtle":   {"price": 10_000,      "hp": 120,  "damage": 5,   "emoji": "🐢"},
    "parrot":   {"price": 8_000,       "hp": 50,   "damage": 20,  "emoji": "🦜"},
    "penguin":  {"price": 11_000,      "hp": 70,   "damage": 15,  "emoji": "🐧"},
    "raccoon":  {"price": 13_000,      "hp": 65,   "damage": 25,  "emoji": "🦝"},
    "dog":      {"price": 12_000,      "hp": 100,  "damage": 20,  "emoji": "🐕"},
    "cat":      {"price": 15_000,      "hp": 80,   "damage": 25,  "emoji": "🐈"},
    "owl":      {"price": 25_000,      "hp": 90,   "damage": 30,  "emoji": "🦉"},
    "fox":      {"price": 40_000,      "hp": 110,  "damage": 35,  "emoji": "🦊"},
    "lynx":     {"price": 35_000,      "hp": 100,  "damage": 45,  "emoji": "🐆"},
    "panther":  {"price": 45_000,      "hp": 120,  "damage": 55,  "emoji": "🐈‍⬛"},
    "rhino":    {"price": 65_000,      "hp": 200,  "damage": 30,  "emoji": "🦏"},
    "elephant": {"price": 80_000,      "hp": 250,  "damage": 35,  "emoji": "🐘"},
    "shark":    {"price": 55_000,      "hp": 130,  "damage": 60,  "emoji": "🦈"},
    "eagle":    {"price": 40_000,      "hp": 90,   "damage": 50,  "emoji": "🦅"},
    "cobra":    {"price": 30_000,      "hp": 80,   "damage": 65,  "emoji": "🐍"},
    "hyena":    {"price": 28_000,      "hp": 110,  "damage": 40,  "emoji": "🐕"},
    "cheetah":  {"price": 50_000,      "hp": 85,   "damage": 75,  "emoji": "🐆"},
    "gorilla":  {"price": 70_000,      "hp": 180,  "damage": 45,  "emoji": "🦍"},
    "wolf":     {"price": 85_000,      "hp": 150,  "damage": 40,  "emoji": "🐺"},
    "tiger":    {"price": 150_000,     "hp": 220,  "damage": 80,  "emoji": "🐯"},
    "bear":     {"price": 225_000,     "hp": 300,  "damage": 60,  "emoji": "🐻"},
    "griffin":  {"price": 500_000,     "hp": 450,  "damage": 120, "emoji": "🦅"},
    "unicorn":  {"price": 180_000,     "hp": 200,  "damage": 100, "emoji": "🦄"},
    "manticore":{"price": 250_000,     "hp": 280,  "damage": 110, "emoji": "🦁"},
    "basilisk": {"price": 350_000,     "hp": 350,  "damage": 130, "emoji": "🦎"},
    "cerberus": {"price": 500_000,     "hp": 500,  "damage": 140, "emoji": "🐕"},
    "thunderbird":{"price": 750_000,   "hp": 400,  "damage": 250, "emoji": "⚡"},
    "yeti":     {"price": 450_000,     "hp": 600,  "damage": 90,  "emoji": "🧊"},
    "wyvern":   {"price": 850_000,     "hp": 450,  "damage": 220, "emoji": "🐲"},
    "ent":      {"price": 400_000,     "hp": 800,  "damage": 70,  "emoji": "🌳"},
    "minotaur": {"price": 300_000,     "hp": 420,  "damage": 140, "emoji": "🐂"},
    "golem_core":{"price": 600_000,    "hp": 750,  "damage": 110, "emoji": "💠"},
    "dragon":   {"price": 1_200_000,   "hp": 1000, "damage": 300, "emoji": "🐉"},
    "golem":    {"price": 2_500_000,   "hp": 2000, "damage": 250, "emoji": "🗿"},
    "hydra":    {"price": 5_000_000,   "hp": 3000, "damage": 400, "emoji": "🐍"},
    "pegasus":  {"price": 8_500_000,   "hp": 4500, "damage": 550, "emoji": "🦄"},
    "phoenix":  {"price": 15_000_000,  "hp": 6000, "damage": 800, "emoji": "🐦‍🔥"},
    "chimera":  {"price": 25_000_000,  "hp": 8000, "damage": 1000, "emoji": "🦁"},
    "kraken":   {"price": 50_000_000,  "hp": 12000, "damage": 1500, "emoji": "🦑"},
    "leviathan":{"price": 100_000_000, "hp": 20000, "damage": 2500, "emoji": "🌊"},
    "titan":    {"price": 250_000_000, "hp": 40000, "damage": 4500, "emoji": "👑"},
    "bahamut":  {"price": 500_000_000, "hp": 75000, "damage": 8000, "emoji": "🌌"},
    "cthulhu":  {"price": 15_000_000_000, "hp": 250_000, "damage": 25_000, "emoji": "🐙"},
    "reaper":   {"price": 12_000_000_000, "hp": 180_000, "damage": 35_000, "emoji": "💀"},
    "archangel":{"price": 25_000_000_000, "hp": 500_000, "damage": 45_000, "emoji": "😇"},
    "demon_lord":{"price": 20_000_000_000, "hp": 400_000, "damage": 55_000, "emoji": "😈"},
    "void_dragon":{"price": 75_000_000_000, "hp": 1_500_000, "damage": 150_000, "emoji": "🌌"},
}

FOOD_ITEMS = {
    "basic": {"price": 25_000, "hunger": 20, "emoji": "🍖", "name": "Comida Básica"},
    "premium": {"price": 100_000, "hunger": 50, "emoji": "🥩", "name": "Comida Premium"},
    "enchanted": {"price": 500_000, "hunger": 100, "emoji": "🍱", "name": "Comida Encantada"},
}

ROLE_SHOP = {
    "bronze":    {"price": 25_000,        "claim": 2_000,       "role_id": 1523427695638085643},
    "silver":    {"price": 75_000,        "claim": 5_000,       "role_id": 1523427696284270715},
    "gold":      {"price": 200_000,       "claim": 12_000,      "role_id": 1523427697198497963},
    "diamond":   {"price": 500_000,       "claim": 30_000,      "role_id": 1523427697966190642},
    "emerald":   {"price": 1_000_000,     "claim": 75_000,      "role_id": 1523427698452463767},
    "mythic":    {"price": 3_000_000,     "claim": 200_000,     "role_id": 1523427698981077023},
    "cosmic":    {"price": 10_000_000,    "claim": 650_000,     "role_id": 1523427699442450675},
    "eternal":   {"price": 25_000_000,    "claim": 1_500_000,   "role_id": 1523427700079988816},
    "secret":    {"price": 75_000_000,    "claim": 4_000_000,   "role_id": 1523427700755136712},
    "godlike":   {"price": 200_000_000,   "claim": 10_000_000,  "role_id": 1523427701363441784},
    "celestial": {"price": 500_000_000,   "claim": 25_000_000,  "role_id": 1523427702252765377},
    "ascended":  {"price": 1_000_000_000, "claim": 60_000_000,  "role_id": 1523427702797893764},
}

PET_RARITIES = {
    "slime": "basic", "rabbit": "basic", "mouse": "basic", "bat": "basic", "spider": "basic",
    "snake": "basic", "frog": "basic", "turtle": "basic", "parrot": "basic", "penguin": "basic",
    "raccoon": "basic", "dog": "basic", "cat": "basic", "owl": "basic", "fox": "basic",
    "wolf": "rare", "tiger": "rare", "bear": "rare", "griffin": "rare", "lynx": "rare",
    "panther": "rare", "rhino": "rare", "elephant": "rare", "shark": "rare", "eagle": "rare",
    "cobra": "rare", "hyena": "rare", "cheetah": "rare", "gorilla": "rare",
    "dragon": "epic", "golem": "epic", "hydra": "epic", "pegasus": "epic", "unicorn": "epic",
    "manticore": "epic", "basilisk": "epic", "cerberus": "epic", "thunderbird": "epic", "yeti": "epic",
    "wyvern": "epic", "ent": "epic", "minotaur": "epic", "golem_core": "epic",
    "phoenix": "legendary", "chimera": "legendary", "kraken": "legendary",
    "leviathan": "legendary", "titan": "legendary", "bahamut": "legendary",
    "cthulhu": "legendary", "reaper": "legendary", "archangel": "legendary",
    "demon_lord": "legendary", "void_dragon": "legendary",
}

ADVENTURE_LOOT = {
    "common": [
        ("🪵 Palo", 8), ("🪨 Piedra", 10), ("🔩 Tornillo", 12), ("🧻 Tela Vieja", 9),
        ("🥫 Lata Oxidada", 11), ("🪢 Cuerda", 15), ("🧴 Botella de Plástico", 6),
        ("📎 Chatarra Metálica", 18), ("🪛 Herramienta Rota", 20), ("🪙 Moneda Pequeña", 25),
        ("🔋 Batería Agotada", 14), ("📦 Cajón de Madera", 22), ("🕯️ Vela", 10),
        ("🧱 Ladrillo", 13), ("⚙️ Engranaje", 28), ("🪓 Hacha Oxidada", 30),
        ("🪤 Trampa para Osos", 38), ("📜 Mapa Rasgado", 40), ("🥄 Cuchara de Plata", 48),
        ("🧲 Imán", 20), ("🧃 Caja de Jugo", 8), ("🪙 Moneda de Cobre", 18),
        ("🎣 Anzuelo", 22), ("📻 Radio Roto", 45), ("⌚ Reloj Viejo", 55),
        ("🧤 Guante de Cuero", 25), ("🪖 Casco Agrietado", 60), ("🗝️ Llave Pequeña", 70),
        ("🪞 Espejo Roto", 38), ("🥾 Bota Vieja", 5), ("🔩 Clavo Oxidado", 6),
        ("🥄 Cuchara de Plástico", 4), ("📦 Caja de Cartón", 8), ("🍾 Botella Vacía", 3),
        ("🩹 Vendaje Usado", 10), ("🦴 Espina de Pez", 7), ("📰 Periódico Mojado", 9),
        ("🧦 Calcetín Sucio", 6), ("🖇️ Clip Doblado", 4), ("💎 Fragmento de Vidrio", 11),
        ("🔪 Cuchillo Mellado", 13), ("🧵 Hilo Deshilachado", 7), ("🔮 Canica Rajada", 8),
        ("🔥 Cerilla Quemada", 2), ("🪵 Ramita", 3), ("🪨 Grava", 4), ("🔩 Tuerca", 5),
    ],
    "rare": [
        ("💍 Anillo de Plata", 200), ("🪙 Moneda de Oro", 300), ("💎 Zafiro", 480),
        ("🔮 Orbe Mágico", 600), ("📿 Collar Antiguo", 720), ("⚔️ Daga de Caballero", 880),
        ("🏺 Vasija Antigua", 1000), ("💠 Esmeralda", 1200), ("🧪 Poción Rara", 1400),
        ("📦 Cofre del Tesoro", 1600), ("🗡️ Hoja de Asesino", 1680), ("🛡️ Escudo Dorado", 2000),
        ("💰 Alijo Oculto", 2200), ("📜 Pergamino Encantado", 2400), ("🪬 Amuleto de la Suerte", 2600),
        ("🧿 Ojo Místico", 2800), ("🐚 Concha con Perla", 3000), ("💎 Cristal de Rubí", 3200),
        ("⚡ Núcleo Cargado", 3400), ("🔑 Llave Antigua", 3600), ("🪨 Guijarro Pulido", 180),
        ("🪙 Moneda de Plata", 240), ("🗝️ Llave de Hierro", 340), ("🥉 Medalla de Bronce", 280),
    ],
    "epic": [
        ("👑 Corona Dorada", 5000), ("💎 Diamante Grande", 7500), ("🏺 Ídolo Maldito", 9000),
        ("🔮 Ojo de Dragón", 12000), ("⚔️ Excalibur Sagrada", 15000), ("🧬 Tecnología Alienígena", 18000),
        ("💠 Esencia Pura", 20000), ("🧪 Elixir de Vida", 25000), ("📜 Profecía Perdida", 30000),
        ("📦 Cajón Celestial", 40000), ("💍 Anillo del Fénix", 50000), ("🛡️ Escudo de Escamas de Dragón", 60000),
    ],
    "legendary": [
        ("🌌 Núcleo del Vacío", 150000), ("⭐ Estrella Caída", 250000), ("🏺 Caja de Pandora", 500000),
        ("🔮 Ojo de la Eternidad", 750000), ("⚔️ Asesino de Dioses", 1000000), ("🧬 Código Génesis", 1500000),
    ],
    "godly": [
        ("♾️ Piedra del Infinito", 10_000_000), ("🌌 Fragmento del Universo", 25_000_000), ("👑 Corona de la Creación", 50_000_000),
    ]
}

PRESTIGE_LEVELS = {
    0: {"name": "Ninguno", "threshold": 0, "discount": 0.0, "loan_mult": 1.0},
    1: {"name": "Bronce", "threshold": 100_000, "discount": 0.02, "loan_mult": 1.0},
    2: {"name": "Plata", "threshold": 500_000, "discount": 0.05, "loan_mult": 2.0},
    3: {"name": "Oro", "threshold": 2_000_000, "discount": 0.08, "loan_mult": 5.0},
    4: {"name": "Platino", "threshold": 10_000_000, "discount": 0.12, "loan_mult": 10.0},
    5: {"name": "Esmeralda", "threshold": 50_000_000, "discount": 0.15, "loan_mult": 20.0},
    6: {"name": "Diamante", "threshold": 200_000_000, "discount": 0.20, "loan_mult": 50.0},
    7: {"name": "Maestro", "threshold": 1_000_000_000, "discount": 0.25, "loan_mult": 100.0},
}

BREEDING_COST_RATIO = 0.25
BREEDING_SUCCESS_CHANCE = 70
BREEDING_RISK_CHANCE = 5

STOCK_SYMBOLS = {
    "VRTX": {"name": "Vertex Dynamics", "sector": "IA y Robótica", "volatility": 0.05, "initial_price": 500, "description": "Soluciones de vanguardia en IA y robótica."},
    "GLBL": {"name": "Global Energy", "sector": "Energía", "volatility": 0.02, "initial_price": 500, "description": "Energía sostenible e infraestructura."},
    "AURA": {"name": "Aura Pharmaceuticals", "sector": "Biotecnología", "volatility": 0.04, "initial_price": 500, "description": "Investigación médica de próxima generación y biotecnología."},
    "ORBT": {"name": "Orbital Space", "sector": "Turismo Espacial", "volatility": 0.08, "initial_price": 500, "description": "Viajes espaciales comerciales y turismo."},
    "TITN": {"name": "Titan Heavy Industries", "sector": "Manufactura", "volatility": 0.03, "initial_price": 500, "description": "Maquinaria pesada y producción industrial."},
}

STOCK_UPDATE_INTERVAL = 30
STOCK_HISTORY_LIMIT = 96
STOCK_FEE = 0.02
STOCK_DIVIDEND_RATE = 0.005
STOCK_NEWS_PROBABILITY = 0.30
STOCK_NEWS_CHANNEL_ID = 1206197908399980575

ADVENTURE_EVENTS = [
    {"text": "¡Tu mascota encontró un pequeño alijo escondido!", "min_gain": 50, "max_gain": 200},
    {"text": "Tu mascota ayudó a un viajero y recibió una propina.", "min_gain": 30, "max_gain": 150},
    {"text": "Tu mascota descubrió un montón de monedas brillantes en una cueva.", "min_gain": 100, "max_gain": 500},
    {"text": "¡Tu mascota ganó una carrera local!", "min_gain": 200, "max_gain": 800},
    {"text": "Tu mascota encontró algo de cambio suelto en la calle.", "min_gain": 10, "max_gain": 50},
    {"text": "Tu mascota desenterró un pequeño cofre del tesoro.", "min_gain": 500, "max_gain": 1500},
    {"text": "Tu mascota encontró una billetera perdida y se quedó con la recompensa.", "min_gain": 150, "max_gain": 400},
    {"text": "Tu mascota rebuscó entre algunas ruinas.", "min_gain": 80, "max_gain": 300},
    {"text": "Tu mascota hizo trucos para una multitud.", "min_gain": 120, "max_gain": 350},
    {"text": "Tu mascota encontró una gema rara y la vendió.", "min_gain": 1000, "max_gain": 3000},
]

STOCKS = {
    "VRTX": {"name": "Vertex Dynamics", "sector": "IA y Robótica", "volatility": 0.12, "initial_price": 500, "description": "Soluciones de vanguardia en IA y robótica."},
    "CRPT": {"name": "CryptoVault Financial", "sector": "Finanzas", "volatility": 0.20, "initial_price": 450, "description": "Finanzas descentralizadas y gestión de activos digitales."},
    "AURA": {"name": "Aura Pharmaceuticals", "sector": "Biotecnología", "volatility": 0.10, "initial_price": 500, "description": "Investigación médica de próxima generación y biotecnología."},
    "ORBT": {"name": "Orbital Space", "sector": "Turismo Espacial", "volatility": 0.18, "initial_price": 500, "description": "Viajes espaciales comerciales y turismo."},
    "TITN": {"name": "Titan Heavy Industries", "sector": "Manufactura", "volatility": 0.08, "initial_price": 500, "description": "Maquinaria pesada y producción industrial."},
}
