import time
import pandas as pd
from jobspy import scrape_jobs

from src.collectors.base import Collector
from src.models import Opportunity


class IndeedJobSpyCollector(Collector):
    """Colector para Indeed Colombia vía JobSpy."""

    name = "indeed"

    def __init__(
        self,
        search_terms: list[str],
        location: str = "Colombia",
        country: str = "colombia",
        results_wanted: int = 15,
        delay_between_searches: int = 5,
        hours_old: int | None = None,
    ):
        self.search_terms = search_terms
        self.location = location
        self.country = country
        self.results_wanted = results_wanted
        self.delay = delay_between_searches
        self.hours_old = hours_old

    def collect(self) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        for i, term in enumerate(self.search_terms):
            if i > 0:
                time.sleep(self.delay)

            try:
                df = scrape_jobs(
                    site_name=["indeed"],
                    search_term=term,
                    location=self.location,
                    country_indeed=self.country,
                    results_wanted=self.results_wanted,
                    hours_old=self.hours_old,
                    verbose=0,
                )
            except Exception as e:
                print(f"    [indeed] keyword '{term}' falló ({e}), se salta")
                continue

            if df.empty:
                continue

            for record in df.to_dict("records"):
                url = _clean(record.get("job_url"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                opportunities.append(self._parse_record(record, url))

        return opportunities

    def _parse_record(self, record: dict, url: str) -> Opportunity:
        min_amount = _clean(record.get("min_amount"))
        max_amount = _clean(record.get("max_amount"))
        interval = _clean(record.get("interval")) or ""
        currency = _clean(record.get("currency")) or "COP"

        presupuesto = ""
        if min_amount and max_amount:
            presupuesto = f"{int(min_amount)} - {int(max_amount)} {currency}/{interval}"
        elif min_amount or max_amount:
            presupuesto = f"{int(min_amount or max_amount)} {currency}/{interval}"

        job_type = _clean(record.get("job_type")) or ""
        tags = [job_type] if job_type else []

        rol = _clean(record.get("title")) or ""
        raw_loc = _clean(record.get("location")) or ""
        descripcion = _clean(record.get("description")) or ""
        is_remote = _clean(record.get("is_remote"))

        low_rol = rol.lower()
        low_loc = raw_loc.lower()
        low_desc = descripcion.lower()

        # Inferencia de modalidad
        if is_remote or "desde casa" in low_loc or any(r in low_rol for r in ("remoto", "remote", "teletrabajo")):
            modalidad = "remoto"
        elif any(h in low_rol or h in low_loc for h in ("hybrid", "híbrido", "hibrido", "híbrida", "hibrida")):
            modalidad = "hibrido"
        elif any(f"modalidad {h}" in low_desc or f"esquema {h}" in low_desc for h in ("híbrida", "hibrida", "híbrido", "hibrido", "hybrid")):
            modalidad = "hibrido"
        elif is_remote is False or any(p in low_rol or p in low_loc for p in ("presencial", "on-site", "onsite")):
            modalidad = "presencial"
        elif raw_loc:
            modalidad = "presencial"
        else:
            modalidad = ""

        # Normalizar texto de ubicación si es "Desde casa"
        ubicacion = raw_loc
        if "desde casa" in low_loc and modalidad == "remoto":
            ubicacion = "Remoto (Colombia)"

        return Opportunity(
            fuente=self.name,
            empresa=_clean(record.get("company")) or "",
            rol=rol,
            url=url,
            tipo="empleo",
            modalidad=modalidad,
            ubicacion=ubicacion,
            presupuesto=presupuesto,
            fecha_publicacion=str(_clean(record.get("date_posted")) or ""),
            descripcion=descripcion,
            tags=tags,
        )


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return value
