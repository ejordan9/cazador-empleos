from src.models import Opportunity


def score(opp: Opportunity, keywords: list[str], exclude: list[str]) -> Opportunity:
    haystack = f"{opp.rol} {opp.descripcion}".lower()

    if any(term.lower() in haystack for term in exclude):
        opp.score = -1
        return opp

    matched = [term for term in keywords if term.lower() in haystack]
    opp.score = len(matched)
    opp.matched_keywords = matched
    return opp
