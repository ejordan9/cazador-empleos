import re
import time

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector
from src.location_filter import is_location_allowed
from src.models import Opportunity

FREELANCE_HINTS = ("freelance", "por proyecto", "project-based")


class GetOnBrdCollector(Collector):
    name = "getonbrd"

    def __init__(self, base_url: str, categories: list[str], user_agent: str,
                 timeout: int, delay: int, allowed_locations: list[str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.categories = categories
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.delay = delay
        self.allowed_locations = allowed_locations

    def collect(self) -> list[Opportunity]:
        cards = []
        for i, category in enumerate(self.categories):
            if i > 0:
                time.sleep(self.delay)
            cards.extend(self._collect_category(category))

        valid_cards = []
        for opp in cards:
            if self.allowed_locations is not None and not is_location_allowed(opp, self.allowed_locations):
                # Descartada de antemano por ubicación (ej. presencial o híbrida fuera de Bogotá)
                continue
            valid_cards.append(opp)

        for i, opp in enumerate(valid_cards):
            if i > 0:
                time.sleep(self.delay)
            opp.descripcion = self.fetch_full_description(opp.url)
        return valid_cards

    def fetch_full_description(self, url: str) -> str:
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        body = soup.select_one("#job-body")
        return body.get_text(separator=" ", strip=True) if body else ""

    def _collect_category(self, category: str) -> list[Opportunity]:
        url = f"{self.base_url}/jobs/{category}"
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.select("ul.gb-results-list > a.results-item")
        return [self._parse_card(card) for card in cards]

    def _parse_card(self, card) -> Opportunity:
        job_url = card.get("href", "")
        teaser = card.get("title", "").strip()

        title_tag = card.select_one("h4.results-list-title strong")
        rol = title_tag.get_text(strip=True) if title_tag else ""

        jornada_tag = card.select_one("h4.results-list-title span.opacity-half")
        jornada = jornada_tag.get_text(strip=True) if jornada_tag else ""

        info_div = card.select_one(".results-list-info > div.size0")
        empresa = ""
        if info_div:
            company_tag = info_div.select_one("strong")
            empresa = company_tag.get_text(strip=True) if company_tag else ""

        location_tag = card.select_one(".location")
        ubicacion = ""
        modalidad = ""
        if location_tag:
            loc_copy = BeautifulSoup(str(location_tag), "html.parser")
            for hide in loc_copy.select(".hide, .location-tooltip-content"):
                hide.decompose()
            raw_loc = " ".join(loc_copy.get_text().split())
            modalidad = self._infer_modalidad(raw_loc)
            ubicacion = re.sub(r"\s*\((Hybrid|In-office|Remot[^\)]*)\)", "", raw_loc, flags=re.I).strip()
            if not ubicacion:
                ubicacion = "Remoto" if modalidad == "remoto" else raw_loc

        salary_tag = card.select_one(".gb-results-list__badges span")
        presupuesto = salary_tag.get_text(strip=True) if salary_tag else ""

        date_tag = card.select_one(".results-secondary .opacity-half.size0")
        fecha_publicacion = date_tag.get_text(strip=True) if date_tag else ""

        text_for_freelance_check = f"{rol} {teaser}".lower()
        tipo = "freelance" if any(h in text_for_freelance_check for h in FREELANCE_HINTS) else "empleo"

        tags = [jornada] if jornada else []

        return Opportunity(
            fuente=self.name,
            empresa=empresa,
            rol=rol,
            url=job_url,
            tipo=tipo,
            modalidad=modalidad,
            ubicacion=ubicacion,
            presupuesto=presupuesto,
            fecha_publicacion=fecha_publicacion,
            descripcion=teaser,
            tags=tags,
        )

    @staticmethod
    def _infer_modalidad(text: str) -> str:
        low = (text or "").lower()
        if any(h in low for h in ("hybrid", "híbrid", "hibrid")):
            return "hibrido"
        if any(r in low for r in ("remot", "remote")):
            return "remoto"
        if any(p in low for p in ("in-office", "presencial", "on-site", "onsite")):
            return "presencial"
        if low:
            return "presencial"
        return ""
