# coding: utf-8

"""Planos de treino e níveis de desafio do treinador de táticas.

Os textos que o usuário vê ficam nas constantes, marcados com `N_()`: isso os
entrega ao extrator de traduções sem traduzir no momento da importação. A
tradução acontece em `preset_label`, `challenge_label` e companhia, a cada
chamada, para que trocar o idioma do NVDA não exija reiniciar o add-on.
"""

from __future__ import annotations

import dataclasses

from .i18n import N_, _
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
		# Translators: Name of the beginner training plan, shown in a combo box.
		label=N_("Fundamentals: mate, fork, pin and skewer"),
		# Translators: Description of the beginner training plan.
		description=N_(
			"The most common tactical patterns: short mates, hanging pieces, forks, pins and skewers. Pick an easier challenge level to keep the positions short.",
		),
		# `short` e `oneMove` saíram. O filtro de temas é um OU, então incluir
		# "posição curta" numa lista de motivos não restringia nada: liberava
		# QUALQUER puzzle curto, sem motivo algum. Como `short` sozinho cobre
		# metade do banco, o plano alcançava 75% dele e os motivos viravam
		# enfeite. Sem os dois, cai para 49,6% e volta a significar o que diz.
		# A intenção de "manter curto" pertence ao nível de dificuldade.
		theme_slugs=(
			"mateIn1",
			"mateIn2",
			"backRankMate",
			"hangingPiece",
			"fork",
			"pin",
			"skewer",
		),
	),
	TrainerPreset(
		preset_id="materialWins",
		# Translators: Name of the training plan about winning material, shown in a combo box.
		label=N_("Win material: forks, pins, skewers and defenders"),
		# Translators: Description of the training plan about winning material.
		description=N_(
			"Train forks, pins, skewers, hanging pieces and removing defenders so you spot clean material gains.",
		),
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
		# Translators: Name of the training plan about attacking the king, shown in a combo box.
		label=N_("Attack the king: mating nets and king hunts"),
		# Translators: Description of the training plan about attacking the king.
		description=N_("Mates in one to three, back rank mates, exposed kings and attacks on either wing."),
		# `mate` saiu: ele só diz que a posição termina em mate, aparece em
		# 31,6% dos puzzles e, num filtro que é OU, engolia os motivos de
		# ataque ao rei que dão nome ao plano. Sem ele o plano passa de 38,4%
		# para 17,5% do banco -- e o que sobra é ataque ao rei de verdade.
		theme_slugs=(
			"mateIn1",
			"mateIn2",
			"mateIn3",
			"backRankMate",
			"exposedKing",
			"kingsideAttack",
			"queensideAttack",
			"attackingF2F7",
			"doubleCheck",
		),
	),
	TrainerPreset(
		preset_id="mixedPractice",
		# Translators: Name of the varied training plan, shown in a combo box.
		label=N_("Mixed motifs: material, mate, sacrifice and defence"),
		# Translators: Description of the varied training plan.
		description=N_(
			"A broad spread across the tactical motif families: winning material, mating, sacrifice and deflection, defence and quiet moves, converting an advantage.",
		),
		# Antes esta lista trazia `short`, `middlegame`, `advantage` e `mate`,
		# que não são motivos táticos e sim comprimento da solução, fase do
		# jogo, avaliação e desfecho. Como `short` sozinho aparece em metade
		# dos puzzles, o filtro alcançava 89,5% do banco: era "todos os temas"
		# com outro nome. Esta lista cobre 72,7%, e cada puzzle entra por causa
		# de um motivo de verdade. Quem quer o banco inteiro escolhe o plano
		# "All themes", que diz o que faz.
		theme_slugs=(
			# ganho de material
			"fork",
			"pin",
			"skewer",
			"hangingPiece",
			"discoveredAttack",
			"trappedPiece",
			# sacrifício e desvio
			"sacrifice",
			"deflection",
			"attraction",
			"clearance",
			# mate
			"mateIn1",
			"mateIn2",
			"backRankMate",
			# defesa e lance quieto
			"defensiveMove",
			"quietMove",
			# conversão de vantagem
			"advancedPawn",
			"promotion",
		),
	),
	TrainerPreset(
		preset_id="allThemes",
		# Translators: Name of the training plan that applies no theme filter, shown in a combo box.
		label=N_("All themes: no filter"),
		# Translators: Description of the training plan that applies no theme filter.
		description=N_("No theme filter at all: the whole puzzle database is in play."),
		# Nenhum slug, e sem ser tema personalizado: o filtro sai vazio e a
		# consulta não acrescenta cláusula de tema. Existe como escolha
		# explícita porque antes o único jeito de chegar aqui era escolher
		# "Custom themes" e deixar o campo em branco, o que ninguém descobre.
	),
	TrainerPreset(
		preset_id="customThemes",
		# Translators: Name of the training plan where the user picks the themes, shown in a combo box.
		label=N_("Custom themes: your own selection"),
		# Translators: Description of the training plan where the user picks the themes.
		description=N_("Choose the exact Lichess themes you want to include in the session."),
		uses_custom_themes=True,
	),
)


