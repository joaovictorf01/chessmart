# Não lançado

O versionamento segue o [Semantic Versioning](https://semver.org/lang/pt-BR/): versão de correção (1.1.x) só corrige; versão menor (1.x.0) acrescenta recurso; versão maior muda o que quem já usa depende. O número é decidido na hora de lançar, pelo que esta seção contém.

## Acrescentado

- **NVDA+Alt+X** abre a Tática de qualquer lugar. Os comandos de puzzle aleatório, Finais, Meu estudo e Nova partida estão no diálogo Definir gestos, na categoria Chessmart, sem tecla de fábrica.

## A fazer

- Download de puzzles: aceitar um `.db.gz` baixado à mão no navegador (pra máquina que não alcança o GitHub pelo add-on); registrar o erro exato quando o manifesto não vem. Primeiro relato: 21-09-2026, "não foi possível alcançar o servidor de download".

## Removido

- Restos da remoção do jogo online e outro código que nada usava: uma base de diálogo sem uso e o módulo de terceiros `sized_controls` embarcado só para ela, o parser de controle de tempo com `;` do Lichess, um sinal sem uso, um som sem uso e alguns métodos e flags que nenhum código lia. Nada muda no comportamento.
- Jogo online no lichess.org. Estava "em breve" desde 2022: um cliente pela metade, uma opção desabilitada no menu e 6 MB de bibliotecas de rede embarcadas. Jogar online com leitor de tela é o que o próprio lichess.org faz bem; este add-on é o lado local — jogar contra a engine, tática, finais, PGN. O pacote encolhe na mesma medida.

## Corrigido

- Finais: Control+N num treino abria a tablebase Syzygy de novo para cada posição candidata que testava (até 2000 vezes), uma pausa perceptível com as tabelas de 5 peças instaladas; agora abre uma vez por sorteio.
- Notação IBCA (F3) dizia "schwarts" (preto) para as brancas; agora as brancas são "weiss" e as pretas "schwarz". No fim da partida o motivo é falado no seu idioma ("afogamento", "tripla repetição", "material insuficiente"...) em vez do nome interno em inglês. A contagem do bolso no Crazyhouse e a linha "X contra Y" da lista de partidas PGN também são traduzidas.
- Nova partida: controle de tempo ou FEN inicial inválido não fecha mais o diálogo com erro interno depois da mensagem; o diálogo continua aberto para corrigir o valor.
- Reproduzir arquivo PGN: a lista de partidas mostrava a data no lugar do evento e do local; um arquivo sem a tag `Result`, com resultado fora do padrão ou salvo em Latin-1 não dá mais tom de erro, aparece como "Resultado desconhecido" (ou com um caractere trocado num nome); um arquivo que não pode ser lido é anunciado ("Não foi possível ler o arquivo PGN. Detalhe: ..."). Backspace agora desfaz de verdade o último lance reproduzido, como o README sempre disse, e leva o foco à casa de onde a peça saiu.
- Partida contra a engine: quando a engine desiste, o tabuleiro agora encerra a partida e diz qual lado desistiu; antes falhava em silêncio (erro interno no log do NVDA) e a partida nunca terminava.
- Control+S e Control+Shift+S (salvar a partida em PGN, salvar o tabuleiro como imagem): o diálogo de salvar agora abre na thread principal do NVDA, como o wx exige; abri-lo de uma thread de trabalho podia travar ou derrubar o NVDA.
- Diálogo de download de puzzles: quando a lista não vem, a mensagem traz o erro exato ("Detalhe: ..."), então um relato de "não foi possível alcançar o servidor" já diz se foi rede, proxy ou certificado. A primeira mensagem pede pra aguardar a lista; se a lista não vier, o botão vira **Tentar de novo** em vez de deixar tudo desabilitado.
- README: o submenu fica em menu do NVDA > Ferramentas.

# Chessmart 1.1.0

- **Finais...** no menu. Cinco treinos de mate contra a engine em força total: dama, torre, duas torres (a escada), dois bispos, e bispo e cavalo contra rei nu. A posição do livro abre cada treino; Control+N sorteia outra (dois bispos sempre em cores opostas). Relógio opcional; no fim o tabuleiro conta os lances contra a meta (menos de 10, 20 ou 35) e chama o afogamento pelo nome.
- Rei e peão contra rei também como treino: com as tablebases instaladas, o Control+N sorteia peão de qualquer coluna, inclusive de torre, e só posições que a tablebase diz ganhas. Sem elas, os quatro exemplos conferidos.
- Nove lições de finais na ordem dos cursos de finais (*Complete Endgame Course*, do Silman; *100 Endgames You Must Know*, do De la Villa): o rei e a oposição; rei e peão contra rei (regra do quadrado, rei na frente, peão na sexta); peça contra peão; peões dos dois lados; torre e peão contra torre (Philidor, torre passiva, Lucena); dama contra peão na sétima; bispo e peão de torre; e os finais de torre que decidem partidas (lado curto, Vancura, defesa da última fila, regra dos cinco, torre atrás do peão passado), cada um na versão certa e na errada. Quarenta posições, todas conferidas na tablebase Syzygy antes de entrar. Cada posição pergunta ganha, empata ou perde para o seu lado, diz a regra e depois é jogada até o fim contra a engine; Backspace desfaz um lance, Control+N vai para a próxima posição.
- Tablebases Syzygy (3 a 5 peças, WDL e DTZ) baixadas arquivo por arquivo do espelho do Lichess, conferidas por SHA-256, com download retomável. Com elas instaladas o tabuleiro julga cada lance do jogador no treino ou na lição ("esse lance deixou a vitória escapar"), Control+T diz o resultado teórico e quantos lances até o próximo lance irreversível, Control+Shift+T os lances que mantêm o resultado. Ajuda da tablebase conta como treino, não como resultado mantido.
- Cada tentativa de treino ou lição fica no histórico do jogador (`tactic.db`): resposta, se o resultado foi mantido, lances, tempo e a posição de partida. O diálogo de Finais mostra quantas vezes seguidas cada posição foi mantida; três seguidas sem ajuda deixam a posição firme.
- **Meu estudo...** no menu: quanto e como você estudou, por dia (tática: puzzles, resolvidos, minutos; finais: posições, mantidas, minutos; totais de hoje, 7 ou 30 dias), e até onde vão as lições de finais: quais posições estão firmes, quais pendentes e onde você está. Um texto só, copiável para a área de transferência.
- Tática: Control+N no meio de um puzzle agora pede a segunda pressão e diz qual é o puzzle ("Pressione Control+N duas vezes para pular a tática X"); o id do puzzle pulado também vai para o log do NVDA. Puzzle terminado continua indo direto com uma pressão.
- Tradução para o espanhol (primeira passada, nomes dos temas pela tradução oficial do Lichess; revisão de nativo é bem-vinda). O changelog na loja de add-ons agora também é traduzido.

# Chessmart 1.0.2

- Escape pergunta antes de sair de uma partida em andamento: "Não, continuar jogando" ou "Sim, sair". Antes fechava o tabuleiro na hora, e o tabuleiro fechado deixava a engine rodando, o relógio andando e a partida online aberta no Lichess. Sair agora desliga a engine, desiste (ou aborta, nos dois primeiros lances) da partida online e libera a janela.
- Um puzzle em que você não tocou (sem lance, sem erro, sem dica) não conta mais como derrota ao passar adiante ou sair.
- Partidas online: o tabuleiro não dá mais erro quando a partida começa (chamava um método que a janela nunca teve); o relógio mostrado é o do servidor. Uma oferta de empate do adversário abre o menu aceitar/recusar e a resposta chega ao servidor; uma desistência nomeia o lado certo; um lance que o servidor recusa é anunciado em vez de travar; o fluxo da partida reconecta depois de um erro, como devia.
- Níveis de desafio renomeados para dizer o que são: iniciante, intermediário, avançado, difícil e adaptativo, cada um falado com a sua faixa de rating. Configurações salvas com os nomes antigos continuam valendo.
- Temas de puzzle com nomes e descrições reais ("Mate em um", "Ataque a f2 ou f7", "Mate sufocado") em vez das tags cruas do Lichess quebradas nas maiúsculas; o seletor de temas lê a descrição junto com cada tema.
- Os planos de treino dizem quais motivos cobrem.
- Interno: camada de banco tipada, fonte única para a configuração de treino, testes unitários do acesso ao banco, do rating e das regras do treinador.

# Chessmart 1.0.1

- A base completa de puzzles (cerca de 620 MB) agora é publicada e baixada em partes de 300 MB: o GitHub recusa um único arquivo desse tamanho. Cada parte é conferida ao chegar, uma parte que falha é refeita sozinha, e o arquivo inteiro é conferido no fim. Manifestos antigos sem partes continuam funcionando.
- Testes unitários do download e da notação de lances rodam no CI.

# Chessmart 1.0.0

Primeira versão pública do treinador de táticas construído sobre o Chessmart de Musharraf Omer.

- Base de puzzles do Lichess baixada sob demanda pelo add-on (leve, 76 MB, ou completa, 591 MB), regenerada todo mês a partir da base aberta do Lichess e oferecida como atualização, nunca instalada sozinha.
- Histórico do jogador (tentativas, rating Glicko-2, evolução) guardado em arquivo próprio, intocado pelas atualizações da base.
- Nível de desafio adaptativo que segue o seu rating de táticas; planos de treino por tema; puzzle por id.
- Próximo puzzle sorteado em segundo plano e catálogo de temas montado em segundo plano: o leitor de tela nunca espera.
- Notação de lances configurável nas opções: descritiva, SAN, UCI, por extenso, NATO e anna (os nomes que jogadores cegos usam no tabuleiro).
- Roda no NVDA 2026.1 e posteriores (Python 3.13 de 64 bits) sem nenhum Python instalado na máquina.
- Tradução para o português do Brasil.
