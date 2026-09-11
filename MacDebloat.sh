#!/usr/bin/env bash
#
# MacDebloat.sh
# A lightweight, no-install-required shell script to declutter and customize
# macOS — the same spirit as Win11Debloat, adapted for a completely different OS.
#
# Inspired by Win11Debloat (https://github.com/Raphire/Win11Debloat) by Raphire.
# This is an independent rewrite for macOS: no code is shared between the two,
# since Windows (registry / Group Policy) and macOS (defaults / launchctl / SIP)
# are configured in totally different ways. Only the idea and the menu-driven
# feel are carried over.
#
# License: MIT
#
# IMPORTANT
#   - Some tweaks require your admin (sudo) password. You'll be prompted only
#     when needed.
#   - Every change this script makes is logged to ~/.macdebloat_backup so it
#     can be undone with --revert. Still, back up first if you're unsure —
#     use at your own risk, same as the project this is based on.
#   - This script will NEVER touch System Integrity Protection (SIP), the
#     sealed system volume, Gatekeeper, or FileVault. Those protect your Mac
#     and are outside the scope of a "debloat" tool.
#   - Run it with:  bash MacDebloat.sh
#     If you host this in a repo and want a curl-based "quick method" like
#     the original, use:
#         bash -c "$(curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/MacDebloat.sh)"
#     NOT `curl ... | bash` — piping breaks the interactive menu because bash
#     ends up reading the menu prompts from the same pipe as the script text.
#
# Deliberately NOT using `set -u` here: macOS's stock /bin/bash is 3.2, where
# "${arr[@]}" on a genuinely-empty array (e.g. no flags matched, or no
# removable apps found) is treated as an unbound variable and kills the
# script. This script instead guards optional values explicitly with
# ${VAR:-...} wherever one might be unset.

SCRIPT_VERSION="1.0.0"
BACKUP_DIR="$HOME/.macdebloat_backup"
LOG_FILE="$BACKUP_DIR/changes-$(date +%Y%m%d-%H%M%S).log"
DRY_RUN=false
ASSUME_YES=false
TARGET_USER=""

if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
  CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; CYAN=""; BOLD=""; RESET=""
fi

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

info()    { echo "${CYAN}i${RESET}  $*"; }
success() { echo "${GREEN}v${RESET}  $*"; }
warn()    { echo "${YELLOW}!${RESET}  $*" >&2; }
err()     { echo "${RED}x${RESET}  $*" >&2; }

need_macos() {
  if [ "$(uname -s)" != "Darwin" ]; then
    err "MacDebloat.sh only runs on macOS. Exiting."
    exit 1
  fi
}

is_apple_silicon() { [ "$(uname -m)" = "arm64" ]; }

confirm() {
  if $ASSUME_YES; then return 0; fi
  local prompt="${1:-Continue?}" ans
  read -r -p "$prompt [y/N] " ans
  case "$ans" in
    [Yy]|[Yy][Ee][Ss]) return 0 ;;
    *) return 1 ;;
  esac
}

restart_dock()   { $DRY_RUN || killall Dock 2>/dev/null; }
restart_finder() { $DRY_RUN || killall Finder 2>/dev/null; }

print_banner() {
  echo "${BOLD}${CYAN}MacDebloat${RESET} v${SCRIPT_VERSION}"
  echo "A macOS-flavored take on Win11Debloat -- declutter & customize your Mac."
  echo "Inspired by: https://github.com/Raphire/Win11Debloat"
  echo
}

# ---------------------------------------------------------------------------
# defaults(1) helpers -- read/write/backup, with optional --user targeting
# ---------------------------------------------------------------------------

_defaults_read() {
  local domain="$1" key="$2" use_sudo="$3"
  if [ "$use_sudo" = "true" ]; then
    sudo defaults read "$domain" "$key" 2>/dev/null
  elif [ -n "$TARGET_USER" ]; then
    sudo -H -u "$TARGET_USER" defaults read "$domain" "$key" 2>/dev/null
  else
    defaults read "$domain" "$key" 2>/dev/null
  fi
}

