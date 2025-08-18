# Rules

1. For all changes to shell file thich is main file here.
   1. you make update the documentation.md file and see if this file is in sync with the app always.
   2. make a backup file for the file with date time sec based exteniosn in backups folder uisng cp command in to backups folder.
   3. there is no use of readinf contetns of files in backups fodlers
   4. only read file names if needed
2. before reading any files in the folder remember to ignore the backup fodlers and .bak file named files as they are backups and there is no use of reading them. Z
# User Instructions: Pathing

- **Always use relative paths:** When interacting with the file system, always use relative paths for files within the project directory.
- **Convert user-provided paths:** If the user provides an absolute path, convert it to a relative path before using it with any tool.
- **Suggest relative paths to user:** If the user provides an absolute path, suggest that they use relative paths in the future, explaining that the agent works best with relative paths.
\nThese rules are in place because Gemini works best with relative paths.

---

### Backup File Naming Convention

"- **Timestamp First:** Backup filenames should always start with a timestamp in the format `YYYYMMDD_HHMMSS` for easy sorting."
"- **Backup Folder:** All backups should be placed in the `backups/` directory."
"- **Example:** `backups/20250818_123456_pomodoro_manager.sh_before_adding_weekday_planner.bak`"
- **Descriptive Name:** The filename should include the original filename and a brief, descriptive message about the change being made (e.g., `before_adding_feature_X`).
