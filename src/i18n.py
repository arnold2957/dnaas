
# Mapping for UI translation
UI_STRINGS = {
    "title_format": "DNaaS Auto Farmer v{} @Dellyla(Bilibili) [Eng]",
    "intro_format": "Issues? Visit:\n{}",
    "adb_setting": "ADB Setting",
    "select_adb_file": "Select ADB Executable",
    "change": "Change",
    "emulator_set": "Emulator Set",
    "emulator_not_set": "Emulator Not Set",
    "port": "Port:",
    "save": "Save",
    "dungeon_target": "Dungeon Target:",
    "level": "Level:",
    "extra_params": "Extra Params:",
    "timeout_check": "Round Timeout Check (s):",
    "use_custom_rounds": "Use Custom Rounds",
    "rounds": " | Rounds:",
    "use_green_book": "Use Green Book",
    "use_green_book_final": "Green Book (Final Round Only)",
    "cast_q_once": "(Once) Cast Q at Start",
    "auto_cast_q": "Auto Cast Q",
    "auto_cast_e": "Auto Cast E",
    "interval_s": " | Interval (s):",
    "print_timers": "Print Internal Skill Timers",
    "start_script": "Script, Start!",
    "stop_script": "Stop",
    "stopped": "Stopped.",
    "quest_active": "Quest Active",
    "quest_stopped": "Quest Stopped",
    "starting_task": "Starting task \"{}\" (Extra={})...",
    "stopping_task": "Stopping task...",
    "starting_money": "Starting 7000G farm...",
    "error_parse_config": "Error: Cannot parse {}. Using default config.",
    "error_load_config": "Error: Error loading config: {}. Using default config.",
    "error_load_image": "Failed to load image: {}",
    "config_saved": "Config saved.",
    "error_save_config": "Error saving config: {}",
    "error_attr_not_found": "Attribute '{}' not found: {}.",
    
    # Script logs
    "checking_closing_adb": "Checking and closing ADB...",
    "checking_closing_emulator": "Checking and closing running emulator instance {}...",
    "adb_terminated": "ADB terminated.",
    "emulator_terminated": "Attempted to terminate emulator process: {}",
    "error_terminate_emulator": "Error terminating emulator process: {}",
    "emulator_executable_not_found": "Emulator executable not found: {}",
    "starting_emulator": "Starting emulator: {}",
    "error_start_emulator": "Failed to start emulator: {}",
    "waiting_emulator_start": "Waiting for emulator to start...",
    "adb_not_found": "ADB executable not found: {}",
    "attempting_connect_adb": "Attempting to connect to ADB. Attempt: {}/{}...",
    "too_many_failures_close_adb": "Too many failures, attempting to close ADB.",
    "checking_adb_service": "Checking ADB service...",
    "adb_service_not_started": "ADB service not started!\nStarting ADB service...",
    "attempting_connect_adb_debug": "Attempting to connect to ADB...",
    "attempting_connect_emulator": "Attempting to connect to emulator...",
    "connected_emulator": "Successfully connected to emulator.",
    "emulator_not_running_start": "Emulator not running, attempting to start...",
    "emulator_started": "Emulator (should be) started.",
    "cannot_connect_check_port": "Cannot connect. Check ADB port.",
    "connection_failed": "Connection failed: {}",
    "error_restart_adb": "Error restarting ADB service: {}",
    "max_retries_reached": "Max retries reached, connection failed.",
    "got_device_object": "Successfully got device object: {}",
    "error_get_adb_device": "Error getting ADB device: {}",
    "adb_command_timeout": "ADB command timed out: {}",
    "adb_operation_failed": "ADB operation failed ({}): {}",
    "attempting_restart_adb": "Attempting to restart ADB service...",
    "unexpected_adb_exception": "Unexpected ADB exception: {}: {}",
    "screenshot_empty": "Screenshot data empty!",
    "opencv_decode_failed": "OpenCV decode failed: image data corrupted",
    "screenshot_size_abnormal": "Screenshot size abnormal! Current {}, expected (1600,900). Please check and modify emulator resolution!",
    "adb_restarting": "ADB restarting...",
    "cv2_exception": "cv2 exception.",
    "found_suspected": "Found suspected {}, match: {:.2f}%",
    "match_below_threshold": "Match below threshold.",
    "match_warning": "Warning: Match for {} is over {:.0f}% but under 90%",
    "matched_successfully": "{} matched successfully!",
    "center_match_check": "Center match check: {:.2f}",
    "error_invalid_target": "Error: Invalid target {}.",
    "screenshot_target_not_found_restart": "{} screenshots and still cannot find target {}, possible freeze. Restarting game.",
    "pre_restart_screenshot_saved": "Pre-restart screenshot saved in {}.\nPlease send this screenshot and log file for bug report.",
    "skipped_screenshot": "Skipped pre-restart screenshot. Ignoring emulator restart for now.",
    "cloud_game_detected": "Cloud game detected, prioritizing cloud game start.",
    "global_server_detected": "HK/TW/Global server detected.",
    "preparing_start_game": "Preparing to start game.",
    "unknown_version_restart_failed": "What version are you playing? Cannot restart, bye.",
    "game_start": "Duet Night Abyss, Start!",
    "task_progress_reset": "Task progress resetting...",
    "starting_reset": "Starting reset.",
    "strange_already_exited": "Strange, already exited.",
    "e_skill_timer": "E Skill Timer: Current: {}",
    "q_skill_timer": "Q Skill Timer: Current: {:.2f}",
    "doing_nothing_kick": "Uh, doing nothing won't do, will get kicked.",
    "already_in_dungeon": "Already in dungeon.",
    "positioning_result": "Positioning result: {:.2f}.",
    "report_graphics_settings": "If you see this message often, please report your graphics settings and if you are using cloud game to the author.",
    "auto_calibration_cancelled": "Auto-calibration cancelled: not in target range.",
    "error_open_letter_mode": "Error: Open Letter mode cannot auto-select quest. Execution cancelled.",
    "extra_param_farming_target": "Due to extra param \"{}\", farming target is {}",
    "quest_list_updated": "\n\nQuest list updated! Please manually re-select dungeon target!\n\n",
    "custom_rounds_set": "Custom rounds set, will farm {} rounds each time.",
    "default_rounds": "Default in-game rounds for {} is {}.",
    "reconnecting": "Reconnecting.",
    "click_enter_game": "Click to enter game.",
    "stop_fishing_detected": "Stop request detected, ending fishing handling.",
    "no_fish_detected": "No fish detected, stopping fishing.",
    "not_in_fishing_ui": "Not in fishing UI. ({})",
    "caught_fish": "Caught a fish!",
    "caught_fish_stat": "Caught {} fish, total time {:.2f}s.",
    "exploration_task_detected": "Exploration task detected, forcing stop.",
    "coop_request_detected": "Co-op request detected, accepting.",
    "quest_menu": "Quest menu.",
    "training": "Training.",
    "level_selection": "Level selection.",
    "start_challenge": "Start challenge!",
    "green_book_used": "Used Green Book due to panel setting.",
    "green_book_used_final": "Last round, used Green Book due to panel setting.",
    "monthly_card_collected": "Collected Monthly Card.",
    "round_completed": "Completed round {}!",
    "round_time_stat": "Round time {:.2f}s.\nTotal time {:.2f}s.",
    "starting_round": "Starting round {}...",
    "target_rounds_completed": "Target rounds completed, evacuating.",
    "game_completed_stat": "{}th {} completed.\nTotal time {:.2f}s.",
    "unsupported_map": "Unsupported map, re-entering.",
    "took_too_long_restart": "Took too long, restarting.",
    "rogue_runs_completed": "Completed {} Rogue runs.",
    "positioning_attempt": "Positioning, attempt: {}/20",
    "game_not_running_start": "Game not running, attempting to start.",
    "max_attempts_restart": "Max attempts reached, restarting game.",
    
    # Rogue specific strings found in code but maybe I missed
    "rogue_mode_used": "Using Rogue mode.",
    "hostage_rescued": "Hostage rescued!",
    "fourth_room": "Fourth Room",
    "facing": "Facing",
    "top_left": "Top Left",
    "bottom_left": "Bottom Left",
    "unusable_second_room": "Unusable second room.",
    "why_run_this": "Wait, how can you run this??",
    "no_start_move_afk": "No start move set. AFK.",
    
    # Rogue room logs
    "rogue_rescue_end": "Rescue ended.",
}