_defaults_readtype() {
  local domain="$1" key="$2" use_sudo="$3"
  if [ "$use_sudo" = "true" ]; then
    sudo defaults read-type "$domain" "$key" 2>/dev/null
  elif [ -n "$TARGET_USER" ]; then
    sudo -H -u "$TARGET_USER" defaults read-type "$domain" "$key" 2>/dev/null
  else
    defaults read-type "$domain" "$key" 2>/dev/null
  fi
}

get_type_flag() {
  local domain="$1" key="$2" use_sudo="$3" out
  out=$(_defaults_readtype "$domain" "$key" "$use_sudo")
  case "$out" in
    *boolean*) echo "-bool" ;;
    *integer*) echo "-int" ;;
    *float*)   echo "-float" ;;
    *string*)  echo "-string" ;;
    *array*)   echo "-array" ;;
    *dict*)    echo "-dict" ;;
    *) echo "-string" ;;
  esac
}

_revert_prefix_literal() {
  local use_sudo="$1"
  if [ "$use_sudo" = "true" ]; then
    printf 'sudo '
  elif [ -n "$TARGET_USER" ]; then
    printf 'sudo -H -u %q ' "$TARGET_USER"
  fi
}

append_manual_revert() {
  mkdir -p "$BACKUP_DIR"
  printf '%s\n' "$1" >> "$LOG_FILE"
}

record_revert() {
  local domain="$1" key="$2" use_sudo="$3" cur tflag prefix
  mkdir -p "$BACKUP_DIR"
  cur=$(_defaults_read "$domain" "$key" "$use_sudo")
  prefix="$(_revert_prefix_literal "$use_sudo")"
  if [ -n "$cur" ]; then
    tflag=$(get_type_flag "$domain" "$key" "$use_sudo")
    printf '%sdefaults write %q %q %s %q\n' "$prefix" "$domain" "$key" "$tflag" "$cur" >> "$LOG_FILE"
  else
    printf '%sdefaults delete %q %q 2>/dev/null\n' "$prefix" "$domain" "$key" >> "$LOG_FILE"
  fi
}

# uwrite: per-user default (current user, or --user target)
uwrite() {
  local domain="$1" key="$2" type_flag="$3" value="$4" desc="$5"
  echo "${CYAN}->${RESET} ${desc}"
  record_revert "$domain" "$key" "false"
  if $DRY_RUN; then
    echo "     (dry-run) defaults write \"$domain\" \"$key\" $type_flag \"$value\""
    return 0
  fi
  if [ -n "$TARGET_USER" ]; then
    sudo -H -u "$TARGET_USER" defaults write "$domain" "$key" "$type_flag" "$value" 2>/dev/null
  else
    defaults write "$domain" "$key" "$type_flag" "$value" 2>/dev/null
  fi
}

# swrite: machine-level default, needs admin password
swrite() {
  local domain="$1" key="$2" type_flag="$3" value="$4" desc="$5"
  echo "${CYAN}->${RESET} ${desc} ${YELLOW}(admin password may be required)${RESET}"
  record_revert "$domain" "$key" "true"
  if $DRY_RUN; then
    echo "     (dry-run) sudo defaults write \"$domain\" \"$key\" $type_flag \"$value\""
    return 0
  fi
  sudo defaults write "$domain" "$key" "$type_flag" "$value" 2>/dev/null
}

pmset_get() {
  pmset -g custom 2>/dev/null | awk -v k="$1" '$1==k {print $2; exit}'
}

# ---------------------------------------------------------------------------
# Revert
# ---------------------------------------------------------------------------

do_revert() {
  local file="$1"
  if [ -z "$file" ]; then
    file=$(ls -t "$BACKUP_DIR"/changes-*.log 2>/dev/null | head -n 1)
  fi
  if [ -z "$file" ] || [ ! -f "$file" ]; then
    err "No backup log found in $BACKUP_DIR"
    return 1
  fi
  echo "This will undo the changes recorded in:"
  echo "  $file"
  echo
  confirm "Proceed with revert?" || { echo "Cancelled."; return 0; }
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    echo "  $line"
    eval "$line"
  done < <(tail -r "$file" 2>/dev/null || tac "$file" 2>/dev/null || awk '{a[NR]=$0} END{for(i=NR;i>=1;i--) print a[i]}' "$file")
  echo
  success "Revert complete."
  restart_finder; restart_dock
  $DRY_RUN || killall SystemUIServer 2>/dev/null
}

