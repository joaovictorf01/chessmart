# coding: utf-8
# pyright: basic

import dataclasses
import types
from typing import TYPE_CHECKING, Any


class Variant:
	"""Provides member definition"""

	def __init__(self, **kwargs):
		self.kwargs = kwargs

	if TYPE_CHECKING:
		# After `__init_subclass__`, the class attribute is the generated dataclass,
		# and calling it constructs the event. For the type checker, this is just
		# a regular call; the real constructor is below.
		def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

	else:

		def __call__(self, cls_type, name, bases=(), namespace=None):
			namespace = namespace or {}
			namespace["__member_name__"] = name
			namespace["__member_type__"] = cls_type
			return dataclasses.make_dataclass(
				name.title(),
				tuple(self.kwargs.items()),
				bases=bases,
				namespace=namespace,
				repr=True,
				frozen=True,
			)


class AlgebraicTypeMeta(type):
	def __repr__(cls):
		parent_cls = cls.__dict__.get("__member_type__")
		if parent_cls is None:
			members = getattr(cls, "__members__", {})
			return f"<AlgebraicType {cls.__name__}: members={tuple(members.values())}>"
		return f"<{parent_cls.__name__}.{getattr(cls, '__member_name__', '?')}>"


class AlgebraicType(metaclass=AlgebraicTypeMeta):
	"""Represents an algebraic type."""

	@classmethod
	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		attributes = {
			key: value(cls, key, bases=(cls,))
			for key, value in cls.__dict__.items()
			if isinstance(value, Variant)
		}
		for key, value in attributes.items():
			setattr(cls, key, value)
		cls.__members__ = types.MappingProxyType(attributes)

	def of_type(self, variant):
		return isinstance(self, variant)

	def of_any_type_of(self, *it_types):
		return any(self.of_type(t) for t in it_types)
