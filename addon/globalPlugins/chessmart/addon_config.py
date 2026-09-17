import dataclasses

import config

from .trainer import DEFAULT_CHALLENGE_ID, DEFAULT_TRAINER_PRESET_ID, resolve_training_selection


CONFIG_SECTION = "chessmart"

CONFIG_SPEC = {
	"tacticsDbPath": 'string(default="")',
	"tacticsTheme": 'string(default="")',
	"tacticsTrainerPreset": f'string(default="{DEFAULT_TRAINER_PRESET_ID}")',
	"tacticsChallengeLevel": f'string(default="{DEFAULT_CHALLENGE_ID}")',
	# Texto, e não inteiro, porque None ("sem limite") é um valor legítimo destas
	# pontas e o config do NVDA é validado por tipo: gravar None num campo
	# `integer` escreve a palavra None no ini e faz a validação estourar depois,
	# a cada troca de perfil de configuração. A string vazia diz "sem limite"
	# sem mentir sobre o tipo, e é a mesma codificação que tactic/repository.py
	# já usa para estes dois campos.
	"tacticsMinRating": 'string(default="800")',
	"tacticsMaxRating": 'string(default="1600")',
	"tacticsMinPopularity": "integer(default=50, min=0, max=1000000)",
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
	min_rating: int | None = 800
	max_rating: int | None = 1600
	min_popularity: int = 50


def ensure_config_spec():
	if CONFIG_SECTION not in config.conf.spec:
		config.conf.spec[CONFIG_SECTION] = {}
	for key, value in CONFIG_SPEC.items():
		config.conf.spec[CONFIG_SECTION][key] = value


def encode_rating(rating: int | None) -> str:
	"""Converte uma ponta da faixa para o texto que vai ao config do NVDA."""
	return "" if rating is None else str(rating)


def decode_rating(raw) -> int | None:
	"""Devolve uma ponta da faixa ao domínio, onde None é "sem limite".

	Aceita também a palavra None: é o resto de quando estes campos eram
	`integer` e o None do Python era gravado cru no ini. Tratá-la aqui faz um
	config já escrito daquele jeito se consertar sozinho na primeira gravação.
	"""
	text = str(raw).strip()
	if not text or text == "None":
		return None
	try:
		return int(text)
	except ValueError:
		return None


def normalize_rating_range(min_rating: int | None, max_rating: int | None):
	"""Põe a faixa em ordem, aceitando pontas abertas.

	`sorted` compara os dois valores, e comparar None com um número levanta
	TypeError em Python. Como None aqui significa "sem limite", não há o que
	ordenar quando ele aparece: a faixa já está na ordem certa.
	"""
	if min_rating is None or max_rating is None:
		return (min_rating, max_rating)
	return tuple(sorted((min_rating, max_rating)))


def get_tactics_defaults() -> TacticsDefaults:
	ensure_config_spec()
	addon_conf = config.conf[CONFIG_SECTION]
	min_rating, max_rating = normalize_rating_range(
		decode_rating(addon_conf["tacticsMinRating"]),
		decode_rating(addon_conf["tacticsMaxRating"]),
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
	addon_conf["tacticsMinRating"] = encode_rating(min_rating)
	addon_conf["tacticsMaxRating"] = encode_rating(max_rating)
	addon_conf["tacticsMinPopularity"] = min_popularity


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
