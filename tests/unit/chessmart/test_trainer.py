# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Planos, níveis, filtro de temas e nomes de temas: as regras puras do treinador."""

import unittest

from chessmart import trainer
from chessmart.theme_catalog import describe_theme_filter, format_theme_filter, parse_theme_filter
from chessmart.theme_names import THEME_TEXTS, humanize_theme_slug, theme_description, theme_label


class TestChallengeLevels(unittest.TestCase):
	def test_legacy_ids_map_to_the_renamed_levels(self):
		self.assertEqual(trainer.get_challenge_level("stretch").challenge_id, "advanced")
		self.assertEqual(trainer.get_challenge_level("veryAccessible").challenge_id, "beginner")
		self.assertEqual(trainer.get_challenge_level("challenge").challenge_id, "hard")
		self.assertEqual(trainer.get_challenge_level("balanced").challenge_id, "intermediate")
		self.assertEqual(trainer.get_challenge_level("adaptive").challenge_id, "adaptive")

	def test_unknown_id_falls_back_to_the_default(self):
		self.assertEqual(trainer.get_challenge_level("nope").challenge_id, trainer.DEFAULT_CHALLENGE_ID)
		self.assertEqual(trainer.get_challenge_level(None).challenge_id, trainer.DEFAULT_CHALLENGE_ID)
		self.assertEqual(trainer.get_trainer_preset("nope").preset_id, trainer.DEFAULT_TRAINER_PRESET_ID)

	def test_label_carries_the_rating_range(self):
		labels = [trainer.challenge_label(level) for level in trainer.CHALLENGE_LEVELS]
		self.assertEqual(labels[0], "Beginner: puzzles rated up to 1100")
		self.assertEqual(labels[1], "Intermediate: puzzles rated 900 to 1500")
		self.assertEqual(labels[3], "Hard: puzzles rated 1600 and above")
		self.assertEqual(labels[4], "Adaptive: puzzles picked around your own tactics rating")

	def test_open_ended_levels_leave_the_bound_unset(self):
		beginner = trainer.get_challenge_level("beginner")
		self.assertIsNone(beginner.min_rating)
		self.assertEqual(beginner.max_rating, 1100)
		hard = trainer.get_challenge_level("hard")
		self.assertEqual(hard.min_rating, 1600)
		self.assertIsNone(hard.max_rating)


class TestResolveSelection(unittest.TestCase):
	def test_preset_themes_win_over_custom_text(self):
		selection = trainer.resolve_training_selection("kingAttack", "advanced", custom_theme_text="fork")
		self.assertIn("mateIn1", selection.theme_text)
		self.assertNotIn("fork", selection.theme_text)
		self.assertEqual((selection.min_rating, selection.max_rating), (1200, 1900))
		self.assertFalse(selection.adaptive)

	def test_custom_preset_uses_the_text_deduplicated(self):
		selection = trainer.resolve_training_selection("customThemes", "adaptive", "fork, pin fork;skewer")
		self.assertEqual(selection.theme_text, "fork, pin, skewer")
		self.assertTrue(selection.adaptive)

	def test_all_themes_has_no_filter(self):
		selection = trainer.resolve_training_selection("allThemes", "beginner")
		self.assertEqual(selection.theme_text, "")

	def test_every_preset_slug_has_a_name(self):
		for preset in trainer.TRAINER_PRESETS:
			for slug in preset.theme_slugs:
				self.assertIn(slug, THEME_TEXTS, f"{preset.preset_id}: {slug}")


class TestThemeFilter(unittest.TestCase):
	def test_parse_splits_on_space_comma_and_semicolon(self):
		self.assertEqual(parse_theme_filter(" fork,pin ;skewer  fork"), ("fork", "pin", "skewer"))
		self.assertEqual(parse_theme_filter(""), ())
		self.assertEqual(format_theme_filter(("pin", "pin", "fork")), "pin, fork")

	def test_describe_uses_the_human_names(self):
		self.assertEqual(describe_theme_filter("fork, backRankMate"), "Fork, Back rank mate")


class TestThemeNames(unittest.TestCase):
	def test_known_slugs_have_readable_names(self):
		self.assertEqual(theme_label("mateIn1"), "Mate in one")
		self.assertEqual(theme_label("attackingF2F7"), "Attack on f2 or f7")
		self.assertEqual(theme_label("superGM"), "From super grandmaster games")
		self.assertTrue(theme_description("fork").endswith("."))

	def test_unknown_slug_falls_back_to_the_humanized_form(self):
		self.assertEqual(humanize_theme_slug("someNewTheme"), "Some New Theme")
		self.assertEqual(theme_label("someNewTheme"), "Some New Theme")
		self.assertIn("Some New Theme", theme_description("someNewTheme"))
