# Claude Usage Indicator — Flujo del Código

## Visión general

La app tiene tres capas bien separadas que se comunican entre sí:

```
┌─────────────────────────────────────────────┐
│              CAPA DE PRESENTACIÓN            │
│  ClaudeIndicator (tray)  +  UsageWindow      │
├─────────────────────────────────────────────┤
│              CAPA DE DATOS                   │
│  read_token()  +  fetch_usage()              │
├─────────────────────────────────────────────┤
│              CAPA DE ICONOS                  │
│  _generate_icons()  +  _render_arc_icon()    │
└─────────────────────────────────────────────┘
```

---

## Arranque

```
main
 ├── _generate_icons()
 │    └── Para cada estado (ok/warn/crit):
 │         └── _render_arc_icon(45/80/95%) → PNG en disco
 │
 └── ClaudeIndicator()
      ├── Crea Gtk.StatusIcon (icono en tray)
      ├── Conecta señales: clic izquierdo → _on_left_click
      │                    clic derecho  → _on_right_click
      ├── _start_fetch()          ← primer fetch inmediato
      ├── GLib.timeout (30 min)   ← polling periódico
      └── Gtk.main()              ← bucle de eventos GTK
```

---

## Flujo de fetch (petición a la API)

El fetch siempre es asíncrono — nunca bloquea la UI.

```
_start_fetch()
 ├── [Guard] ¿Ya hay un fetch en curso?  → salir
 ├── [Guard] ¿Datos con menos de 60s?    → salir
 ├── Marca _fetching = True
 └── Lanza threading.Thread(do_fetch)
      │
      │  [hilo background — fuera del hilo GTK]
      ├── read_token()
      │    ├── Lee ~/.claude/.credentials.json
      │    ├── Verifica que el token no ha expirado
      │    └── Devuelve (token, None) o (None, error)
      │
      ├── [Si hay error de token] → GLib.idle_add(_on_fetch_done, None, error)
      │
      └── fetch_usage(token)
           ├── GET https://api.anthropic.com/api/oauth/usage
           ├── Headers: Authorization Bearer + anthropic-beta
           └── Devuelve (data, None) o (None, error)
                └── GLib.idle_add(_on_fetch_done, data, error)
```

> `GLib.idle_add` es crucial: devuelve la ejecución al hilo principal de GTK
> antes de tocar cualquier elemento de la UI.

---

## Procesado del resultado (_on_fetch_done)

```
_on_fetch_done(data, error)
 ├── Marca _fetching = False
 │
 ├── ¿Sin error?
 │    └── _apply_usage_data(data)
 │         ├── Guarda usage_data + last_updated
 │         ├── Actualiza icono del tray (verde/ámbar/rojo)
 │         └── Actualiza tooltip con los porcentajes
 │
 ├── ¿Error 429 (rate limit)?
 │    └── Ignora silenciosamente — mantiene último estado conocido
 │
 └── ¿Otro error?
      └── Guarda en last_error

 └── [Si el popup está visible]
      └── popup_window.update(usage_data, error, updated_at)
```

---

## Color semántico — fuente única de verdad

`_tier(utilization)` decide el color para TODA la app:

```
utilization < 70%   → tier 0 → Verde  #26A269
utilization 70-89%  → tier 1 → Ámbar  #E5A50A
utilization ≥ 90%   → tier 2 → Rojo   #C01C28
```

Este tier se usa en tres sitios:
- `icon_path_for()` → qué PNG cargar en el tray
- `_arc_color()` → color del arco al generar los PNG con Cairo
- `_bar_css()` → CSS inyectado en las barras del popup

---

## Clic izquierdo → popup

```
_on_left_click()
 ├── Destruye popup anterior (libera recursos GTK)
 ├── Crea UsageWindow()
 │    ├── Ventana GTK sin decoración
 │    ├── Dos secciones: Session (5h) y Week (7d)
 │    ├── Cada sección: label grande % + barra coloreada + hora de reset
 │    ├── Label timestamp abajo ("Fetching..." inicial)
 │    └── Inicia animación pulse en las barras
 │
 ├── GLib.idle_add(_position_popup)
 │    └── Posiciona la ventana junto al icono del tray
 │         ├── Obtiene posición del icono con get_geometry()
 │         └── Coloca el popup arriba o abajo según mitad de pantalla
 │
 └── ¿Datos recientes (< 60s)?
      ├── Sí → popup_window.update() con datos en caché (sin fetch)
      └── No → _start_fetch() → cuando termine, _on_fetch_done actualiza popup
```

---

## Ciclo de vida del popup (UsageWindow)

```
Estado inicial:          barras pulsando, "Fetching..."
                              ↓
Datos recibidos:         barras se detienen y muestran valor real
                         timestamp: "Updated just now" o "Updated HH:MM"
                              ↓
Usuario mueve el foco:   ventana se oculta automáticamente (focus-out-event)
                              ↓
Siguiente clic:          ventana anterior destruida, nueva creada desde cero
```

---

## Polling en background

```
GLib.timeout_add_seconds(1800)
 └── Cada 30 minutos llama a _poll_and_reschedule()
      └── _start_fetch()
           └── Si el popup está abierto cuando llegue el resultado:
                └── _on_fetch_done actualiza el popup en vivo
```

---

## Generación de iconos con Cairo

```
_render_arc_icon(utilization, size=22)
 ├── Crea surface ARGB32 de 22×22 px
 ├── Dibuja track base: arco completo 270° en blanco 25% opacidad
 │    └── Desde las 7 en punto (225°) hasta las 5 en punto (135°)
 └── Dibuja fill: arco proporcional al % en color semántico
      └── fraction = utilization / 100 → ángulo = fraction × 270°
```

Tres PNG se generan al arrancar con valores representativos:
- `icon_ok.png`   → render al 45%  (verde)
- `icon_warn.png` → render al 80%  (ámbar)
- `icon_crit.png` → render al 95%  (rojo)

---

## Manejo de errores

| Error | Comportamiento |
|---|---|
| Archivo credentials no encontrado | Popup muestra mensaje de error |
| Token expirado | Popup muestra "Token expired" |
| HTTP 429 (rate limit) | Silencioso — muestra último dato o `–` |
| Error de red | Popup muestra el error |
| Error HTTP otro | Popup muestra código y mensaje |