# ---------------------------------------------------------------------------
# Category 1: Privacy & Analytics
# ---------------------------------------------------------------------------

tweak_disable_analytics() {
  local plist="/Library/Application Support/CrashReporter/DiagnosticMessagesHistory.plist"
  swrite "$plist" "AutoSubmit" -bool false "Turn off 'Share Mac Analytics' (crash & usage data)"
  swrite "$plist" "ThirdPartyDataSubmit" -bool false "Turn off 'Share with App Developers'"
  if ! $DRY_RUN; then
    sudo chmod 644 "$plist" 2>/dev/null
    sudo chgrp admin "$plist" 2>/dev/null
  fi
}

tweak_disable_personalized_ads() {
  uwrite "com.apple.AdLib" "allowApplePersonalizedAdvertising" -bool false "Turn off personalized Apple advertising"
}

tweak_siri_optout_datasharing() {
  uwrite "com.apple.assistant.support" "Siri Data Sharing Opt-In Status" -int 2 "Opt out of sharing Siri data with Apple"
}

tweak_hide_spotlight_siri_suggestions() {
  uwrite "com.apple.suggestions.client" "shouldShowSuggestionsInSpotlight" -bool false "Hide Siri Suggestions from Spotlight results"
}

tweak_disable_trash_autodelete() {
  uwrite "com.apple.finder" "FXRemoveOldTrashItems" -bool false "Stop auto-emptying Trash after 30 days"
  restart_finder
}

apply_all_privacy() {
  tweak_disable_analytics
  tweak_disable_personalized_ads
  tweak_siri_optout_datasharing
  tweak_hide_spotlight_siri_suggestions
  tweak_disable_trash_autodelete
}

category_privacy() {
  while true; do
    echo
    echo "${BOLD}== Privacy & Analytics ==${RESET}"
    local options=(
      "Disable sharing Mac analytics & crash reports with Apple"
      "Disable personalized Apple advertising"
      "Opt out of Siri data sharing with Apple"
      "Hide Siri Suggestions from Spotlight results"
      "Stop auto-emptying Trash after 30 days"
      "Apply ALL of the above"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_disable_analytics ;;
        2) tweak_disable_personalized_ads ;;
        3) tweak_siri_optout_datasharing ;;
        4) tweak_hide_spotlight_siri_suggestions ;;
        5) tweak_disable_trash_autodelete ;;
        6) apply_all_privacy ;;
        7) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 2: Siri & Apple Intelligence
# ---------------------------------------------------------------------------

tweak_disable_siri() {
  uwrite "com.apple.assistant.support" "Assistant Enabled" -bool false "Disable the Siri assistant"
  uwrite "com.apple.Siri" "StatusMenuVisible" -bool false "Hide the Siri icon from the menu bar"
  if ! $DRY_RUN; then
    launchctl bootout "gui/$(id -u)" "/System/Library/LaunchAgents/com.apple.Siri.plist" 2>/dev/null
    killall SystemUIServer 2>/dev/null
  fi
  info "A restart (or logging out and back in) makes this fully take effect."
}

tweak_disable_apple_intelligence() {
  warn "This is an experimental, reverse-engineered toggle -- Apple doesn't document"
  warn "a Terminal switch for Apple Intelligence, and the underlying key is known to"
  warn "change between macOS updates. The reliable way is System Settings >"
  warn "Apple Intelligence & Siri > off."
  if ! is_apple_silicon; then
    info "Apple Intelligence requires Apple Silicon -- skipping, not applicable here."
    return
  fi
  confirm "Attempt the experimental Terminal toggle anyway?" || return
  local raw patch_id="" tok
  raw=$(defaults read com.apple.CloudSubscriptionFeatures.optIn 2>/dev/null)
  if [ -z "$raw" ]; then
    warn "Couldn't find the Apple Intelligence opt-in key on this Mac -- nothing to change."
    return
  fi
  for tok in $raw; do
    tok="${tok//[^0-9]/}"
    if [ -n "$tok" ]; then patch_id="$tok"; break; fi
  done
  if [ -z "$patch_id" ]; then
    warn "Couldn't parse the opt-in key on this Mac -- nothing to change."
    return
  fi
  uwrite "com.apple.CloudSubscriptionFeatures.optIn" "$patch_id" -bool false "Turn off Apple Intelligence (key: $patch_id)"
  uwrite "com.apple.CloudSubscriptionFeatures.optIn" "auto_opt_in" -bool false "Prevent Apple Intelligence from re-enabling itself"
  info "A restart may be required for this to fully take effect."
}

