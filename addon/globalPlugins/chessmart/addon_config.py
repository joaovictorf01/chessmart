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
from typing import Any

import config

from .trainer import DEFAULT_CHALLENGE_ID, DEFAULT_TRAINER_PRESET_ID


CONFIG_SECTION = "chessmart"

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
	# The Lichess username last imported from, offered again in the import dialog.
	"lichessUser": 'string(default="")',
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
	"""The Chessmart folder in Documents: visible in the Explorer, unlike the add-on's own data folder."""
	return os.path.join(os.path.expanduser("~"), "Documents", "Chessmart")


def get_games_folder() -> str:
	"""The folder the analysis board saves to: the one chosen in the settings, or the default."""
	return str(_section()["gamesFolder"]).strip() or default_games_folder()


def save_games_folder(folder: str) -> None:
	_section()["gamesFolder"] = folder.strip()


def get_lichess_user() -> str:
	return str(_section()["lichessUser"]).strip()


def save_lichess_user(user: str) -> None:
	_section()["lichessUser"] = user.strip()
