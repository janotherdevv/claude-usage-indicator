# Spec: Dynamic Icon, Enhanced Menu & Desktop Notifications
**Date:** 2026-03-14
**Project:** claude-usage-indicator
**Features:** Dynamic tray icon (F1), Enhanced right-click menu (F2), Desktop notifications via Gio (F3)

---

## 1. Scope

Three independent enhancements to the existing GTK3 system tray indicator:

- **F1** — Tray icon renders the actual utilization percentage dynamically instead of using three static PNGs.
- **F2** — Right-click context menu gains "Refresh Now" and "Open claude.ai" items.
- **F3** — Desktop notifications fire on tier transitions (green↔amber↔red), using `Gio.Notification` which requires migrating `ClaudeIndicator` to `Gtk.Application`.

Out of scope: usage history, sparklines, configuration files, settings UI.

---

## 2. F1 — Dynamic Tray Icon

### Problem

`generate_icons()` writes three static PNGs at startup representing fixed utilization values (45/80/95%). The tray icon only reflects the tier (green/amber/red), not the precise utilization value.

### Design

**`indicator/icons.py`** — add two functions:

```python
def render_icon(utilization: float, size: int = 22) -> bytes:
    """Renders an arc progress icon and returns PNG bytes."""
    # Reuses existing _render_arc_icon logic

def write_dynamic_icon(utilization: float) -> str:
    """Renders icon at actual utilization, writes to assets/icon_current.png, returns path."""
    ASSETS_DIR.mkdir(exist_ok=True)
    path = ASSETS_DIR / "icon_current.png"
    path.write_bytes(render_icon(utilization))
    return str(path)
```

`generate_icons()` is kept for backwards compatibility but becomes optional at startup. The three static PNGs (icon_ok/warn/crit) can be removed from the generation step.

**`indicator/tray.py`** — `_apply_usage_data()` replaces:
```python
self.status_icon.set_from_file(icon_path_for(max(five_h, seven_d)))
```
with:
```python
self.status_icon.set_from_file(write_dynamic_icon(max(five_h, seven_d)))
```

### Behavior

- Icon updates after every successful fetch with the precise utilization value.
- The arc fill is proportional to `max(five_h, seven_d)` — the more critical of the two windows.
- Color follows existing tier thresholds (green/amber/red) via `arc_color()`.
- **At startup**, before the first fetch completes, call `write_dynamic_icon(0.0)` in `do_activate()` so the tray has a valid file from the start (renders an empty green arc). `generate_icons()` is no longer called from the entry point.

---

## 3. F2 — Enhanced Right-Click Menu

### Problem

The context menu contains only "Quit", missing common tray app expectations: manual refresh and quick access to the service.

### Design

**`indicator/tray.py`** — `_build_menu()` changes to:

```
Refresh Now
Open claude.ai
──────────────
Quit
```

**Refresh Now:**
```python
def _on_refresh_now(self, _):
    self.last_updated = None  # bypass 60s cooldown
    self._start_fetch()
```

**Open claude.ai:**
```python
Gio.AppInfo.launch_default_for_uri("https://claude.ai", None)
```
Uses GLib natively — no subprocess, no extra imports beyond what F3 already brings in.

### Notes

- The separator between "Open claude.ai" and "Quit" uses `Gtk.SeparatorMenuItem`.
- "Refresh Now" is disabled while a fetch is in progress (`_fetching` flag) to prevent double-fetch confusion. The item is re-enabled in `_on_fetch_done`.

---

## 4. F3 — Desktop Notifications

### 4.1 Gtk.Application Migration

`Gio.Notification` requires a `Gtk.Application` instance to call `send_notification()`. `ClaudeIndicator` currently uses bare `Gtk.main()`.

**Minimal migration** — `ClaudeIndicator` becomes:

```python
class ClaudeIndicator(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.claudeusage.indicator")
        # No setup here — moved to do_activate()

    def do_activate(self):
        # IMPORTANT: call self.hold() so the app doesn't quit when no window is
        # active. Gtk.Application tracks active windows; StatusIcon is not a window.
        self.hold()
        # All existing __init__ setup code moves here
        ...

    def run(self):
        super().run(sys.argv)  # Replaces Gtk.main()
```

**`claude_usage_indicator.py`** — entry point stays identical:
```python
app = ClaudeIndicator()
app.run()
```

The `Gtk.Application` base class handles the main loop internally. The Quit menu item callback must call `self.release()` then `self.quit()`, where `self` is the `ClaudeIndicator` instance (not the menu item widget). Use a lambda or a bound method:

