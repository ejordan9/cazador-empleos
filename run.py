from src.collectors.computrabajo import ComputrabajoCollector
from src.collectors.getonbrd import GetOnBrdCollector
from src.collectors.indeed import IndeedJobSpyCollector
from src.collectors.jobspy_source import LinkedInJobSpyCollector
from src.collectors.telegram_channel import TelegramChannelCollector
from src.collectors.torre import TorreCollector
from src.config import load_config
from src.contract_filter import is_freelance_or_part_time
from src.language_filter import is_spanish
from src.location_filter import is_location_allowed
from src.notifier import notify_new_opportunities
from src.scoring import score
from src.seen_store import SeenStore


def build_collectors(config: dict) -> list:
    collectors = []

    allowed_locations = config.get("filters", {}).get("allowed_locations_presencial_hibrido")
    gob_cfg = config.get("sources", {}).get("getonbrd", {})
    if gob_cfg.get("enabled"):
        collectors.append(GetOnBrdCollector(
            base_url=gob_cfg.get("base_url", "https://www.getonbrd.com"),
            categories=gob_cfg.get("categories", ["marketing-digital", "data-science-analytics"]),
            user_agent=config.get("http", {}).get("user_agent", "cazador-empleos-bot/1.0"),
            timeout=config.get("http", {}).get("timeout_seconds", 15),
            delay=config.get("http", {}).get("delay_between_requests_seconds", 2),
            allowed_locations=allowed_locations,
        ))

    li_cfg = config.get("sources", {}).get("linkedin", {})
    if li_cfg.get("enabled"):
        collectors.append(LinkedInJobSpyCollector(
            search_terms=config["profile"]["keywords"],
            location=li_cfg.get("location", "Latin America"),
            results_wanted=li_cfg.get("results_wanted_per_keyword", 15),
            delay_between_searches=li_cfg.get("delay_between_searches_seconds", 10),
            hours_old=li_cfg.get("hours_old"),
        ))

    indeed_cfg = config.get("sources", {}).get("indeed", {})
    if indeed_cfg.get("enabled"):
        collectors.append(IndeedJobSpyCollector(
            search_terms=config["profile"]["keywords"],
            location=indeed_cfg.get("location", "Colombia"),
            country=indeed_cfg.get("country", "colombia"),
            results_wanted=indeed_cfg.get("results_wanted_per_keyword", 10),
            delay_between_searches=indeed_cfg.get("delay_between_searches_seconds", 5),
            hours_old=indeed_cfg.get("hours_old"),
        ))

    ct_cfg = config.get("sources", {}).get("computrabajo", {})
    if ct_cfg.get("enabled"):
        collectors.append(ComputrabajoCollector(
            search_terms=config["profile"]["keywords"],
            base_url=ct_cfg.get("base_url", "https://co.computrabajo.com"),
            delay=ct_cfg.get("delay_between_requests_seconds", 2),
            max_results_per_keyword=ct_cfg.get("max_results_per_keyword", 10),
            allowed_locations=allowed_locations,
        ))

    torre_cfg = config.get("sources", {}).get("torre", {})
    if torre_cfg.get("enabled"):
        collectors.append(TorreCollector(
            search_terms=config["profile"]["keywords"],
            cookie_path=torre_cfg.get("cookie_path"),
            delay=torre_cfg.get("delay_between_requests_seconds", 2),
            max_results_per_keyword=torre_cfg.get("max_results_per_keyword", 10),
            allowed_locations=allowed_locations,
        ))

    tg_cfg = config.get("sources", {}).get("telegram_channels", {})
    if tg_cfg.get("enabled"):
        collectors.append(TelegramChannelCollector(
            channels=tg_cfg.get("channels", ["vacantesremotasempleoverse"]),
            max_posts_per_channel=tg_cfg.get("max_posts_per_channel", 25),
            delay=tg_cfg.get("delay_between_requests_seconds", 2),
        ))

    return collectors


def main():
    print("========================================")
    print(" 🎯 Cazador de Empleos Multiplataforma")
    print("========================================")

    config = load_config()
    collectors = build_collectors(config)

    profile = config["profile"]
    min_score = config.get("filters", {}).get("min_score", 2)
    prefer_remote = config.get("filters", {}).get("prefer_remote", True)
    only_freelance = config.get("filters", {}).get("only_freelance_or_part_time", False)
    allowed_locations = config.get("filters", {}).get("allowed_locations_presencial_hibrido")
    seen_path = config.get("output", {}).get("seen_path", "state/seen.json")
    seen_store = SeenStore(seen_path)

    matched = {}
    for collector in collectors:
        print(f"\n[{collector.name}] Recolectando ofertas...")
        try:
            opportunities = collector.collect()
        except Exception as e:
            print(f"  ⚠️ Error en colector {collector.name}: {e}")
            continue

        print(f"  {len(opportunities)} vacantes obtenidas de {collector.name}")

        for opp in opportunities:
            opp = score(opp, profile["keywords"], profile.get("exclude", []))
            if opp.score < min_score:
                continue
            if not is_spanish(f"{opp.rol}. {opp.descripcion}"):
                continue
            if not is_location_allowed(opp, allowed_locations):
                continue
            if only_freelance:
                allowed, category = is_freelance_or_part_time(opp)
                if not allowed:
                    continue
                opp.tipo = category
            else:
                is_fl, cat = is_freelance_or_part_time(opp)
                if is_fl:
                    opp.tipo = cat

            matched[opp.url] = opp
            loc_label = f" ({opp.ubicacion})" if opp.ubicacion else ""
            contract_label = f" [{opp.tipo}]" if opp.tipo and opp.tipo != "empleo" else ""
            print(f"    ⭐ Match ({opp.score} pts, {opp.modalidad or 'sin modalidad'}{loc_label}{contract_label}): {opp.rol} — {opp.empresa} [{opp.fuente}]")

    ranked = sorted(
        matched.values(),
        key=lambda o: (0 if prefer_remote and o.modalidad == "remoto" else 1, -o.score),
    )
    new_opportunities = seen_store.filter_new(ranked)

    print("\n----------------------------------------")
    print(f"Total coincidencias: {len(matched)}")
    print(f"Nuevas (a notificar): {len(new_opportunities)}")

    if new_opportunities:
        notify_new_opportunities(new_opportunities)
        seen_store.mark_seen(new_opportunities)
    else:
        print("No hay nuevas oportunidades en esta corrida.")


if __name__ == "__main__":
    main()
