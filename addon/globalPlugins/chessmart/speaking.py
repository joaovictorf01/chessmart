# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Speaking through NVDA: the add-on's speech queue and a helper for building sequences."""

import speech


def intersperse(lst, item) -> speech.SpeechSequence:
	"""Puts `item` between every two elements: [a, b, c] -> [a, item, b, item, c].

	Used to place a pause (BreakCommand) between the parts of an announcement.
	Taken from: https://stackoverflow.com/a/5921708
	"""
	result = [item] * (len(lst) * 2 - 1)
	result[0::2] = lst
	return result


def speak_next(speech_sequence: speech.SpeechSequence, priority=speech.priorities.Spri.NEXT) -> None:
	"""Speaks after what's already queued, without interrupting what NVDA is currently saying."""
	speech.speak(speech_sequence, priority=priority)
