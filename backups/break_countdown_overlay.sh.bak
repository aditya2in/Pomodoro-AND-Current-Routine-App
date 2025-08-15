#!/usr/bin/env bash
# Soft-lock break overlay with ticking countdown (Hyprland)
# Usage:
#   ./break_countdown_overlay.sh [BREAK_DURATION] [GRACE]
# Examples:
#   ./break_countdown_overlay.sh 5m 30s
#   ./break_countdown_overlay.sh 45s 10s
set -euo pipefail

# Optional: --monitor=NAME to target a single monitor (run multiple instances for multi-monitor)
TARGET_MON=""
OPTS=()
for arg in "$@"; do
  case "$arg" in
    --monitor=*) TARGET_MON="${arg#*=}" ;;
    --monitor) shift; TARGET_MON="${1:-}" ;;
    *) OPTS+=("$arg") ;;
  esac
done
set -- "${OPTS[@]}"

parse_duration_to_seconds() {
  local str="$1"
  if [[ "$str" =~ ^[0-9]+$ ]]; then echo "$str"; return 0; fi
  local value unit
  value="${str%[smh]}"
  unit="${str##*[0-9]}"
  case "$unit" in
    s|S) echo "$value" ;;
    m|M) echo $((value * 60)) ;;
    h|H) echo $((value * 3600)) ;;
    *) echo 0 ;;
  esac
}

BREAK_DURATION_STR=${1:-"5m"}
GRACE_STR=${2:-"30s"}
BREAK_DURATION_SEC=$(parse_duration_to_seconds "$BREAK_DURATION_STR")
GRACE_SEC=$(parse_duration_to_seconds "$GRACE_STR")

# Requirements
command -v hyprctl >/dev/null 2>&1 || { echo "Error: hyprctl not found." >&2; exit 1; }

# Resolve Python interpreter (Arch uses 'python')
PYTHON_BIN="$(command -v python3 || true)"
[ -z "$PYTHON_BIN" ] && PYTHON_BIN="$(command -v python || true)"
[ -n "$PYTHON_BIN" ] || { echo "Error: Python missing. Install: sudo pacman -S python" >&2; exit 1; }

"$PYTHON_BIN" - <<'PY' >/dev/null 2>&1 || { echo "Error: Python Tkinter missing. Install: sudo pacman -S tk" >&2; exit 1; }
import sys
try:
    import tkinter  # noqa
except Exception:
    sys.exit(1)
sys.exit(0)
PY

start_ts=$(date +%s)
end_ts=$(( start_ts + BREAK_DURATION_SEC ))
end_hhmm=$(date -d @"$end_ts" +"%H:%M:%S" 2>/dev/null || date -r "$end_ts" +"%H:%M:%S")

# Resolve default beep sound (sounds/beep.wav next to this script)
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
BEEP_SOUND_FILE="${BEEP_SOUND_FILE:-"$SCRIPT_DIR/sounds/beep.wav"}"

# Remove input freezing feature to avoid any interference with fullscreen or focus
FREEZE_INPUT=OFF
freeze_input_devices() { return 0; }
unfreeze_input_devices() { return 0; }

# Remove Hyprland submap feature to avoid interference
set_break_submap() { :; }
reset_break_submap() { :; }
trap 'unfreeze_input_devices' EXIT INT TERM

# If no specific monitor is requested, spawn one instance per monitor and exit.
if command -v jq >/dev/null 2>&1 && [ -z "$TARGET_MON" ]; then
  # No submap or input freezing; keep environment minimal
  # Minimal: no guard timers or submap resets
  children=()
  mon_list=()
  i=0
  for mon in $(hyprctl monitors -j | jq -r '.[].name'); do
    if [ $i -eq 0 ]; then BLEADER=1; else BLEADER=0; fi
    SUBMAP_ALREADY=1 BEEP_LEADER=$BLEADER "$0" --monitor="$mon" "$BREAK_DURATION_STR" "$GRACE_STR" &
    children+=($!)
    mon_list+=("$mon")
    i=$((i+1))
  done
  # Initial ensure tiled+fullscreen for each overlay window (best-effort retries)
  if command -v jq >/dev/null 2>&1; then
    for mon in "${mon_list[@]}"; do
      tries=0
      addr=""
      while [ $tries -lt 20 ]; do
        addr=$(hyprctl clients -j 2>/dev/null | jq -r --arg t "Pomodoro Break - $mon" '.[] | select(.title==$t) | .address' | head -n1)
        [ -n "$addr" ] && [ "$addr" != "null" ] && break
        sleep 0.1
        tries=$((tries+1))
      done
      if [ -n "$addr" ] && [ "$addr" != "null" ]; then
        floating=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .floating // false')
        if [ "$floating" = "true" ]; then
          hyprctl dispatch togglefloating address:$addr >/dev/null 2>&1 || true
        fi
        fs=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .fullscreen // false')
        if [ "$fs" != "true" ]; then
          hyprctl dispatch fullscreen 1,address:$addr >/dev/null 2>&1 || true
        fi
      fi
    done
  fi
  for pid in "${children[@]}"; do wait "$pid"; done
  unfreeze_input_devices
  exit 0
