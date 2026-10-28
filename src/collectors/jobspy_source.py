import time

import pandas as pd
from jobspy import scrape_jobs
from jobspy.exception import LinkedInException
from jobspy.linkedin import LinkedIn
from jobspy.model import Country, Location

from src.collectors.base import Collector
from src.models import Opportunity

# JobSpy's Country enum no incluye varios países (Bolivia, Paraguay, Guyana,
# El Salvador, Nicaragua...); Country.from_string revienta con ValueError y
# tumba la búsqueda completa por un solo listing en un país no soportado.
# Parcheamos para que caiga a WORLDWIDE en vez de abortar.
_original_from_string = Country.from_string.__func__


def _lenient_from_string(cls, country_str):
    try:
        return _original_from_string(cls, country_str)
    except ValueError:
        return cls.WORLDWIDE


Country.from_string = classmethod(_lenient_from_string)


# JobSpy descarta ciudades si la ubicación no tiene exactamente 2 o 3 partes.
# En Colombia LinkedIn suele devolver 4 partes ("Bogota, D.C., Capital District, Colombia").
# Parcheamos _get_location para soportar cualquier número de partes y no perder la ubicación.
def _robust_linkedin_get_location(self, metadata_card):
    if metadata_card is None:
        return Location(country=Country.from_string(self.country))
    location_tag = metadata_card.find("span", class_="job-search-card__location")
    if not location_tag or not location_tag.text.strip():
        return Location(country=Country.from_string(self.country))
    location_string = location_tag.text.strip()
    parts = [p.strip() for p in location_string.split(", ") if p.strip()]
    if len(parts) == 1:
        return Location(city=parts[0], country=Country.WORLDWIDE)
    elif len(parts) == 2:
        return Location(city=parts[0], state=parts[1], country=Country.WORLDWIDE)
    elif len(parts) == 3:
        try:
            country = Country.from_string(parts[2])
        except Exception:
            country = parts[2]
        return Location(city=parts[0], state=parts[1], country=country)
    else:
        try:
            country = Country.from_string(parts[-1])
        except Exception:
            country = parts[-1]
        return Location(city=parts[0], state=", ".join(parts[1:-1]), country=country)


LinkedIn._get_location = _robust_linkedin_get_location


class LinkedInJobSpyCollector(Collector):
    """Usa JobSpy (github.com/speedyapply/JobSpy), que lee el buscador público
    de empleos de LinkedIn (endpoint 'jobs-guest', sin login ni cookies de
    sesión) — no usa tu cuenta, así que el riesgo no es baneo sino
    rate-limit/bloqueo de IP si se abusa. Por eso: una búsqueda por keyword,
    con pausa entre cada una, y resultados acotados."""

    name = "linkedin"

    def __init__(self, search_terms: list[str], location: str, results_wanted: int,
                 delay_between_searches: int, hours_old: int | None = None):
        self.search_terms = search_terms
        self.location = location
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
                    site_name=["linkedin"],
                    search_term=term,
                    location=self.location,
                    results_wanted=self.results_wanted,
                    linkedin_fetch_description=True,
                    hours_old=self.hours_old,
                    verbose=0,
                )
            except LinkedInException as e:
                print(f"    [linkedin] keyword '{term}' falló ({e}), se salta")
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
        currency = _clean(record.get("currency")) or "USD"

        presupuesto = ""
        if min_amount and max_amount:
            presupuesto = f"{int(min_amount)} - {int(max_amount)} {currency}/{interval}"
        elif min_amount or max_amount:
            presupuesto = f"{int(min_amount or max_amount)} {currency}/{interval}"

        job_type = _clean(record.get("job_type")) or ""
        tags = [job_type] if job_type else []

        rol = _clean(record.get("title")) or ""
        ubicacion = _clean(record.get("location")) or ""
        descripcion = _clean(record.get("description")) or ""
        is_remote = _clean(record.get("is_remote"))
        wfh = _clean(record.get("work_from_home_type")) or ""

        # Inferencia inteligente de modalidad (hibrido, remoto, presencial)
        low_title = rol.lower()
        low_loc = ubicacion.lower()
        low_wfh = wfh.lower()
        low_desc = descripcion.lower()

        hybrid_terms = ("hybrid", "híbrido", "hibrido", "híbrida", "hibrida")
        if any(h in low_title or h in low_loc or h in low_wfh for h in hybrid_terms):
            modalidad = "hibrido"
        elif any(f"modalidad {h}" in low_desc or f"esquema {h}" in low_desc or f"trabajo {h}" in low_desc or f"formato {h}" in low_desc for h in hybrid_terms):
            modalidad = "hibrido"
        elif is_remote or any(r in low_title or r in low_wfh for r in ("remoto", "remote", "teletrabajo")):
            modalidad = "remoto"
        elif is_remote is False or any(p in low_title or p in low_loc for p in ("presencial", "on-site", "onsite")):
            modalidad = "presencial"
        elif ubicacion:
            modalidad = "presencial"
        else:
            modalidad = ""

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
