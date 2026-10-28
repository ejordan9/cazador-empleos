"""Módulo para clasificar y filtrar oportunidades freelance, por horas, part-time o por proyecto."""

import re
import unicodedata
from src.models import Opportunity


def normalize_text(text: str) -> str:
    """Elimina tildes, pasa a minúsculas y normaliza espacios."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ASCII", "ignore").decode("utf-8")
    return " ".join(ascii_text.lower().split())


CONTRACT_BADGES = {
    "freelance": "💼 Freelance",
    "part-time": "⏱️ Part-time",
    "part_time": "⏱️ Part-time",
    "por_horas": "⏳ Por horas",
    "por_proyecto": "📁 Por proyecto",
}


def get_contract_badge(category: str) -> str:
    return CONTRACT_BADGES.get(category, "")


# Patrones que indican que freelance/independiente fue negado explícitamente
_NEGATION_PATTERNS = [
    re.compile(r"\bno\s+(?:es\s+)?freelanc\w*", re.IGNORECASE),
    re.compile(r"\bno\s+aceptamos\s+freelanc\w*", re.IGNORECASE),
    re.compile(r"\bno\s+buscamos\s+freelanc\w*", re.IGNORECASE),
    re.compile(r"\babstenerse\s+(?:los\s+)?freelanc\w*", re.IGNORECASE),
    re.compile(r"\babstenerse\s+(?:los\s+)?independientes\b", re.IGNORECASE),
    re.compile(r"\bsin\s+freelanc\w*", re.IGNORECASE),
]

# Patrones donde 'freelance' sólo aparece como requisito de experiencia previa del candidato
_EXPERIENCE_ONLY_PATTERNS = [
    re.compile(r"\b(?:experiencia|experiencia\s+previa|haber\s+trabajado)\s+(?:de\s+\d+\s+a[nñ]os\s+)?(?:como|en|de)\s+freelanc\w*", re.IGNORECASE),
    re.compile(r"\b(?:experiencia|experiencia\s+previa)\s+freelanc\w*", re.IGNORECASE),
]

# Patrones de tiempo completo / exclusividad corporativa
_FULLTIME_PATTERNS = [
    re.compile(r"\btiempo\s+completo\b", re.IGNORECASE),
    re.compile(r"\bfull[-\s]?time\b", re.IGNORECASE),
    re.compile(r"\bjornada\s+completa\b", re.IGNORECASE),
    re.compile(r"\bdedicaci[oó]n\s+exclusiva\b", re.IGNORECASE),
    re.compile(r"\bexclusividad\b", re.IGNORECASE),
    re.compile(r"\b(?:directo\s+por\s+|contrato\s+por\s+)?n[oó]mina\b", re.IGNORECASE),
    re.compile(r"\bcontrato\s+(?:a\s+)?t[eé]rmino\s+indefinido\b", re.IGNORECASE),
    re.compile(r"\bcontrato\s+indefinido\b", re.IGNORECASE),
    re.compile(r"\bt[eé]rmino\s+indefinido\b", re.IGNORECASE),
    re.compile(r"\b(?:3[5-9]|[4-5][0-9])\s*horas?\s*(?:semanales|a\s+la\s+semana|por\s+semana)\b", re.IGNORECASE),
    re.compile(r"\b(?:3[5-9]|[4-5][0-9])\s*h(?:rs?)?\s*(?:semanales|a\s+la\s+semana|por\s+semana)\b", re.IGNORECASE),
]

# Alternativas donde la vacante explícitamente permite elegir freelance o part-time
_ALTERNATIVE_PATTERNS = [
    re.compile(r"(?:tiempo\s+completo|full[-\s]?time|jornada\s+completa)\s+(?:o|or|\/)\s+(?:freelance|part[-\s]?time|medio\s+tiempo|por\s+horas?|por\s+proyectos?|prestaci[oó]n\s+de\s+servicios)", re.IGNORECASE),
    re.compile(r"(?:freelance|part[-\s]?time|medio\s+tiempo|por\s+horas?|por\s+proyectos?|prestaci[oó]n\s+de\s+servicios)\s+(?:o|or|\/)\s+(?:tiempo\s+completo|full[-\s]?time|jornada\s+completa)", re.IGNORECASE),
]

# Patrones positivos por categoría
_POR_HORAS_PATTERNS = [
    re.compile(r"\bpago\s+por\s+horas?\b", re.IGNORECASE),
    re.compile(r"\btarifa\s+por\s+horas?\b", re.IGNORECASE),
    re.compile(r"\bvalor\s+(?:por\s+)?hora\b", re.IGNORECASE),
    re.compile(r"\bcobro\s+por\s+horas?\b", re.IGNORECASE),
    re.compile(r"\bpor\s+horas?\b", re.IGNORECASE),
    re.compile(r"\bhourly\b", re.IGNORECASE),
    re.compile(r"\b(?:banco|bolsa)\s+de\s+horas\b", re.IGNORECASE),
    re.compile(r"\b(?:[1-9]|[1-2][0-9]|3[0-2])\s*(?:a|-)?\s*(?:[1-2]?[0-9]|3[0-2])?\s*horas?\s*(?:semanales|a\s+la\s+semana|por\s+semana|al\s+mes)\b", re.IGNORECASE),
]

_POR_PROYECTO_PATTERNS = [
    re.compile(r"\bpor\s+proyectos?\b", re.IGNORECASE),
    re.compile(r"\bpor\s+entregables?\b", re.IGNORECASE),
    re.compile(r"\bproject[-\s]?based\b", re.IGNORECASE),
    re.compile(r"\bproyecto\s+(?:puntual|temporal)\b", re.IGNORECASE),
    re.compile(r"\bduraci[oó]n\s+del\s+proyecto\b", re.IGNORECASE),
    re.compile(r"\bcontrato\s+por\s+proyecto\b", re.IGNORECASE),
    re.compile(r"\bcontrato\s+por\s+obra\s+o\s+labor\s+por\s+proyecto\b", re.IGNORECASE),
]

_PART_TIME_PATTERNS = [
    re.compile(r"\bpart[-\s]?time\b", re.IGNORECASE),
    re.compile(r"\bmedio\s+tiempo\b", re.IGNORECASE),
    re.compile(r"\bmedia\s+jornada\b", re.IGNORECASE),
    re.compile(r"\bjornada\s+parcial\b", re.IGNORECASE),
    re.compile(r"\btiempo\s+parcial\b", re.IGNORECASE),
]

_FREELANCE_PATTERNS = [
    re.compile(r"\bfreelanc\w*\b", re.IGNORECASE),
    re.compile(r"\bcontractor\b", re.IGNORECASE),
    re.compile(r"\bcontratista(?:\s+independiente)?\b", re.IGNORECASE),
    re.compile(r"\bprofesional\s+independiente\b", re.IGNORECASE),
    re.compile(r"\b(?:como|modalidad)\s+independiente\b", re.IGNORECASE),
    re.compile(r"\bprestaci[oó]n\s+de\s+servicios?\b", re.IGNORECASE),
    re.compile(r"\bcontrato\s+(?:de\s+|por\s+)?servicios\b", re.IGNORECASE),
    re.compile(r"\bservicios\s+profesionales\b", re.IGNORECASE),
    re.compile(r"\bpor\s+honorarios\b", re.IGNORECASE),
    re.compile(r"\bhonorarios\s+profesionales\b", re.IGNORECASE),
    re.compile(r"\br[eé]gimen\s+de\s+honorarios\b", re.IGNORECASE),
    re.compile(r"\btrabajo\s+independiente\b", re.IGNORECASE),
    re.compile(r"\bconsultor(?:a)?\s+independiente\b", re.IGNORECASE),
    re.compile(r"\bcuenta\s+propia\b", re.IGNORECASE),
    re.compile(r"\b1099\b", re.IGNORECASE),
]


def _match_category(text: str, is_freelance_negated: bool = False) -> str | None:
    """Verifica qué categoría flexible o freelance coincide con el texto analizado."""
    for pat in _POR_HORAS_PATTERNS:
        if pat.search(text):
            return "por_horas"
    for pat in _POR_PROYECTO_PATTERNS:
        if pat.search(text):
            return "por_proyecto"
    for pat in _PART_TIME_PATTERNS:
        if pat.search(text):
            return "part-time"
    if not is_freelance_negated:
        for pat in _FREELANCE_PATTERNS:
            if pat.search(text):
                return "freelance"
    return None


def is_freelance_or_part_time(opp: Opportunity) -> tuple[bool, str]:
    """Evalúa si una oportunidad corresponde a trabajo freelance, por horas, part-time o por proyecto.
    
    Retorna:
        (True, categoria) donde categoria es 'freelance', 'part-time', 'por_horas' o 'por_proyecto'.
        (False, motivo) donde motivo es 'full-time', 'negated' o 'unspecified'.
    """
    norm_rol = normalize_text(opp.rol)
    norm_desc = normalize_text(opp.descripcion)
    norm_presupuesto = normalize_text(opp.presupuesto)
    norm_tags = [normalize_text(t) for t in opp.tags]
    tags_text = " ".join(norm_tags)
    tipo = normalize_text(opp.tipo)

    # 1. Presupuesto por hora (ej. "$25 USD/hora", "30 USD/h", "hourly")
    if norm_presupuesto and re.search(r"/(?:hora|hr|h|hour|hourly)\b|\bhourly\b|\bpor\s+hora\b", norm_presupuesto):
        return True, "por_horas"

    # 2. Señal explícita en tags
    for tag in norm_tags:
        if any(h in tag for h in ("por horas", "hourly")):
            return True, "por_horas"
        if any(h in tag for h in ("por proyecto", "project-based", "project based")):
            return True, "por_proyecto"
        if any(h in tag for h in ("parttime", "part-time", "medio tiempo", "tiempo parcial", "media jornada")):
            return True, "part-time"
        if any(h in tag for h in ("freelance", "freelancer", "contract", "contractor")):
            return True, "freelance"

    # 3. Señal explícita en el Título / Rol (alta prioridad)
    cat_in_rol = _match_category(norm_rol)
    if cat_in_rol:
        return True, cat_in_rol

    # 4. Verificar negaciones explícitas de freelance en todo el texto
    full_text = f"{norm_rol} {tags_text} {norm_desc}"
    is_negated = any(pat.search(full_text) for pat in _NEGATION_PATTERNS)

    # 5. Limpiar menciones de freelance que sean únicamente experiencia previa requerida
    cleaned_desc = norm_desc
    for pat in _EXPERIENCE_ONLY_PATTERNS:
        cleaned_desc = pat.sub("", cleaned_desc)

    text_to_analyze = f"{norm_rol} {tags_text} {cleaned_desc}"

    # 6. Revisar si hay una alternativa explícita (ej. "tiempo completo o freelance", "full-time o part-time")
    has_alternative = any(pat.search(text_to_analyze) for pat in _ALTERNATIVE_PATTERNS)

    # 7. Verificar indicadores de Tiempo Completo / Exclusividad
    has_fulltime_signal = any(pat.search(text_to_analyze) for pat in _FULLTIME_PATTERNS)
    has_fulltime_tag = any(t in ("fulltime", "full-time", "tiempo completo", "jornada completa") for t in norm_tags)

    if (has_fulltime_signal or has_fulltime_tag) and not has_alternative:
        # Puesto corporativo de tiempo completo
        return False, "full-time"

    # 8. Buscar coincidencia positiva en el texto depurado
    cat = _match_category(text_to_analyze, is_freelance_negated=is_negated)
    if cat:
        return True, cat

    # 9. Si el collector ya lo había marcado como freelance de origen (ej. GetOnBrd)
    if tipo == "freelance" and not is_negated:
        return True, "freelance"

    if is_negated:
        return False, "negated"

    # 10. Sin indicadores (vacante estándar de nómina/tiempo completo)
    return False, "unspecified"
