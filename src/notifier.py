import os
import time
from datetime import datetime
from pathlib import Path
import requests

from src.contract_filter import CONTRACT_BADGES
from src.models import Opportunity

BATCH_SIZE = 10
DELAY_BETWEEN_BATCHES_SECONDS = 3


def _load_env_file(path: Path) -> dict:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip().strip("\"'")
    return values


def get_telegram_credentials() -> tuple[str | None, str | None]:
    """Obtiene el token del bot y el chat_id desde variables de entorno o archivo .env."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")

    if not token or not chat_id:
        # 1. Buscar en archivo .env en la raíz del proyecto
        env_path = Path(__file__).resolve().parent.parent / ".env"
        env_vars = _load_env_file(env_path)
        token = token or env_vars.get("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or env_vars.get("TELEGRAM_CHAT_ID") or env_vars.get("TELEGRAM_DEFAULT_CHAT_ID")

    if not token or not chat_id:
        # 2. Buscar en fallback ~/.config/telegram-bot/credentials.env
        fallback_path = Path.home() / ".config" / "telegram-bot" / "credentials.env"
        fallback_vars = _load_env_file(fallback_path)
        token = token or fallback_vars.get("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or fallback_vars.get("TELEGRAM_CHAT_ID") or fallback_vars.get("TELEGRAM_DEFAULT_CHAT_ID")

    return token, chat_id


def _get_greeting(dt: datetime | None = None) -> str:
    now = dt or datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "¡Hola! Buenos días ☀️"
    elif 12 <= hour < 19:
        return "¡Hola! Buenas tardes ⛅"
    else:
        return "¡Hola! Buenas noches 🌙"


def _format_opportunity(opp: Opportunity) -> str:
    if opp.modalidad == "remoto":
        icon = "✅"
    elif opp.modalidad == "hibrido":
        icon = "🔄"
    elif opp.modalidad == "presencial":
        icon = "🏢"
    else:
        icon = "📌" if opp.modalidad else ""

    badge = CONTRACT_BADGES.get(opp.tipo, "")
    badge_str = f" · {badge}" if badge else ""

    loc = f" ({opp.ubicacion})" if opp.ubicacion and opp.modalidad != "remoto" else ""
    salario = f" · 💰 {opp.presupuesto}" if opp.presupuesto else ""
    prefix = f"{icon} " if icon else ""
    clean_rol = opp.rol.replace("[", "(").replace("]", ")")
    return f"{prefix}[{clean_rol}]({opp.url}) — {opp.empresa}{loc}{badge_str}{salario}"


def build_batches(new_opportunities: list[Opportunity], batch_size: int = BATCH_SIZE, now: datetime | None = None) -> list[str]:
    if not new_opportunities:
        return []

    ranked = sorted(new_opportunities, key=lambda o: -o.score)
    total = len(ranked)
    total_batches = (total + batch_size - 1) // batch_size
    greeting = _get_greeting(now)

    messages = []
    for i in range(0, total, batch_size):
        chunk = ranked[i:i + batch_size]
        batch_num = i // batch_size + 1

        if batch_num == 1:
            if total == 1:
                header = f"{greeting}\nLes comparto la oferta destacada del día:"
            elif total_batches == 1:
                header = f"{greeting}\nLes comparto las *{total} ofertas destacadas* del día:"
            else:
                header = f"{greeting}\nLes comparto las ofertas destacadas del día (*{total}* en total — parte 1 de {total_batches}):"
        else:
            header = f"Continuación de las ofertas destacadas (parte {batch_num} de {total_batches}):"

        lines = [header, ""] + [_format_opportunity(o) for o in chunk]

        if batch_num == total_batches:
            lines.append("")
            lines.append("¡Mucho éxito en las postulaciones! 🚀")

        messages.append("\n".join(lines))

    return messages


def _send_telegram(token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[notifier] error enviando mensaje a Telegram: {e}")
        return False


def notify_new_opportunities(new_opportunities: list[Opportunity]) -> None:
    if not new_opportunities:
        return

    token, chat_id = get_telegram_credentials()
    if not token or not chat_id:
        print("\n⚠️  [notifier] No se detectaron credenciales de Telegram (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        print("    Crea tu archivo '.env' para recibir avisos automáticos en tu celular (ver README.md).")
        return

    batches = build_batches(new_opportunities)
    print(f"\n📤 Enviando {len(new_opportunities)} oportunidad(es) a Telegram ({len(batches)} mensaje(s))...")
    for i, message in enumerate(batches):
        if i > 0:
            time.sleep(DELAY_BETWEEN_BATCHES_SECONDS)
        _send_telegram(token, chat_id, message)
    print("✅ Notificaciones enviadas correctamente.")
