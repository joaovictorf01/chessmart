# sqlite3 runtime

O Python embarcado no NVDA (3.13, 64 bits) não traz o módulo `sqlite3`.
Esta pasta contém, sem alteração, os arquivos do CPython 3.13.13 para Windows x64
que faltam:

- `_sqlite3.pyd` e `sqlite3.dll` — do pacote embarcável oficial
  `python-3.13.13-embed-amd64.zip` (python.org)
- `sqlite3/` — o pacote da biblioteca padrão, `Lib/sqlite3/` da tag `v3.13.13`

Licença: PSF License (CPython); SQLite é domínio público.
Ao atualizar o NVDA para outra série do Python (3.14...), estes arquivos precisam
ser trocados pelos da série correspondente — extensões `.pyd` são presas à versão.
