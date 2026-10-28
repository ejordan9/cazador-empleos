import unicodedata
from src.models import Opportunity


def normalize_text(text: str) -> str:
    """Elimina tildes, pasa a minúsculas y limpia espacios."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ASCII", "ignore").decode("utf-8")
    return " ".join(ascii_text.lower().split())


def _matches_any_location(text: str, allowed_locations: list[str]) -> bool:
    norm_text = normalize_text(text)
    for loc in allowed_locations:
        norm_loc = normalize_text(loc)
        if norm_loc and norm_loc in norm_text:
            return True
    return False


def is_location_allowed(opp: Opportunity, allowed_locations: list[str] | None = None) -> bool:
    """Verifica si una oportunidad cumple con las restricciones de ubicación.
    
    Reglas:
    - Remoto: Permitido sin importar la ubicación física.
    - Presencial o Híbrido: Solo permitido si se ubica en las localidades autorizadas (por defecto Bogotá).
    - Modalidad no especificada: Si tiene ubicación física distinta a las permitidas, se descarta.
      Si es genérica o vacía, se verifica si en el texto del rol/descripción se especifica la localidad autorizada
      o se infiere que es remoto.
    """
    if allowed_locations is None:
        allowed_locations = ["bogota", "bogotá"]

    modalidad = (opp.modalidad or "").strip().lower()
    ubicacion = (opp.ubicacion or "").strip()

    # 1. Remoto: siempre permitido
    if modalidad == "remoto":
        return True

    # 2. Presencial o Híbrido: debe estar en una ubicación permitida
    if modalidad in ("presencial", "hibrido"):
        # Revisar en el campo de ubicación
        if _matches_any_location(ubicacion, allowed_locations):
            return True
        # Especial para LinkedIn: "capital district, colombia"
        norm_ubicacion = normalize_text(ubicacion)
        if "capital district" in norm_ubicacion and "colombia" in norm_ubicacion:
            return True

        # Si la ubicación está vacía o es solo país ("Colombia"), buscar mención explícita en rol o descripción
        if not ubicacion or norm_ubicacion == "colombia":
            if _matches_any_location(opp.rol, allowed_locations):
                return True
            if _matches_any_location(opp.descripcion, allowed_locations):
                return True

        return False

    # 3. Modalidad no identificada
    # Si la ubicación menciona una localidad autorizada: permitida
    if _matches_any_location(ubicacion, allowed_locations):
        return True
    norm_ubicacion = normalize_text(ubicacion)
    if "capital district" in norm_ubicacion and "colombia" in norm_ubicacion:
        return True

    # Si tiene una ubicación física explícita que no es la permitida (ej. Santiago, Lima, Medellín): descartada
    if ubicacion and norm_ubicacion not in ("colombia", "latin america", "latam"):
        return False

    # Si no tiene ubicación o es genérica ("Colombia"), revisar si el rol/descripción indica remoto o Bogotá
    haystack = f"{opp.rol} {opp.descripcion}".lower()
    if any(term in haystack for term in ("remoto", "remote", "teletrabajo", "home office", "wfh")):
        return True
    if _matches_any_location(haystack, allowed_locations):
        return True

    return False