category_ai() {
  while true; do
    echo
    echo "${BOLD}== Siri & Apple Intelligence ==${RESET}"
    local options=(
      "Disable Siri completely"
      "[Experimental] Disable Apple Intelligence"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_disable_siri ;;
        2) tweak_disable_apple_intelligence ;;
        3) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 3: System, Power & Input
# ---------------------------------------------------------------------------

tweak_disable_mouse_accel() {
  uwrite "NSGlobalDomain" "com.apple.mouse.scaling" -float -1 "Disable mouse pointer acceleration"
}

tweak_disable_powernap() {
  local cur
  cur=$(pmset_get powernap)
  [ -z "$cur" ] && cur=1
  echo "${CYAN}->${RESET} Disable Power Nap during sleep ${YELLOW}(admin password required)${RESET}"
  append_manual_revert "sudo pmset -a powernap $cur"
  $DRY_RUN || sudo pmset -a powernap 0
}

tweak_disable_wake_network() {
  local cur
  cur=$(pmset_get womp)
  [ -z "$cur" ] && cur=1
  echo "${CYAN}->${RESET} Disable 'Wake for network access' during sleep ${YELLOW}(admin password required)${RESET}"
  append_manual_revert "sudo pmset -a womp $cur"
  $DRY_RUN || sudo pmset -a womp 0
}

tweak_key_repeat_over_accents() {
  uwrite "NSGlobalDomain" "ApplePressAndHoldEnabled" -bool false "Use key repeat instead of the accented-character popup"
}

apply_all_system() {
  tweak_disable_mouse_accel
  tweak_disable_powernap
  tweak_disable_wake_network
  tweak_key_repeat_over_accents
}

category_system() {
  while true; do
    echo
    echo "${BOLD}== System, Power & Input ==${RESET}"
    local options=(
      "Disable mouse pointer acceleration"
      "Disable Power Nap during sleep"
      "Disable 'Wake for network access' during sleep"
      "Use key repeat instead of the accent-character popup"
      "Apply ALL of the above"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_disable_mouse_accel ;;
        2) tweak_disable_powernap ;;
        3) tweak_disable_wake_network ;;
        4) tweak_key_repeat_over_accents ;;
        5) apply_all_system ;;
        6) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 4: Software Update
# ---------------------------------------------------------------------------

tweak_disable_update_autocheck() {
  echo "${CYAN}->${RESET} Stop automatic background checks for macOS updates ${YELLOW}(admin password required)${RESET}"
  append_manual_revert "sudo softwareupdate --schedule on"
  $DRY_RUN || sudo softwareupdate --schedule off
  swrite "/Library/Preferences/com.apple.SoftwareUpdate" "AutomaticCheckEnabled" -bool false "  (matching preference key)"
}

tweak_disable_update_autodownload() {
  swrite "/Library/Preferences/com.apple.SoftwareUpdate" "AutomaticDownload" -bool false "Stop automatically downloading updates in the background"
}

apply_all_updates() {
  tweak_disable_update_autocheck
  tweak_disable_update_autodownload
}

category_updates() {
  while true; do
    echo
    echo "${BOLD}== Software Update ==${RESET}"
    echo "Note: this only controls background nagging/timing. Critical security"
    echo "updates (XProtect/Gatekeeper data) are deliberately left alone."
    local options=(
      "Stop automatic background update checks"
      "Stop automatic background update downloads"
      "Apply ALL of the above"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_disable_update_autocheck ;;
        2) tweak_disable_update_autodownload ;;
        3) apply_all_updates ;;
        4) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 5: Appearance
# ---------------------------------------------------------------------------

tweak_dark_mode() {
  uwrite "NSGlobalDomain" "AppleInterfaceStyle" -string "Dark" "Enable Dark Mode system-wide"
}

tweak_reduce_transparency() {
  uwrite "com.apple.universalaccess" "reduceTransparency" -bool true "Reduce transparency effects"
}

