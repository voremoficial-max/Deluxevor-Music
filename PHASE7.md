# Vorem Music - Fase 7

## Visualizador
- 29 barras independientes. Se eliminaron las 11 barras finales que no recibían respuesta útil.
- Las 29 barras se distribuyen sobre las 32 bandas que entrega GStreamer.
- Sensibilidad ajustada a 1.48 con curva 1.65 para responder a la música sin quedarse arriba.
- Suavizado de ataque y caída.
- Intensidad configurable desde Ajustes.
- Se detiene cuando el visualizador está desactivado o la reproducción está pausada.

## Reproductor grande
- Al reproducir una canción se abre el reproductor grande.
- El menú lateral permanece visible.
- El menú lateral se oculta únicamente al pulsar el botón de pantalla completa del reproductor grande.
- El botón de pantalla completa cambia a restaurar al entrar en pantalla completa.
- Al salir de pantalla completa reaparece el menú lateral.
- Minimizar el reproductor grande vuelve a la página anterior.

## Ajustes funcionales
- Carpetas de música: acceso directo a Biblioteca.
- Reproducción continua.
- Shuffle.
- Repetición desactivada, lista o canción.
- Volumen inicial persistente.
- Visualizador activado/desactivado.
- Intensidad del visualizador.
- Animaciones activadas/desactivadas.
- Tema Sistema, Oscuro o Claro.
- Página inicial Canciones, Biblioteca o Última página.
- Los valores se guardan en SQLite.

## Extras
- Atajos de teclado para reproducción, siguiente y anterior.
- Notificación de escritorio al cambiar de canción.
- Las opciones de Ajustes afectan al reproductor sin reiniciar la aplicación.
