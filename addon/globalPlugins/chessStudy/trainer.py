# coding: utf-8
# pyright: basic

"""Training plans and challenge levels for the tactics trainer.

The strings the user sees live in the constants, marked with `N_()`: this
hands them to the translation extractor without translating at import time.
The actual translation happens in `preset_label`, `challenge_label` and
similar functions, on every call, so changing NVDA's language doesn't
require restarting the add-on.
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
	# None on either end means "no limit": the SQL filter simply doesn't add
	# the clause, so training reaches the whole database instead of an
	# arbitrary range.
	min_rating: int | None
	max_rating: int | None
	min_popularity: int
	# In adaptive mode the ranges above are ignored: difficulty instead
	# follows the player's rating, draw by draw.
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
		# `short` and `oneMove` were removed. The theme filter is an OR, so
		# including "short position" in a list of motifs didn't restrict
		# anything: it let in ANY short puzzle, regardless of motif. Since
		# `short` alone covers half the database, the plan reached 75% of it
		# and the motifs became decoration. Without the two, it drops to
		# 49.6% and means what it says again. The intent of "keep it short"
		# belongs to the challenge level.
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
		# `mate` was removed: it only says the position ends in mate, appears
		# in 31.6% of puzzles, and, in an OR filter, swallowed the king-attack
		# motifs that give the plan its name. Without it the plan drops from
		# 38.4% to 17.5% of the database -- and what's left is a real king
		# attack.
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
		# This list used to include `short`, `middlegame`, `advantage` and
		# `mate`, which aren't tactical motifs but solution length, game
		# phase, evaluation and outcome. Since `short` alone appears in half
		# the puzzles, the filter reached 89.5% of the database: it was "all
		# themes" under another name. This list covers 72.7%, and each puzzle
		# enters because of a real motif. Anyone who wants the whole database
		# picks the "All themes" plan, which says what it does.
		theme_slugs=(
			# material gain
			"fork",
			"pin",
			"skewer",
			"hangingPiece",
			"discoveredAttack",
			"trappedPiece",
			# sacrifice and deflection
			"sacrifice",
			"deflection",
			"attraction",
			"clearance",
			# mate
			"mateIn1",
			"mateIn2",
			"backRankMate",
			# defense and quiet move
			"defensiveMove",
			"quietMove",
			# advantage conversion
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
		# No slugs, and not a custom theme: the filter comes out empty and
		# the query adds no theme clause. This exists as an explicit choice
		# because previously the only way to get here was picking "Custom
		# themes" and leaving the field blank, which nobody discovers.
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
		# No floor: the database currently goes down to rating 399, and a
		# fixed number here would hide the easiest puzzles from the people
		# who need them most.
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
		# No ceiling: the database goes up to 3329, and capping at 2400 would
		# remove from training exactly the puzzles that would still have
		# something to teach.
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

# Identifiers saved in the configuration by earlier versions. The name
# changed because "stretch" and "challenge" didn't mean anything to someone
# hearing the list read aloud.
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
	"""Name of the level with the rating range: it's everything the screen reader speaks in the list."""
	# Translators: One challenge level in the combo box, e.g. "Intermediate: puzzles rated 900 to 1500".
	return _("{name}: {rating_range}").format(name=_(level.label), rating_range=describe_rating_range(level))


def challenge_description(level: ChallengeLevel) -> str:
	return _(level.description)


def describe_rating_range(selection: ChallengeLevel | ResolvedTrainingSelection) -> str:
	"""The rating range in words, meant to be read aloud.

	Lives here, not in each dialog, because there are two -- the session one
	and the settings panel -- and they've already diverged once: one handled
	the open end and the other announced the word "None" to the user. One
	screen reader rule, in one place.
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