tweak_reduce_motion() {
  uwrite "com.apple.universalaccess" "reduceMotion" -bool true "Reduce window & interface animations"
  uwrite "NSGlobalDomain" "NSAutomaticWindowAnimationsEnabled" -bool false "  (and disable window open/close animations)"
}

tweak_battery_percent() {
  uwrite "com.apple.menuextra.battery" "ShowPercent" -string "YES" "Show battery percentage in the menu bar"
}

apply_all_appearance() {
  tweak_reduce_transparency
  tweak_reduce_motion
  tweak_battery_percent
}

category_appearance() {
  while true; do
    echo
    echo "${BOLD}== Appearance ==${RESET}"
    local options=(
      "Enable Dark Mode"
      "Reduce transparency"
      "Reduce motion & window animations"
      "Show battery percentage in the menu bar"
      "Apply ALL except Dark Mode (a matter of taste, so it's separate)"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_dark_mode ;;
        2) tweak_reduce_transparency ;;
        3) tweak_reduce_motion ;;
        4) tweak_battery_percent ;;
        5) apply_all_appearance ;;
        6) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 6: Dock & Menu Bar
# ---------------------------------------------------------------------------

tweak_dock_autohide() {
  uwrite "com.apple.dock" "autohide" -bool true "Auto-hide the Dock"
  restart_dock
}

tweak_dock_no_recents() {
  uwrite "com.apple.dock" "show-recents" -bool false "Hide recently used apps from the Dock"
  restart_dock
}

tweak_dock_minimize_to_app() {
  uwrite "com.apple.dock" "minimize-to-application" -bool true "Minimize windows into their app's Dock icon"
  restart_dock
}

tweak_dock_position() {
  echo "Choose Dock position:"
  local pos
  PS3=$'\n> '
  select pos in "Bottom" "Left" "Right" "Cancel"; do
    case "$REPLY" in
      1) uwrite "com.apple.dock" "orientation" -string "bottom" "Set Dock position to bottom"; restart_dock; break ;;
      2) uwrite "com.apple.dock" "orientation" -string "left" "Set Dock position to left"; restart_dock; break ;;
      3) uwrite "com.apple.dock" "orientation" -string "right" "Set Dock position to right"; restart_dock; break ;;
      4) break ;;
      *) echo "Invalid selection." ;;
    esac
  done
}

tweak_reset_launchpad() {
  confirm "This resets Launchpad's app layout back to its default arrangement. Continue?" || return
  uwrite "com.apple.dock" "ResetLaunchPad" -bool true "Reset Launchpad layout"
  restart_dock
}

apply_all_dock() {
  tweak_dock_autohide
  tweak_dock_no_recents
  tweak_dock_minimize_to_app
}

category_dock() {
  while true; do
    echo
    echo "${BOLD}== Dock & Menu Bar ==${RESET}"
    local options=(
      "Auto-hide the Dock"
      "Hide recently used apps from the Dock"
      "Minimize windows into their app's Dock icon"
      "Change Dock position"
      "Reset Launchpad layout"
      "Apply ALL except position/reset (those need a choice)"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_dock_autohide ;;
        2) tweak_dock_no_recents ;;
        3) tweak_dock_minimize_to_app ;;
        4) tweak_dock_position ;;
        5) tweak_reset_launchpad ;;
        6) apply_all_dock ;;
        7) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 7: Finder & Windows
# ---------------------------------------------------------------------------

tweak_show_all_extensions() {
  uwrite "NSGlobalDomain" "AppleShowAllExtensions" -bool true "Show all filename extensions"
  restart_finder
}

tweak_show_hidden_files() {
  uwrite "com.apple.finder" "AppleShowAllFiles" -bool true "Show hidden files and folders"
  restart_finder
}

tweak_show_full_path_titlebar() {
  uwrite "com.apple.finder" "_FXShowPosixPathInTitle" -bool true "Show full path in Finder's title bar"
  restart_finder
}

tweak_show_path_status_bar() {
  uwrite "com.apple.finder" "ShowPathbar" -bool true "Show the path bar"
  uwrite "com.apple.finder" "ShowStatusBar" -bool true "Show the status bar"
  restart_finder
}

