# coding: utf-8
# pyright: basic

import typing as t
import wx


if t.TYPE_CHECKING:
	_ItemContainerBase = wx.ItemContainerImmutable
else:
	_ItemContainerBase = object


class EnumItemContainerMixin(_ItemContainerBase):
	"""An item container that accepts a DisplayStringIntEnum as its choices argument."""

	items_arg: str = ""

	def __init__(self, *args, choice_enum, **kwargs):
		kwargs[self.items_arg] = [m.displayString for m in choice_enum]
		super().__init__(*args, **kwargs)
		self.choice_enum = choice_enum
		self.choice_members = tuple(choice_enum)
		if self.choice_members:
			self.SetSelection(0)

	def GetSelectedValue(self):
		return self.choice_members[self.GetSelection()]

	@property
	def SelectedValue(self):
		return self.GetSelectedValue()

	def SetSelectionByValue(self, value):
		if not isinstance(value, self.choice_enum):
			raise TypeError(f"{value} is not a {self.choice_enum}")
		self.SetSelection(self.choice_members.index(value))


class EnumRadioBox(EnumItemContainerMixin, wx.RadioBox):
	"""A RadioBox that accepts enum as choices."""

	items_arg = "choices"


class EnumChoice(EnumItemContainerMixin, wx.Choice):
	items_arg = "choices"
