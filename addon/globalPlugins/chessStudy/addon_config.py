# coding: utf-8
# pyright: basic

"""What the add-on stores in NVDA's configuration.

For the tactics trainer, only the user's choices are kept: database, plan, level
and custom themes. The rating range and minimum popularity are a function of the
level (see `trainer.py`) and are derived on the fly; storing them too would mean
two sources for the same data, and they have already diverged once.
"""

import dataclasses
import os
from pathlib import Path
from typing import Any

import config

from . import former_name
from .trainer import DEFAULT_CHALLENGE_ID, DEFAULT_TRAINER_PRESET_ID


CONFIG_SECTION = "chessStudy"

CONFIG_SPEC = {
	"tacticsDbPath": 'string(default="")',
	"tacticsTheme": 'string(default="")',
	"tacticsTrainerPreset": f'string(default="{DEFAULT_TRAINER_PRESET_ID}")',
	"tacticsChallengeLevel": f'string(default="{DEFAULT_CHALLENGE_ID}")',
	# How moves are spoken; see notation.py. Free text validated by us, not
	# `option(...)`, so a value from a future version doesn't blow up the config.
	"moveNotation": 'string(default="descriptive")',
	# Where the analysis board saves games; empty means the default below.
	"gamesFolder": 'string(default="")',
	# The analysis board writes every change to the game's file, once it has one.
	"autosaveAnalysis": "boolean(default=True)",
	# The Lichess username last imported from, offered again in the import dialog.
	"lichessUser": 'string(default="")',
	# Game review: whose moves, from which verdict, how many, what the engine
	# reveals, seconds per position, whether opening theory is skipped.
	"reviewSide": 'string(default="mine")',
	"reviewThreshold": 'string(default="mistake")',
	"reviewMaxMoments": "integer(default=5)",
	"reviewReveal": 'string(default="nothing")',
	"reviewSeconds": "float(default=1.0)",
	"reviewSkipTheory": "boolean(default=True)",
}


@dataclasses.dataclass(frozen=True)
class TacticsDefaults:
	db_path: str = ""
	theme: str = ""
	trainer_preset: str = DEFAULT_TRAINER_PRESET_ID
	challenge_level: str = DEFAULT_CHALLENGE_ID


def ensure_config_spec():
	if CONFIG_SECTION not in config.conf.spec:
		config.conf.spec[CONFIG_SECTION] = {}
	for key, value in CONFIG_SPEC.items():
		config.conf.spec[CONFIG_SECTION][key] = value
	_carry_over_former_settings()


_former_settings_checked = False


def _carry_over_former_settings() -> None:
	"""Copy the settings saved under the former name, once: only while the new section is absent."""
	global _former_settings_checked
	if _former_settings_checked:
		return
	_former_settings_checked = True
	base_profile = config.conf.profiles[0]
	former = base_profile.get(former_name.FORMER_NAME)
	if CONFIG_SECTION in base_profile or not former:
		return
	from .tactic.db import ADDON_DATA_DIRECTORY

	former_data_folder = ADDON_DATA_DIRECTORY.parent / former_name.FORMER_NAME
	settings = former_name.carried_over_settings(
		former, CONFIG_SPEC, former_data_folder, ADDON_DATA_DIRECTORY
	)
	if settings:
		config.conf[CONFIG_SECTION] = settings


def _section() -> Any:
	"""The add-on's section in NVDA's config. `Any` because ConfigObj has no useful per-key type."""
	ensure_config_spec()
	return config.conf[CONFIG_SECTION]


def get_tactics_defaults() -> TacticsDefaults:
	addon_conf = _section()
	return TacticsDefaults(
		db_path=str(addon_conf["tacticsDbPath"]).strip(),
		theme=str(addon_conf["tacticsTheme"]).strip(),
		trainer_preset=str(addon_conf["tacticsTrainerPreset"]).strip() or DEFAULT_TRAINER_PRESET_ID,
		challenge_level=str(addon_conf["tacticsChallengeLevel"]).strip() or DEFAULT_CHALLENGE_ID,
	)