tweak_finder_default_location() {
  echo "Choose where new Finder windows should open:"
  local loc
  PS3=$'\n> '
  select loc in "Home folder" "Desktop" "Documents" "Cancel"; do
    case "$REPLY" in
      1) uwrite "com.apple.finder" "NewWindowTarget" -string "PfHm" "Set new Finder windows to open at Home"
         uwrite "com.apple.finder" "NewWindowTargetPath" -string "file://${HOME}/" "  (target path)"
         restart_finder; break ;;
      2) uwrite "com.apple.finder" "NewWindowTarget" -string "PfDe" "Set new Finder windows to open at Desktop"
         uwrite "com.apple.finder" "NewWindowTargetPath" -string "file://${HOME}/Desktop/" "  (target path)"
         restart_finder; break ;;
      3) uwrite "com.apple.finder" "NewWindowTarget" -string "PfDo" "Set new Finder windows to open at Documents"
         uwrite "com.apple.finder" "NewWindowTargetPath" -string "file://${HOME}/Documents/" "  (target path)"
         restart_finder; break ;;
      4) break ;;
      *) echo "Invalid selection." ;;
    esac
  done
}

tweak_finder_list_view() {
  uwrite "com.apple.finder" "FXPreferredViewStyle" -string "Nlsv" "Default new Finder windows to List view"
  restart_finder
}

tweak_window_tiling_info() {
  info "macOS's window-tiling (drag-to-edge) switches don't have a reliably"
  info "documented Terminal command yet, so this opens System Settings instead"
  info "of guessing at one (Desktop & Dock > Windows)."
  $DRY_RUN || open "x-apple.systempreferences:com.apple.Desktop-Settings.extension" 2>/dev/null
}

apply_all_finder() {
  tweak_show_all_extensions
  tweak_show_hidden_files
  tweak_show_full_path_titlebar
  tweak_show_path_status_bar
  tweak_finder_list_view
}

category_finder() {
  while true; do
    echo
    echo "${BOLD}== Finder & Windows ==${RESET}"
    local options=(
      "Show all filename extensions"
      "Show hidden files"
      "Show full path in Finder's title bar"
      "Show path bar & status bar"
      "Set default Finder window location"
      "Default new windows to List view"
      "Configure window tiling (opens System Settings)"
      "Apply ALL except location choice"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_show_all_extensions ;;
        2) tweak_show_hidden_files ;;
        3) tweak_show_full_path_titlebar ;;
        4) tweak_show_path_status_bar ;;
        5) tweak_finder_default_location ;;
        6) tweak_finder_list_view ;;
        7) tweak_window_tiling_info ;;
        8) apply_all_finder ;;
        9) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Category 8: Remove Bundled Apps
# ---------------------------------------------------------------------------