fi

# Grace period
if (( GRACE_SEC > 0 )); then
  echo "Break for $BREAK_DURATION_STR. Overlay in $GRACE_SEC sec (ends $end_hhmm)..."
  sleep "$GRACE_SEC"
fi

# No global workspace switch; we will cover every monitor's current workspace

# Hint Hyprland to start our overlay windows in fullscreen immediately (no flicker)
if command -v hyprctl >/dev/null 2>&1; then
  if [ -n "$TARGET_MON" ]; then
    # Ensure the window is tiled before fullscreening (XWayland/Tk may default to floating)
    hyprctl keyword windowrulev2 "immediate,tile,title:^(Pomodoro Break - $TARGET_MON)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,fullscreen,title:^(Pomodoro Break - $TARGET_MON)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,tile,class:^(PomodoroBreak)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,fullscreen,class:^(PomodoroBreak)$" >/dev/null 2>&1 || true
  else
    hyprctl keyword windowrulev2 "immediate,tile,title:^(Pomodoro Break - .*)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,fullscreen,title:^(Pomodoro Break - .*)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,tile,class:^(PomodoroBreak)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,fullscreen,class:^(PomodoroBreak)$" >/dev/null 2>&1 || true
  fi
fi

# Optional: freeze input devices completely during the break (full blocker)
# Enable by setting FREEZE_INPUT=ON
FREEZE_INPUT=${FREEZE_INPUT:-OFF}
FROZEN_DEVICES_FILE="/tmp/pomodoro_frozen_devices.$$"
FREEZE_GUARD_PID=""
freeze_input_devices() {
  [ "$FREEZE_INPUT" != "ON" ] && return 0
  command -v jq >/dev/null 2>&1 || { echo "Warning: FREEZE_INPUT requires jq; skipping device freeze." >&2; return 0; }
  echo "[overlay] Freezing input devices..." >&2
  # Collect keyboards and mice; extend as needed
  hyprctl devices -j | jq -r '.keyboards[].name, .mice[].name' | awk 'NF' | while IFS= read -r dev; do
    printf '%s\n' "$dev" >> "$FROZEN_DEVICES_FILE"
    hyprctl keyword "device:$dev:enabled" false >/dev/null 2>&1 || true
  done
  # Failsafe: unfreeze after the expected total period even if script dies
  GUARD_SECS=$(( GRACE_SEC + BREAK_DURATION_SEC + 5 ))
  (
    sleep "$GUARD_SECS"
    if [ -f "$FROZEN_DEVICES_FILE" ]; then
      while IFS= read -r dev; do hyprctl keyword "device:$dev:enabled" true >/dev/null 2>&1 || true; done < "$FROZEN_DEVICES_FILE"
      rm -f "$FROZEN_DEVICES_FILE"
    fi
  ) &
  FREEZE_GUARD_PID=$!
}
unfreeze_input_devices() {
  [ -f "$FROZEN_DEVICES_FILE" ] || return 0
  echo "[overlay] Unfreezing input devices..." >&2
  while IFS= read -r dev; do hyprctl keyword "device:$dev:enabled" true >/dev/null 2>&1 || true; done < "$FROZEN_DEVICES_FILE"
  rm -f "$FROZEN_DEVICES_FILE"
  [ -n "${FREEZE_GUARD_PID:-}" ] && kill "$FREEZE_GUARD_PID" >/dev/null 2>&1 || true
}

# Create temporary Python overlay template
OVERLAY_PY=$(mktemp /tmp/pomodoro_break_overlay.XXXXXX.py)
cat >"$OVERLAY_PY" <<'PY'
#!/usr/bin/env python3
import os, time, subprocess, tkinter as tk
end_ts = int(os.environ.get('BREAK_END_TS','0'))
font_family = os.environ.get('OVERLAY_FONT','Noto Sans')
color = os.environ.get('OVERLAY_COLOR','#ECEFF4')
sound_file = os.environ.get('BEEP_SOUND_FILE','')
beep_leader = os.environ.get('BEEP_LEADER','1') == '1'
end_fmt = time.strftime('%H:%M:%S', time.localtime(end_ts))
root = tk.Tk(className='PomodoroBreak')
title = os.environ.get('WINDOW_TITLE','Pomodoro Break')
root.title(title)
try:
    root.wm_class('PomodoroBreak')