```python
item_quit.connect("activate", lambda _: (self.release(), self.quit()))
```

### 4.2 Tier Transition Detection

New instance variable in `do_activate()`:
```python
self._last_notified_tier: int | None = None
```

Logic added to `_on_fetch_done()` after `_apply_usage_data(data)`. `five_h` and `seven_d` are unpacked from `data` the same way `_apply_usage_data` does:

```python
five_h = data.get("five_hour", {}).get("utilization", 0)
seven_d = data.get("seven_day", {}).get("utilization", 0)
current_tier = tier(max(five_h, seven_d))
if self._last_notified_tier is None:
    # First fetch — establish baseline silently
    self._last_notified_tier = current_tier
elif current_tier != self._last_notified_tier:
    self._send_tier_notification(current_tier, five_h, seven_d, data)
    self._last_notified_tier = current_tier
```

### 4.3 Notification Content

```python
def _send_tier_notification(self, new_tier, five_h, seven_d, data):
    notif = Gio.Notification.new("Claude Usage")
    reset_str = _best_reset_time(five_h, seven_d, data)

    if new_tier == 0:
        body = f"Back to normal — {max(five_h, seven_d):.0f}%"
    elif new_tier == 1:
        body = f"High usage — {max(five_h, seven_d):.0f}%  ·  resets {reset_str}"
    else:  # tier 2
        body = f"Critical usage — {max(five_h, seven_d):.0f}%!  ·  resets {reset_str}"

    notif.set_body(body)
    notif.set_priority(
        Gio.NotificationPriority.NORMAL if new_tier <= 1
        else Gio.NotificationPriority.HIGH
    )
    self.send_notification("usage-alert", notif)
```

**`_best_reset_time(five_h, seven_d, data) -> str`** — helper defined in `tray.py`:
```python
def _best_reset_time(five_h, seven_d, data):
    # Returns the reset time of whichever window has higher utilization.
    # If five_h >= seven_d, use five_hour.resets_at; otherwise seven_day.resets_at.
    # Tie-breaking: prefer five_hour (shorter window, more actionable).
    if five_h >= seven_d:
        resets_at = data.get("five_hour", {}).get("resets_at", "")
    else:
        resets_at = data.get("seven_day", {}).get("resets_at", "")
    return format_reset_time(resets_at) if resets_at else "unknown"
```

Notification strings are in English to match the existing codebase (log messages, UI labels in `window.py`).

### 4.4 Debounce Guarantee

- One notification per tier transition direction.
- If tier stays at 2 across multiple polls, no repeated notifications.
- If tier oscillates 1→2→1→2, each transition notifies once.

### 4.5 Import changes

Add to `indicator/tray.py`:
```python
from gi.repository import Gtk, GLib, Gdk, Gio
from .theme import tier
```

`tier` is already imported in `window.py` — just needs to be added to `tray.py`'s imports.

---

## 5. File Change Summary

| File | Change |
|---|---|
| `indicator/icons.py` | Add `render_icon()` and `write_dynamic_icon()` |
| `indicator/tray.py` | Migrate to `Gtk.Application`, dynamic icon, enhanced menu, notifications |
| `claude_usage_indicator.py` | Remove `generate_icons()` call (or keep as no-op) |

No new files. No new dependencies.

---

## 6. Error Handling

- **`write_dynamic_icon` fails**: Catch exception, fall back to `icon_path_for(tier(utilization))` static icon. Log warning.
- **`launch_default_for_uri` fails**: No-op — browser not available is a non-critical failure.
- **`send_notification` fails**: Catch exception, log warning. Notification is best-effort.
- **`Gtk.Application` already running**: `application_id` prevents duplicate instances — second launch raises `Gio.ApplicationFlags` signal and exits cleanly.

---

## 7. Testing Checklist

- [ ] Tray icon arc fills proportionally at different utilization values (10%, 50%, 85%, 100%)
- [ ] Icon color changes at correct thresholds (70% amber, 90% red)
- [ ] "Refresh Now" bypasses cooldown and triggers immediate fetch
- [ ] "Refresh Now" is disabled while fetch is in progress
- [ ] "Open claude.ai" opens the browser
- [ ] No notification on first fetch (baseline establishment)
- [ ] Notification fires on green→amber transition
- [ ] Notification fires on amber→red transition
- [ ] Notification fires on red→green transition (back to normal)
- [ ] No duplicate notifications on same tier across multiple polls
- [ ] App exits cleanly via "Quit" menu item
