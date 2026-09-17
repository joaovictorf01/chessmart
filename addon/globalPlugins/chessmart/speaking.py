# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Falar pelo NVDA: a fila de fala do add-on e um ajudante para montar sequências."""

import speech


def intersperse(lst, item) -> speech.SpeechSequence:
	"""Põe `item` entre cada dois elementos: [a, b, c] -> [a, item, b, item, c].

	Serve para colocar uma pausa (BreakCommand) entre as partes de um anúncio.
	Taken from: https://stackoverflow.com/a/5921708
	"""
	result = [item] * (len(lst) * 2 - 1)
	result[0::2] = lst
	return result


def speak_next(speech_sequence: speech.SpeechSequence, priority=speech.priorities.Spri.NEXT) -> None:
	"""Fala depois do que já está na fila, sem interromper o que o NVDA está dizendo."""
	speech.speak(speech_sequence, priority=priority)