except Exception:
    pass
try:
    root.attributes('-fullscreen', True)
except Exception:
    pass
try: root.attributes('-topmost', True)
except Exception: pass
root.configure(bg='#000000')
# Do not force focus or grabs to avoid stealing focus across monitors

# Block inputs inside window
block=lambda *a,**k: 'break'
for seq in ['<Alt-F4>','<Escape>','<Control-q>']:
    root.bind(seq, block)
root.bind_all('<Key>', block)
root.bind_all('<Button>', block)

frame = tk.Frame(root, bg='#000000'); frame.pack(expand=True, fill='both')
label = tk.Label(frame, text='00:00', fg=color, bg='#000000')
try: label.config(font=(font_family, 120, 'bold'))
except Exception: label.config(font=('Noto Sans',120,'bold'))
label.pack(pady=30)
sub = tk.Label(frame, text=f'Break ends at {end_fmt}', fg='#C8C8C8', bg='#000000')
try: sub.config(font=(font_family, 24))
except Exception: sub.config(font=('Noto Sans',24))
sub.pack()
hint = tk.Label(frame, text='Take a break. This screen will close at 00:00.', fg='#B4B4B4', bg='#000000')
try: hint.config(font=(font_family, 16))
except Exception: hint.config(font=('Noto Sans',16))
hint.pack(pady=16)

last_rem = None

