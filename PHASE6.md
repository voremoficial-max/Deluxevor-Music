# Vorem Music — Fase 6

## Cambios
- Corrección del seek del reproductor inferior: el control vuelve a permitir adelantar y retroceder con el mouse.
- El nombre largo se reinicia automáticamente cada 5 segundos dentro de su propio espacio.
- Vista grande de reproducción con carátula, título, artista, visualizador y controles.
- Botón para volver a la lista.
- Pantalla completa.
- Fondo dinámico basado en el color medio de la carátula.
- Transiciones suaves entre páginas.
- La vista grande se actualiza al cambiar de canción.
- El visualizador y la barra de progreso se mantienen sincronizados con GStreamer.

## Dependencias
Se añadió Pillow para obtener de forma ligera el color dominante aproximado de las carátulas embebidas.
