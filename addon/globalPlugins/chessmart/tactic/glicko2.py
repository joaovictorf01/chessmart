# coding: utf-8

"""Glicko-2 para o treinador de táticas.

Cada tentativa de puzzle é tratada como uma partida: você de um lado, o puzzle
do outro. O banco do Lichess já traz `rating` e `rating_deviation` de cada
puzzle, que são exatamente as duas entradas que a fórmula pede do adversário,
então o número que sai daqui é comparável a um rating de tática do Lichess.

Só o jogador é atualizado. O rating do puzzle vem do banco e fica onde está --
ele foi calculado sobre milhões de tentativas e nada que você faça sozinho
deveria movê-lo.

Módulo puro de propósito: não importa NVDA, não importa sqlite, não toca em
disco. Dá para exercitar com um Python qualquer, o que é o que permite testar a
matemática sem subir um leitor de tela.

Referência: Mark E. Glickman, "Example of the Glicko-2 system" (glicko.net).
"""

from __future__ import annotations

import dataclasses
import math


# A escala interna do Glicko-2 é diferente da que se lê na tela. 173.7178 é o
# fator de conversão entre as duas, e 1500 é o centro da escala visível.
SCALE = 173.7178
CENTER = 1500.0

# Rating de partida de quem nunca resolveu nada: 1500 com desvio 350 quer dizer
# "não faço ideia do teu nível". O desvio despenca nas primeiras tentativas.
DEFAULT_RATING = 1500.0
DEFAULT_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06

# Tau limita o quanto a volatilidade pode mudar de uma vez. Valores baixos
# deixam o rating mais estável; altos deixam ele reagir mais rápido a uma
# sequência fora do normal. Glickman sugere entre 0.3 e 1.2.
DEFAULT_TAU = 0.5

# Critério de parada da iteração que resolve a volatilidade.
CONVERGENCE = 1e-6
MAX_ITERATIONS = 100

# Acima deste desvio o rating ainda é palpite: 1500 com desvio 200 quer dizer
# "algo entre 1100 e 1900". Quem anuncia o número deve dizer que é provisório.
PROVISIONAL_DEVIATION = 110.0


@dataclasses.dataclass(frozen=True)
class Rating:
	"""Os três números que descrevem a força de alguém no Glicko-2."""

	rating: float = DEFAULT_RATING
	deviation: float = DEFAULT_DEVIATION
	volatility: float = DEFAULT_VOLATILITY

	def rounded(self) -> int:
		"""O rating como se mostra a um humano."""
		return int(round(self.rating))

	def confidence_interval(self) -> tuple[int, int]:
		"""Faixa de ~95% de confiança: rating +- dois desvios.

		Serve para dizer honestamente "entre 1420 e 1580" enquanto o sistema
		ainda não te conhece, em vez de fingir precisão que não existe.
		"""
		margin = 2 * self.deviation
		return int(round(self.rating - margin)), int(round(self.rating + margin))


def _g(phi: float) -> float:
	"""Peso do adversário: quanto mais incerto o rating dele, menos ele pesa."""
	return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
	"""Probabilidade de você resolver este puzzle, entre 0 e 1."""
	return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _new_volatility(phi: float, v: float, delta: float, sigma: float, tau: float) -> float:
	"""Resolve a nova volatilidade pelo método de Illinois.

	Esta é a única parte do Glicko-2 sem fórmula fechada: a equação não se
	isola, então se procura a raiz por tentativa dirigida. O método de Illinois
	é uma variação da falsa posição que evita ficar preso de um lado só.
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
		# Nenhum palpite óbvio: recua de tau em tau até a função trocar de sinal.
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
			# O "Illinois": corta o valor pela metade do lado que não se moveu,
			# senão a convergência se arrasta.
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
	"""Devolve o rating do jogador depois de uma tentativa.

	`solved` é o placar da "partida": resolver vale 1, errar vale 0. O Glicko-2
	aceita empate (0.5), mas um puzzle não empata.

	O rating do puzzle entra como adversário e sai intacto -- quem muda é você.
	"""
	score = 1.0 if solved else 0.0

	# Para a escala interna.
	mu = (player.rating - CENTER) / SCALE
	phi = player.deviation / SCALE
	mu_j = (puzzle_rating - CENTER) / SCALE
	phi_j = max(puzzle_deviation, 1.0) / SCALE

	g_j = _g(phi_j)
	expected = _expected(mu, mu_j, phi_j)

	# v é a variância da estimativa: o quanto esta única tentativa informa.
	# Um puzzle muito acima ou muito abaixo de você quase não informa, porque o
	# resultado já era previsível -- e é isso que o termo E*(1-E) captura.
	v = 1.0 / (g_j * g_j * expected * (1.0 - expected))

	# delta é a correção sugerida: a surpresa (placar menos esperado), pesada.
	delta = v * g_j * (score - expected)

	sigma = _new_volatility(phi, v, delta, player.volatility, tau)

	# O desvio primeiro cresce pela volatilidade, depois encolhe pela informação
	# que a tentativa trouxe. É por isso que sumir por meses aumenta teu desvio:
	# o sistema volta a desconfiar do número.
	phi_star = math.sqrt(phi * phi + sigma * sigma)
	phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
	mu_new = mu + phi_new * phi_new * g_j * (score - expected)

	return Rating(
		rating=mu_new * SCALE + CENTER,
		deviation=phi_new * SCALE,
		volatility=sigma,
	)


def decay(player: Rating, periods: float, tau: float = DEFAULT_TAU) -> Rating:
	"""Aumenta o desvio por inatividade, sem mexer no rating.

	`periods` é quantos períodos de avaliação se passaram sem tentativa alguma.
	O rating em si não muda -- não há motivo para supor que você piorou --, mas
	a confiança nele diminui, que é o que o Glicko-2 chama de rating decay.
	"""
	if periods <= 0:
		return player
	phi = player.deviation / SCALE
	phi_new = math.sqrt(phi * phi + periods * player.volatility * player.volatility)
	# Um desvio maior que o inicial seria dizer que se sabe menos do que se
	# sabia antes de qualquer tentativa, o que não faz sentido.
	deviation = min(phi_new * SCALE, DEFAULT_DEVIATION)
	return dataclasses.replace(player, deviation=deviation)


def expected_score(player: Rating, puzzle_rating: float, puzzle_deviation: float) -> float:
	"""Chance de o jogador resolver este puzzle, entre 0 e 1.

	É a mesma conta que `update` faz por dentro, exposta para a seleção
	adaptativa: para treinar de verdade, se procura puzzle com chance perto de
	meio a meio, onde há mais a aprender.
	"""
	mu = (player.rating - CENTER) / SCALE
	mu_j = (puzzle_rating - CENTER) / SCALE
	phi_j = max(puzzle_deviation, 1.0) / SCALE
	return _expected(mu, mu_j, phi_j)
