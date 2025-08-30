import os
import re
import shlex
import subprocess
from flask import Flask, render_template, request, redirect, url_for, jsonify
import time
import threading
from datetime import datetime
import zoneinfo  # Python 3.9+ for timezone support

import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Project base directory (two levels up from this file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Configure logging (project-local)
log_file = os.path.join(BASE_DIR, "pomodoro_web_gui.log")
handler = RotatingFileHandler(log_file, maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

# Cache-busting for static assets: append file mtime as version query param
@app.context_processor
def add_cache_busting_url_for():
    def dated_url_for(endpoint, **values):
        if endpoint == 'static':
            filename = values.get('filename')
            if filename:
                file_path = os.path.join(app.static_folder, filename)
                if os.path.exists(file_path):
                    values['v'] = int(os.path.getmtime(file_path))
                else:
                    values['v'] = int(time.time())
        return url_for(endpoint, **values)
    return dict(url_for=dated_url_for)

# --- Configuration (project-local defaults; can be changed via config file) ---
POMODORO_MANAGER_SCRIPT = os.path.join(BASE_DIR, "pomodoro_manager.sh")
POMODORO_STATE_FILE = os.path.join(BASE_DIR, "pomodoro_state.json")
POMODORO_CONFIG_FILE = os.path.join(BASE_DIR, "pomodoro_config.conf")

# Define default configuration values. These should match the defaults in pomodoro_manager.sh
DEFAULT_CONFIG = {
    "TEST_MODE": "OFF",
    "BREAK_LOCK_DELAY_SEC_DEFAULT": "30",
    "BREAK_LOCK_DELAY_SEC_TEST": "3",
    "WORK_DURATION_DEFAULT": "25m",
    "SHORT_BREAK_DURATION_DEFAULT": "5m",
    "LONG_BREAK_DURATION_DEFAULT": "15m",
    "WORK_DURATION_TEST": "15s",
    "SHORT_BREAK_DURATION_TEST": "15s",
    "LONG_BREAK_DURATION_TEST": "15s",
    "POMODORO_DIR": BASE_DIR,
    "STATE_FILE": os.path.join(BASE_DIR, "pomodoro_state.json"),
    "DAILY_LOG_FILE": os.path.join(BASE_DIR, "pomodoro_daily_log.txt"),
    "LOCK_FILE": os.path.join(BASE_DIR, "pomodoro_lock"),
    "DAEMON_PID_FILE": os.path.join(BASE_DIR, "pomodoro_daemon.pid"),
    "BREAK_LOCKER_PID_FILE": os.path.join(BASE_DIR, "break_locker.pid"),
    "SOUND_FILE": os.path.join(BASE_DIR, "sounds", "beep.wav"),
    "GET_ROUTINE_SCRIPT": os.path.join(BASE_DIR, "RoutineTaskSubTaskScripts", "get_current_CategoryAction.sh"),
    "CURRENT_ROUTINE_FILE": os.path.join(BASE_DIR, "RoutineTaskSubTaskScripts", "current_routine.txt"),
    "LAST_ROUTINE_UPDATE_TIME_FILE": os.path.join(BASE_DIR, "last_routine_update.timestamp"),
    "ROUTINE_UPDATE_FREQUENCY_SEC": "30",
    "OBSIDIAN_VAULT_PATH": os.path.expanduser("~/.config/obsidian"),
    "OBSIDIAN_VAULT_NAME": "obsidian",
    "OBSIDIAN_BREAK_NOTE_PATH": os.path.expanduser("~/.config/obsidian/All Things/Journal/Pomodoro session records/POMODORO BREAK FILE.md"),
    "OBSIDIAN_MARKDOWN_LOG_PATH": os.path.expanduser("~/.config/obsidian/All Things/Journal/Pomodoro session records/POMODORO mark down table data for obsidian Analysis.md"),
    "EVENING_LOCK_INTERVAL_SEC": "30",
    "EVENING_LOCK_ENABLED": "ON",
    "LOCK_START_TIME_CONFIG": "1930",
    "LOCK_FREQUENCY_CONFIG": "10",
    # Evening enforcement extras
    "STRICT_LOCK_ENABLED": "ON",
    "STRICT_LOCK_START_TIME_CONFIG": "1945",
    "STRICT_LOCK_END_TIME_CONFIG": "0700",
    "STRICT_LOCK_FREQUENCY_SEC": "1",
    "PRE_SHUTDOWN_ENFORCEMENT_ENABLED": "ON",
    "PRE_SHUTDOWN_START_TIME": "1940",
    "PRE_SHUTDOWN_END_TIME": "1945",
    "PRE_SHUTDOWN_BEEP_INTERVAL_SEC": "1",
    "PRE_SHUTDOWN_NOTIFY_INTERVAL_SEC": "10",
    "PRE_SHUTDOWN_SHUTDOWN_TIME": "1945",
    "THEME_MODE": "dark",
    # Lunch-time break lock (screen lock window)
    "LUNCH_BREAK_LOCK_ENABLED": "ON",
    "LUNCH_BREAK_START_TIME": "1300",
    "LUNCH_BREAK_END_TIME": "1330",
    "LUNCH_BREAK_LOCK_FREQUENCY_SEC": "10",
    # Beep when user unlocks during break until next lock cycle
    "BREAK_UNLOCK_ALERT_ENABLED": "ON",
    "BREAK_UNLOCK_BEEP_INTERVAL_SEC": "1",
    # Master toggle for break-time frequent locking during all breaks
    "BREAK_LOCK_ENABLED": "ON",
    # Post-break continuous reminder
    "POST_BREAK_BEEP_ENABLED": "ON",
    "POST_BREAK_BEEP_FILE": os.path.join(BASE_DIR, "sounds", "bells-notification.mp3"),
    "POST_BREAK_BEEP_GAP_SEC": "0",
    "POST_BREAK_BEEP_SINK": "",
    # Reminders (optional; default OFF)
    "UNSCHEDULED_REMINDER_ENABLED": "OFF",
    "UNSCHEDULED_REMINDER_INTERVAL_SEC": "180",
    # Nature sounds
    "NATURE_SOUNDS_ENABLED": "OFF",
    "NATURE_SOUNDS_COMMAND": "nature-sounds",
}

# --- Utility Functions ---

def read_raw_config_file():
    try:
        with open(POMODORO_CONFIG_FILE, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: {POMODORO_CONFIG_FILE} not found."
    except Exception as e:
        return f"Error reading raw config file: {e}"

def get_current_config():
    config = {}
    try:
        with open(POMODORO_CONFIG_FILE, 'r') as f:
            config_content = f.read()

        # Parse key-value pairs from the config file
        for line in config_content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"')  # Remove quotes
                    config[key] = value

        # Determine active durations based on TEST_MODE
        if config.get("TEST_MODE") == "ON":
            config["WORK_DURATION"] = config.get("WORK_DURATION_TEST", "N/A")
            config["SHORT_BREAK_DURATION"] = config.get("SHORT_BREAK_DURATION_TEST", "N/A")
            config["LONG_BREAK_DURATION"] = config.get("LONG_BREAK_DURATION_TEST", "N/A")
            config["BREAK_LOCK_DELAY_SEC"] = config.get("BREAK_LOCK_DELAY_SEC_TEST", "N/A")
        else:
            config["WORK_DURATION"] = config.get("WORK_DURATION_DEFAULT", "N/A")
            config["SHORT_BREAK_DURATION"] = config.get("SHORT_BREAK_DURATION_DEFAULT", "N/A")
            config["LONG_BREAK_DURATION"] = config.get("LONG_BREAK_DURATION_DEFAULT", "N/A")
            config["BREAK_LOCK_DELAY_SEC"] = config.get("BREAK_LOCK_DELAY_SEC_DEFAULT", "N/A")

        # Normalize toggle flags for UI using explicit flags if present
        def norm_on_off(val, default_val):
            if val is None:
                return default_val
            return "ON" if str(val).upper() == "ON" else "OFF"

        config["EVENING_LOCK_ENABLED"] = norm_on_off(config.get("EVENING_LOCK_ENABLED"), DEFAULT_CONFIG["EVENING_LOCK_ENABLED"])
        config["STRICT_LOCK_ENABLED"] = norm_on_off(config.get("STRICT_LOCK_ENABLED"), DEFAULT_CONFIG.get("STRICT_LOCK_ENABLED", "ON"))
        config["PRE_SHUTDOWN_ENFORCEMENT_ENABLED"] = norm_on_off(config.get("PRE_SHUTDOWN_ENFORCEMENT_ENABLED"), DEFAULT_CONFIG.get("PRE_SHUTDOWN_ENFORCEMENT_ENABLED", "ON"))
        config["UNSCHEDULED_REMINDER_ENABLED"] = norm_on_off(config.get("UNSCHEDULED_REMINDER_ENABLED"), DEFAULT_CONFIG.get("UNSCHEDULED_REMINDER_ENABLED", "OFF"))
        config["NATURE_SOUNDS_ENABLED"] = norm_on_off(config.get("NATURE_SOUNDS_ENABLED"), DEFAULT_CONFIG.get("NATURE_SOUNDS_ENABLED", "OFF"))

        # Get local timezone for display
        try:
            tz = datetime.now().astimezone().tzinfo
            config["LOCAL_TIMEZONE"] = str(tz) if tz else "Unknown"
        except Exception:
            config["LOCAL_TIMEZONE"] = "Unknown (Install 'tzdata' or use Python 3.9+)"

    except FileNotFoundError:
        app.logger.warning(f"Error: {POMODORO_CONFIG_FILE} not found. Creating with defaults.")
        # If config file not found, create it with defaults and then read
        with open(POMODORO_CONFIG_FILE, 'w') as f:
            f.write("# Pomodoro Configuration\n")
            f.write(f"""TEST_MODE=\"{DEFAULT_CONFIG['TEST_MODE']}\"\n""")
            f.write(f"""BREAK_LOCK_DELAY_SEC_DEFAULT={DEFAULT_CONFIG['BREAK_LOCK_DELAY_SEC_DEFAULT']}\n""")
            f.write(f"""BREAK_LOCK_DELAY_SEC_TEST={DEFAULT_CONFIG['BREAK_LOCK_DELAY_SEC_TEST']}\n""")
            f.write(f"""WORK_DURATION_DEFAULT=\"{DEFAULT_CONFIG['WORK_DURATION_DEFAULT']}\"\n""")
            f.write(f"""SHORT_BREAK_DURATION_DEFAULT=\"{DEFAULT_CONFIG['SHORT_BREAK_DURATION_DEFAULT']}\"\n""")
            f.write(f"""LONG_BREAK_DURATION_DEFAULT=\"{DEFAULT_CONFIG['LONG_BREAK_DURATION_DEFAULT']}\"\n""")
            f.write(f"""WORK_DURATION_TEST=\"{DEFAULT_CONFIG['WORK_DURATION_TEST']}\"\n""")
            f.write(f"""SHORT_BREAK_DURATION_TEST=\"{DEFAULT_CONFIG['SHORT_BREAK_DURATION_TEST']}\"\n""")
            f.write(f"""LONG_BREAK_DURATION_TEST=\"{DEFAULT_CONFIG['LONG_BREAK_DURATION_TEST']}\"\n""")
            f.write(f"""POMODORO_DIR=\"{DEFAULT_CONFIG['POMODORO_DIR']}\"\n""")
            f.write(f"""SOUND_FILE=\"{DEFAULT_CONFIG['SOUND_FILE']}\"\n""")
            f.write(f"""ROUTINE_UPDATE_FREQUENCY_SEC=\"{DEFAULT_CONFIG['ROUTINE_UPDATE_FREQUENCY_SEC']}\"\n""")
            f.write(f"""OBSIDIAN_VAULT_PATH=\"{DEFAULT_CONFIG['OBSIDIAN_VAULT_PATH']}\"\n""")
            f.write(f"""OBSIDIAN_VAULT_NAME=\"{DEFAULT_CONFIG['OBSIDIAN_VAULT_NAME']}\"\n""")
            f.write(f"""OBSIDIAN_BREAK_NOTE_PATH=\"{DEFAULT_CONFIG['OBSIDIAN_BREAK_NOTE_PATH']}\"\n""")
            f.write(f"""OBSIDIAN_MARKDOWN_LOG_PATH=\"{DEFAULT_CONFIG['OBSIDIAN_MARKDOWN_LOG_PATH']}\"\n""")
            f.write(f"""EVENING_LOCK_INTERVAL_SEC={DEFAULT_CONFIG['EVENING_LOCK_INTERVAL_SEC']}\n""")
            f.write(f"""EVENING_LOCK_ENABLED=\"{DEFAULT_CONFIG['EVENING_LOCK_ENABLED']}\"\n""")
            f.write(f"""LOCK_START_TIME_CONFIG=\"{DEFAULT_CONFIG['LOCK_START_TIME_CONFIG']}\"\n""")
            f.write(f"""LOCK_FREQUENCY_CONFIG=\"{DEFAULT_CONFIG['LOCK_FREQUENCY_CONFIG']}\"\n""")
            f.write(f"""THEME_MODE=\"{DEFAULT_CONFIG['THEME_MODE']}\"\n""")
        return get_current_config()  # Re-read
    except Exception as e:
        app.logger.error(f"Error reading config: {e}")
        return None
    return config


def update_config(new_config_values):
    app.logger.debug(f"Starting update_config with values: {new_config_values}")
    try:
        with open(POMODORO_CONFIG_FILE, 'r') as f:
            config_content = f.readlines()
        app.logger.debug(f"Original config content length: {len(config_content)}")

        updated_lines = []

        # Extract special handling values first
        test_mode_value = new_config_values.pop("TEST_MODE", None)
        evening_lock_enabled_value = new_config_values.pop("EVENING_LOCK_ENABLED", None)
        if evening_lock_enabled_value is not None:
            normalized_evening_lock = str(evening_lock_enabled_value).strip().upper()

        # Nature sounds explicit handling (avoid duplicate-key issues)
        nature_enabled_value = new_config_values.pop("NATURE_SOUNDS_ENABLED", None)
        nature_command_value = new_config_values.pop("NATURE_SOUNDS_COMMAND", None)

        # Keys explicitly handled here to avoid duplicate processing later
        explicitly_handled_keys = {
            "TEST_MODE", "EVENING_LOCK_INTERVAL_SEC", "EVENING_LOCK_ENABLED", "THEME_MODE",
            "LOCK_START_TIME_CONFIG", "LOCK_FREQUENCY_CONFIG",
            "WORK_DURATION_DEFAULT", "SHORT_BREAK_DURATION_DEFAULT", "LONG_BREAK_DURATION_DEFAULT", "BREAK_LOCK_DELAY_SEC_DEFAULT",
            "WORK_DURATION_TEST", "SHORT_BREAK_DURATION_TEST", "LONG_BREAK_DURATION_TEST", "BREAK_LOCK_DELAY_SEC_TEST"
        }

        for line in config_content:
            stripped_line = line.strip()
            updated = False

            # Handle TEST_MODE toggle
            if test_mode_value is not None and stripped_line.startswith("TEST_MODE="):
                updated_lines.append(f"""TEST_MODE="{test_mode_value}"\n""")
                updated = True

            # Handle EVENING_LOCK_ENABLED flag
            elif evening_lock_enabled_value is not None and stripped_line.startswith("EVENING_LOCK_ENABLED="):
                on_off_literal = "ON" if normalized_evening_lock == "ON" else "OFF"
                updated_lines.append(f"""EVENING_LOCK_ENABLED="{on_off_literal}"
""")
                updated = True

            # Keep EVENING_LOCK_INTERVAL_SEC consistent with the flag (OFF => 0, ON => default or keep existing)
            elif evening_lock_enabled_value is not None and stripped_line.startswith("EVENING_LOCK_INTERVAL_SEC="):
                interval_value = DEFAULT_CONFIG["EVENING_LOCK_INTERVAL_SEC"] if normalized_evening_lock == "ON" else "0"
                updated_lines.append(f"""EVENING_LOCK_INTERVAL_SEC={interval_value}
""")
                updated = True

            # Handle time/frequency values
            elif "LOCK_START_TIME_CONFIG" in new_config_values and stripped_line.startswith("LOCK_START_TIME_CONFIG="):
                updated_lines.append(f"""LOCK_START_TIME_CONFIG="{new_config_values["LOCK_START_TIME_CONFIG"]}"
""")
                updated = True
                new_config_values.pop("LOCK_START_TIME_CONFIG")

            elif "LOCK_FREQUENCY_CONFIG" in new_config_values and stripped_line.startswith("LOCK_FREQUENCY_CONFIG="):
                updated_lines.append(f"""LOCK_FREQUENCY_CONFIG="{new_config_values["LOCK_FREQUENCY_CONFIG"]}"
""")
                updated = True
                new_config_values.pop("LOCK_FREQUENCY_CONFIG")

            # Handle THEME_MODE
            elif "THEME_MODE" in new_config_values and stripped_line.startswith("THEME_MODE="):
                updated_lines.append(f"""THEME_MODE="{new_config_values["THEME_MODE"]}"\n""")
                updated = True
                new_config_values.pop("THEME_MODE")

            # Handle other variables
            else:
                for key, value in list(new_config_values.items()):
                    if key not in explicitly_handled_keys and stripped_line.startswith(f"{key}="):
                        if '"' in stripped_line:
                            updated_lines.append(f"""{key}="{value}"\n""")
                        else:
                            updated_lines.append(f"""{key}={value}\n""")
                        updated = True
                        new_config_values.pop(key)
                        break

            if not updated:
                updated_lines.append(line)

        # Append any keys that did not exist in the file
        for key, value in new_config_values.items():
            # Quote all values to be safe (durations/ON-OFF/paths)
            updated_lines.append(f"{key}=\"{value}\"\n")

        with open(POMODORO_CONFIG_FILE, 'w') as f:
            # Ensure authoritative values for nature sounds are placed at the end (last-one-wins)
            if nature_enabled_value is not None:
                on_off_literal = "ON" if str(nature_enabled_value).strip().upper() == "ON" else "OFF"
                updated_lines.append(f"NATURE_SOUNDS_ENABLED=\"{on_off_literal}\"\n")
            if nature_command_value is not None:
                updated_lines.append(f"NATURE_SOUNDS_COMMAND=\"{nature_command_value}\"\n")

            f.writelines(updated_lines)
        app.logger.debug("Config file write successful.")

        # Nudge manager to re-source config
        subprocess.run([POMODORO_MANAGER_SCRIPT, "status"], check=False, capture_output=True)
        app.logger.debug("Triggered pomodoro_manager.sh to re-source config.")

        return True
    except Exception as e:
        app.logger.error(f"ERROR: Exception during update_config: {e}")
        return False


# --- Flask Routes ---

def execute_pomodoro_command(action: str) -> bool:
    """Run a safe, whitelisted command against pomodoro_manager.sh."""
    allowed = {
        "start",
        "pause",
        "resume",
        "stop",
        "reset",
        "status",
        "daemon",
        "stop-daemon",
        "restart-daemon",
        "cleanup",
        "quick-start",
    }
    special_web_actions = {"web-restart", "web-stop"}
    if action not in allowed and action not in special_web_actions:
        app.logger.warning(f"Blocked non-whitelisted action: {action}")
        return False
    try:
        if action in special_web_actions:
            # Schedule a delayed restart/stop so this request can return cleanly
            # Detach the child so it survives when this server is killed
            delayed = f"sleep 1; {shlex.quote(POMODORO_MANAGER_SCRIPT)} {action}"
            subprocess.Popen(
                ["bash", "-lc", delayed],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        elif action == "restart-daemon":
            # Perform a controlled restart in a background thread: stop → wait clear → start → verify
            def do_restart():
                try:
                    # Stop
                    subprocess.run([POMODORO_MANAGER_SCRIPT, "stop-daemon"], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # Wait until no processes remain (up to 5s)
                    deadline = time.time() + 5
                    while time.time() < deadline:
                        if not list_daemon_processes():
                            break
                        time.sleep(0.2)
                    # Start
                    subprocess.Popen([POMODORO_MANAGER_SCRIPT, "daemon"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     preexec_fn=os.setsid)
                    # Wait until at least one appears (up to 3s)
                    deadline2 = time.time() + 3
                    while time.time() < deadline2:
                        if list_daemon_processes():
                            break
                        time.sleep(0.2)
                    # Second attempt if still not up
                    if not list_daemon_processes():
                        subprocess.Popen([POMODORO_MANAGER_SCRIPT, "daemon"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         preexec_fn=os.setsid)
                        time.sleep(0.5)
                except Exception as e:
                    app.logger.error(f"restart-daemon background error: {e}")
            threading.Thread(target=do_restart, daemon=True).start()
        elif action == "daemon":
            # Start the daemon in background so the request does not hang
            subprocess.Popen(
                [POMODORO_MANAGER_SCRIPT, "daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        else:
            subprocess.run([POMODORO_MANAGER_SCRIPT, action], check=False)
        return True
    except Exception as e:
        app.logger.error(f"Failed to run action '{action}': {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    current_config = get_current_config()
    pomodoro_status = get_pomodoro_status()
    daemon_status = get_daemon_status()  # Get daemon status

    if request.method == 'POST':
        if 'save_config' in request.form:
            new_config = {}
            # Collect keys from DEFAULT_CONFIG and any keys present in current config
            all_config_keys = set(DEFAULT_CONFIG.keys()) | set((current_config or {}).keys())
            # Ensure toggles are included
            all_config_keys.update({
                "EVENING_LOCK_ENABLED",
                "STRICT_LOCK_ENABLED",
                "PRE_SHUTDOWN_ENFORCEMENT_ENABLED",
            })

            for key in all_config_keys:
                if key == "EVENING_LOCK_INTERVAL_SEC":
                    # Derived from ENABLED toggle; skip direct set
                    continue
                form_value = request.form.get(key)
                if form_value is not None:
                    new_config[key] = form_value
                elif current_config and key in current_config:
                    new_config[key] = current_config[key]

            if update_config(new_config):
                return redirect(url_for('index', message='Configuration saved successfully!'))
            else:
                return redirect(url_for('index', error='Failed to save configuration.'))

        elif 'restore_defaults' in request.form:
            defaults_to_restore = DEFAULT_CONFIG.copy()
            defaults_to_restore["EVENING_LOCK_ENABLED"] = DEFAULT_CONFIG["EVENING_LOCK_ENABLED"]
            if update_config(defaults_to_restore):
                return redirect(url_for('index', message='All defaults restored successfully!'))
            else:
                return redirect(url_for('index', error='Failed to restore all defaults.'))

        elif 'restore_individual_default' in request.form:
            key_to_restore = request.form['restore_individual_default']
            value_to_restore = DEFAULT_CONFIG.get(key_to_restore)
            if key_to_restore == "EVENING_LOCK_INTERVAL_SEC":
                # Restoring interval implies ON by default
                if update_config({"EVENING_LOCK_ENABLED": DEFAULT_CONFIG["EVENING_LOCK_ENABLED"], "EVENING_LOCK_INTERVAL_SEC": DEFAULT_CONFIG["EVENING_LOCK_INTERVAL_SEC"] }):
                    return redirect(url_for('index', message=f'Default for {key_to_restore} restored!'))
                else:
                    return redirect(url_for('index', error=f'Failed to restore default for {key_to_restore}.'))
            elif value_to_restore is not None:
                if update_config({key_to_restore: value_to_restore}):
                    return redirect(url_for('index', message=f'Default for {key_to_restore} restored!'))
                else:
                    return redirect(url_for('index', error=f'Failed to restore default for {key_to_restore}.'))
            else:
                return redirect(url_for('index', error=f'Default value for {key_to_restore} not found.'))

        elif 'pomodoro_action' in request.form:
            action = request.form['pomodoro_action']
            if execute_pomodoro_command(action):
                return redirect(url_for('index', message=f'Command "{action}" executed successfully!'))
            else:
                return redirect(url_for('index', error=f'Failed to execute command "{action}".'))

    message = request.args.get('message')
    error = request.args.get('error')

    return render_template('index.html',
                           current_config=current_config,
                           default_config=DEFAULT_CONFIG,
                           pomodoro_status=pomodoro_status,
                           daemon_status=daemon_status,
                           theme_mode=current_config.get("THEME_MODE", "dark") if current_config else "dark",
                           message=message,
                           error=error,
                           raw_config_content=read_raw_config_file())


def get_startup_service_status():
    """Get systemd user service status for pomodoro-startup.service"""
    try:
        # Check if service is enabled
        enabled_result = subprocess.run(['systemctl', '--user', 'is-enabled', 'pomodoro-startup.service'], 
                                      capture_output=True, text=True)
        is_enabled = enabled_result.stdout.strip() == 'enabled'
        
        # Check service status
        status_result = subprocess.run(['systemctl', '--user', 'status', 'pomodoro-startup.service'], 
                                     capture_output=True, text=True)
        status_lines = status_result.stdout.strip().split('\n')
        
        # Extract key information
        loaded_line = next((line for line in status_lines if 'Loaded:' in line), '')
        active_line = next((line for line in status_lines if 'Active:' in line), '')
        
        status_info = {
            'enabled': is_enabled,
            'loaded': 'loaded' in loaded_line.lower(),
            'active': 'active' in active_line.lower(),
            'status_summary': active_line.strip() if active_line else 'Unknown'
        }
        
        return status_info
    except Exception as e:
        return {'error': str(e), 'enabled': False, 'loaded': False, 'active': False}

def get_daemon_status():
    # Prefer actual processes over PID file
    procs = list_daemon_processes()
    if procs:
        return "Running"
    # Fallback to PID file if pgrep found nothing
    daemon_pid_file = os.path.join(BASE_DIR, "pomodoro_daemon.pid")
    if os.path.exists(daemon_pid_file):
        try:
            with open(daemon_pid_file, 'r') as f:
                raw = f.read().strip()
                pid = int(raw) if raw else None
            if pid and os.path.exists(f"/proc/{pid}"):
                return "Running"
            else:
                try:
                    os.remove(daemon_pid_file)
                except Exception:
                    pass
                return "Stopped"
        except (ValueError, IOError):
            return "Stopped"
    return "Stopped"


def list_daemon_processes():
    """Return a list of running pomodoro daemon processes with pid and command."""
    try:
        res = subprocess.run(
            ["pgrep", "-af", r"pomodoro_manager\\.sh.*daemon"],
            capture_output=True, text=True, check=False
        )
        lines = [ln for ln in (res.stdout or "").splitlines() if ln.strip()]
        processes = []
        for ln in lines:
            # Expected: "<pid> <full command>"
            parts = ln.strip().split(" ", 1)
            if not parts:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            cmd = parts[1] if len(parts) > 1 else ""
            processes.append({"pid": pid, "cmd": cmd})
        # Fallback: include PID from pid file if valid and not already listed
        try:
            pid_file = os.path.join(BASE_DIR, "pomodoro_daemon.pid")
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    raw = f.read().strip()
                if raw:
                    pid = int(raw)
                    if os.path.exists(f"/proc/{pid}") and all(p.get("pid") != pid for p in processes):
                        # Read command line
                        cmd = ""
                        try:
                            with open(f"/proc/{pid}/cmdline", 'rb') as cf:
                                cmd = cf.read().decode('utf-8').replace('\x00', ' ').strip()
                        except Exception:
                            cmd = "pomodoro_manager.sh daemon"
                        processes.append({"pid": pid, "cmd": cmd})
        except Exception:
            pass
        return processes
    except Exception:
        return []


def get_pomodoro_status():
    try:
        # Execute the status command from pomodoro_manager.sh
        result = subprocess.run(
            [POMODORO_MANAGER_SCRIPT, "status"],
            capture_output=True, text=True, check=True
        )
        # The status command outputs JSON, so we parse it
        status_json = result.stdout.strip()
        import json
        status_data = json.loads(status_json)
        return status_data.get('text', 'Unknown Status')
    except Exception as e:
        return f"Error: {e}"


# Lightweight API for live status polling (must be defined before app.run)
@app.get('/api/status')
def api_status():
    try:
        text = get_pomodoro_status()
        daemon = get_daemon_status()
        daemons = list_daemon_processes()
        startup_service = get_startup_service_status()
        # State stats
        sessions_today, focus_seconds_today = read_state_stats()
        # Log entries today
        current_config = get_current_config() or {}
        daily_log_path = current_config.get("DAILY_LOG_FILE") or DEFAULT_CONFIG.get("DAILY_LOG_FILE")
        logs_today = count_today_log_entries(daily_log_path)
        return jsonify({
            "text": text,
            "daemon": daemon,
            "daemon_count": len(daemons),
            "daemons": daemons,
            "startup_service": startup_service,
            "sessions_today": sessions_today,
            "focus_seconds_today": focus_seconds_today,
            "log_entries_today": logs_today,
        })
    except Exception as e:
        app.logger.error(f"/api/status error: {e}")
        return jsonify({
            "text": f"Error: {e}",
            "daemon": "Unknown",
            "daemon_count": 0,
            "daemons": [],
            "sessions_today": 0,
            "focus_seconds_today": 0,
            "log_entries_today": 0,
        }), 500


@app.get('/api/logs')
def api_logs():
    try:
        day = (request.args.get('day') or 'today').lower()
        limit = int(request.args.get('limit') or 200)
        current_config = get_current_config() or {}
        daily_log_path = current_config.get("DAILY_LOG_FILE") or DEFAULT_CONFIG.get("DAILY_LOG_FILE")
        lines = get_log_lines_for_day(daily_log_path, day, limit)
        return jsonify({"day": day, "lines": lines})
    except Exception as e:
        app.logger.error(f"/api/logs error: {e}")
        return jsonify({"day": "unknown", "lines": [], "error": str(e)}), 500


def get_log_lines_for_day(log_path: str, day: str, limit: int) -> list:
    if not log_path or not os.path.exists(log_path):
        return []
    if day == 'yesterday':
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        target_date = datetime.now().strftime('%Y-%m-%d')
    prefix = f'[{target_date}'
    matched = []
    try:
        with open(log_path, 'r', errors='ignore') as f:
            for line in f:
                if line.startswith(prefix):
                    matched.append(line.rstrip('\n'))
        # Return up to limit, prefer latest entries
        if len(matched) > limit:
            matched = matched[-limit:]
        return matched
    except Exception:
        return []

def read_state_stats():
    try:
        if os.path.exists(POMODORO_STATE_FILE):
            import json as _json
            with open(POMODORO_STATE_FILE, 'r') as f:
                data = _json.load(f)
            sessions = int(data.get('total_pomodoro_cycles_today') or 0)
            focus_seconds = int(data.get('total_focus_seconds_today') or 0)
            return sessions, focus_seconds
    except Exception:
        pass
    return 0, 0


def count_today_log_entries(log_path: str) -> int:
    try:
        if not log_path or not os.path.exists(log_path):
            return 0
        today_prefix = datetime.now().strftime('[%Y-%m-%d')
        count = 0
        with open(log_path, 'r', errors='ignore') as f:
            for line in f:
                if today_prefix in line:
                    count += 1
        return count
    except Exception:
        return 0


if __name__ == '__main__':
    # Run without debug/reloader to avoid duplicate processes when launched from the manager
    app.run(debug=False, use_reloader=False, host='127.0.0.1', port=5001)
