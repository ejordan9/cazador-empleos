import html
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector
from src.models import Opportunity

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class TelegramChannelCollector(Collector):
    """Colector para canales públicos de Telegram vía su vista previa web (t.me/s/...)."""

    name = "telegram_channel"

    def __init__(
        self,
        channels: list[str],
        max_posts_per_channel: int = 25,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 15,
        delay: int = 2,
    ):
        self.channels = channels
        self.max_posts_per_channel = max_posts_per_channel
        self.headers = {
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }
        self.timeout = timeout
        self.delay = delay

    def collect(self) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        for i, channel in enumerate(self.channels):
            if i > 0:
                time.sleep(self.delay)

            clean_channel = self._clean_channel_name(channel)
            if not clean_channel:
                continue

            try:
                posts = self._collect_channel(clean_channel)
            except Exception as e:
                print(f"    [telegram] canal '@{clean_channel}' falló ({e}), se salta")
                continue

            for opp in posts:
                if opp.url in seen_urls:
                    continue
                seen_urls.add(opp.url)
                opportunities.append(opp)

        return opportunities

    def _clean_channel_name(self, channel: str) -> str:
        ch = channel.strip()
        ch = re.sub(r"^https?://(?:www\.)?t\.me/(?:s/)?", "", ch)
        ch = ch.lstrip("@").strip().rstrip("/")
        return ch

    def _collect_channel(self, channel_name: str) -> list[Opportunity]:
        url = f"https://t.me/s/{channel_name}"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code != 200:
            print(f"    [telegram] error {resp.status_code} al consultar @{channel_name}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        wraps = soup.select(".tgme_widget_message_wrap")

        opportunities = []
        for wrap in wraps[-self.max_posts_per_channel:]:
            opp = self._parse_message(wrap, channel_name)
            if opp:
                opportunities.append(opp)

        return opportunities

    def _parse_message(self, wrap, channel_name: str) -> Opportunity | None:
        text_elem = wrap.select_one(".tgme_widget_message_text")
        date_elem = wrap.select_one(".tgme_widget_message_date")
        if not text_elem or not date_elem:
            return None

        post_url = date_elem.get("href", "")
        if not post_url:
            return None

        # Clonar o limpiar elementos emoji para evitar textos duplicados
        soup_copy = BeautifulSoup(str(text_elem), "html.parser")
        for em in soup_copy.select("i.emoji"):
            em.decompose()

        raw_text = soup_copy.get_text("\n").strip()
        if not raw_text:
            return None

        # Filtrar si no es publicación de empleo (ej. mensajes de buenas noches o avisos)
        lower = raw_text.lower()
        job_keywords = [
            "vacante", "búsqueda", "busqueda", "buscamos", "requisitos",
            "remoto", "sueldo", "perfil", "hiring", "contratación",
            "contratacion", "postula", "salario"
        ]
        if not any(k in lower for k in job_keywords):
            return None

        skip_phrases = [
            "cerramos la jornada", "buen día y feliz inicio",
            "feliz inicio de semana", "feliz fin de semana"
        ]
        if any(sp in lower for sp in skip_phrases):
            return None

        # Extracción de título
        rol = self._extract_title(raw_text)

        # Extracción de empresa
        empresa = self._extract_company(raw_text, channel_name)

        # Modalidad y Ubicación
        modalidad = "remoto"
        if "híbrido" in lower or "hibrido" in lower:
            modalidad = "hibrido"
        elif "presencial" in lower:
            modalidad = "presencial"

        ubicacion = self._extract_location(raw_text)

        # Presupuesto
        presupuesto = self._extract_salary(raw_text)

        # Fecha
        time_tag = date_elem.select_one("time")
        fecha = time_tag.get("datetime", "") if time_tag else ""

        # Enlaces externos de postulación
        external_links = []
        for a in text_elem.select("a"):
            href = a.get("href", "")
            if href and not href.startswith("?") and "t.me" not in href:
                external_links.append(href)

        description = raw_text
        if external_links:
            unique_links = list(dict.fromkeys(external_links))
            links_str = "\n".join(f"- {link}" for link in unique_links)
            description = f"{description}\n\nEnlaces de postulación:\n{links_str}"

        return Opportunity(
            fuente=f"telegram:{channel_name}",
            empresa=empresa,
            rol=rol,
            url=post_url,
            tipo="empleo",
            modalidad=modalidad,
            ubicacion=ubicacion,
            presupuesto=presupuesto,
            fecha_publicacion=fecha,
            descripcion=description,
        )

    def _extract_title(self, text: str) -> str:
        lines = [self._clean_line(line) for line in text.split("\n") if self._clean_line(line)]
        if not lines:
            return "Oportunidad Remota"

        first = lines[0]
        # Si la primera línea es un saludo genérico, buscamos en el texto
        if re.match(r"^(?:¡?hola|buen(?:as?|os?)|saludos|comunidad|esta oferta)", first, re.IGNORECASE):
            m = re.search(
                r"(?:búsqueda|busqueda|buscamos)\s+(?:de\s+)?(?:un[a/]?\s+)?([A-ZÁÉÍÓÚ][\w\s/&.,+-]{3,45}?)(?:\s+con|\s+para|\s+remoto|[.,\n])",
                text,
                re.IGNORECASE,
            )
            if m:
                return self._clean_line(m.group(1))
            if len(lines) > 1 and len(lines[1]) > 5:
                first = lines[1]

        # Limpiar prefijos usuales
        first = re.sub(
            r"^(?:We[’\']re Hiring|Hiring|Buscamos|Nueva Oportunidad|Oportunidad Laboral|Busqueda Laboral en)[:\s]+",
            "",
            first,
            flags=re.IGNORECASE,
        ).strip()

        # Si viene dividido por pipes (ej. VACANTE | Rol | Empresa)
        if "|" in first:
            parts = [p.strip() for p in first.split("|")]
            for p in parts:
                clean_p = re.sub(
                    r"^(?:We[’\']re Hiring|Hiring|Buscamos|Nueva Oportunidad|Oportunidad Laboral)[:\s]+",
                    "",
                    p,
                    flags=re.IGNORECASE,
                ).strip()
                if not re.search(r"vacante|remot[ao]|oportunidad|hiring|latam|méxico|colombia|argentina", clean_p, re.IGNORECASE):
                    return clean_p[:80]
            return parts[0][:80]

        return first[:80]

    def _extract_company(self, text: str, fallback_channel: str) -> str:
        m = re.search(
            r"(?:en|para|desde)\s+([A-ZÁÉÍÓÚ][\w\s&.,-]{2,25}?)(?:\s+estamos|\s+nos encontramos|\s+buscamos|:|\n)",
            text,
        )
        if m:
            cand = m.group(1).strip().rstrip(".,:")
            if not re.search(r"equipo|empresa|industria|búsqueda|semana|este|esta", cand, re.IGNORECASE):
                return cand
        return "EmpleoVerse" if "empleoverse" in fallback_channel.lower() else f"Canal @{fallback_channel}"

    def _extract_location(self, text: str) -> str:
        m_loc = re.search(r"\((MÉXICO|MEXICO|COLOMBIA|ARGENTINA|CHILE|PERÚ|PERU|ESPAÑA|ESPANA|LATAM)\)", text, re.IGNORECASE)
        if m_loc:
            return f"Remoto ({m_loc.group(1).capitalize()})"

        m_tag = re.search(r"#(Mexico|México|Colombia|Argentina|Chile|Peru|Perú|Latam)", text, re.IGNORECASE)
        if m_tag:
            return f"Remoto ({m_tag.group(1).capitalize()})"

        return "Remoto"

    def _extract_salary(self, text: str) -> str:
        m_sal = re.search(r"(?:sueldo|salario|remuneración|remuneracion):\s*([^\n]+)", text, re.IGNORECASE)
        if m_sal:
            return m_sal.group(1).strip()
        m_usd = re.search(r"(\d+[\d.,]*\s*(?:USD|US\$|\$)\b[^\n]*)", text)
        if m_usd:
            return m_usd.group(1).strip()
        return ""

    def _clean_line(self, line: str) -> str:
        cleaned = html.unescape(line)
        cleaned = re.sub(r"\bamp;\b", "&", cleaned)
        cleaned = re.sub(r"^[🚨📢📌🌎💼🍁✨💻🚀👉\s\|!¡\.-]+", "", cleaned)
        cleaned = re.sub(r"[🚨📢📌🌎💼🍁✨💻🚀👉\s\|!¡\.-]+$", "", cleaned)
        return cleaned.strip()
