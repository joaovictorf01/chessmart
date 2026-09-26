# Chess Study

* Autor: João Victor, a partir do Chessmart de Musharraf Omer
* Compatibilidade: NVDA 2026.1 ou posterior
* Download: [versões do Chess Study no GitHub](https://github.com/joaovictorf01/chessStudy/releases) (e a Loja de Complementos do NVDA, quando for publicado lá)
* Código-fonte: [o repositório do Chess Study no GitHub](https://github.com/joaovictorf01/chessStudy)
* Licença: GNU GPL v2

O **Chess Study** é um add-on do NVDA que transforma o leitor de tela num ambiente de xadrez acessível, todo pelo teclado e todo falado:

* um treinador de táticas construído sobre a [base de puzzles do Lichess](https://database.lichess.org/#puzzles), com um rating que acompanha você, e os puzzles que você errou voltam para revisão;
* treinos de mate e lições de finais, julgados lance a lance pelas tablebases Syzygy;
* um tabuleiro de análise para gravar, anotar e analisar as suas partidas com o Stockfish 16: variantes, comentários, marcas, nomes de abertura, uma revisão da partida inteira e partidas importadas do Lichess;
* um editor de tabuleiro para montar qualquer posição;
* partidas contra o motor ou contra um amigo no mesmo teclado, no xadrez padrão e em oito variantes, e reprodução de PGN;
* o Meu estudo, um registro de quanto e como você estudou.

Ele começou como um fork do [Chessmart de Musharraf Omer](https://github.com/blindpandas/chessmart), que fornece o tabuleiro, os motores e as variantes, e também se chamava Chessmart até a versão 1.2.0. Desde a 2.0.0, a pedido dele, tem nome próprio. Os dois são distribuídos sob a GNU GPL v2.

Não é preciso instalar mais nada: os motores e o runtime do SQLite de que o treinador precisa vêm dentro do add-on (o NVDA 2026.1 roda o Python 3.13 de 64 bits para o qual eles foram compilados).

O que mudou em cada versão: [o changelog do Chess Study](https://github.com/joaovictorf01/chessStudy/blob/main/changelog.pt_BR.md).

## Primeiros passos

1. Instale o add-on e reinicie o NVDA.
2. Abra o menu do NVDA (NVDA+N), vá até **Ferramentas** e encontre o submenu **Chess Study**.
3. Escolha o que você quer fazer.

### Vindo do Chessmart

Se você usava o Chessmart 1.x, o NVDA vê o Chess Study como outro add-on e não atualiza um no outro. Remova o Chessmart na Loja de Complementos, instale o Chess Study e reinicie o NVDA. Na primeira vez que abre, o Chess Study assume o que era do Chessmart: o seu rating e histórico, os puzzles errados esperando revisão, a base de puzzles e as tablebases (a pasta é renomeada, nada é baixado de novo) e as suas configurações. As suas partidas continuam em `Documents\Chessmart`, que segue sendo a pasta de partidas.

### O menu Chess Study

* **Nova partida...** — jogue contra o computador ou contra um amigo no mesmo teclado (veja "Jogar uma partida").
* **Táticas...** — monte uma sessão de táticas e treine (veja "Treino de táticas").
* **Puzzle aleatório** — começa na hora uma sessão de táticas, com a configuração de treino salva como padrão, sem o diálogo.
* **Finais...** — os treinos de mate e as lições de finais (veja "Finais").
* **Meu estudo...** — quanto e como você estudou, e até onde vão as lições (veja "Meu estudo").
* **Reproduzir arquivo PGN...** — reproduz uma partida salva, lance a lance (veja "Reproduzir um arquivo PGN").
* **Gravar e analisar partida** — registre uma partida lance a lance no tabuleiro de análise (veja "Gravar e analisar uma partida").
* **Editor de tabuleiro** — monte uma posição casa a casa (veja "Editor de tabuleiro").
* **Importar partida do Lichess...** — baixa uma partida do Lichess e abre no tabuleiro de análise (veja "Importar uma partida do Lichess").
* **Analisar arquivo PGN...** — abre uma partida salva no tabuleiro de análise.
* **Minhas partidas...** — as partidas da sua pasta de partidas (veja "Minhas partidas").
* **Configurações...** — as configurações do Chess Study (veja "Configurações").

### Atalhos

**NVDA+Alt+X** abre as Táticas de qualquer lugar. Puzzle aleatório, Finais, Meu estudo, Minhas partidas e Nova partida também têm atalhos, sem tecla de fábrica: atribua uma no diálogo Definir comandos do NVDA (menu Preferências), na categoria Chess Study.

### A base de puzzles

Na primeira vez que você abre as Táticas ou o Puzzle aleatório, o add-on oferece baixar a base de puzzles. Escolha a **Leve** (cerca de 90 MB, os puzzles que muitos jogadores já resolveram e aprovaram -- perto de 880.000) ou a **Completa** (cerca de 600 MB, a base inteira do Lichess, mais de 6 milhões). Esses números são aproximados: o diálogo de download dá os exatos de cada base, a quantidade de puzzles, o tamanho para baixar e o tamanho no disco, que crescem um pouco todo mês, quando o Lichess publica uma base nova. O download roda em segundo plano, com o progresso falado; você pode cancelar com Escape. A base fica guardada na pasta de configuração do NVDA, em `chessStudy`, junto com o seu histórico de treino.

### A barra do Tab

O tabuleiro de puzzle, os tabuleiros de finais, o tabuleiro de análise e o Editor de tabuleiro têm cada um uma barra de ações, aberta com **Tab** a partir do tabuleiro. O **Tab** cai na primeira ação e o **Shift+Tab** na última. Dentro da barra, **Tab** e **Seta direita** vão para a próxima ação, **Shift+Tab** e **Seta esquerda** para a anterior, e **Enter** executa a ação em foco. **Escape**, a ação "Voltar ao tabuleiro" ou passar de qualquer uma das pontas da barra volta ao tabuleiro. As ações de cada barra estão listadas junto com os comandos do seu tabuleiro.

## Treino de táticas

O diálogo **Táticas** monta uma sessão:

* **Base de táticas** — a base de puzzles em uso, com **Procurar...** para apontar uma base em outro lugar e **Baixar ou atualizar...** (veja "Manter a base atualizada").
* **ID do puzzle** — digite o id de um puzzle do Lichess para abrir exatamente esse; o plano de treino e o nível são então ignorados.
* **Plano de treino** — quais temas entram em jogo: fundamentos (mate, garfo, cravada e espeto), ganhar material, ataque ao rei, motivos variados, todos os temas, ou a sua própria seleção de temas do Lichess.
* **Nível de desafio** — o quão difíceis são os puzzles, com a faixa de rating falada na lista: iniciante (até 1100), intermediário (900 a 1500), avançado (1200 a 1900), difícil (1600 ou mais), ou **adaptativo**, que acompanha o seu próprio rating de táticas.
* **Resumo do treino** — um texto só de leitura que resume o plano e o nível escolhidos.
* **Temas** — os temas em jogo. Com a sua própria seleção como plano de treino, **Selecionar temas...** abre a lista de temas do Lichess, cada um com a sua descrição e o número de puzzles, e **Limpar temas** esvazia a seleção.
* **Salvar esta configuração de treino como padrão** — guarda esta configuração para a próxima vez, e para o Puzzle aleatório.

Cada puzzle aparece no tabuleiro com o último lance do adversário já jogado. Encontre o lance, navegue até a peça, pressione Enter, navegue até a casa de destino e pressione Enter de novo. Puzzles de vários lances continuam até o fim da solução; as respostas do adversário são anunciadas.

O **Puzzle aleatório** no menu pula o diálogo e abre uma sessão com a configuração salva como padrão.

### Rating

Cada puzzle que você tenta conta como uma partida valendo rating contra aquele puzzle, pelo sistema Glicko-2 (da mesma família que o Lichess usa). O seu rating começa em 1500, com uma incerteza grande, e se acomoda conforme você joga. Como no Lichess, o primeiro lance errado já conta como falha: resolver o puzzle depois ensina a solução, mas não muda o rating, e tentar um puzzle de novo nunca vale rating.

O rating, as tentativas e o histórico delas ficam em `tactic.db`, na pasta de configuração do NVDA. As atualizações da base nunca tocam nesse arquivo.

### Revisão dos puzzles que você errou

Um puzzle que você errou -- um lance errado, uma dica, ou a solução jogada com Control+Enter -- volta no dia seguinte. Quando uma sessão de táticas abre e há revisões para hoje, elas vêm primeiro: até 3, as mais antigas primeiro, seja qual for o plano de treino e o nível. Cada uma é anunciada como revisão e nunca vale rating: você já viu a solução uma vez, então um rating por ela mediria memória, não tática.

Uma revisão limpa (todos os lances encontrados, nenhuma dica) traz o puzzle de volta mais uma vez, três dias depois. A segunda revisão limpa seguida o deixa firme, e ele sai da fila. Uma revisão com um deslize recomeça: volta no dia seguinte.

Control+N ou Próximo puzzle durante uma revisão pergunta se você quer pular as revisões, com Não como padrão; Sim vai direto para puzzles novos, e os pulados continuam pendentes. O Control+F2 conta as revisões limpas da sessão separadas dos puzzles novos, e o Meu estudo mostra a fila.

### Comandos de teclado no tabuleiro de puzzle

| Tecla | Ação |
|---|---|
| Control+N | Próximo puzzle (sorteado em segundo plano enquanto você resolve o atual). Com um puzzle em andamento, pressione duas vezes: a primeira pressão diz "Pressione Control+N duas vezes para pular a tática". Durante uma revisão, pergunta se você quer pular as revisões |
| Control+R | Tentar de novo o puzzle atual (não vale rating) |
| Control+H | Dica: primeiro os temas, depois a casa de origem, depois a de destino |
| Control+Enter (duas vezes) | Jogar o lance esperado |
| Control+F1 | Detalhes do puzzle: o id do puzzle, rating, popularidade, número de jogadas, temas, tags de abertura, e se a partida de origem está disponível no Lichess |
| Control+F2 | Estado da sessão: resolvidos, erros, dicas |
| Control+Shift+R | O seu rating de táticas atual |
| Tab / Shift+Tab | As ações de treino: Repetir a instrução, Objetivo do puzzle, Dica, Detalhes do puzzle, Estado da sessão, Reiniciar o puzzle, Próximo puzzle, Voltar ao tabuleiro |
| Escape | Sair do treino. Pergunta antes; um puzzle em que você não mexeu não é contado |

Os comandos do tabuleiro de partida (veja "Comandos de teclado no tabuleiro") também funcionam no tabuleiro de puzzle, menos o Control+D, que aqui não faz nada, e o F2 / Shift+F2, que dizem "Sem controle de tempo".

### Manter a base atualizada

O Lichess publica uma base de puzzles nova todo mês. Este projeto regenera as bases a partir dela e as publica na [release `puzzles-latest`](https://github.com/joaovictorf01/chessStudy/releases/tag/puzzles-latest). No diálogo Táticas ou nas configurações, **Baixar ou atualizar...** mostra o que você tem instalado em comparação com o que está publicado e deixa você atualizar. As atualizações nunca são instaladas automaticamente.

## Finais

**Finais...** é o treinador de finais. Ele segue a ordem dos cursos de finais (o *Complete Endgame Course*, do Silman, Partes 1 a 4, e o *100 Endgames You Must Know*, do De la Villa), e toda posição é teórica: resultado conhecido, método conhecido, conferida nas tablebases Syzygy.

* **As lições 1a a 1e** são os treinos de mate: dama e rei, torre e rei, duas torres (a escada), dois bispos, e bispo e cavalo, contra o rei nu, jogados contra o motor em força total. A primeira posição é o exemplo do livro; **Control+N** abre uma sorteada (os dois bispos sempre caem em cores opostas). Dá para definir um relógio opcional, para bater recordes; por padrão não há nenhum. No fim, o tabuleiro diz em quantos lances saiu o mate e se ficou dentro da meta (menos de 10 com a dama ou com as duas torres, menos de 20 com a torre ou com os dois bispos, menos de 35 com bispo e cavalo), e chama o afogamento pelo nome.
* **A lição 3b** é a lição 3 jogada até o fim: rei e peão contra rei, promover e dar mate, sem afogar. Com as tablebases instaladas, o Control+N põe o peão em qualquer coluna, peão de torre incluído, e só em posição ganha. Não há meta de lances.
* **As lições 2 a 9** são as ideias: o rei e a oposição; rei e peão contra rei (regra do quadrado, rei na frente, peão na sexta); uma peça contra um peão; peões dos dois lados; torre e peão contra torre (Philidor, a torre passiva, Lucena); dama contra peão na sétima; bispo e peão de torre; e os finais de torre que decidem partidas (o lado curto, Vancura, a defesa da última fileira, a regra dos cinco, a torre atrás do peão passado), cada um na versão certa e na errada. Toda posição é conferida na tablebase Syzygy antes de entrar. Cada posição é montada no tabuleiro e pergunta **ganha, empata ou perde** para o seu lado. Responda, e o tabuleiro diz se você acertou e fala a regra. Depois você joga a posição até o fim contra o motor: ganhe, ou segure o empate. As posições perdidas são só a pergunta e a regra.

### O diálogo Finais

* **Lição** — as lições, na ordem do curso.
* **Posição** — num treino (1a a 1e, 3b), "Exemplo do livro" ou "Posição sorteada"; numa lição, as posições dela, cada uma com quantas vezes seguidas você a manteve ("(3 seguidas)") ou "(ainda não mantida)", depois que você já tentou.
* **Sobre esta lição** — um texto só de leitura: o que a lição ensina e a fonte.
* **Relógio dos treinos de mate** — minutos+segundos (por exemplo `5+0`), ou vazio para ficar sem relógio. Só os treinos (1a a 1e, 3b) usam.
* As tablebases instaladas, e **Baixar tablebases...** (veja "O juiz das tablebases").

### O juiz das tablebases

**Baixar tablebases...**, no diálogo Finais, busca as tabelas Syzygy (3 a 5 peças, WDL e DTZ, 984 MB; ou até 4 peças, 4 MB) arquivo por arquivo do espelho do Lichess, conferindo cada um por SHA-256; um download cancelado continua de onde parou. Com as tabelas instaladas, em qualquer treino ou lição o tabuleiro julga cada lance que você faz: um lance que transforma uma vitória em empate, ou um empate em derrota, é anunciado na hora, e numa lição o **Backspace** desfaz esse lance. O **Control+T** diz o resultado teórico da posição e quantos lances faltam até o próximo lance irreversível (lance de peão, captura ou mate); o **Control+Shift+T** diz quais lances mantêm o resultado.

Cada tentativa fica registrada no seu histórico (`tactic.db`): a posição de partida e os lances, a resposta, se o resultado foi mantido sem deslize, quantas dicas foram pedidas, lances e tempo. O diálogo mostra quantas vezes seguidas cada posição foi mantida; uma tentativa com dicas conta como treino, não como mantida.

### Comandos de teclado no tabuleiro de finais

| Tecla | Ação |
|---|---|
| Tab / Shift+Tab | A barra de ações. Num treino: Repetir meta, Veredito da tablebase, Melhores lances, Nova posição, Voltar ao tabuleiro. Numa lição: Repetir regra, Veredito da tablebase, Melhores lances, Desfazer lance, Recomeçar posição, Próxima posição, Voltar ao tabuleiro |
| Control+F1 | Repetir a meta (treino) ou a regra (lição) |
| Control+N | Outra posição do treino, ou a próxima posição da lição |
| Control+R | A mesma posição da lição de novo (só nas lições) |
| Backspace | Desfazer o seu último lance (lições) |
| Control+T | O veredito da tablebase para a posição |
| Control+Shift+T | Os lances que mantêm o resultado |
| Escape | Sair. Durante uma partida, pergunta antes |

Os comandos do tabuleiro de partida (veja "Comandos de teclado no tabuleiro") também funcionam aqui, menos o Control+D, que aqui não faz nada, e o F2 / Shift+F2, que dizem "Sem controle de tempo", a não ser que um treino tenha recebido um relógio.

## Meu estudo

**Meu estudo...** lê o mesmo histórico e diz quanto e como você estudou: por dia, as táticas (puzzles, resolvidos, minutos), os finais (posições, mantidas, minutos) e as revisões dos puzzles errados (quantas, quantas limpas), com o total do dia, para hoje, os últimos 7 ou os últimos 30 dias; e até onde vão as lições de finais, lição por lição: quais posições estão firmes (mantidas três vezes seguidas, pergunta certa e resultado mantido sem deslize), quais estão pendentes e onde você está; e a fila de revisão: quantos puzzles errados estão para hoje, quantos esperam o seu dia e quantos estão firmes. **Copiar para a área de transferência** põe o texto inteiro na área de transferência. As partidas ficam de fora de propósito: partidas de verdade são jogadas em outro lugar.

## Jogar uma partida

**Nova partida...** abre a configuração da partida:

* **Modo de jogo**: humano contra computador, ou humano contra humano no mesmo teclado.
* **Variante**: Padrão, Xadrez 960, Antixadrez, Atômico, Rei da colina, Corrida de reis, Horda, Três xeques e Crazyhouse.
* **Controle de tempo**: Clássica (90+30), Rápida (15+10), Rápida (10+5), Blitz (5+5), Blitz (3+2), Bullet (2+2), Bullet (1+0), Sem controle de tempo, ou Controle de tempo personalizado, digitado num campo próprio (por exemplo `10+5`).
* **Jogar de**: Aleatória, Brancas ou Pretas, quando você joga contra o computador.
* **FEN inicial**: qualquer posição.
* **Opções do motor...**: força (Elo) e tempo de reflexão, quando você joga contra o computador. O xadrez padrão usa o Stockfish 16 (a versão oficial de 64 bits); as variantes usam o Fairy-Stockfish.
* **Destacar visualmente as interações no tabuleiro**: desenha a casa em foco na imagem do tabuleiro, para quem acompanha pela tela.

### Reproduzir um arquivo PGN

**Reproduzir arquivo PGN...** abre um arquivo PGN; quando o arquivo tem várias partidas, uma lista pergunta qual. O Enter joga o próximo lance da partida e o Backspace desfaz, enquanto as setas deixam você examinar o tabuleiro em qualquer ponto. Para acrescentar variantes e comentários, abra o arquivo com **Analisar arquivo PGN...**.

### Comandos de teclado no tabuleiro

| Tecla | Ação |
|---|---|
| Setas | Andar pelas casas; cada casa anuncia a peça e o nome |
| Enter, Enter do teclado numérico ou Espaço | Selecionar a peça a mover, depois a casa de destino |
| R, N, B, Q, K, P | Ir para a sua próxima torre, cavalo, bispo, dama, rei ou peão. Quando você não é dono de um lado (humano contra humano, tabuleiro de análise), vão para as peças do lado que tem a vez. No Editor de tabuleiro, elas colocam peças |
| Shift + letra | Ir para a próxima peça daquele tipo do adversário (ou, quando você não é dono de um lado, do outro lado) |
| A | Quais peças atacam a casa em foco |
| M | Contagem de material dos dois lados |
| F1 / Shift+F1 | Resumo das suas peças / das peças do adversário |
| F2 / Shift+F2 | Tempo restante no relógio do lado que tem a vez / do outro lado |
| F3 | A casa em foco e a peça, em notação IBCA |
| F4 | Planilha de lances: os lances jogados até agora, como uma lista. Seta acima e Seta abaixo percorrem; F4 ou Escape fecha |
| F6 / Shift+F6 | A sua reserva / a reserva do adversário (Crazyhouse) |
| Control+D | Oferecer empate, ou retirar a oferta. Humano contra humano: depois do próximo lance o outro jogador aceita ou recusa. Contra o computador: ele responde na vez dele, "O computador aceita o empate." ou "O computador recusa o empate."; antes do lance 20 sempre recusa, e depois só aceita quando avalia a posição como igual ou pior para ele |
| Control+S | Salvar a partida como arquivo PGN |
| Control+Shift+S | Salvar o tabuleiro como imagem PNG |
| Escape | Fechar o tabuleiro. Durante uma partida, pergunta antes: sair abandona a partida contra o motor |

## Gravar e analisar uma partida

**Gravar e analisar partida** abre o tabuleiro de análise na posição inicial, onde você registra uma partida lance a lance, os dois lados pelo teclado — uma partida que você jogou no tabuleiro físico, acompanhando no seu jogo tátil, ou qualquer partida que você queira estudar. (Para começar de um tabuleiro vazio e montar uma posição, use o "Editor de tabuleiro".) **Analisar arquivo PGN...** abre uma partida salva no mesmo tabuleiro, com variantes e comentários.

Nada encerra a sessão: um xeque-mate dentro de uma variante é só uma posição. Onde a linha já continua, um lance diferente abre uma **variante**; você pode voltar à linha principal a qualquer momento. Cada lance pode levar um **comentário** (o que você estava pensando, o que deixou passar) e uma **marca**: ! bom lance, ? erro, !! lance brilhante, ?? erro grave, !? lance interessante, ?! lance duvidoso. As marcas são faladas em palavras.

**Control+S** salva. Na primeira vez, uma partida nova pede os jogadores, o evento, a data e o resultado, e vai para a sua **pasta de partidas** (Configurações; por padrão `Documents\Chess Study`) como `ano-mês-dia_Brancas-vs-Pretas.pgn`. Depois disso, e para uma partida aberta de um arquivo com uma partida só ou importada do Lichess, o Control+S salva nesse arquivo sem perguntar. **Control+Alt+S** abre os detalhes (jogadores, evento, data, resultado) a qualquer momento, e salva.

Quando a partida já tem arquivo, cada mudança -- um lance, um comentário, uma marca, uma linha acrescentada pelo motor -- é salva sozinha, então nada se perde se você fechar o tabuleiro ou o NVDA. A configuração "Salvar partidas analisadas automaticamente, depois que tiverem arquivo" desliga isso; aí o Control+S salva, e o Escape pergunta antes de sair deixando mudanças sem salvar.

### Minhas partidas

**Minhas partidas...** lista todas as partidas da sua pasta de partidas, as alteradas mais recentemente primeiro: a data, os jogadores, o resultado e quanto você já anotou ("Comentários: 12, marcas: 4, variantes: 2", ou "Sem anotações"). O Enter abre a partida no tabuleiro de análise, onde ela continua sendo salva no próprio arquivo. Um arquivo com várias partidas mostra cada uma delas; uma partida aberta de um arquivo assim é salva como um arquivo novo. O atalho não tem tecla de fábrica: atribua uma no diálogo Definir comandos do NVDA (menu Preferências), na categoria Chess Study.

### Revisão da partida

**F7** no tabuleiro de análise (ou Tab, "Revisar a partida") revisa a partida inteira: o motor avalia cada posição da linha principal (cerca de um segundo cada; F7 de novo interrompe; o progresso segue a configuração "Barras de progresso" do NVDA, em Apresentação de objetos, com bipes por padrão), julga cada lance pelas regras do Lichess e diz a precisão de cada jogador, calculada como o Lichess calcula ("Sua precisão 96 por cento, adversário 87."), depois os momentos críticos: "3 momentos críticos: lance 14, erro; lance 22, imprecisão; lance 31, erro grave." **Alt+Page Down** e **Alt+Page Up** vão de um para o outro. Cada um abre na posição antes do lance, para que o lance melhor seja procurado ali: jogue um candidato e o Shift+E avalia.

O grupo "Revisão da partida (F7 no tabuleiro de análise)" nas Configurações, ou "Opções da revisão..." na barra do Tab do tabuleiro de análise, decidem o quanto o motor diz: de quem são os lances (só os seus, o lado de baixo do tabuleiro, ou os dois); o que conta (só erros graves; erros e erros graves; tudo); quantos momentos no máximo (3, 5, 10 ou todos, ficando com os piores); o que o motor revela (por padrão, só onde o lance deu errado; ou também o lance dele; ou o lance dele e a linha dele como variante); o tempo por posição; e se a teoria de abertura é pulada. A revisão marca um lance crítico com o veredito só quando você deixou o lance sem marca: as suas marcas nunca são alteradas.

### Importar uma partida do Lichess

**Importar partida do Lichess...** oferece o link do Lichess que estiver na área de transferência, se houver um (no navegador, Control+L e depois Control+C copiam o link), e senão pede um link de partida, um código de partida ou um usuário do Lichess (a última partida desse jogador; o nome fica lembrado para a próxima vez). A partida é salva na pasta de partidas como `ano-mês-dia_Brancas-vs-Pretas_código-do-lichess.pgn` e abre no tabuleiro de análise, visto do lado das pretas quando o usuário lembrado jogou de pretas. Importar de novo a mesma partida abre a sua cópia salva, com as suas anotações, em vez de baixar por cima dela. As avaliações do próprio Lichess ficam de fora: o motor responde a você, ele não fala primeiro.

Cada lance leva o seu relógio: andar pela partida diz o tempo que restava e o tempo que o lance levou ("relógio 0:48, levou 0:12, menos de um minuto"). O **T** resume o relógio dos dois lados: a partir de qual lance um jogador ficou com menos de um minuto, o menor relógio, o maior tempo gasto num lance.

### Análise com o motor

O motor é o Stockfish 16. Uma avaliação é dita como os jogadores dizem: "brancas um pouco melhores, mais 0,4" (um peão vale 1,0). O Shift+E julga um lance como o Lichess julga: a avaliação vira uma chance de vitória de 0 a 100, e o lance é uma imprecisão quando entrega 5 pontos dela, um erro com 10, um erro grave com 15. Por isso perder um peão numa posição igual é uma imprecisão, enquanto perder um com uma torre a mais não é nada. A marca sugerida é só uma sugestão: a marca continua sendo sua.

Os nomes de abertura vêm do Lichess ([lichess-org/chess-openings](https://github.com/lichess-org/chess-openings), domínio público), buscados pela posição, então uma transposição também é reconhecida. Um lance que chega a uma nova abertura com nome diz o nome, o primeiro lance fora da tabela diz "fora da teoria", o Shift+E num lance de teoria diz isso em vez de perguntar ao motor, e salvar grava as tags ECO e Opening.

As suas próprias variantes não têm limite: calcule até conseguir dizer como a posição está, e pare ali. A linha do motor acrescentada com Control+E para em 8 meios-lances, o bastante para ver a ideia.

### Comandos de teclado no tabuleiro de análise

Os comandos do tabuleiro de partida também funcionam aqui (setas, Enter, A, M, F1, F4...), com três diferenças: as letras das peças vão para as peças do lado que tem a vez, o Control+D não faz nada, e o F2 / Shift+F2 dizem "Sem controle de tempo". Além deles:

| Tecla | Ação |
|---|---|
| Alt+Seta esquerda / Alt+Seta direita | Voltar / avançar um lance na linha atual |
| Alt+Home / Alt+End | Início da partida / fim da linha atual |
| Alt+Seta acima | Sair da variante: volta para a posição de onde ela se separou |
| Alt+Seta abaixo | Os lances registrados a partir desta posição: a continuação e as variantes dela |
| Backspace | Desfazer o último lance de uma linha, para corrigir um lance registrado por engano |
| C / Shift+C | Escrever / ler o comentário do lance atual |
| Control+1 a Control+6 | Marcar o lance: ! ? !! ?? !? ?! |
| Control+0 | Tirar a marca |
| Control+P | Tornar a variante atual a linha principal |
| Control+S | Salvar a partida na pasta de partidas (uma partida nova pede os detalhes na primeira vez) |
| Control+Alt+S | Editar jogadores, evento, data e resultado, e salvar |
| E | Com cinco peças ou menos e as tablebases instaladas (Finais, Baixar tablebases): o resultado exato e os lances que o mantêm, em vez do motor. Senão, a avaliação do motor, uma frase para cada coisa: quem está melhor e por quanto, o melhor lance, a linha dele (três lances) e dois outros candidatos. O nome do motor e a profundidade ficam fora da fala; o Control+E grava os dois na partida. Pressione duas vezes para o motor pensar 8 segundos em vez de 2 |
| X | A ameaça, como no Lichess: o que o outro lado jogaria se fosse a vez dele, com a avaliação e a linha. Não funciona em xeque (a ameaça já está no tabuleiro) |
| Shift+E | Avaliar o lance que levou até aqui contra o melhor lance do motor: o lance do motor, bom, imprecisão, erro ou erro grave, e a marca que isso sugere |
| Control+E | Depois do E, acrescentar a linha do motor (até 8 meios-lances) como variante, com a avaliação como comentário |
| F7 | Revisar a partida inteira; F7 de novo interrompe |
| Alt+Page Down / Alt+Page Up | Próximo / anterior momento crítico da revisão |
| T | O relógio da partida, dos dois lados (partidas importadas) |
| O | A abertura em que a linha está, com o código ECO, e se a posição ainda é teoria |
| Tab / Shift+Tab | Todas essas ações como uma barra, cada uma com a sua tecla: para quando você esquecer uma tecla. A barra também tem Opções da revisão..., Marcar o lance, Jogar daqui contra o computador..., Virar o tabuleiro e Voltar ao tabuleiro |
| Escape | Fechar o tabuleiro; se algo mudou desde a última vez que você salvou, pergunta antes |

"Jogar daqui contra o computador...", na barra do Tab, abre o diálogo Nova partida com esta posição como início e o lado que tem a vez como o seu: escolha ali a força do motor e o relógio.

## Editor de tabuleiro

O **Editor de tabuleiro** abre um tabuleiro vazio para montar qualquer posição casa a casa. As letras das peças colocam peças, como no FEN: **Shift+K, Q, R, B, N, P** para rei, dama, torre, bispo, cavalo ou peão brancos, a letra sozinha para uma peça preta. **Delete** ou **Backspace** esvaziam a casa; **Enter** diz o que há nela. **Control+C** copia a posição como FEN, **Control+V** pega uma da área de transferência. As setas, F1, F3, A, M e F4 funcionam como no tabuleiro de partida.

O **Tab** abre as ações do editor: trocar de quem é a vez; trocar cada direito de roque (um direito só existe enquanto o rei e a torre dele estão nas casas iniciais); verificar a posição, que diz em palavras o que está errado ("Não há rei preto.", "Há um peão na primeira ou na oitava fileira.", "O lado que não está na vez está em xeque.") ou que ela é válida; analisar esta posição no tabuleiro de análise; copiar como FEN (Control+C); colar um FEN (Control+V); a posição inicial; limpar o tabuleiro; virar o tabuleiro; voltar ao tabuleiro. "Analisar esta posição" abre a posição no tabuleiro de análise, onde "Jogar daqui contra o computador...", na barra do Tab, começa uma partida a partir dela.

O **Escape** fecha o editor; quando há peças no tabuleiro, ele pergunta antes, já que a posição se perderia (o Control+C copia a posição antes de você sair).

## Configurações

**Configurações...**, no menu Chess Study, abre o diálogo de configurações do Chess Study:

* **Base de táticas**, com **Procurar...** para apontar uma base em outro lugar e **Baixar ou atualizar...**.
* **Plano de treino padrão**, **Nível de desafio padrão**, o resumo do treino e **Temas padrão**, para as novas sessões de táticas e para o Puzzle aleatório.
* **Notação dos lances**: como os lances e as casas são falados.
* **Pasta de partidas**: onde o tabuleiro de análise salva as partidas, com **Procurar pasta...**.
* **Salvar partidas analisadas automaticamente, depois que tiverem arquivo**: ligada por padrão (veja "Gravar e analisar uma partida").
* **Revisão da partida (F7 no tabuleiro de análise)**: as opções da revisão (veja "Revisão da partida").

### Notação dos lances

Os mesmos estilos do modo para cegos do Lichess, mais o estilo descritivo que o Chess Study sempre teve:

| Estilo | Exemplo |
|---|---|
| Descritiva | cavalo das brancas de g1 para f3 |
| SAN | Cf3 |
| UCI | g1f3 |
| Por extenso | cavalo f 3 |
| OTAN | cavalo foxtrot 3 |
| Anna | cavalo felix 3 |

Anna é a notação que os jogadores cegos usam no tabuleiro (anna, bella, cesar, david, eva, felix, gustav, hector). Nos estilos OTAN e Anna, as casas também são faladas assim quando você anda pelo tabuleiro. Só a fala muda: os lances são sempre feitos no tabuleiro, nunca digitados.

## Traduções

A interface está em inglês, português do Brasil e espanhol (uma primeira versão; revisão por falantes nativos é bem-vinda). Este manual também tem uma versão em português do Brasil, que o botão Ajuda do NVDA abre quando o NVDA está em português. As traduções ficam em `addon/locale/<idioma>/LC_MESSAGES/nvda.po`, na estrutura padrão de add-ons do NVDA, e são bem-vindas: para começar uma nova, rode `py -3 tools/i18n.py update <idioma>` e preencha as linhas `msgstr`, ou peça para o add-on entrar no projeto de add-ons do NVDA no Crowdin. Os nomes das casas OTAN e Anna e a notação IBCA são internacionais e não são traduzidos.

Para compilar o add-on ou mexer no código, leia [o guia de contribuição do Chess Study](https://github.com/joaovictorf01/chessStudy/blob/main/CONTRIBUTING.md), em inglês.

## Créditos

* [Musharraf Omer](https://github.com/mush42) — o Chessmart original: tabuleiro, motores, variantes, reprodução de PGN.
* [Lichess](https://lichess.org) — a base de puzzles (CC0), os nomes de abertura, a fórmula de precisão, o espelho das tablebases Syzygy e os estilos de notação do modo para cegos.
* [Stockfish](https://stockfishchess.org) e [Fairy-Stockfish](https://fairy-stockfish.github.io) — os motores.
* [python-chess](https://python-chess.readthedocs.io) — a biblioteca de xadrez.
* João Victor — o treinador de táticas e as ferramentas da base dele, a revisão dos puzzles errados, os treinos e as lições de finais, o juiz das tablebases, o Meu estudo, o tabuleiro de análise, a análise com o motor, os nomes de abertura, a revisão da partida, a importação do Lichess, o Editor de tabuleiro, o Minhas partidas, a notação dos lances, a atualização para o Stockfish 16 e para o python-chess atual, a limpeza do código antigo de jogo online, e a tradução para o português.
