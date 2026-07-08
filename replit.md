# YSL Bot

A Discord bot built with `discord.py` using a modular Cog-based architecture. Features include economy, pets, games, stocks, starboard, bounties, and business systems — all backed by MongoDB.

## Stack
- **Python** + `discord.py`
- **MongoDB** (via `pymongo`) — database for all user data
- **Flask** — keep-alive HTTP server running in a background thread
- **OpenAI** — used by the `fake_admin_ai` cog

## Required Secrets
| Secret | Description |
|--------|-------------|
| `DISCORD_TOKEN` | Discord bot token |
| `MONGO_URI` | MongoDB connection string |
| `GITHUB_TOKEN` | GitHub PAT for pushing changes |
| `OPENAI_API_KEY` | OpenAI key (for fake_admin_ai cog) |

## How to run
```bash
python main.py
```

## Structure
- `main.py` — entry point, loads cogs, starts Flask keep-alive
- `cogs/` — feature modules (admin, economy, pets, games, utility, events, fake_admin_ai, starboard, stocks, bounties, business)
- `utils/` — shared helpers and DB operations
- `views/` — Discord UI components (buttons, selects)
- `config.py` — constants, loot tables, shop prices, env vars
- `database.py` — MongoDB connection and collection references

## Git workflow
After each requested change, push to `origin main` on GitHub using the configured `GITHUB_TOKEN`.

## Repositorio traducido (rite-bot)
Existe una copia completa del proyecto traducida al español (todo el texto visible al usuario, comentarios y docstrings — los nombres de comandos permanecen en inglés) publicada en un repositorio nuevo: `https://github.com/quimcressonjodar/rite-bot` (rama `main`). Se generó a partir de un commit huérfano (sin el historial del repo original) para evitar conflictos con el remoto `origin`. El remoto local `rite-bot` apunta a este repositorio.

## User preferences
- Make requested code changes then git push after each one.
- Comandos del bot (nombres tipo `name="..."` en los decoradores de discord.py) deben quedar siempre en inglés; todo lo demás (mensajes, embeds, descripciones, comentarios) en español.