def tick():
    now = int(time.time())
    rem = end_ts - now
    if rem < 0: rem = 0
    m, s = divmod(rem, 60)
    label.config(text=f"{m:02d}:{s:02d}")
    global last_rem
    if last_rem is None or rem != last_rem:
        if beep_leader and 0 < rem <= 5 and sound_file:
            try:
                subprocess.Popen(["bash","-lc", f'paplay "{sound_file}" >/dev/null 2>&1 || aplay "{sound_file}" >/dev/null 2>&1'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        last_rem = rem
    if rem == 0:
        root.after(200, root.destroy); return
    root.after(250, tick)
root.after(0, tick)
root.mainloop()
PY

chmod +x "$OVERLAY_PY"

# Function to start an overlay on a specific monitor
spawn_overlay_for_monitor() {
  local mon_name="$1"
  local title="Pomodoro Break - $mon_name"
  # Resolve monitor geometry to help some WMs honor sizing immediately
  local mx="" my="" mw="" mh=""
  if command -v jq >/dev/null 2>&1; then
    local mj=$(hyprctl monitors -j 2>/dev/null || echo '[]')
    mx=$(echo "$mj" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .x // empty')
    my=$(echo "$mj" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .y // empty')
    mw=$(echo "$mj" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .width // empty')
    mh=$(echo "$mj" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .height // empty')
    ms=$(echo "$mj" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .scale // 1')
  fi
  ( BREAK_END_TS="$end_ts" OVERLAY_FONT="${OVERLAY_FONT:-Noto Sans}" OVERLAY_COLOR="${OVERLAY_COLOR:-#ECEFF4}" WINDOW_TITLE="$title" BEEP_SOUND_FILE="$BEEP_SOUND_FILE" BEEP_LEADER="${BEEP_LEADER:-1}" \
    MONITOR_X="$mx" MONITOR_Y="$my" MONITOR_W="$mw" MONITOR_H="$mh" MONITOR_SCALE="$ms" \
    "$PYTHON_BIN" "$OVERLAY_PY" & echo $! )
}

declare -A pids

if [ -n "$TARGET_MON" ]; then
  set_break_submap
  freeze_input_devices || true
  # Failsafe for single-monitor mode
  GUARD_SECS=$(( GRACE_SEC + BREAK_DURATION_SEC + 5 ))
  ( sleep "$GUARD_SECS"; hyprctl dispatch submap reset >/dev/null 2>&1 || true ) &
  GUARD_PID=$!
  if command -v jq >/dev/null 2>&1; then
    monitors_json=$(hyprctl monitors -j)
    sel_mon="$TARGET_MON"
    if ! echo "$monitors_json" | jq -e --arg m "$sel_mon" '.[] | select(.name==$m)' >/dev/null; then
      echo "Error: monitor '$sel_mon' not found. Use: hyprctl monitors -j | jq -r '.[].name'" >&2
      exit 1
    fi
    ws_id=$(echo "$monitors_json" | jq -r --arg m "$sel_mon" '.[] | select(.name==$m) | .activeWorkspace.id')
    hyprctl keyword windowrulev2 "immediate,workspace $ws_id,title:^(Pomodoro Break - $sel_mon)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,workspace $ws_id,class:^(PomodoroBreak)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,tile,title:^(Pomodoro Break - $sel_mon)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "immediate,fullscreen,title:^(Pomodoro Break - $sel_mon)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "noinitialfocus,title:^(Pomodoro Break - $sel_mon)$" >/dev/null 2>&1 || true
    hyprctl keyword windowrulev2 "noinput,title:^(Pomodoro Break - $sel_mon)$" >/dev/null 2>&1 || true
  fi
  pid=$(spawn_overlay_for_monitor "$TARGET_MON")
  pids["$TARGET_MON"]=$pid
  # Initial ensure fullscreen for the overlay window
  if command -v jq >/dev/null 2>&1; then
    sleep 0.3
    addr=$(hyprctl clients -j 2>/dev/null | jq -r --arg t "Pomodoro Break - $TARGET_MON" '.[] | select(.title==$t) | .address' | head -n1)
    if [ -z "$addr" ] || [ "$addr" = "null" ]; then
      addr=$(hyprctl clients -j 2>/dev/null | jq -r '.[] | select(.class=="PomodoroBreak") | .address' | head -n1)
    fi
    if [ -n "$addr" ] && [ "$addr" != "null" ]; then
      # If the window is floating, force it to tiled first, then fullscreen
      hyprctl dispatch focuswindow address:$addr >/dev/null 2>&1 || true
      floating=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .floating // false')
      if [ "$floating" = "true" ]; then
        hyprctl dispatch togglefloating address:$addr >/dev/null 2>&1 || true
      fi
      # Toggle fullscreen like Super+f until Hyprland reports it on
      tries=0
      while [ $tries -lt 15 ]; do
        fs=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .fullscreen // false')
        [ "$fs" = "true" ] && break
        hyprctl dispatch fullscreen address:$addr >/dev/null 2>&1 || true
        sleep 0.1
        tries=$((tries+1))
      done
      : # removed focus enforcement per user request
    fi
  fi
else
  # Fallback if jq is missing and no monitor specified
  pid=$(spawn_overlay_for_monitor "Main")
  pids["Main"]=$pid
fi

# Enforcement loop (minimal to avoid flicker):
# - Keep each monitor on workspace 9
# - If an overlay dies before end, respawn it
(
  while :; do
    now=$(date +%s)
    [ $now -ge $end_ts ] && break
    if [ -n "$TARGET_MON" ]; then
      mons=("$TARGET_MON")
    else
      mons=("${!pids[@]}")
    fi
    for mon in "${mons[@]}"; do
      pid=${pids[$mon]:-}
      if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        newpid=$(spawn_overlay_for_monitor "$mon")
        pids["$mon"]=$newpid
        sleep 0.3
      fi
      if command -v jq >/dev/null 2>&1; then
        addr=$(hyprctl clients -j 2>/dev/null | jq -r --arg t "Pomodoro Break - $mon" '.[] | select(.title==$t) | .address' | head -n1)
        if [ -z "$addr" ] || [ "$addr" = "null" ]; then
          addr=$(hyprctl clients -j 2>/dev/null | jq -r '.[] | select(.class=="PomodoroBreak") | .address' | head -n1)
        fi
        if [ -n "$addr" ] && [ "$addr" != "null" ]; then
          hyprctl dispatch focuswindow address:$addr >/dev/null 2>&1 || true
          floating=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .floating // false')
          if [ "$floating" = "true" ]; then
            hyprctl dispatch togglefloating address:$addr >/dev/null 2>&1 || true
          fi
          tries=0
          while [ $tries -lt 15 ]; do
            fs=$(hyprctl clients -j 2>/dev/null | jq -r --arg a "$addr" '.[] | select(.address==$a) | .fullscreen // false')
            [ "$fs" = "true" ] && break
            hyprctl dispatch fullscreen address:$addr >/dev/null 2>&1 || true
            sleep 0.1
            tries=$((tries+1))
          done
        fi
      fi
    done
    sleep 0.3
  done
) &

# Wait for time expiry (not for processes), then exit; overlays self-close at 00:00
remain=$(( end_ts - $(date +%s) ))
(( remain < 0 )) && remain=0
sleep "$remain" || true

rm -f "$OVERLAY_PY"
exit 0
