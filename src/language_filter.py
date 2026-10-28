from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0  # resultados deterministas entre corridas


def is_spanish(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    try:
        return detect(text) == "es"
    except LangDetectException:
        return False
