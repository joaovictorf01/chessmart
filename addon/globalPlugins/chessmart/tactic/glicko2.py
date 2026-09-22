# coding: utf-8
# pyright: basic

"""Glicko-2 for the tactics trainer.

Each puzzle attempt is treated as a game: the player on one side, the puzzle
on the other. The Lichess database already provides `rating` and
`rating_deviation` for each puzzle, which are exactly the two inputs the
formula needs for the opponent, so the number produced here is comparable
to a Lichess tactics rating.

Only the player is updated. The puzzle's rating comes from the database and
stays put -- it was computed over millions of attempts, and nothing a single
player does should move it.

A pure module by design: no NVDA, no sqlite, no disk access. It can be
exercised with any Python, which is what lets the math be tested without
starting a screen reader.

Reference: Mark E. Glickman, "Example of the Glicko-2 system" (glicko.net).
"""

from __future__ import annotations

import dataclasses
import math


# The Glicko-2 internal scale differs from the one shown on screen. 173.7178
# is the conversion factor between the two, and 1500 is the center of the visible scale.
SCALE = 173.7178
CENTER = 1500.0

# Starting rating for someone who has never solved anything: 1500 with a
# deviation of 350 means "no idea what your level is". The deviation drops fast in the first attempts.
DEFAULT_RATING = 1500.0
DEFAULT_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06

# Tau limits how much volatility can change at once. Low values keep the
# rating more stable; high values let it react faster to an unusual streak.
# Glickman suggests between 0.3 and 1.2.
DEFAULT_TAU = 0.5

# Stopping criterion for the iteration that solves for volatility.
CONVERGENCE = 1e-6
MAX_ITERATIONS = 100

# Above this deviation the rating is still a guess: 1500 with a deviation of
# 200 means "somewhere between 1100 and 1900". Whoever announces the number should say it's provisional.
PROVISIONAL_DEVIATION = 110.0


@dataclasses.dataclass(frozen=True)
class Rating:
	"""The three numbers that describe someone's strength in Glicko-2."""

	rating: float = DEFAULT_RATING
	deviation: float = DEFAULT_DEVIATION
	volatility: float = DEFAULT_VOLATILITY

	def rounded(self) -> int:
		"""The rating as shown to a human."""
		return int(round(self.rating))

	def confidence_interval(self) -> tuple[int, int]:
		"""~95% confidence interval: rating +- two deviations.

		Lets the system honestly say "between 1420 and 1580" while it still
		doesn't know the player, instead of faking a precision that isn't there.
		"""
		margin = 2 * self.deviation
		return int(round(self.rating - margin)), int(round(self.rating + margin))


def _g(phi: float) -> float:
	"""Weight of the opponent: the more uncertain their rating, the less it weighs."""
	return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
	"""Probability of solving this puzzle, between 0 and 1."""
	return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _new_volatility(phi: float, v: float, delta: float, sigma: float, tau: float) -> float:
	"""Solve for the new volatility using the Illinois method.

	This is the only part of Glicko-2 without a closed-form formula: the
	equation cannot be isolated, so the root is found by directed search. The
	Illinois method is a variant of regula falsi that avoids getting stuck on one side.
	"""
	a = math.log(sigma * sigma)
	phi2, delta2 = phi * phi, delta * delta

	def f(x: float) -> float:
		ex = math.exp(x)
		numerator = ex * (delta2 - phi2 - v - ex)
		denominator = 2.0 * (phi2 + v + ex) ** 2
		return numerator / denominator - (x - a) / (tau * tau)

	A = a
	if delta2 > phi2 + v:
		B = math.log(delta2 - phi2 - v)
	else:
		# No obvious guess: step back by tau until the function changes sign.
		k = 1
		while f(a - k * tau) < 0 and k <= MAX_ITERATIONS:
			k += 1
		B = a - k * tau

	fA, fB = f(A), f(B)
	for _ in range(MAX_ITERATIONS):
		if abs(B - A) <= CONVERGENCE:
			break
		C = A + (A - B) * fA / (fB - fA)
		fC = f(C)
		if fC * fB <= 0:
			A, fA = B, fB
		else:
			# The "Illinois" trick: halve the value on the side that hasn't
			# moved, otherwise convergence drags on.
			fA = fA / 2.0
		B, fB = C, fC
	return math.exp(A / 2.0)


def update(
	player: Rating,
	puzzle_rating: float,
	puzzle_deviation: float,
	solved: bool,
	tau: float = DEFAULT_TAU,
) -> Rating:
	"""Return the player's rating after one attempt.

	`solved` is the "game" score: solving is worth 1, missing is worth 0.
	Glicko-2 accepts a draw (0.5), but a puzzle has no draw.

	The puzzle's rating enters as the opponent and comes out unchanged -- only the player's rating moves.
	"""
	score = 1.0 if solved else 0.0

	# To the internal scale.
	mu = (player.rating - CENTER) / SCALE
	phi = player.deviation / SCALE
	mu_j = (puzzle_rating - CENTER) / SCALE
	phi_j = max(puzzle_deviation, 1.0) / SCALE

	g_j = _g(phi_j)
	expected = _expected(mu, mu_j, phi_j)

	# v is the variance of the estimate: how much this single attempt informs
	# it. A puzzle far above or far below the player's level barely informs
	# it, because the result was already predictable -- which is what the E*(1-E) term captures.
	v = 1.0 / (g_j * g_j * expected * (1.0 - expected))

	# delta is the suggested correction: the surprise (score minus expected), weighted.
	delta = v * g_j * (score - expected)

	sigma = _new_volatility(phi, v, delta, player.volatility, tau)

	# The deviation first grows from volatility, then shrinks from the
	# information the attempt brought. This is why going inactive for months
	# increases the deviation: the system starts doubting the number again.
	phi_star = math.sqrt(phi * phi + sigma * sigma)
	phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
	mu_new = mu + phi_new * phi_new * g_j * (score - expected)

	return Rating(
		rating=mu_new * SCALE + CENTER,
		deviation=phi_new * SCALE,
		volatility=sigma,
	)


def decay(player: Rating, periods: float, tau: float = DEFAULT_TAU) -> Rating:
	"""Increase the deviation for inactivity, without touching the rating.

	`periods` is how many rating periods have passed with no attempt at all.
	The rating itself does not change -- there is no reason to assume the
	player got worse -- but confidence in it decreases, which is what Glicko-2 calls rating decay.
	"""
	if periods <= 0:
		return player
	phi = player.deviation / SCALE
	phi_new = math.sqrt(phi * phi + periods * player.volatility * player.volatility)
	# A deviation larger than the initial one would mean knowing less than
	# before any attempt at all, which makes no sense.
	deviation = min(phi_new * SCALE, DEFAULT_DEVIATION)
	return dataclasses.replace(player, deviation=deviation)


def expected_score(player: Rating, puzzle_rating: float, puzzle_deviation: float) -> float:
	"""Chance the player solves this puzzle, between 0 and 1.

	The same computation `update` does internally, exposed for adaptive
	selection: to train effectively, look for a puzzle with a chance close to
	fifty-fifty, where there is the most to learn.
	"""
	mu = (player.rating - CENTER) / SCALE
	mu_j = (puzzle_rating - CENTER) / SCALE
	phi_j = max(puzzle_deviation, 1.0) / SCALE
	return _expected(mu, mu_j, phi_j)
