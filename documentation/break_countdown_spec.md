# Break Countdown Overlay Requirements (User Spec)

## What you want (my understanding)
- Arch Linux + Hyprland environment.
- During a break:
  - After the existing 30s grace period and Obsidian fullscreen on workspace 9,
  - The screen should be blocked by a fullscreen banner that:
    - Shows a live, ticking countdown (mm:ss), down to 00:00.
    - Clearly communicates that you must take a break now.
  - While the banner is active, you should not be able to use the desktop normally.
  - When the countdown reaches 00:00 (break over), the screen should automatically unblock and return to normal.
- It does NOT need to be a password-based system lock. A strong “soft lock” banner/overlay is acceptable if it prevents usage until the timer ends.
- You still want the same pre-break flow (Obsidian to workspace 9, 30s grace), and the new overlay starts after the grace.

## Constraints and preferences
- Prefer stability and zero crashes.
- Avoid getting stuck behind a password screen.
- The banner must keep showing the time remaining (seconds ticking) while the desktop is blocked.
- Ideal if it stays on workspace 9 and resists attempts to switch away during the break.

## Acceptance criteria
- After grace period, a fullscreen overlay appears on workspace 9 with a large countdown mm:ss that updates every second.
- Normal interactions are prevented while the overlay is present.
- At 00:00, the overlay disappears automatically (no password entry required).
- The solution does not crash Hyprland or the session.
- If you try to switch workspaces/apps, it promptly re-focuses the overlay (soft enforcement is acceptable; TTY switching cannot be prevented by user-space tools).

## Non-goals / Clarifications
- Preventing VT/TTY switching (Ctrl+Alt+Fx) is outside scope — requires system-level policy.
- A traditional screen lock (hyprlock/gtklock) is not required if it blocks usage and risks instability; a reliable soft overlay is acceptable.

## Integration plan (later, after validation)
- Keep it separate for testing.
- If accepted, integrate into `pomodoro_manager.sh` as a configurable backend for the break phase (after 30s grace), without changing other flows.
