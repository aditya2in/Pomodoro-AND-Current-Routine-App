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

# If this is the main call, spawn an instance for each monitor.
if [ -z "$TARGET_MON" ]; then
    # Check for hyprctl and jq before proceeding
    command -v hyprctl >/dev/null 2>&1 || { echo "Error: hyprctl not found." >&2; exit 1; }
    command -v jq >/dev/null 2>&1 || { echo "Error: jq not found. Please install it." >&2; exit 1; }

    monitors_json=$(hyprctl monitors -j)
    if [ -z "$monitors_json" ]; then
        echo "Error: Could not detect any monitors from hyprctl." >&2
        exit 1
    fi

    pids=()
    for mon_name in $(echo "$monitors_json" | jq -r '.[].name'); do
        "$0" --monitor="$mon_name" "$@" &
        pids+=($!)
    done

    # Give windows time to be created
    sleep 0.5

    for mon_name in $(echo "$monitors_json" | jq -r '.[].name'); do
        workspace_id=$(echo "$monitors_json" | jq -r --arg m "$mon_name" '.[] | select(.name==$m) | .activeWorkspace.id')
        addr=$(hyprctl clients -j | jq -r --arg t "Pomodoro Break - $mon_name" '.[] | select(.title==$t) | .address' | head -n1)

        if [ -n "$addr" ] && [ "$addr" != "null" ]; then
            hyprctl dispatch movetoworkspacesilent "$workspace_id,address:$addr" >/dev/null 2>&1
            
            # Force fullscreen with a retry loop
            tries=0
            while [ $tries -lt 10 ]; do
                fs=$(hyprctl clients -j | jq -r --arg a "$addr" '.[] | select(.address==$a) | .fullscreen // false')
                if [ "$fs" = "true" ]; then
                    break
                fi
                hyprctl dispatch fullscreen 1,address:$addr >/dev/null 2>&1
                sleep 0.1
                tries=$((tries+1))
            done
        fi
    done

    for pid in "${pids[@]}"; do
        wait "$pid"
    done
    exit 0
fi

# The rest of the script is for a single monitor instance
BREAK_DURATION_STR=${1:-30s}
GRACE_STR=${2:-3s}

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
BREAK_DURATION_SEC=$(parse_duration_to_seconds "$BREAK_DURATION_STR")
GRACE_SEC=$(parse_duration_to_seconds "$GRACE_STR")

PYTHON_BIN="$(command -v python3 || command -v python)"
[ -n "$PYTHON_BIN" ] || { echo "Error: Python not found." >&2; exit 1; }

# Create temporary Python overlay template
OVERLAY_PY=$(mktemp /tmp/simple_overlay.XXXXXX.py)
cat >"$OVERLAY_PY" <<'PY'
import os
import time
import tkinter as tk

# Use environment variables passed from the shell script
duration_sec = int(os.environ.get('BREAK_DURATION_SEC', 300))
window_title = os.environ.get('WINDOW_TITLE', 'Break')
end_ts = int(time.time()) + duration_sec

root = tk.Tk()
root.title(window_title)
root.attributes('-fullscreen', True)
root.attributes('-topmost', True)
root.configure(bg='black')

# Center the labels
frame = tk.Frame(root, bg='black')
frame.pack(expand=True)

# Countdown Label
label = tk.Label(frame, text="", fg='white', bg='black', font=('Noto Sans', 120, 'bold'))
label.pack(pady=20)

def tick():
    remaining = end_ts - int(time.time())
    if remaining < 0:
        remaining = 0
    
    minutes, seconds = divmod(remaining, 60)
    label.config(text=f"{minutes:02d}:{seconds:02d}")
    
    if remaining == 0:
        root.destroy()
    else:
        root.after(250, tick)

tick()
root.mainloop()
PY

chmod +x "$OVERLAY_PY"

# Set environment variables for the Python script
export BREAK_DURATION_SEC
export WINDOW_TITLE="Pomodoro Break - $TARGET_MON"

# Run the Python overlay
"$PYTHON_BIN" "$OVERLAY_PY"

# Cleanup
rm -f "$OVERLAY_PY"