# Chess Study

* Autor: João Victor, a partir de Chessmart de Musharraf Omer
* Compatibilidad: NVDA 2026.1 o posterior
* Descarga: [versiones de Chess Study en GitHub](https://github.com/joaovictorf01/chessStudy/releases) (y la Tienda de Complementos de NVDA, cuando se publique allí)
* Código fuente: [el repositorio de Chess Study en GitHub](https://github.com/joaovictorf01/chessStudy)
* Licencia: GNU GPL v2

**Chess Study** es un complemento de NVDA que convierte el lector de pantalla en un entorno de ajedrez accesible, todo desde el teclado y todo hablado:

* un entrenador de táctica construido sobre la [base de problemas de Lichess](https://database.lichess.org/#puzzles), con un rating que te acompaña y los problemas que fallaste volviendo para repaso;
* ejercicios de mate y lecciones de finales, juzgados jugada a jugada por las bases de tablas Syzygy;
* un tablero de análisis para registrar, anotar y analizar tus partidas con Stockfish 16: variantes, comentarios, signos, nombres de apertura, una revisión de la partida entera y partidas importadas de Lichess;
* un editor de tablero para preparar cualquier posición;
* partidas contra el motor o contra un amigo en el mismo teclado, en ajedrez estándar y en ocho variantes, y reproducción de PGN;
* Mi estudio, un registro de cuánto y cómo estudiaste.

Empezó como una bifurcación (fork) de [Chessmart de Musharraf Omer](https://github.com/blindpandas/chessmart), que aporta el tablero, los motores y las variantes, y también se llamó Chessmart hasta la versión 1.2.0. Desde la 2.0.0, a petición suya, tiene nombre propio. Ambos se distribuyen bajo la GNU GPL v2.

No hace falta instalar nada más: los motores y el runtime de SQLite que necesita el entrenador vienen dentro del complemento (NVDA 2026.1 ejecuta el Python 3.13 de 64 bits para el que están compilados).

Qué cambió en cada versión: [el registro de cambios de Chess Study](https://github.com/joaovictorf01/chessStudy/blob/main/changelog.md), en inglés.

## Primeros pasos

1. Instala el complemento y reinicia NVDA.
2. Abre el menú de NVDA (NVDA+N), ve a **Herramientas** y busca el submenú **Chess Study**.
3. Elige lo que quieres hacer.

### Si vienes de Chessmart

Si usabas Chessmart 1.x, NVDA ve Chess Study como un complemento distinto y no actualiza uno en el otro. Elimina Chessmart en la Tienda de Complementos, instala Chess Study y reinicia NVDA. La primera vez que se inicia, Chess Study se queda con lo que era de Chessmart: tu rating y tu historial, los problemas fallados que esperan repaso, la base de problemas y las bases de tablas (la carpeta se renombra, no se vuelve a descargar nada) y tus opciones. Tus partidas se quedan en `Documents\Chessmart`, que sigue siendo la carpeta de partidas.

### El menú Chess Study

* **Nueva partida...** — juega contra la computadora o contra un amigo en el mismo teclado (consulta "Jugar una partida").
* **Táctica...** — prepara una sesión de táctica y entrena (consulta "Entrenamiento de táctica").
* **Problema al azar** — empieza al instante una sesión de táctica, con la configuración de entrenamiento guardada como predeterminada, sin el diálogo.
* **Finales...** — los ejercicios de mate y las lecciones de finales (consulta "Finales").
* **Mi estudio...** — cuánto y cómo estudiaste, y hasta dónde llegan las lecciones (consulta "Mi estudio").
* **Reproducir archivo PGN...** — reproduce una partida guardada jugada a jugada (consulta "Reproducir un archivo PGN").
* **Registrar y analizar partida** — introduce una partida jugada a jugada en el tablero de análisis (consulta "Registrar y analizar una partida").
* **Editor de tablero** — prepara una posición casilla a casilla (consulta "Editor de tablero").
* **Importar partida de Lichess...** — descarga una partida de Lichess y la abre en el tablero de análisis (consulta "Importar una partida de Lichess").
* **Analizar archivo PGN...** — abre una partida guardada en el tablero de análisis.
* **Mis partidas...** — las partidas de tu carpeta de partidas (consulta "Mis partidas").
* **Opciones...** — las opciones de Chess Study (consulta "Opciones").

### Atajos

**NVDA+Alt+X** abre Táctica desde cualquier lugar. Problema al azar, Finales, Mi estudio, Mis partidas y Nueva partida también tienen atajos, sin tecla asignada por defecto: asigna una en el diálogo Gestos de Entrada de NVDA (menú Preferencias), categoría Chess Study.

### La base de problemas

La primera vez que abres Táctica o Problema al azar, el complemento ofrece descargar la base de problemas. Elige **Ligera** (unos 90 MB, los problemas que muchos jugadores han resuelto y valorado bien -- alrededor de 880.000) o **Completa** (unos 600 MB, la base entera de Lichess, más de 6 millones). Estas cifras son aproximadas: el diálogo de descarga da las exactas de cada base, el número de problemas, el tamaño a descargar y el tamaño en disco, que crecen un poco cada mes, cuando Lichess publica una base nueva. La descarga se hace en segundo plano, con el progreso hablado; puedes cancelarla con Escape. La base se guarda en la carpeta de configuración de NVDA, en `chessStudy`, junto con tu historial de entrenamiento.

### La barra de Tab

El tablero de problemas, los tableros de finales, el tablero de análisis y el Editor de tablero tienen cada uno una barra de acciones, que se abre con **Tab** desde el tablero. **Tab** cae en su primera acción y **Shift+Tab** en la última. Dentro de la barra, **Tab** y **Flecha derecha** van a la acción siguiente, **Shift+Tab** y **Flecha izquierda** a la anterior, e **Intro** ejecuta la acción enfocada. **Escape**, la acción "Volver al tablero" o pasar de cualquiera de los extremos de la barra devuelven al tablero. Las acciones de cada barra aparecen junto con los comandos de su tablero.

## Entrenamiento de táctica

El diálogo **Táctica** prepara una sesión:

* **Base de táctica** — la base de problemas en uso, con **Examinar...** para indicar una base en otro lugar y **Descargar o actualizar...** (consulta "Mantener la base actualizada").
* **ID del problema** — escribe el id de un problema de Lichess para abrir exactamente ese; el plan de entrenamiento y el nivel se ignoran entonces.
* **Plan de entrenamiento** — qué temas entran en juego: fundamentos (mate, ataque doble, clavada y pincho), ganar material, atacar al rey, motivos mixtos, todos los temas, o tu propia selección de temas de Lichess.
* **Nivel de desafío** — lo difíciles que son los problemas, con el rango de rating hablado en la lista: principiante (hasta 1100), intermedio (de 900 a 1500), avanzado (de 1200 a 1900), difícil (1600 o más), o **adaptativo**, que sigue tu propio rating de táctica.
* **Resumen del entrenador** — un texto de solo lectura que resume el plan y el nivel elegidos.
* **Temas** — los temas en juego. Con tu propia selección como plan de entrenamiento, **Seleccionar temas...** abre la lista de temas de Lichess, cada uno con su descripción y su número de problemas, y **Limpiar temas** vacía la selección.
* **Guardar la configuración de entrenamiento como predeterminada** — conserva esta configuración para la próxima vez, y para Problema al azar.

Cada problema aparece en el tablero con la última jugada del rival ya hecha. Encuentra la jugada, navega hasta la pieza, pulsa Intro, navega hasta la casilla de destino y pulsa Intro otra vez. Los problemas de varias jugadas siguen hasta el final de la solución; las respuestas del rival se anuncian.

**Problema al azar**, en el menú, se salta el diálogo y abre una sesión con la configuración guardada como predeterminada.

### Rating

Cada problema que intentas cuenta como una partida puntuada contra ese problema, con el sistema Glicko-2 (de la misma familia que usa Lichess). Tu rating empieza en 1500, con una incertidumbre grande, y se asienta a medida que juegas. Como en Lichess, la primera jugada equivocada ya cuenta como fallo: resolver el problema después te enseña la solución pero no cambia el rating, y reintentar un problema nunca puntúa.

El rating, los intentos y su historial se guardan en `tactic.db`, en la carpeta de configuración de NVDA. Las actualizaciones de la base nunca tocan ese archivo.

### Repasar los problemas que fallaste

Un problema que fallaste -- una jugada equivocada, una pista, o la solución jugada con Control+Intro -- vuelve al día siguiente. Cuando se abre una sesión de táctica y hay repasos pendientes, van primero: hasta 3, los más antiguos primero, sean cuales sean el plan de entrenamiento y el nivel. Cada uno se anuncia como repaso y nunca puntúa: ya viste la solución una vez, así que un rating por él mediría memoria, no táctica.

Un repaso limpio (todas las jugadas encontradas, ninguna pista) trae el problema una vez más, tres días después. El segundo repaso limpio seguido lo deja firme y sale de la cola. Un repaso con un resbalón vuelve a empezar: regresa al día siguiente.

Control+N o Siguiente problema durante un repaso pregunta si quieres saltar los repasos, con No como opción predeterminada; Sí pasa directamente a problemas nuevos, y los saltados siguen pendientes. Control+F2 cuenta los repasos limpios de la sesión aparte de los problemas nuevos, y Mi estudio muestra la cola.

### Comandos de teclado en el tablero de problemas

| Tecla | Acción |
|---|---|
| Control+N | Siguiente problema (sorteado en segundo plano mientras resuelves el actual). Con un problema en curso, púlsalo dos veces: la primera pulsación dice "Pulsa Control+N dos veces para saltar el ejercicio". Durante un repaso pregunta si quieres saltar los repasos |
| Control+R | Reintentar el problema actual (no puntúa) |
| Control+H | Pista: primero los temas, luego la casilla de origen, luego la de destino |
| Control+Intro (dos veces) | Jugar la jugada esperada |
| Control+F1 | Detalles del problema: el id del problema, el rating, la popularidad, el número de veces jugado, los temas, las etiquetas de apertura y si la partida de origen está disponible en Lichess |
| Control+F2 | Estado de la sesión: resueltos, errores, pistas |
| Control+Shift+R | Tu rating de táctica actual |
| Tab / Shift+Tab | Las acciones de entrenamiento: Repetir instrucción, Objetivo del problema, Pista, Detalles del problema, Estado de la sesión, Reiniciar problema, Siguiente problema, Volver al tablero |
| Escape | Salir del entrenamiento. Pregunta antes; un problema que no has tocado no se cuenta |

Los comandos del tablero de partida (consulta "Comandos de teclado en el tablero") también funcionan en el tablero de problemas, salvo Control+D, que aquí no hace nada, y F2 / Shift+F2, que dicen "Sin control de tiempo".

### Mantener la base actualizada

Lichess publica una base de problemas nueva cada mes. Este proyecto regenera las bases a partir de ella y las publica en la [versión `puzzles-latest`](https://github.com/joaovictorf01/chessStudy/releases/tag/puzzles-latest). En el diálogo Táctica o en las opciones, **Descargar o actualizar...** muestra lo que tienes instalado frente a lo que está publicado y te deja actualizar. Las actualizaciones nunca se instalan automáticamente.

## Finales

**Finales...** es el entrenador de finales. Sigue el orden de los cursos de finales (el *Complete Endgame Course* de Silman, partes 1 a 4, y *100 finales que hay que saber* de De la Villa), y cada posición es teórica: resultado conocido, método conocido, comprobada con las bases de tablas Syzygy.

* **Las lecciones 1a a 1e** son los ejercicios de mate: dama y rey, torre y rey, dos torres (la escalera), dos alfiles, y alfil y caballo, contra el rey solo, jugados contra el motor a plena fuerza. La primera posición es el ejemplo del libro; **Control+N** abre una al azar (los dos alfiles siempre quedan en casillas de distinto color). Se puede poner un reloj opcional para batir marcas; por defecto no hay ninguno. Al final, el tablero dice en cuántas jugadas llegó el mate y si entró en el objetivo (menos de 10 con la dama o con las dos torres, menos de 20 con la torre o con los dos alfiles, menos de 35 con alfil y caballo), y llama al ahogado por su nombre.
* **La lección 3b** es la lección 3 jugada hasta el final: rey y peón contra rey, coronar y dar mate, sin ahogado. Con las bases de tablas instaladas, Control+N pone el peón en cualquier columna, peones de torre incluidos, y solo en una posición ganada. No hay objetivo de jugadas.
* **Las lecciones 2 a 9** son las ideas: el rey y la oposición; rey y peón contra rey (la regla del cuadrado, el rey delante, el peón en sexta); una pieza contra un peón; peones en ambos flancos; torre y peón contra torre (Philidor, la torre pasiva, Lucena); dama contra peón en séptima; alfil y peón de torre; y los finales de torre que deciden partidas (el lado corto, Vancura, la defensa de la última fila, la regla de los cinco, la torre detrás del peón pasado), cada uno con su versión correcta y la equivocada. Cada posición se comprueba con la base de tablas Syzygy antes de incluirla. Cada posición se prepara en el tablero y pregunta **victoria, tablas o derrota** para tu bando. Responde, y el tablero dice si acertaste y enuncia la regla. Después juegas la posición hasta el final contra el motor: gánala, o mantén las tablas. Las posiciones perdidas son solo la pregunta y la regla.

### El diálogo Finales

* **Lección** — las lecciones, en el orden del curso.
* **Posición** — en un ejercicio (1a a 1e, 3b), "Ejemplo del libro" o "Posición al azar"; en una lección, sus posiciones, cada una con cuántas veces seguidas la mantuviste ("(3 seguidas)") o "(aún no mantenida)", una vez que la has intentado.
* **Sobre esta lección** — un texto de solo lectura: qué enseña la lección y su fuente.
* **Reloj para los ejercicios de mate** — minutos+segundos (por ejemplo `5+0`), o vacío para no usar reloj. Solo lo usan los ejercicios (1a a 1e, 3b).
* Las bases de tablas instaladas, y **Descargar tablebases...** (consulta "El juez de las bases de tablas").

### El juez de las bases de tablas

**Descargar tablebases...**, en el diálogo Finales, descarga las tablas Syzygy (de 3 a 5 piezas, WDL y DTZ, 984 MB; o hasta 4 piezas, 4 MB) archivo por archivo desde el espejo de Lichess, comprobando cada uno con SHA-256; una descarga cancelada continúa donde se detuvo. Con las tablas instaladas, en cualquier ejercicio o lección el tablero juzga cada jugada que haces: una jugada que convierte una victoria en tablas, o unas tablas en derrota, se anuncia al instante, y en una lección **Retroceso** la deshace. **Control+T** dice el resultado teórico de la posición y cuántas jugadas faltan hasta la próxima jugada irreversible (jugada de peón, captura o mate); **Control+Shift+T** nombra las jugadas que mantienen el resultado.

Cada intento queda registrado en tu historial (`tactic.db`): la posición inicial y las jugadas, la respuesta, si el resultado se mantuvo sin resbalones, cuántas pistas se pidieron, las jugadas y el tiempo. El diálogo muestra cuántas veces seguidas se mantuvo cada posición; un intento con pistas cuenta como práctica, no como mantenida.

### Comandos de teclado en el tablero de finales

| Tecla | Acción |
|---|---|
| Tab / Shift+Tab | La barra de acciones. En un ejercicio: Repetir objetivo, Veredicto de la tablebase, Mejores jugadas, Nueva posición, Volver al tablero. En una lección: Repetir regla, Veredicto de la tablebase, Mejores jugadas, Deshacer jugada, Reiniciar posición, Siguiente posición, Volver al tablero |
| Control+F1 | Repetir el objetivo (ejercicio) o la regla (lección) |
| Control+N | Otra posición del ejercicio, o la siguiente posición de la lección |
| Control+R | La misma posición de la lección otra vez (solo en las lecciones) |
| Retroceso | Deshacer tu última jugada (lecciones) |
| Control+T | El veredicto de la base de tablas para la posición |
| Control+Shift+T | Las jugadas que mantienen el resultado |
| Escape | Salir. Durante una partida pregunta antes |

Los comandos del tablero de partida (consulta "Comandos de teclado en el tablero") también funcionan aquí, salvo Control+D, que aquí no hace nada, y F2 / Shift+F2, que dicen "Sin control de tiempo", a menos que se haya puesto un reloj a un ejercicio.

## Mi estudio

**Mi estudio...** lee el mismo historial y te dice cuánto y cómo estudiaste: por día, la táctica (problemas, resueltos, minutos), los finales (posiciones, mantenidas, minutos) y los repasos de problemas fallados (cuántos, cuántos limpios), con el total del día, para hoy, los últimos 7 o los últimos 30 días; hasta dónde llegan las lecciones de finales, lección por lección: qué posiciones están firmes (mantenidas tres veces seguidas, con la pregunta bien respondida y el resultado conservado sin un resbalón), cuáles están pendientes y dónde estás; y la cola de repaso: cuántos problemas fallados tocan hoy, cuántos esperan su día y cuántos están firmes. **Copiar al portapapeles** pone todo el texto en el portapapeles. Las partidas no se cuentan aquí a propósito: las partidas de verdad se juegan en otra parte.

## Jugar una partida

**Nueva partida...** abre la configuración de la partida:

* **Modo de juego**: humano contra computadora, o humano contra humano en el mismo teclado.
* **Variante**: Estándar, Ajedrez 960, Antiajedrez, Atómico, Rey de la colina, Carrera de reyes, Horda, Tres jaques y Crazyhouse.
* **Control de tiempo**: Clásica (90+30), Rápida (15+10), Rápida (10+5), Blitz (5+5), Blitz (3+2), Bala (2+2), Bala (1+0), Sin control de tiempo, o Control de tiempo personalizado, escrito en su propio campo (por ejemplo `10+5`).
* **Jugar con**: Al azar, Blancas o Negras, cuando juegas contra la computadora.
* **FEN inicial**: cualquier posición.
* **Opciones del motor...**: fuerza (Elo) y tiempo de reflexión, cuando juegas contra la computadora. El ajedrez estándar usa Stockfish 16 (la compilación oficial de 64 bits); las variantes usan Fairy-Stockfish.
* **Resaltar visualmente las interacciones con el tablero**: dibuja la casilla enfocada en la imagen del tablero, para quien siga la pantalla.

### Reproducir un archivo PGN

**Reproducir archivo PGN...** abre un archivo PGN; cuando el archivo contiene varias partidas, una lista pregunta cuál. Intro juega la siguiente jugada de la partida y Retroceso la deshace, mientras que las flechas te dejan examinar el tablero en cualquier momento. Para añadir variantes y comentarios, abre el archivo con **Analizar archivo PGN...**.

### Comandos de teclado en el tablero

| Tecla | Acción |
|---|---|
| Flechas | Moverse entre casillas; cada casilla anuncia su pieza y su nombre |
| Intro, Intro del teclado numérico o Barra espaciadora | Seleccionar la pieza que se va a mover, y luego la casilla de destino |
| R, N, B, Q, K, P | Saltar a tu siguiente torre, caballo, alfil, dama, rey o peón. Cuando no llevas un bando (humano contra humano, el tablero de análisis) saltan a las piezas del bando que mueve. En el Editor de tablero, en cambio, colocan piezas |
| Shift + letra | Saltar a la siguiente pieza de ese tipo del rival (o, cuando no llevas un bando, del otro bando) |
| A | Qué piezas atacan la casilla enfocada |
| M | Recuento de material de ambos bandos |
| F1 / Shift+F1 | Resumen de tus piezas / de las piezas del rival |
| F2 / Shift+F2 | Tiempo restante en el reloj del bando que mueve / del otro bando |
| F3 | La casilla enfocada y su pieza en notación IBCA |
| F4 | Planilla: las jugadas hechas hasta ahora, como una lista. Flecha arriba y Flecha abajo la recorren; F4 o Escape la cierran |
| F6 / Shift+F6 | Tu reserva / la reserva del rival (Crazyhouse) |
| Control+D | Ofrecer tablas, o retirar la oferta. Humano contra humano: después de la siguiente jugada el otro jugador acepta o rechaza. Contra la computadora: responde en su turno, "La computadora acepta las tablas." o "La computadora rechaza las tablas."; siempre rechaza antes de la jugada 20, y a partir de ahí solo acepta cuando juzga la posición igualada o peor para ella |
| Control+S | Guardar la partida como archivo PGN |
| Control+Shift+S | Guardar el tablero como imagen PNG |
| Escape | Cerrar el tablero. Durante una partida pregunta antes: salir abandona la partida contra el motor |

## Registrar y analizar una partida

**Registrar y analizar partida** abre el tablero de análisis en la posición inicial, donde introduces una partida jugada a jugada, los dos bandos desde el teclado — una partida que jugaste sobre el tablero, siguiéndola en tu juego táctil, o cualquier partida que quieras estudiar. (Para empezar desde un tablero vacío y preparar una posición, usa el "Editor de tablero".) **Analizar archivo PGN...** abre una partida guardada en el mismo tablero, con sus variantes y comentarios.

Nada termina la sesión: un jaque mate dentro de una variante es solo una posición. Donde la línea ya continúa, una jugada distinta abre una **variante**; puedes volver a la línea principal en cualquier momento. Cada jugada puede llevar un **comentario** (lo que estabas pensando, lo que se te escapó) y un **signo**: ! buena jugada, ? error, !! jugada brillante, ?? error grave, !? jugada interesante, ?! jugada dudosa. Los signos se dicen con palabras.

**Control+S** guarda. La primera vez, una partida nueva pide los jugadores, el evento, la fecha y el resultado, y va a tu **carpeta de partidas** (Opciones; por defecto `Documents\Chess Study`) como `año-mes-día_Blancas-vs-Negras.pgn`. A partir de ahí, y para una partida abierta desde un archivo con una sola partida o importada de Lichess, Control+S guarda en ese archivo sin preguntar. **Control+Alt+S** abre los datos (jugadores, evento, fecha, resultado) en cualquier momento, y guarda.

Una vez que la partida tiene archivo, cada cambio -- una jugada, un comentario, un signo, una línea añadida por el motor -- se guarda solo, así que no se pierde nada si cierras el tablero o NVDA. La opción "Guardar las partidas analizadas automáticamente, cuando ya tengan archivo" lo desactiva; entonces Control+S guarda y Escape pregunta antes de salir dejando cambios sin guardar.

### Mis partidas

**Mis partidas...** muestra todas las partidas de tu carpeta de partidas, las modificadas más recientemente primero: la fecha, los jugadores, el resultado y cuánto las has anotado ("Comentarios: 12, signos: 4, variantes: 2", o "Sin anotaciones"). Intro abre la partida en el tablero de análisis, donde se sigue guardando en su propio archivo. Un archivo con varias partidas muestra cada una de ellas; una partida abierta desde un archivo así se guarda como un archivo nuevo. El atajo no tiene tecla asignada por defecto: asigna una en el diálogo Gestos de Entrada de NVDA (menú Preferencias), categoría Chess Study.

### Revisión de la partida

**F7** en el tablero de análisis (o Tab, "Revisar la partida") revisa la partida entera: el motor evalúa cada posición de la línea principal (alrededor de un segundo cada una; F7 otra vez lo detiene; el progreso sigue la opción "Salida en las Barras de Progreso" de NVDA, en la categoría Presentación de Objetos, que por defecto pita), juzga cada jugada con las reglas de Lichess y dice la precisión de cada jugador, calculada como la calcula Lichess ("Tu precisión 96 por ciento, rival 87."), y luego los momentos críticos: "3 momentos críticos: jugada 14, error; jugada 22, imprecisión; jugada 31, error grave." **Alt+AvPág** y **Alt+RePág** van de uno a otro. Cada uno se abre en la posición anterior a la jugada, para buscar allí la jugada mejor: juega una candidata y Shift+E la juzga.

El grupo "Revisión de la partida (F7 en el tablero de análisis)" de las Opciones, u "Opciones de la revisión..." en la barra de Tab del tablero de análisis, deciden cuánto dice el motor: de quién son las jugadas (solo las tuyas, el bando de abajo del tablero, o ambos); qué cuenta (solo errores graves; errores y errores graves; todo); cuántos momentos como máximo (3, 5, 10 o todos, quedándose con los peores); qué revela el motor (por defecto, solo dónde falló la jugada; o también su jugada; o su jugada y su línea como variante); el tiempo por posición; y si se salta la teoría de aperturas. El repaso marca una jugada crítica con su veredicto solo cuando dejaste la jugada sin signo: tus propios signos nunca se cambian.

### Importar una partida de Lichess

**Importar partida de Lichess...** ofrece el enlace de Lichess que haya en el portapapeles, si hay uno (en el navegador, Control+L y luego Control+C lo copian), y si no, pide un enlace de partida, un código de partida o un nombre de usuario de Lichess (la última partida de ese jugador; el nombre se recuerda para la próxima vez). La partida se guarda en la carpeta de partidas como `año-mes-día_Blancas-vs-Negras_código-de-lichess.pgn` y se abre en el tablero de análisis, desde el lado de las negras cuando el usuario recordado jugó con negras. Importar otra vez la misma partida abre tu copia guardada, con tus anotaciones, en lugar de descargarla encima. Las evaluaciones propias de Lichess se dejan fuera: el motor te responde, no habla primero.

Cada jugada lleva su reloj: al recorrer la partida se dice el tiempo que quedaba y el tiempo que tardó la jugada ("reloj 0:48, tardó 0:12, menos de un minuto"). **T** resume el reloj de ambos bandos: desde qué jugada un jugador tuvo menos de un minuto, el reloj más bajo, la reflexión más larga.

### Análisis con el motor

El motor es Stockfish 16. Una evaluación se dice como la dicen los jugadores: "ligera ventaja de las blancas, más 0,4" (un peón vale 1,0). Shift+E juzga una jugada como lo hace Lichess: la evaluación se convierte en una probabilidad de ganar de 0 a 100, y la jugada es una imprecisión cuando regala 5 puntos de ella, un error con 10, un error grave con 15. Por eso perder un peón en una posición igualada es una imprecisión, mientras que perder uno con una torre de ventaja no es nada. El signo sugerido es solo una sugerencia: el signo sigue siendo tuyo.

Los nombres de apertura vienen de Lichess ([lichess-org/chess-openings](https://github.com/lichess-org/chess-openings), dominio público) y se buscan por posición, así que también se reconoce una transposición. Una jugada que llega a una nueva apertura con nombre dice su nombre, la primera jugada fuera de la tabla dice "fuera de la teoría", Shift+E sobre una jugada de teoría lo dice en lugar de preguntar al motor, y al guardar se escriben las etiquetas ECO y Opening.

Tus propias variantes no tienen límite: calcula hasta poder decir cómo está la posición, y detente ahí. La línea del motor añadida con Control+E se detiene en 8 medias jugadas, suficiente para ver la idea.

### Comandos de teclado en el tablero de análisis

Los comandos del tablero de partida también funcionan aquí (flechas, Intro, A, M, F1, F4...), con tres diferencias: las letras de las piezas saltan a las piezas del bando que mueve, Control+D no hace nada, y F2 / Shift+F2 dicen "Sin control de tiempo". Además de ellos:

| Tecla | Acción |
|---|---|
| Alt+Flecha izquierda / Alt+Flecha derecha | Retroceder / avanzar una jugada en la línea actual |
| Alt+Inicio / Alt+Fin | Inicio de la partida / final de la línea actual |
| Alt+Flecha arriba | Salir de la variante: vuelve a la posición donde se separó |
| Alt+Flecha abajo | Las jugadas registradas desde esta posición: la continuación y sus variantes |
| Retroceso | Deshacer la última jugada de una línea, para corregir una jugada introducida por error |
| C / Shift+C | Escribir / leer el comentario de la jugada actual |
| Control+1 a Control+6 | Marcar la jugada: ! ? !! ?? !? ?! |
| Control+0 | Quitar el signo |
| Control+P | Convertir la variante actual en la línea principal |
| Control+S | Guardar la partida en la carpeta de partidas (una partida nueva pide sus datos la primera vez) |
| Control+Alt+S | Editar los jugadores, el evento, la fecha y el resultado, y guardar |
| E | Con cinco piezas o menos y las bases de tablas instaladas (Finales, Descargar tablebases): el resultado exacto y las jugadas que lo mantienen, en lugar del motor. Si no, la evaluación del motor, una frase para cada cosa: quién está mejor y por cuánto, la mejor jugada, su línea (tres jugadas) y otras dos candidatas. El nombre del motor y la profundidad no se dicen; Control+E los escribe en la partida. Púlsala dos veces para que el motor piense 8 segundos en lugar de 2 |
| X | La amenaza, como en Lichess: lo que jugaría el otro bando si le tocara mover, con la evaluación y la línea. No funciona en jaque (la amenaza ya está en el tablero) |
| Shift+E | Juzgar la jugada que llevó hasta aquí frente a la mejor del motor: la jugada del motor, buena, imprecisión, error o error grave, y el signo que eso sugiere |
| Control+E | Después de E, añadir la línea del motor (hasta 8 medias jugadas) como variante, con la evaluación como comentario |
| F7 | Revisar la partida entera; F7 otra vez lo detiene |
| Alt+Avance página / Alt+Retroceso página | Momento crítico siguiente / anterior de la revisión |
| T | El reloj de la partida, de ambos bandos (partidas importadas) |
| O | La apertura en la que está la línea, con su código ECO, y si la posición todavía es teoría |
| Tab / Shift+Tab | Todas estas acciones como una barra, cada una con su tecla: para cuando se olvida una tecla. La barra también tiene Opciones de la revisión..., Marcar la jugada, Jugar desde aquí contra la computadora..., Girar el tablero y Volver al tablero |
| Escape | Cerrar el tablero; si algo cambió desde la última vez que guardaste, pregunta antes |

"Jugar desde aquí contra la computadora...", en la barra de Tab, abre el diálogo Nueva partida con esta posición como inicio y con el bando que mueve como el tuyo: elige allí la fuerza del motor y el reloj.

## Editor de tablero

**Editor de tablero** abre un tablero vacío para preparar cualquier posición casilla a casilla. Las letras de las piezas colocan piezas, como en FEN: **Shift+K, Q, R, B, N, P** para un rey, dama, torre, alfil, caballo o peón blanco, y la letra sola para uno negro. **Suprimir** o **Retroceso** vacían la casilla; **Intro** dice qué hay en ella. **Control+C** copia la posición como FEN, **Control+V** toma una del portapapeles. Las flechas, F1, F3, A, M y F4 funcionan como en el tablero de partida.

**Tab** abre las acciones del editor: cambiar a quién le toca mover; cambiar cada derecho de enroque (un derecho solo existe mientras su rey y su torre están en sus casillas iniciales); verificar la posición, que dice con palabras qué está mal ("No hay rey negro.", "Hay un peón en la primera o en la octava fila.", "El bando que no mueve está en jaque.") o que es válida; analizar esta posición en el tablero de análisis; copiar como FEN (Control+C); pegar un FEN (Control+V); la posición inicial; vaciar el tablero; girarlo; volver al tablero. "Analizar esta posición" la abre en el tablero de análisis, donde "Jugar desde aquí contra la computadora...", en la barra de Tab, empieza una partida a partir de ella.

**Escape** cierra el editor; cuando hay piezas en el tablero pregunta antes, ya que la posición se perdería (Control+C la copia antes de salir).

## Opciones

**Opciones...**, en el menú Chess Study, abre el diálogo de opciones de Chess Study:

* **Base de táctica**, con **Examinar...** para indicar una base en otro lugar y **Descargar o actualizar...**.
* **Plan de entrenamiento predeterminado**, **Nivel de desafío predeterminado**, el resumen del entrenador y **Temas predeterminados**, para las nuevas sesiones de táctica y para Problema al azar.
* **Notación de jugadas**: cómo se dicen las jugadas y las casillas.
* **Carpeta de partidas**: dónde guarda las partidas el tablero de análisis, con **Examinar carpeta...**.
* **Guardar las partidas analizadas automáticamente, cuando ya tengan archivo**: activada por defecto (consulta "Registrar y analizar una partida").
* **Revisión de la partida (F7 en el tablero de análisis)**: las opciones de la revisión (consulta "Revisión de la partida").

### Notación de jugadas

Los mismos estilos que el modo para ciegos de Lichess, más el estilo descriptivo que Chess Study siempre tuvo:

| Estilo | Ejemplo |
|---|---|
| Descriptiva | caballo blanco de g1 a f3 |
| SAN | Cf3 |
| UCI | g1f3 |
| Literal | caballo f 3 |
| OTAN | caballo foxtrot 3 |
| Anna | caballo felix 3 |

Anna es la notación que usan los jugadores ciegos ante el tablero (anna, bella, cesar, david, eva, felix, gustav, hector). En los estilos OTAN y Anna, las casillas también se dicen así cuando te mueves por el tablero. Solo cambia la voz: las jugadas siempre se hacen en el tablero, nunca se escriben.

## Traducciones

La interfaz está en inglés, portugués de Brasil y español (una primera versión; se agradece la revisión de hablantes nativos). Este manual también tiene versiones en portugués de Brasil y en español, que el botón Ayuda de NVDA abre cuando NVDA está en esos idiomas. Las traducciones están en `addon/locale/<idioma>/LC_MESSAGES/nvda.po`, con la estructura estándar de los complementos de NVDA, y son bienvenidas: para empezar una nueva, ejecuta `py -3 tools/i18n.py update <idioma>` y rellena las líneas `msgstr`, o pide que el complemento se añada al proyecto de complementos de NVDA en Crowdin. Los nombres de casillas OTAN y Anna y la notación IBCA son internacionales y no se traducen.

Para compilar el complemento o cambiar su código, lee [la guía de contribución de Chess Study](https://github.com/joaovictorf01/chessStudy/blob/main/CONTRIBUTING.md), en inglés.

## Créditos

* [Musharraf Omer](https://github.com/mush42) — el Chessmart original: tablero, motores, variantes, reproducción de PGN.
* [Lichess](https://lichess.org) — la base de problemas (CC0), los nombres de apertura, la fórmula de precisión, el espejo de las bases de tablas Syzygy y los estilos de notación de su modo para ciegos.
* [Stockfish](https://stockfishchess.org) y [Fairy-Stockfish](https://fairy-stockfish.github.io) — los motores.
* [python-chess](https://python-chess.readthedocs.io) — la biblioteca de ajedrez.
* João Victor — el entrenador de táctica y las herramientas de su base, el repaso de los problemas fallados, los ejercicios y las lecciones de finales, el juez de las bases de tablas, Mi estudio, el tablero de análisis, el análisis con el motor, los nombres de apertura, la revisión de la partida, la importación de Lichess, el Editor de tablero, Mis partidas, la notación de jugadas, la actualización a Stockfish 16 y al python-chess actual, la limpieza del antiguo código de juego en línea, y la traducción al portugués.