def save_tactics_defaults(defaults: TacticsDefaults) -> None:
	addon_conf = _section()
	addon_conf["tacticsDbPath"] = defaults.db_path.strip()
	addon_conf["tacticsTheme"] = defaults.theme.strip()
	addon_conf["tacticsTrainerPreset"] = defaults.trainer_preset.strip() or DEFAULT_TRAINER_PRESET_ID
	addon_conf["tacticsChallengeLevel"] = defaults.challenge_level.strip() or DEFAULT_CHALLENGE_ID


def get_move_notation() -> str:
	"""The move-speaking style; falls back to the default if the stored value is unknown."""
	from .notation import DEFAULT_STYLE, STYLE_IDS

	value = str(_section()["moveNotation"]).strip()
	return value if value in STYLE_IDS else DEFAULT_STYLE


def save_move_notation(style: str) -> None:
	from .notation import DEFAULT_STYLE, STYLE_IDS

	_section()["moveNotation"] = style if style in STYLE_IDS else DEFAULT_STYLE


def default_games_folder() -> str:
	"""The Chess Study folder in Documents: visible in the Explorer, unlike the add-on's own data folder.

	Until the user has games under the new name, the former Chessmart folder is kept.
	"""
	return str(former_name.games_folder(Path(os.path.expanduser("~")) / "Documents"))


def get_games_folder() -> str:
	"""The folder the analysis board saves to: the one chosen in the settings, or the default."""
	return str(_section()["gamesFolder"]).strip() or default_games_folder()


def save_games_folder(folder: str) -> None:
	_section()["gamesFolder"] = folder.strip()


def get_autosave_analysis() -> bool:
	return bool(_section()["autosaveAnalysis"])


def save_autosave_analysis(enabled: bool) -> None:
	_section()["autosaveAnalysis"] = bool(enabled)


def get_lichess_user() -> str:
	return str(_section()["lichessUser"]).strip()


def save_lichess_user(user: str) -> None:
	_section()["lichessUser"] = user.strip()


def get_review_options():
	"""The saved review options; an unknown stored value falls back to the default."""
	from .engine_eval import MoveVerdict
	from .game_review import Reveal, ReviewOptions, Side

	section = _section()
	defaults = ReviewOptions()

	def choose(enum_class, value, fallback):
		try:
			return enum_class(str(value))
		except ValueError:
			return fallback

	max_moments = int(section["reviewMaxMoments"])
	return ReviewOptions(
		side=choose(Side, section["reviewSide"], defaults.side),
		threshold=choose(MoveVerdict, section["reviewThreshold"], defaults.threshold),
		# 0 in the configuration means every critical moment.
		max_moments=max_moments if max_moments > 0 else None,
		reveal=choose(Reveal, section["reviewReveal"], defaults.reveal),
		seconds=float(section["reviewSeconds"]) or defaults.seconds,
		skip_theory=bool(section["reviewSkipTheory"]),
	)


def save_review_options(options) -> None:
	section = _section()
	section["reviewSide"] = options.side.value
	section["reviewThreshold"] = options.threshold.value
	section["reviewMaxMoments"] = options.max_moments or 0
	section["reviewReveal"] = options.reveal.value
	section["reviewSeconds"] = options.seconds
	section["reviewSkipTheory"] = options.skip_theory


def nvda_progress_bar_output() -> tuple[str, float, int]:
	"""NVDA's own "Progress bar output": the mode (beep, speak, both, off), the beep interval in percent, the lowest beep in Hz."""
	conf: Any = config.conf
	progress = conf["presentation"]["progressBarUpdates"]
	return (
		str(progress["progressBarOutputMode"]),
		float(progress["beepPercentageInterval"]),
		int(progress["beepMinHZ"]),
	)