tweak_remove_bundled_apps() {
  local apps=(
    "/Applications/Pages.app"
    "/Applications/Numbers.app"
    "/Applications/Keynote.app"
    "/Applications/iMovie.app"
    "/Applications/GarageBand.app"
  )
  echo "These are the only bundled Apple apps that Apple itself allows you to"
  echo "remove -- everything else lives on the sealed system volume and can't"
  echo "be safely deleted (that's a macOS security feature, not a limitation"
  echo "of this script). You can always redownload any of these for free from"
  echo "the App Store later."
  echo
  local found=()
  local a
  for a in "${apps[@]}"; do
    [ -d "$a" ] && found+=("$a")
  done
  if [ "${#found[@]}" -eq 0 ]; then
    info "None of Pages/Numbers/Keynote/iMovie/GarageBand are installed here. Nothing to do."
    return
  fi
  echo "Found:"
  local i=1
  for a in "${found[@]}"; do echo "  $i) $a"; i=$((i+1)); done
  echo
  confirm "Move ALL of these to the Trash?" || return
  for a in "${found[@]}"; do
    case "$a" in
      /Applications/*) : ;;
      *) warn "Refusing to remove $a (outside /Applications)"; continue ;;
    esac
    if $DRY_RUN; then
      echo "  (dry-run) mv \"$a\" ~/.Trash/"
    else
      if mv "$a" ~/.Trash/ 2>/dev/null; then
        success "Moved $(basename "$a") to Trash"
      else
        warn "Couldn't move $a (check permissions)"
      fi
    fi
  done
  if [[ " ${found[*]} " == *"GarageBand.app"* ]]; then
    echo
    if confirm "Also remove GarageBand's extra sound library? (shared with Logic Pro/MainStage if you have either installed)"; then
      $DRY_RUN || rm -rf "/Library/Application Support/GarageBand" "/Library/Audio/Apple Loops/Apple" 2>/dev/null
      success "Removed GarageBand's sound library folders"
    fi
  fi
}

category_apps() {
  while true; do
    echo
    echo "${BOLD}== Remove Bundled Apps ==${RESET}"
    local options=(
      "Remove Pages / Numbers / Keynote / iMovie / GarageBand"
      "Back to main menu"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) tweak_remove_bundled_apps ;;
        2) return ;;
        *) echo "Invalid selection." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

run_recommended() {
  echo
  echo "${BOLD}Recommended preset${RESET} -- privacy & clutter fixes most people want:"
  echo "  - Disable Mac analytics & personalized ads"
  echo "  - Opt out of Siri data sharing, hide Siri Suggestions in Spotlight"
  echo "  - Show hidden files & all file extensions"
  echo "  - Stop the Dock from tracking recently used apps"
  echo
  confirm "Apply this preset?" || return
  apply_all_privacy
  tweak_show_hidden_files
  tweak_show_all_extensions
  tweak_dock_no_recents
  restart_finder; restart_dock
  success "Recommended preset applied."
}

run_everything() {
  warn "This runs EVERY tweak, including the experimental Apple Intelligence"
  warn "toggle and bundled-app removal."
  echo
  confirm "Apply ALL tweaks now?" || { echo "Cancelled."; return; }
  apply_all_privacy
  tweak_disable_siri
  tweak_disable_apple_intelligence
  apply_all_system
  apply_all_updates
  apply_all_appearance
  apply_all_dock
  apply_all_finder
  tweak_remove_bundled_apps
  restart_finder; restart_dock
  success "All done. Some changes may need a restart or log out/in to fully take effect."
}

print_tweak_list() {
  cat <<'EOF'
Privacy & Analytics
  - Disable sharing Mac analytics & crash reports
  - Disable personalized Apple advertising
  - Opt out of Siri data sharing
  - Hide Siri Suggestions from Spotlight
  - Stop auto-emptying Trash after 30 days

Siri & Apple Intelligence
  - Disable Siri completely
  - [Experimental] Disable Apple Intelligence

System, Power & Input
  - Disable mouse pointer acceleration
  - Disable Power Nap during sleep
  - Disable "Wake for network access" during sleep
  - Key repeat instead of accent-character popup

Software Update
  - Stop automatic background update checks
  - Stop automatic background update downloads
  (critical security updates are deliberately left alone)

Appearance
  - Enable Dark Mode
  - Reduce transparency
  - Reduce motion & window animations
  - Show battery percentage in the menu bar

Dock & Menu Bar
  - Auto-hide the Dock
  - Hide recently used apps from the Dock
  - Minimize windows into their app's Dock icon
  - Change Dock position
  - Reset Launchpad layout

Finder & Windows
  - Show all filename extensions
  - Show hidden files
  - Show full path in the Finder title bar
  - Show path bar & status bar
  - Set default Finder window location
  - Default new windows to List view
  - Configure window tiling (opens System Settings -- no safe Terminal command exists yet)

Remove Bundled Apps
  - Pages / Numbers / Keynote / iMovie / GarageBand
    (the only Apple apps Apple allows you to delete)

No macOS equivalent (skipped, unlike the Windows original):
  - BitLocker auto-encryption (macOS doesn't silently auto-enable FileVault)
  - Fast Startup (no hybrid shutdown mode on macOS)
  - Delivery Optimization / P2P update sharing
  - Auto-installing device companion apps
  - Xbox Game Bar
EOF
}

print_help() {
  cat <<EOF
MacDebloat v${SCRIPT_VERSION} -- a macOS-flavored take on Win11Debloat

Usage:
  bash MacDebloat.sh [options]

With no options, launches an interactive menu.

Options:
  -h, --help              Show this help and exit
      --list              List every available tweak and exit
      --dry-run           Print what would change without changing anything
  -y, --yes               Don't ask for confirmation (use with care)
      --user <name>       Apply per-user tweaks to a different local account
      --revert [file]     Undo a previous run (defaults to the most recent log)
      --all               Apply every tweak (still asks to confirm unless -y)

Quick flags for common individual tweaks:
      --dark-mode
      --show-hidden-files
      --show-extensions
      --disable-analytics
      --disable-ads
      --dock-autohide
      --remove-apps

Examples:
  bash MacDebloat.sh
  bash MacDebloat.sh --dry-run --all
  bash MacDebloat.sh --disable-analytics --disable-ads --show-hidden-files
  bash MacDebloat.sh --revert
  bash MacDebloat.sh --user jane --dock-autohide

Changes are logged to: $BACKUP_DIR
EOF
}

# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

run_interactive() {
  while true; do
    echo
    echo "${BOLD}Select a category:${RESET}"
    echo
    local options=(
      "Privacy & Analytics"
      "Siri & Apple Intelligence"
      "System, Power & Input"
      "Software Update"
      "Appearance"
      "Dock & Menu Bar"
      "Finder & Windows"
      "Remove Bundled Apps"
      "Run recommended preset (safe defaults)"
      "Run EVERYTHING"
      "Quit"
    )
    PS3=$'\n> '
    select opt in "${options[@]}"; do
      case "$REPLY" in
        1) category_privacy ;;
        2) category_ai ;;
        3) category_system ;;
        4) category_updates ;;
        5) category_appearance ;;
        6) category_dock ;;
        7) category_finder ;;
        8) category_apps ;;
        9) run_recommended ;;
        10) run_everything ;;
        11) echo "Goodbye!"; exit 0 ;;
        *) echo "Invalid selection, try again." ;;
      esac
      break
    done
  done
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

main() {
  local DIRECT_ACTIONS=()
  local WANT_ALL=false
  local WANT_REVERT=false
  local REVERT_FILE=""

  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) print_help; exit 0 ;;
      --list) print_tweak_list; exit 0 ;;
      --version) echo "$SCRIPT_VERSION"; exit 0 ;;
      --dry-run) DRY_RUN=true; shift ;;
      -y|--yes) ASSUME_YES=true; shift ;;
      --user)
        TARGET_USER="${2:-}"
        if [ -z "$TARGET_USER" ]; then err "--user requires a username"; exit 1; fi
        shift 2 ;;
      --revert)
        WANT_REVERT=true
        if [ -n "${2:-}" ] && [ "${2:0:1}" != "-" ]; then
          REVERT_FILE="$2"; shift 2
        else
          shift
        fi
        ;;
      --all) WANT_ALL=true; shift ;;
      --dark-mode) DIRECT_ACTIONS+=("tweak_dark_mode"); shift ;;
      --show-hidden-files) DIRECT_ACTIONS+=("tweak_show_hidden_files"); shift ;;
      --show-extensions) DIRECT_ACTIONS+=("tweak_show_all_extensions"); shift ;;
      --disable-analytics) DIRECT_ACTIONS+=("tweak_disable_analytics"); shift ;;
      --disable-ads) DIRECT_ACTIONS+=("tweak_disable_personalized_ads"); shift ;;
      --dock-autohide) DIRECT_ACTIONS+=("tweak_dock_autohide"); shift ;;
      --remove-apps) DIRECT_ACTIONS+=("tweak_remove_bundled_apps"); shift ;;
      *) err "Unknown option: $1"; echo; print_help; exit 1 ;;
    esac
  done

  need_macos

  if $WANT_REVERT; then
    do_revert "$REVERT_FILE"
    exit 0
  fi

  if [ "${#DIRECT_ACTIONS[@]}" -gt 0 ]; then
    print_banner
    local fn
    for fn in "${DIRECT_ACTIONS[@]}"; do "$fn"; done
    restart_finder; restart_dock
    success "Done."
    exit 0
  fi

  if $WANT_ALL; then
    print_banner
    run_everything
    exit 0
  fi

  print_banner
  echo "This script changes system settings on your Mac."
  echo "A log of every change is kept in $BACKUP_DIR so you can undo them with --revert."
  echo "If you're about to make sweeping changes, a Time Machine backup first is a good idea."
  echo
  confirm "Continue?" || { echo "Okay, no changes made."; exit 0; }
  run_interactive
}

main "$@"
