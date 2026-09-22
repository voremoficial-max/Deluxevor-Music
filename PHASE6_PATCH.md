# Fase 6 — correcciones adicionales

## Cambios

- La vista grande usa un `Gtk.ScrolledWindow` y una carátula de 250x250 para evitar que su contenido quede oculto en pantallas de poca altura.
- El visualizador aumentó su sensibilidad a `4.15` y usa una curva de respuesta `0.48`.
- El reproductor inferior tiene un botón para abrir la vista grande.
- La reproducción automática de la siguiente canción ya no fuerza la apertura de la vista grande. La música continúa mientras el usuario permanece en la búsqueda, artistas, historial, álbumes, etc.
- La navegación lateral conserva la página actual cuando se minimiza la vista grande.
- La vista grande sigue ocultando el reproductor inferior y al minimizarlo vuelve a mostrarlo.

## Pruebas

- `python3 -m compileall -q .`
- `PYTHONPATH=. pytest -q` → 8 passed
