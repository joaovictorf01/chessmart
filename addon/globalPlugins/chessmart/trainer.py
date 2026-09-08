# coding: utf-8

from __future__ import annotations

import dataclasses

from .theme_catalog import format_theme_filter, parse_theme_filter


@dataclasses.dataclass(frozen=True)
class TrainerPreset:
    preset_id: str
    label: str
    description: str
    theme_slugs: tuple[str, ...] = ()
    uses_custom_themes: bool = False


@dataclasses.dataclass(frozen=True)
class ChallengeLevel:
    challenge_id: str
    label: str
    description: str
    # None em qualquer das pontas significa "sem limite": o filtro SQL
    # simplesmente não acrescenta a cláusula, então o treino alcança o banco
    # inteiro em vez de uma faixa arbitrária.
    min_rating: int | None
    max_rating: int | None
    min_popularity: int
    # No modo adaptativo as faixas acima são ignoradas: a dificuldade passa a
    # seguir o rating do jogador, sorteio a sorteio.
    adaptive: bool = False


@dataclasses.dataclass(frozen=True)
class ResolvedTrainingSelection:
    preset: TrainerPreset
    challenge: ChallengeLevel
    theme_text: str
    min_rating: int | None
    max_rating: int | None
    min_popularity: int
    adaptive: bool = False


TRAINER_PRESETS = (
    TrainerPreset(
        preset_id="guidedBasics",
        label="Guided basics",
        description="Start with the most common tactical patterns and short positions.",
        theme_slugs=(
            "mateIn1",
            "mateIn2",
            "oneMove",
            "short",
            "hangingPiece",
            "fork",
            "pin",
            "skewer",
        ),
    ),
    TrainerPreset(
        preset_id="materialWins",
        label="Win material",
        description="Train forks, pins, skewers and defenders so you spot clean material gains.",
        theme_slugs=(
            "fork",
            "pin",
            "skewer",
            "hangingPiece",
            "capturingDefender",
            "deflection",
            "discoveredAttack",
        ),
    ),
    TrainerPreset(
        preset_id="kingAttack",
        label="Attack the king",
        description="Focus on mating nets and direct attacking play.",
        theme_slugs=(
            "mate",
            "mateIn1",
            "mateIn2",
            "backRankMate",
            "exposedKing",
            "kingsideAttack",
            "doubleCheck",
        ),
    ),
    TrainerPreset(
        preset_id="mixedPractice",
        label="Mixed practice",
        description="Use a broad mix of popular tactical positions without forcing a single theme family.",
        theme_slugs=(
            "short",
            "middlegame",
            "advantage",
            "mate",
            "fork",
            "pin",
            "skewer",
            "hangingPiece",
        ),
    ),
    TrainerPreset(
        preset_id="customThemes",
        label="Custom themes",
        description="Choose the exact Lichess themes you want to include in the session.",
        uses_custom_themes=True,
    ),
)


CHALLENGE_LEVELS = (
    ChallengeLevel(
        challenge_id="veryAccessible",
        label="Very accessible",
        description="Favor shorter, cleaner and more popular examples.",
        # Sem piso: o banco desce até rating 399 hoje, e um número fixo aqui
        # esconderia os puzzles mais fáceis de quem mais precisa deles.
        min_rating=None,
        max_rating=1100,
        min_popularity=70,
    ),
    ChallengeLevel(
        challenge_id="balanced",
        label="Balanced",
        description="A comfortable middle ground for daily training.",
        min_rating=900,
        max_rating=1500,
        min_popularity=50,
    ),
    ChallengeLevel(
        challenge_id="stretch",
        label="Stretch",
        description="Push a bit higher and allow trickier positions.",
        min_rating=1200,
        max_rating=1900,
        min_popularity=25,
    ),
    ChallengeLevel(
        challenge_id="challenge",
        label="Challenge",
        description="Use a harder range with fewer popularity restrictions.",
        # Sem teto: o banco sobe até 3329, e travar em 2400 tiraria do treino
        # justamente os puzzles que ainda teriam algo a ensinar.
        min_rating=1600,
        max_rating=None,
        min_popularity=0,
    ),
    ChallengeLevel(
        challenge_id="adaptive",
        label="Adaptive",
        description="Follows your tactics rating: the difficulty tracks you as you improve.",
        min_rating=None,
        max_rating=None,
        min_popularity=25,
        adaptive=True,
    ),
)

DEFAULT_TRAINER_PRESET_ID = TRAINER_PRESETS[0].preset_id
DEFAULT_CHALLENGE_ID = CHALLENGE_LEVELS[1].challenge_id


def iter_trainer_presets() -> tuple[TrainerPreset, ...]:
    return TRAINER_PRESETS


def iter_challenge_levels() -> tuple[ChallengeLevel, ...]:
    return CHALLENGE_LEVELS


def get_trainer_preset(preset_id: str | None) -> TrainerPreset:
    for preset in TRAINER_PRESETS:
        if preset.preset_id == preset_id:
            return preset
    return TRAINER_PRESETS[0]


def get_challenge_level(challenge_id: str | None) -> ChallengeLevel:
    for level in CHALLENGE_LEVELS:
        if level.challenge_id == challenge_id:
            return level
    return CHALLENGE_LEVELS[1]


def uses_custom_themes(preset_id: str | None) -> bool:
    return get_trainer_preset(preset_id).uses_custom_themes


def resolve_training_selection(
    preset_id: str | None,
    challenge_id: str | None,
    custom_theme_text: str = "",
) -> ResolvedTrainingSelection:
    preset = get_trainer_preset(preset_id)
    challenge = get_challenge_level(challenge_id)
    if preset.uses_custom_themes:
        theme_text = format_theme_filter(parse_theme_filter(custom_theme_text))
    else:
        theme_text = format_theme_filter(preset.theme_slugs)
    return ResolvedTrainingSelection(
        preset=preset,
        challenge=challenge,
        theme_text=theme_text,
        min_rating=challenge.min_rating,
        max_rating=challenge.max_rating,
        min_popularity=challenge.min_popularity,
        adaptive=challenge.adaptive,
    )
