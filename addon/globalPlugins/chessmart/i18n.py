# coding: utf-8
"""Ponto único de tradução do add-on: `from .i18n import _`.

`addonHandler.initTranslation()` descobre o módulo que o chamou pelo frame e
grava NESSE módulo as funções `_`, `ngettext`, `pgettext` e `npgettext`
apontando para o catálogo do add-on (locale/<idioma>/LC_MESSAGES/nvda.mo).
Por isso a chamada fica aqui, no nível do módulo, e não dentro de uma função:
de dentro de uma função ela gravaria no módulo do mesmo jeito, mas o valor
devolvido pela função -- o `_` do `builtins`, que é a tradução do próprio NVDA
-- sobrescreveria o certo. Foi exatamente esse o bug até a 1.0.

Fora de um add-on instalado (scratchpad, testes) a chamada falha, e `_`
cai no `_` que já existir ou na identidade.
"""

import builtins

from logHandler import log


def _identity(message):
	return message


try:
	import addonHandler

	addonHandler.initTranslation()
except Exception as error:  # noqa: BLE001 - fora do NVDA ou fora de um add-on instalado
	log.debug("Chessmart translation is unavailable in this context: %s", error)
	_ = builtins.__dict__.get("_", _identity)
	ngettext = builtins.__dict__.get("ngettext", lambda singular, plural, n: singular if n == 1 else plural)
	pgettext = builtins.__dict__.get("pgettext", lambda context, message: message)
	npgettext = builtins.__dict__.get(
		"npgettext",
		lambda context, singular, plural, n: singular if n == 1 else plural,
	)

__all__ = ["_", "ngettext", "pgettext", "npgettext"]
