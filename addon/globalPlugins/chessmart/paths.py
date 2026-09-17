# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Onde as coisas do add-on estão no disco, e como carregar as bibliotecas embarcadas.

Sem NVDA aqui de propósito: é o módulo que qualquer outro pode importar, inclusive
os testes fora do leitor de tela.
"""

import contextlib
import os
import sys

PLUGIN_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
LIB_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "lib")
BIN_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "bin")
SOUNDS_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "sounds")


@contextlib.contextmanager
def import_bundled(packages_path=LIB_DIRECTORY):
	"""Deixa `import chess` (e as outras bibliotecas de lib/) funcionar dentro do bloco.

	A pasta entra no `sys.path` só enquanto o `with` dura: o módulo importado
	fica em `sys.modules`, então continua acessível depois, mas o caminho não
	polui o resto do NVDA.
	"""
	sys.path.insert(0, packages_path)
	try:
		yield
	finally:
		sys.path.remove(packages_path)
