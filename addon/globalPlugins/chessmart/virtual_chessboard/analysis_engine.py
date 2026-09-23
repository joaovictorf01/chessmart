# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Stockfish for the analysis board: one engine per board, started on first use.

Every request runs on the add-on's thread pool and hands back a Future; the board
turns the result into speech on the main thread. One request at a time: a second
press while the engine thinks is refused instead of queued, so answers never
arrive for a position the user has already left.

UCI in two lines: the add-on sends the position and a limit ("think two
seconds"); the engine answers with its evaluation and principal variation, the
line it expects both sides to play. python-chess speaks the protocol.
"""

import dataclasses
import os
import subprocess
import threading
import typing as t
from concurrent.futures import Future

from logHandler import log

from ..concurrency import call_threaded
from ..engine_eval import Assessment, MoveReview
from ..paths import import_bundled
from .user_engine import STOCKFISH_EXECUTABLE_PATH, STOCKFISH_VERSION


with import_bundled():
	import chess
	import chess.engine


# Seconds per evaluation: enough for depth 18-22 on an ordinary laptop, short
# enough to wait for. Pressing the key twice asks for the long think.
QUICK_SECONDS = 2.0
DEEP_SECONDS = 8.0
# Memory for the engine's position table, in MB; the default 16 fills in seconds.
HASH_MB = 128
# Candidate moves per evaluation (UCI MultiPV): the best one and two others,
# as Lichess can show. Each costs a little depth; three is the usual compromise.
CANDIDATES = 3


def _threads() -> int:
	"""Half the processors, at most 4: fast analysis without freezing NVDA or the rest of the machine."""
	return max(1, min(4, (os.cpu_count() or 2) // 2))


@dataclasses.dataclass(frozen=True)
class Evaluation:
	board: "chess.Board"
	assessment: Assessment
	depth: int
	# The principal variation: the line the engine expects, best move first.
	line: tuple["chess.Move", ...]

	@property
	def best_move(self) -> t.Optional["chess.Move"]:
		return self.line[0] if self.line else None


class AnalysisEngine:
	version = STOCKFISH_VERSION

	def __init__(self, executable: str = STOCKFISH_EXECUTABLE_PATH):
		self.executable = executable
		self._engine: t.Optional["chess.engine.SimpleEngine"] = None
		self._lock = threading.Lock()
		self._busy = False

	@property
	def busy(self) -> bool:
		return self._busy

	def _ensure_engine(self) -> "chess.engine.SimpleEngine":
		if self._engine is None:
			startupinfo = subprocess.STARTUPINFO()
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			self._engine = chess.engine.SimpleEngine.popen_uci(
				self.executable,
				creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
				startupinfo=startupinfo,
				close_fds=True,
			)
			self._engine.configure({"Threads": _threads(), "Hash": HASH_MB})
		return self._engine

	def _analyse_lines(self, board: "chess.Board", seconds: float, lines: int) -> list[Evaluation]:
		infos = self._ensure_engine().analyse(board, chess.engine.Limit(time=seconds), multipv=lines)
		return [
			Evaluation(
				board=board,
				assessment=Assessment.from_score(info["score"]),
				depth=int(info.get("depth", 0)),
				line=tuple(info.get("pv", ())),
			)
			for info in infos
			if "score" in info
		]

	def _analyse(self, board: "chess.Board", seconds: float) -> Evaluation:
		return self._analyse_lines(board, seconds, 1)[0]

	def try_start(self) -> bool:
		"""Claims the engine for one request; False if it is still thinking."""
		with self._lock:
			if self._busy:
				return False
			self._busy = True
			return True

	def _release(self) -> None:
		with self._lock:
			self._busy = False

	@call_threaded
	def evaluate(self, board: "chess.Board", seconds: float = QUICK_SECONDS) -> list[Evaluation]:
		"""The best line first, then the other candidates. Call only after `try_start()` returned True."""
		try:
			return self._analyse_lines(board.copy(), seconds, CANDIDATES)
		finally:
			self._release()

	@call_threaded
	def review_move(
		self,
		board_before: "chess.Board",
		move: "chess.Move",
		seconds: float = QUICK_SECONDS,
	) -> tuple[MoveReview, Evaluation]:
		"""The move against the engine's best from the same position. Call after `try_start()`."""
		try:
			before = self._analyse(board_before.copy(), seconds)
			after_board = board_before.copy()
			after_board.push(move)
			if before.best_move == move:
				played = before.assessment
			elif after_board.is_game_over():
				outcome = after_board.outcome()
				assert outcome is not None
				if outcome.winner is None:
					played = Assessment(centipawns=0, mate=None)
				else:
					played = Assessment(centipawns=None, mate=1 if outcome.winner == chess.WHITE else -1)
			else:
				played = self._analyse(after_board, seconds).assessment
			assert before.best_move is not None, "a position with a move to review has a best move"
			review = MoveReview(
				mover=board_before.turn,
				played=played,
				best=before.assessment,
				best_move=before.best_move,
				played_move=move,
			)
			return review, before
		finally:
			self._release()

	@call_threaded
	def evaluate_positions(
		self,
		boards: t.Sequence["chess.Board"],
		seconds: float,
		progress: t.Callable[[int, int], None],
		cancel: threading.Event,
	) -> list[t.Optional[Evaluation]]:
		"""One evaluation per board, in order; None for a finished position. Call after `try_start()`.

		`progress(done, total)` is called from this worker thread after each
		board; setting `cancel` stops before the next one and returns what is done.
		"""
		try:
			results: list[t.Optional[Evaluation]] = []
			for done, board in enumerate(boards, start=1):
				if cancel.is_set():
					break
				results.append(None if board.is_game_over() else self._analyse(board.copy(), seconds))
				progress(done, len(boards))
			return results
		finally:
			self._release()

	def quit(self) -> None:
		engine, self._engine = self._engine, None
		if engine is None:
			return
		try:
			engine.quit()
		except (chess.engine.EngineError, chess.engine.EngineTerminatedError, OSError):
			log.debug("chessmart: analysis engine already gone")


def result_of(future: Future):
	"""The value, or the engine error to report; never raises."""
	try:
		return future.result(), None
	except (chess.engine.EngineError, chess.engine.EngineTerminatedError, OSError) as error:
		log.warning("chessmart: analysis engine failed: %s", error)
		return None, error
