# coding: utf-8
# pyright: basic

"""Finais: treinos de mate, lições com pergunta e regra, e o juiz por tablebase.

`drills` são os mates elementares contra a engine; `tablebase` baixa e abre
as tabelas Syzygy; `judge` traduz a consulta à tabela em veredito falado;
`lessons` é a trilha de ideias (o que empata, o que não empata). Nenhum
destes módulos importa o NVDA: o tabuleiro e os diálogos ficam em
`virtual_chessboard` e `graphical_interface`.
"""