# Mapping for Logic Values (Chinese <-> English)
# Used for Combobox values that correspond to keys in DUNGEON_TARGETS or image filenames
LOGIC_MAPPING = {
    "角色经验": "Character Exp",
    "角色材料": "Character Mats",
    "武器突破": "Weapon Break",
    "皎皎币": "Lunar Coins",
    "夜航手册": "Night Manual",
    "魔之楔(不是夜航手册!)": "Demon Wedge (Not Manual!)",
    "mod强化": "Mod Enhance",
    "开密函": "Open Letter",
    "钓鱼": "Fishing",
    "迷津": "Maze",
    
    # Sub-levels / Keys in inner dicts
    "驱离": "Expel",
    "探险无尽": "Endless Explore",
    "半自动无巧手": "Semi-Auto No Dexterity",
    "悠闲": "Leisure",
    "默认难度": "Default Diff",
    "60(测试)": "60 (Test)",
    
    # Extra params
    "无关心": "Don't Care"
}

# Create reverse mapping
REVERSE_LOGIC_MAPPING = {v: k for k, v in LOGIC_MAPPING.items()}

def get_text(key, *args):
    """Get translated UI string."""
    text = UI_STRINGS.get(key, key)
    if args:
        return text.format(*args)
    return text

def to_english(text):
    """Convert Chinese logic value to English display value."""
    # If the text is a digit (e.g. "60"), return as is
    if isinstance(text, str) and text.isdigit():
        return text
    if isinstance(text, int):
        return str(text)
        
    return LOGIC_MAPPING.get(text, text)

def to_chinese(text):
    """Convert English display value back to Chinese logic value."""
    return REVERSE_LOGIC_MAPPING.get(text, text)
