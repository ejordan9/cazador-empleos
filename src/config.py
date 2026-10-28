from pathlib import Path
import yaml


def load_config(path: str = "config.yaml") -> dict:
    raw_path = Path(path)
    if not raw_path.is_absolute():
        config_file = Path(__file__).resolve().parent.parent / raw_path
    else:
        config_file = raw_path

    if not config_file.exists():
        example_file = config_file.parent / "config.example.yaml"
        hint = f" (puedes copiar '{example_file.name}' a '{config_file.name}')" if example_file.exists() else ""
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración en '{config_file}'{hint}. "
            "Por favor crea tu 'config.yaml' antes de ejecutar el scraper."
        )

    with open(config_file, encoding="utf-8") as f:
        return yaml.safe_load(f)
