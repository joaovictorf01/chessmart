import dataclasses

import config

from .trainer import DEFAULT_CHALLENGE_ID, DEFAULT_TRAINER_PRESET_ID, resolve_training_selection


CONFIG_SECTION = "chessmart"

CONFIG_SPEC = {
    "tacticsDbPath": 'string(default="")',
    "tacticsTheme": 'string(default="")',
    "tacticsTrainerPreset": f'string(default="{DEFAULT_TRAINER_PRESET_ID}")',
    "tacticsChallengeLevel": f'string(default="{DEFAULT_CHALLENGE_ID}")',
    "tacticsMinRating": "integer(default=800, min=0, max=4000)",
    "tacticsMaxRating": "integer(default=1600, min=0, max=4000)",
    "tacticsMinPopularity": "integer(default=50, min=0, max=1000000)",
}


@dataclasses.dataclass(frozen=True)
class TacticsDefaults:
    db_path: str = ""
    theme: str = ""
    trainer_preset: str = DEFAULT_TRAINER_PRESET_ID
    challenge_level: str = DEFAULT_CHALLENGE_ID
    min_rating: int = 800
    max_rating: int = 1600
    min_popularity: int = 50


def ensure_config_spec():
    if CONFIG_SECTION not in config.conf.spec:
        config.conf.spec[CONFIG_SECTION] = {}
    for key, value in CONFIG_SPEC.items():
        config.conf.spec[CONFIG_SECTION][key] = value


def normalize_rating_range(min_rating: int, max_rating: int):
    return tuple(sorted((min_rating, max_rating)))


def get_tactics_defaults() -> TacticsDefaults:
    ensure_config_spec()
    addon_conf = config.conf[CONFIG_SECTION]
    min_rating, max_rating = normalize_rating_range(
        addon_conf["tacticsMinRating"],
        addon_conf["tacticsMaxRating"],
    )
    return TacticsDefaults(
        db_path=addon_conf["tacticsDbPath"].strip(),
        theme=addon_conf["tacticsTheme"].strip(),
        trainer_preset=addon_conf["tacticsTrainerPreset"].strip() or DEFAULT_TRAINER_PRESET_ID,
        challenge_level=addon_conf["tacticsChallengeLevel"].strip() or DEFAULT_CHALLENGE_ID,
        min_rating=min_rating,
        max_rating=max_rating,
        min_popularity=addon_conf["tacticsMinPopularity"],
    )


def save_tactics_defaults(
    db_path: str,
    theme: str,
    trainer_preset: str = DEFAULT_TRAINER_PRESET_ID,
    challenge_level: str = DEFAULT_CHALLENGE_ID,
    min_rating: int | None = None,
    max_rating: int | None = None,
    min_popularity: int | None = None,
):
    ensure_config_spec()
    if min_rating is None or max_rating is None or min_popularity is None:
        resolved = resolve_training_selection(
            trainer_preset,
            challenge_level,
            custom_theme_text=theme,
        )
        min_rating = resolved.min_rating
        max_rating = resolved.max_rating
        min_popularity = resolved.min_popularity
    min_rating, max_rating = normalize_rating_range(min_rating, max_rating)
    addon_conf = config.conf[CONFIG_SECTION]
    addon_conf["tacticsDbPath"] = (db_path or "").strip()
    addon_conf["tacticsTheme"] = (theme or "").strip()
    addon_conf["tacticsTrainerPreset"] = (trainer_preset or DEFAULT_TRAINER_PRESET_ID).strip()
    addon_conf["tacticsChallengeLevel"] = (challenge_level or DEFAULT_CHALLENGE_ID).strip()
    addon_conf["tacticsMinRating"] = min_rating
    addon_conf["tacticsMaxRating"] = max_rating
    addon_conf["tacticsMinPopularity"] = min_popularity