CHALLENGE_LEVELS = (
	ChallengeLevel(
		challenge_id="beginner",
		# Translators: Name of the easiest challenge level. The rating range is appended automatically.
		label=N_("Beginner"),
		# Translators: Description of the easiest challenge level.
		description=N_("Shorter, cleaner and well liked examples."),
		# Sem piso: o banco desce até rating 399 hoje, e um número fixo aqui
		# esconderia os puzzles mais fáceis de quem mais precisa deles.
		min_rating=None,
		max_rating=1100,
		min_popularity=70,
	),
	ChallengeLevel(
		challenge_id="intermediate",
		# Translators: Name of the middle challenge level. The rating range is appended automatically.
		label=N_("Intermediate"),
		# Translators: Description of the middle challenge level.
		description=N_("A comfortable middle ground for daily training."),
		min_rating=900,
		max_rating=1500,
		min_popularity=50,
	),
	ChallengeLevel(
		challenge_id="advanced",
		# Translators: Name of the harder challenge level. The rating range is appended automatically.
		label=N_("Advanced"),
		# Translators: Description of the harder challenge level.
		description=N_("Harder positions with more to calculate."),
		min_rating=1200,
		max_rating=1900,
		min_popularity=25,
	),
	ChallengeLevel(
		challenge_id="hard",
		# Translators: Name of the hardest fixed challenge level. The rating range is appended automatically.
		label=N_("Hard"),
		# Translators: Description of the hardest fixed challenge level.
		description=N_("The top of the database, with no popularity filter."),
		# Sem teto: o banco sobe até 3329, e travar em 2400 tiraria do treino
		# justamente os puzzles que ainda teriam algo a ensinar.
		min_rating=1600,
		max_rating=None,
		min_popularity=0,
	),
	ChallengeLevel(
		challenge_id="adaptive",
		# Translators: Name of the challenge level that follows the user's rating. The explanation is appended automatically.
		label=N_("Adaptive"),
		# Translators: Description of the challenge level that follows the user's rating.
		description=N_("The difficulty tracks your own tactics rating as you improve."),
		min_rating=None,
		max_rating=None,
		min_popularity=25,
		adaptive=True,
	),
)

# Identificadores gravados na configuração por versões anteriores. O nome
# mudou porque "stretch" e "challenge" não diziam nada a quem ouvia a lista.
LEGACY_CHALLENGE_IDS = {
	"veryAccessible": "beginner",
	"balanced": "intermediate",
	"stretch": "advanced",
	"challenge": "hard",
}

DEFAULT_TRAINER_PRESET_ID = TRAINER_PRESETS[0].preset_id
DEFAULT_CHALLENGE_ID = CHALLENGE_LEVELS[1].challenge_id


def get_trainer_preset(preset_id: str | None) -> TrainerPreset:
	for preset in TRAINER_PRESETS:
		if preset.preset_id == preset_id:
			return preset
	return TRAINER_PRESETS[0]


def get_challenge_level(challenge_id: str | None) -> ChallengeLevel:
	challenge_id = LEGACY_CHALLENGE_IDS.get(challenge_id or "", challenge_id)
	for level in CHALLENGE_LEVELS:
		if level.challenge_id == challenge_id:
			return level
	return CHALLENGE_LEVELS[1]


def uses_custom_themes(preset_id: str | None) -> bool:
	return get_trainer_preset(preset_id).uses_custom_themes


def preset_label(preset: TrainerPreset) -> str:
	return _(preset.label)


def preset_description(preset: TrainerPreset) -> str:
	return _(preset.description)


def challenge_label(level: ChallengeLevel) -> str:
	"""Nome do nível com a faixa de rating: é tudo o que o leitor de tela fala na lista."""
	# Translators: One challenge level in the combo box, e.g. "Intermediate: puzzles rated 900 to 1500".
	return _("{name}: {rating_range}").format(name=_(level.label), rating_range=describe_rating_range(level))


def challenge_description(level: ChallengeLevel) -> str:
	return _(level.description)


def describe_rating_range(selection: ChallengeLevel | ResolvedTrainingSelection) -> str:
	"""A faixa de rating em palavras, para ser lida em voz alta.

	Vive aqui, e não em cada diálogo, porque são dois -- o de sessão e o painel
	de configurações -- e eles já divergiram uma vez: um tratava a ponta aberta
	e o outro anunciava a palavra "None" para o usuário. Regra de leitura de
	tela em uma frase só, num lugar só.
	"""
	if selection.adaptive:
		# Translators: Rating description when the trainer follows the user's own rating.
		return _("puzzles picked around your own tactics rating")
	if selection.min_rating is None and selection.max_rating is None:
		# Translators: Rating description when no rating limit applies.
		return _("puzzles of any rating")
	if selection.min_rating is None:
		# Translators: Rating description with an upper limit only. {max_rating} is a number.
		return _("puzzles rated up to {max_rating}").format(max_rating=selection.max_rating)
	if selection.max_rating is None:
		# Translators: Rating description with a lower limit only. {min_rating} is a number.
		return _("puzzles rated {min_rating} and above").format(min_rating=selection.min_rating)
	# Translators: Rating description with both limits. Both are numbers.
	return _("puzzles rated {min_rating} to {max_rating}").format(
		min_rating=selection.min_rating,
		max_rating=selection.max_rating,
	)


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
