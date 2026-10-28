import time
from pathlib import Path
import requests

from src.collectors.base import Collector
from src.location_filter import is_location_allowed
from src.models import Opportunity

DEFAULT_COOKIE_PATH = Path.home() / ".config" / "torre" / "cookie.txt"


class TorreCollector(Collector):
    """Colector para Torre AI utilizando la sesión web."""

    name = "torre"

    def __init__(
        self,
        search_terms: list[str],
        cookie_path: str | None = None,
        cookie: str | None = None,
        timeout: int = 15,
        delay: int = 2,
        max_results_per_keyword: int = 15,
        allowed_locations: list[str] | None = None,
    ):
        self.search_terms = search_terms
        self.timeout = timeout
        self.delay = delay
        self.max_results_per_keyword = max_results_per_keyword
        self.allowed_locations = allowed_locations

        resolved_cookie = (cookie or "").strip()
        if not resolved_cookie:
            cpath = Path(cookie_path).expanduser() if cookie_path else DEFAULT_COOKIE_PATH
            if cpath.exists():
                resolved_cookie = cpath.read_text(encoding="utf-8").strip()

        self.cookie = resolved_cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": self.cookie,
            "Content-Type": "application/json",
        }

    def collect(self) -> list[Opportunity]:
        if not self.cookie:
            print("    [torre] no se encontró cookie de sesión en ~/.config/torre/cookie.txt, se salta")
            return []

        opportunities = []
        seen_ids = set()

        for i, term in enumerate(self.search_terms):
            if i > 0:
                time.sleep(self.delay)

            try:
                cards = self._search_term(term)
            except Exception as e:
                print(f"    [torre] keyword '{term}' falló ({e}), se salta")
                continue

            for opp in cards:
                if opp.url in seen_ids:
                    continue
                seen_ids.add(opp.url)

                # Pre-filtro por ubicación si es presencial o híbrido
                if self.allowed_locations is not None and not is_location_allowed(opp, self.allowed_locations):
                    continue

                # Descargar detalle completo de la vacante para robustecer el scoring
                time.sleep(self.delay)
                opp_id = opp.url.rstrip("/").split("/")[-1]
                full_desc = self._fetch_full_description(opp_id)
                if full_desc:
                    opp.descripcion = f"{opp.descripcion}\n\n{full_desc}".strip()

                opportunities.append(opp)

        return opportunities

    def _search_term(self, term: str) -> list[Opportunity]:
        url = f"https://search.torre.co/opportunities/_search/?size={self.max_results_per_keyword}"
        payload = {
            "skill/role": {
                "text": term,
                "experience": "potential-to-develop",
            }
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            if resp.status_code == 401:
                print("    [torre] sesión expirada o no autorizada (401)")
            return []

        data = resp.json()
        results = data.get("results", [])
        return [self._parse_item(item) for item in results if item]

    def _parse_item(self, item: dict) -> Opportunity:
        opp_id = item.get("id", "")
        job_url = f"https://torre.ai/jobs/{opp_id}"

        rol = item.get("objective") or ""
        orgs = item.get("organizations", [])
        empresa = orgs[0].get("name", "") if orgs else "Confidencial"

        is_remote = bool(item.get("remote"))
        place = item.get("place") or {}
        loc_type = place.get("locationType", "").lower()

        if loc_type == "hybrid":
            modalidad = "hibrido"
        elif is_remote or loc_type == "remote":
            modalidad = "remoto"
        else:
            modalidad = "presencial"

        locs = item.get("locations", [])
        if locs:
            ubicacion = ", ".join(locs[:2])
        elif modalidad == "remoto":
            ubicacion = "Remoto"
        else:
            ubicacion = ""

        # Presupuesto
        presupuesto = ""
        comp = item.get("compensation") or {}
        comp_data = comp.get("data") or {}
        min_amount = comp_data.get("minAmount")
        max_amount = comp_data.get("maxAmount")
        currency = comp_data.get("currency") or "USD"
        period = comp_data.get("periodicity") or ""

        if min_amount and max_amount:
            presupuesto = f"{int(min_amount)} - {int(max_amount)} {currency}/{period}"
        elif min_amount or max_amount:
            presupuesto = f"{int(min_amount or max_amount)} {currency}/{period}"

        fecha = str(item.get("created") or "")

        # Resumen inicial con tagline y skills requeridas
        tagline = item.get("tagline") or ""
        skills = [s.get("name", "") for s in item.get("skills", []) if s.get("name")]
        skills_text = f"Habilidades: {', '.join(skills)}" if skills else ""
        initial_desc = f"{tagline}\n{skills_text}".strip()

        commitment = item.get("commitment") or {}
        commit_code = commitment.get("code") or ""
        tags = [commit_code] if commit_code else []
        tipo = "freelance" if commit_code in ("freelance", "contractor", "part-time") else "empleo"

        return Opportunity(
            fuente=self.name,
            empresa=empresa,
            rol=rol,
            url=job_url,
            tipo=tipo,
            modalidad=modalidad,
            ubicacion=ubicacion,
            presupuesto=presupuesto,
            fecha_publicacion=fecha,
            descripcion=initial_desc,
            tags=tags,
        )

    def _fetch_full_description(self, opp_id: str) -> str:
        url = f"https://torre.ai/api/suite/opportunities/{opp_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            details = data.get("details", [])
            parts = []
            for d in details:
                content = d.get("content")
                if content and isinstance(content, str):
                    parts.append(content.strip())
            return "\n\n".join(parts)
        except Exception:
            return ""
