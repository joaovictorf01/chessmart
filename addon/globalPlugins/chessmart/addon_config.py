# coding: utf-8

"""O que o add-on guarda na configuração do NVDA.

Do treino de táticas ficam só as escolhas do usuário: banco, plano, nível e os
temas personalizados. A faixa de rating e a popularidade mínima são função do
nível (ver `trainer.py`) e se derivam na hora; guardá-las também era ter duas
fontes para o mesmo dado, e elas já divergiram uma vez.
"""

import dataclasses

import config

from .trainer import DEFAULT_CHALLENGE_ID, DEFAULT_TRAINER_PRESET_ID


CONFIG_SECTION = "chessmart"

CONFIG_SPEC = {
	"tacticsDbPath": 'string(default="")',
	"tacticsTheme": 'string(default="")',
	"tacticsTrainerPreset": f'string(default="{DEFAULT_TRAINER_PRESET_ID}")',
	"tacticsChallengeLevel": f'string(default="{DEFAULT_CHALLENGE_ID}")',
	# Como os lances são falados; ver notation.py. Texto livre validado por nós,
	# e não `option(...)`, para um valor de versão futura não estourar o config.
	"moveNotation": 'string(default="descriptive")',
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


def get_tactics_defaults() -> TacticsDefaults:
	ensure_config_spec()
	addon_conf = config.conf[CONFIG_SECTION]
	return TacticsDefaults(
		db_path=addon_conf["tacticsDbPath"].strip(),
		theme=addon_conf["tacticsTheme"].strip(),
		trainer_preset=addon_conf["tacticsTrainerPreset"].strip() or DEFAULT_TRAINER_PRESET_ID,
		challenge_level=addon_conf["tacticsChallengeLevel"].strip() or DEFAULT_CHALLENGE_ID,
	)


def save_tactics_defaults(defaults: TacticsDefaults) -> None:
	ensure_config_spec()
	addon_conf = config.conf[CONFIG_SECTION]
	addon_conf["tacticsDbPath"] = defaults.db_path.strip()
	addon_conf["tacticsTheme"] = defaults.theme.strip()
	addon_conf["tacticsTrainerPreset"] = defaults.trainer_preset.strip() or DEFAULT_TRAINER_PRESET_ID
	addon_conf["tacticsChallengeLevel"] = defaults.challenge_level.strip() or DEFAULT_CHALLENGE_ID


def get_move_notation() -> str:
	"""O estilo de fala dos lances; volta ao padrão se o valor guardado for desconhecido."""
	from .notation import DEFAULT_STYLE, STYLE_IDS

	ensure_config_spec()
	value = str(config.conf[CONFIG_SECTION]["moveNotation"]).strip()
	return value if value in STYLE_IDS else DEFAULT_STYLE


def save_move_notation(style: str) -> None:
	from .notation import DEFAULT_STYLE, STYLE_IDS

	ensure_config_spec()
	config.conf[CONFIG_SECTION]["moveNotation"] = style if style in STYLE_IDS else DEFAULT_STYLE
