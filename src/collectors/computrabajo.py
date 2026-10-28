import re
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector
from src.location_filter import is_location_allowed
from src.models import Opportunity

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class ComputrabajoCollector(Collector):
    """Colector para Computrabajo Colombia."""

    name = "computrabajo"

    def __init__(
        self,
        search_terms: list[str],
        base_url: str = "https://co.computrabajo.com",
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 15,
        delay: int = 2,
        max_results_per_keyword: int = 15,
        allowed_locations: list[str] | None = None,
    ):
        self.search_terms = search_terms
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9",
        }
        self.timeout = timeout
        self.delay = delay
        self.max_results_per_keyword = max_results_per_keyword
        self.allowed_locations = allowed_locations

    def collect(self) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        for i, term in enumerate(self.search_terms):
            if i > 0:
                time.sleep(self.delay)

            try:
                cards = self._collect_term(term)
            except Exception as e:
                print(f"    [computrabajo] keyword '{term}' falló ({e}), se salta")
                continue

            for opp in cards:
                if opp.url in seen_urls:
                    continue
                seen_urls.add(opp.url)

                # Pre-filtro de ubicación antes de descargar descripción completa
                if self.allowed_locations is not None and not is_location_allowed(opp, self.allowed_locations):
                    continue

                time.sleep(self.delay)
                try:
                    opp.descripcion = self._fetch_full_description(opp.url)
                except Exception:
                    pass

                opportunities.append(opp)

        return opportunities

    def _collect_term(self, term: str) -> list[Opportunity]:
        url = f"{self.base_url}/empleos-en-colombia?q={quote_plus(term)}"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        boxes = soup.select("article.box_offer")
        cards = []

        for b in boxes[: self.max_results_per_keyword]:
            opp = self._parse_card(b)
            if opp:
                cards.append(opp)

        return cards

    def _parse_card(self, card) -> Opportunity | None:
        title_el = card.select_one("h2 a.js-o-link") or card.select_one("h2 a")
        if not title_el:
            return None

        rol = title_el.text.strip()
        href = title_el.get("href", "")
        clean_path = href.split("#")[0]
        job_url = f"{self.base_url}{clean_path}" if clean_path.startswith("/") else clean_path

        p_tags = card.find_all("p", recursive=False)
        raw_company = p_tags[0].get_text(strip=True) if len(p_tags) >= 1 else ""
        raw_loc = p_tags[1].get_text(strip=True) if len(p_tags) >= 2 else ""
        raw_date = p_tags[2].get_text(strip=True) if len(p_tags) >= 3 else ""

        if raw_company:
            empresa = re.sub(r"^\d+([.,]\d+)?\s*", "", raw_company).strip()
        else:
            company_el = card.select_one("p.fs16 a") or card.select_one("p.fs16")
            empresa = company_el.text.strip() if company_el else "Confidencial"
            empresa = re.sub(r"^\d+([.,]\d+)?\s*", "", empresa).strip()

        ubicacion = raw_loc
        fecha_publicacion = raw_date
        presupuesto = ""
        modalidad = ""

        lines = [line.strip() for line in card.stripped_strings]
        for line in lines:
            low = line.lower()
            if "$" in line or "a convenir" in low:
                presupuesto = line
            elif not fecha_publicacion and (line.startswith("Hace ") or line in ("Ayer", "Hoy")):
                fecha_publicacion = line
            elif any(r in low for r in ("remoto", "teletrabajo", "desde casa")):
                modalidad = "remoto"
            elif any(h in low for h in ("híbrido", "hibrido", "hybrid")):
                modalidad = "hibrido"
            elif "presencial" in low:
                modalidad = "presencial"
            elif not ubicacion and "," in line and line != raw_company and not any(
                skip in low
                for skip in (
                    "contrato",
                    "tiempo",
                    "postulado",
                    "vista",
                    "favorito",
                    "oculta",
                    "salario",
                    "mensual",
                )
            ):
                ubicacion = line

        # Limpiar repetición en ubicación (ej. "Bogotá, D.C., Bogotá, D.C." -> "Bogotá, D.C.")
        if ubicacion:
            parts = [p.strip() for p in ubicacion.split(",") if p.strip()]
            dedup = []
            for p in parts:
                if p not in dedup:
                    dedup.append(p)
            ubicacion = ", ".join(dedup)

        if not modalidad:
            modalidad = "presencial" if ubicacion else ""

        tags = []
        for line in lines:
            low = line.lower()
            if any(t in low for t in ("tiempo completo", "medio tiempo", "por horas", "obra o labor", "indefinido", "prestacion de servicios", "freelance")):
                tags.append(line)

        return Opportunity(
            fuente=self.name,
            empresa=empresa,
            rol=rol,
            url=job_url,
            tipo="empleo",
            modalidad=modalidad,
            ubicacion=ubicacion,
            presupuesto=presupuesto,
            fecha_publicacion=fecha_publicacion,
            descripcion="",
            tags=tags,
        )

    def _fetch_full_description(self, url: str) -> str:
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        box = soup.select_one(".box_detail.fl") or soup.select_one(".box_detail")
        if not box:
            return ""

        for el in box.select(".hide, script, style, form, button, .tag, .t_ellipsis"):
            el.decompose()

        return " ".join(box.get_text(separator=" ").split())
