from dataclasses import dataclass, field


@dataclass
class Opportunity:
    fuente: str
    empresa: str
    rol: str
    url: str
    tipo: str = "empleo"  # "empleo" | "freelance"
    modalidad: str = ""  # remoto | hibrido | presencial
    ubicacion: str = ""
    presupuesto: str = ""
    fecha_publicacion: str = ""
    descripcion: str = ""
    score: int = 0
    tags: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
