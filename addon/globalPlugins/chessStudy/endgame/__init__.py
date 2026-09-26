# coding: utf-8
# pyright: basic

"""Endgames: mate drills, lessons with question-and-rule, and the tablebase judge.

`drills` are the elementary mates against the engine; `tablebase` downloads
and opens the Syzygy tables; `judge` translates a table lookup into a spoken
verdict; `lessons` is the trail of ideas (what draws, what doesn't). None of
these modules import NVDA: the board and dialogs live in `virtual_chessboard`
and `graphical_interface`.
"""
