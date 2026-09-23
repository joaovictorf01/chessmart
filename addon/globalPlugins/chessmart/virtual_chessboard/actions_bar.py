# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The bar Tab opens on the puzzle, endgame and analysis boards.

One implementation for the three boards (architecture review, finding 11): the
bar, its buttons, and moving the focus between it and the board. The Tab and
Shift+Tab keys stay in each board's cell class, because NVDA only binds the
`script_*` methods a class defines itself (baseObject.ScriptableType).
"""

import typing

import controlTypes
import eventHandler
import queueHandler

from .ui_components import MenuItemObject, MenuObject


class TrainingActionItem(MenuItemObject):
	role = controlTypes.Role.BUTTON

	def __init__(self, *args, callback, **kwargs):
		super().__init__(*args, **kwargs)
		self.callback = callback
		self.bindGesture("kb:tab", "go_next")
		self.bindGesture("kb:shift+tab", "go_prev")
		self.bindGesture("kb:rightarrow", "go_next")
		self.bindGesture("kb:leftarrow", "go_prev")


class TrainingActionsBar(MenuObject):
	role = controlTypes.Role.TOOLBAR
	use_default_navigation_scripts = False

	def __init__(self, *args, items, **kwargs):
		super().__init__(*args, **kwargs)
		action_items = [
			TrainingActionItem(parent=self, name=name, callback=callback) for name, callback in items
		]
		self.init_container_state(
			action_items,
			on_top_edge=self.parent.focus_board_from_actions,
			on_bottom_edge=self.parent.focus_board_from_actions,
		)

	def close_menu(self):
		self.parent.focus_board_from_actions()

	def on_item_activated(self, item):
		item.callback()


class ActionsBarMixin:
	"""Moves the focus between a board and its actions bar. Combined with a board class."""

	_actions_bar: typing.Any = None
	_current_focused_object: typing.Any
	_focused_cell: int

	def install_actions_bar(self, name, items):
		"""`items` is a list of (label, callback); Tab lands on the first, Shift+Tab on the last."""
		self._actions_bar = TrainingActionsBar(parent=self, name=name, items=items)
		return self._actions_bar

	def focus_action_bar(self, reverse=False):
		if not self._actions_bar:
			return
		self._current_focused_object = self._actions_bar
		self._actions_bar.set_current(len(self._actions_bar) - 1 if reverse else 0)
		eventHandler.executeEvent("gainFocus", self._actions_bar)

	def focus_board_from_actions(self):
		self._current_focused_object = None
		self.set_focus_to_cell(self._focused_cell)  # pyright: ignore[reportAttributeAccessIssue]

	def _from_actions(self, action):
		"""An action run from the bar: back to the board first, so what it says is heard there.

		The endgame boards override this: their actions move the focus themselves.
		"""

		def run():
			self.focus_board_from_actions()
			queueHandler.queueFunction(queueHandler.eventQueue, action)

		return run
