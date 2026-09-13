"""
The tweak catalog: every setting deblaot can change, ported one-for-one
from MacDebloat.sh's category/tweak structure. Each Tweak wraps a small
apply function that takes (run_id, param) and returns (success, message);
run_id is threaded through to engine.defaults_write so every change records
what it takes to undo just that change.

MacDebloat.sh stays the reference implementation for the exact `defaults`
domains/keys/values used here -- this module mirrors it rather than
reinventing the settings from scratch, so the two should always agree.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import engine, history

CATEGORIES: dict[str, str] = {
    "privacy": "Privacy & Analytics",
    "ai": "Siri & Apple Intelligence",
    "system": "System, Power & Input",
    "updates": "Software Update",
    "appearance": "Appearance",
    "dock": "Dock & Menu Bar",
    "finder": "Finder & Windows",
    "apps": "Remove Bundled Apps",
}

RECOMMENDED_PRESET: list[str] = [
    "disable-analytics",
    "disable-ads",
    "siri-optout-datasharing",
    "hide-spotlight-siri-suggestions",
    "disable-trash-autodelete",
    "show-hidden-files",
    "show-all-extensions",
    "dock-no-recents",
]


@dataclass
class Tweak:
    id: str
    category: str
    title: str
    description: str
    requires_admin: bool = False
    experimental: bool = False
    parameters: Optional[list[str]] = None
    apply_fn: Callable[[str, Optional[str]], tuple[bool, str]] = field(default=None, repr=False)


REGISTRY: dict[str, Tweak] = {}


def register(t: Tweak) -> Tweak:
    REGISTRY[t.id] = t
    return t


def simple_defaults(
    id: str, category: str, title: str, description: str,
    domain: str, key: str, type_flag: str, value: str,
    admin: bool = False, restart: Optional[str] = None,
) -> Tweak:
    def _apply(run_id: str, param: Optional[str] = None) -> tuple[bool, str]:
        ok, msg = engine.defaults_write(domain, key, type_flag, value, admin=admin, run_id=run_id, tweak_id=id)
        if ok and restart:
            engine.restart_app(restart)
        return ok, msg
    return register(Tweak(id, category, title, description, requires_admin=admin, apply_fn=_apply))


# ---------------------------------------------------------------------------
# Privacy & Analytics
# ---------------------------------------------------------------------------

def _apply_disable_analytics(run_id: str, param=None):
    plist = "/Library/Application Support/CrashReporter/DiagnosticMessagesHistory.plist"
    ok1, msg1 = engine.defaults_write(plist, "AutoSubmit", "-bool", "false", admin=True, run_id=run_id, tweak_id="disable-analytics")
    ok2, msg2 = engine.defaults_write(plist, "ThirdPartyDataSubmit", "-bool", "false", admin=True, run_id=run_id, tweak_id="disable-analytics")
    if not (ok1 and ok2):
        return False, f"Write failed: {msg1 if not ok1 else msg2}"
    engine.run_privileged(["chmod", "644", plist])
    engine.run_privileged(["chgrp", "admin", plist])
    return True, "Mac analytics & crash-report sharing disabled"


register(Tweak(
    "disable-analytics", "privacy", "Disable sharing Mac analytics & crash reports",
    "Turns off 'Share Mac Analytics' and 'Share with App Developers'.",
    requires_admin=True, apply_fn=_apply_disable_analytics,
))

simple_defaults(
    "disable-ads", "privacy", "Disable personalized Apple advertising",
    "Opts out of Apple's personalized-advertising identifier.",
    "com.apple.AdLib", "allowApplePersonalizedAdvertising", "-bool", "false",
)

simple_defaults(
    "siri-optout-datasharing", "privacy", "Opt out of Siri data sharing",
    "Stops sharing Siri interaction data with Apple.",
    "com.apple.assistant.support", "Siri Data Sharing Opt-In Status", "-int", "2",
)

simple_defaults(
    "hide-spotlight-siri-suggestions", "privacy", "Hide Siri Suggestions from Spotlight",
    "Removes the Siri Suggestions section from Spotlight search results.",
    "com.apple.suggestions.client", "shouldShowSuggestionsInSpotlight", "-bool", "false",
)

simple_defaults(
    "disable-trash-autodelete", "privacy", "Stop auto-emptying Trash after 30 days",
    "Keeps items in the Trash until you empty it yourself.",
    "com.apple.finder", "FXRemoveOldTrashItems", "-bool", "false", restart="Finder",
)

# ---------------------------------------------------------------------------
# Siri & Apple Intelligence
# ---------------------------------------------------------------------------

def _apply_disable_siri(run_id: str, param=None):
    ok1, msg1 = engine.defaults_write("com.apple.assistant.support", "Assistant Enabled", "-bool", "false", run_id=run_id, tweak_id="disable-siri")
    ok2, msg2 = engine.defaults_write("com.apple.Siri", "StatusMenuVisible", "-bool", "false", run_id=run_id, tweak_id="disable-siri")
    if not (ok1 and ok2):
        return False, f"Write failed: {msg1 if not ok1 else msg2}"
    engine.run_user(["killall", "SystemUIServer"])
    return True, "Siri disabled -- a restart or log out/in fully applies this"


register(Tweak(
    "disable-siri", "ai", "Disable Siri completely",
    "Disables the Siri assistant and hides its menu bar icon.",
    apply_fn=_apply_disable_siri,
))


def _apply_disable_apple_intelligence(run_id: str, param=None):
    raw = engine.defaults_read_domain("com.apple.CloudSubscriptionFeatures.optIn")
    if not raw:
        return False, "No Apple Intelligence opt-in key found on this Mac -- nothing to change"
    patch_id = None
    for tok in raw.split():
        digits = "".join(c for c in tok if c.isdigit())
        if digits:
            patch_id = digits
            break
    if not patch_id:
        return False, "Could not parse the opt-in key on this Mac"
    ok1, msg1 = engine.defaults_write("com.apple.CloudSubscriptionFeatures.optIn", patch_id, "-bool", "false", run_id=run_id, tweak_id="disable-apple-intelligence")
    ok2, msg2 = engine.defaults_write("com.apple.CloudSubscriptionFeatures.optIn", "auto_opt_in", "-bool", "false", run_id=run_id, tweak_id="disable-apple-intelligence")
    if ok1 and ok2:
        return True, f"Apple Intelligence opt-in disabled (key: {patch_id}); a restart may be required"
    return False, f"Write failed: {msg1 if not ok1 else msg2}"


register(Tweak(
    "disable-apple-intelligence", "ai", "[Experimental] Disable Apple Intelligence",
    "Reverse-engineered toggle -- the underlying key has changed across macOS "
    "updates before. System Settings > Apple Intelligence & Siri is the reliable path.",
    experimental=True, apply_fn=_apply_disable_apple_intelligence,
))

# ---------------------------------------------------------------------------
# System, Power & Input
# ---------------------------------------------------------------------------

simple_defaults(
    "disable-mouse-accel", "system", "Disable mouse pointer acceleration",
    "Sets pointer speed to a flat, unaccelerated scale.",
    "NSGlobalDomain", "com.apple.mouse.scaling", "-float", "-1",
)


def _pmset_get(key: str) -> Optional[str]:
    result = engine.run_user(["pmset", "-g", "custom"])
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == key:
            return parts[1]
    return None


def _apply_disable_powernap(run_id: str, param=None):
    cur = _pmset_get("powernap") or "1"
    history.record(run_id, "disable-powernap", "shell", requires_admin=True,
                    revert_shell_cmd=f"pmset -a powernap {cur}")
    result = engine.run_privileged(["pmset", "-a", "powernap", "0"])
    if result.ok:
        return True, "Power Nap disabled during sleep"
    return False, f"Failed: {result.output}"


register(Tweak(
    "disable-powernap", "system", "Disable Power Nap during sleep",
    "Stops background wake-ups during sleep to save battery.",
    requires_admin=True, apply_fn=_apply_disable_powernap,
))


def _apply_disable_wake_network(run_id: str, param=None):
    cur = _pmset_get("womp") or "1"
    history.record(run_id, "disable-wake-network", "shell", requires_admin=True,
                    revert_shell_cmd=f"pmset -a womp {cur}")
    result = engine.run_privileged(["pmset", "-a", "womp", "0"])
    if result.ok:
        return True, "'Wake for network access' disabled during sleep"
    return False, f"Failed: {result.output}"


register(Tweak(
    "disable-wake-network", "system", "Disable 'Wake for network access'",
    "Stops the Mac waking for network activity during sleep.",
    requires_admin=True, apply_fn=_apply_disable_wake_network,
))

simple_defaults(
    "key-repeat-over-accents", "system", "Use key repeat instead of the accent popup",
    "Holding a key repeats it instead of showing the accented-character menu.",
    "NSGlobalDomain", "ApplePressAndHoldEnabled", "-bool", "false",
)

# ---------------------------------------------------------------------------
# Software Update
# ---------------------------------------------------------------------------

def _apply_disable_update_autocheck(run_id: str, param=None):
    history.record(run_id, "disable-update-autocheck", "shell", requires_admin=True,
                    revert_shell_cmd="softwareupdate --schedule on")
    r1 = engine.run_privileged(["softwareupdate", "--schedule", "off"])
    ok2, msg2 = engine.defaults_write(
        "/Library/Preferences/com.apple.SoftwareUpdate", "AutomaticCheckEnabled",
        "-bool", "false", admin=True, run_id=run_id, tweak_id="disable-update-autocheck",
    )
    if r1.ok and ok2:
        return True, "Automatic update checks disabled (critical security updates are untouched)"
    return False, f"Failed: {r1.output if not r1.ok else msg2}"


register(Tweak(
    "disable-update-autocheck", "updates", "Stop automatic background update checks",
    "Critical security patches (XProtect/Gatekeeper data) are deliberately left alone.",
    requires_admin=True, apply_fn=_apply_disable_update_autocheck,
))

simple_defaults(
    "disable-update-autodownload", "updates", "Stop automatic background update downloads",
    "Critical security patches are deliberately left alone.",
    "/Library/Preferences/com.apple.SoftwareUpdate", "AutomaticDownload", "-bool", "false",
    admin=True,
)

# ---------------------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------------------

simple_defaults(
    "dark-mode", "appearance", "Enable Dark Mode",
    "Switches the whole system to Dark Mode.",
    "NSGlobalDomain", "AppleInterfaceStyle", "-string", "Dark",
)

simple_defaults(
    "reduce-transparency", "appearance", "Reduce transparency",
    "Improves contrast and can help performance on older Macs.",
    "com.apple.universalaccess", "reduceTransparency", "-bool", "true",
)


def _apply_reduce_motion(run_id: str, param=None):
    ok1, msg1 = engine.defaults_write("com.apple.universalaccess", "reduceMotion", "-bool", "true", run_id=run_id, tweak_id="reduce-motion")
    ok2, msg2 = engine.defaults_write("NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "-bool", "false", run_id=run_id, tweak_id="reduce-motion")
    if ok1 and ok2:
        return True, "Motion & window animations reduced"
    return False, f"Write failed: {msg1 if not ok1 else msg2}"


register(Tweak(
    "reduce-motion", "appearance", "Reduce motion & window animations",
    "Turns off window open/close and other interface animations.",
    apply_fn=_apply_reduce_motion,
))

simple_defaults(
    "battery-percent", "appearance", "Show battery percentage in the menu bar",
    "Adds a numeric percentage next to the battery icon.",
    "com.apple.menuextra.battery", "ShowPercent", "-string", "YES",
)

# ---------------------------------------------------------------------------
# Dock & Menu Bar
# ---------------------------------------------------------------------------

simple_defaults(
    "dock-autohide", "dock", "Auto-hide the Dock",
    "Hides the Dock until you move your pointer to the screen edge.",
    "com.apple.dock", "autohide", "-bool", "true", restart="Dock",
)

simple_defaults(
    "dock-no-recents", "dock", "Hide recently used apps from the Dock",
    "Removes the auto-populated 'recent apps' section.",
    "com.apple.dock", "show-recents", "-bool", "false", restart="Dock",
)

simple_defaults(
    "dock-minimize-to-app", "dock", "Minimize windows into their app's Dock icon",
    "Cleans up the right-hand side of the Dock.",
    "com.apple.dock", "minimize-to-application", "-bool", "true", restart="Dock",
)


def _apply_dock_position(run_id: str, param=None):
    if param not in ("bottom", "left", "right"):
        return False, "param must be one of: bottom, left, right"
    ok, msg = engine.defaults_write("com.apple.dock", "orientation", "-string", param, run_id=run_id, tweak_id="dock-position")
    if not ok:
        return False, f"Write failed: {msg}"
    engine.restart_app("Dock")
    return True, f"Dock moved to {param}"


register(Tweak(
    "dock-position", "dock", "Change Dock position",
    "Move the Dock to the bottom, left, or right edge of the screen.",
    parameters=["bottom", "left", "right"], apply_fn=_apply_dock_position,
))


def _apply_reset_launchpad(run_id: str, param=None):
    ok, msg = engine.defaults_write("com.apple.dock", "ResetLaunchPad", "-bool", "true", run_id=run_id, tweak_id="reset-launchpad")
    if not ok:
        return False, f"Write failed: {msg}"
    engine.restart_app("Dock")
    return True, "Launchpad layout reset to default"


register(Tweak(
    "reset-launchpad", "dock", "Reset Launchpad layout",
    "Restores Launchpad's default app arrangement.",
    apply_fn=_apply_reset_launchpad,
))

# ---------------------------------------------------------------------------
# Finder & Windows
# ---------------------------------------------------------------------------

simple_defaults(
    "show-all-extensions", "finder", "Show all filename extensions",
    "Shows extensions for every file type, not just some.",
    "NSGlobalDomain", "AppleShowAllExtensions", "-bool", "true", restart="Finder",
)

simple_defaults(
    "show-hidden-files", "finder", "Show hidden files",
    "Shows dotfiles and hidden folders in Finder.",
    "com.apple.finder", "AppleShowAllFiles", "-bool", "true", restart="Finder",
)

simple_defaults(
    "show-full-path-titlebar", "finder", "Show full path in Finder's title bar",
    "Displays the full POSIX path in every Finder window's title bar.",
    "com.apple.finder", "_FXShowPosixPathInTitle", "-bool", "true", restart="Finder",
)


def _apply_path_status_bar(run_id: str, param=None):
    ok1, msg1 = engine.defaults_write("com.apple.finder", "ShowPathbar", "-bool", "true", run_id=run_id, tweak_id="show-path-status-bar")
    ok2, msg2 = engine.defaults_write("com.apple.finder", "ShowStatusBar", "-bool", "true", run_id=run_id, tweak_id="show-path-status-bar")
    if not (ok1 and ok2):
        return False, f"Write failed: {msg1 if not ok1 else msg2}"
    engine.restart_app("Finder")
    return True, "Path bar & status bar shown in Finder windows"


register(Tweak(
    "show-path-status-bar", "finder", "Show path bar & status bar",
    "Shows both bars in every Finder window.",
    apply_fn=_apply_path_status_bar,
))

_LOCATIONS = {
    "home": ("PfHm", "{HOME}/"),
    "desktop": ("PfDe", "{HOME}/Desktop/"),
    "documents": ("PfDo", "{HOME}/Documents/"),
}


def _apply_finder_default_location(run_id: str, param=None):
    if param not in _LOCATIONS:
        return False, "param must be one of: home, desktop, documents"
    target, path_tpl = _LOCATIONS[param]
    path = "file://" + path_tpl.format(HOME=os.path.expanduser("~"))
    ok1, msg1 = engine.defaults_write("com.apple.finder", "NewWindowTarget", "-string", target, run_id=run_id, tweak_id="finder-default-location")
    ok2, msg2 = engine.defaults_write("com.apple.finder", "NewWindowTargetPath", "-string", path, run_id=run_id, tweak_id="finder-default-location")
    if not (ok1 and ok2):
        return False, f"Write failed: {msg1 if not ok1 else msg2}"
    engine.restart_app("Finder")
    return True, f"New Finder windows will open at {param}"


register(Tweak(
    "finder-default-location", "finder", "Set default Finder window location",
    "Choose where new Finder windows open.",
    parameters=["home", "desktop", "documents"], apply_fn=_apply_finder_default_location,
))

simple_defaults(
    "finder-list-view", "finder", "Default new windows to List view",
    "Sets List view as the default for new Finder windows.",
    "com.apple.finder", "FXPreferredViewStyle", "-string", "Nlsv", restart="Finder",
)


def _apply_window_tiling_info(run_id: str, param=None):
    result = engine.run_user(["open", "x-apple.systempreferences:com.apple.Desktop-Settings.extension"])
    if not result.ok:
        return False, f"Couldn't open System Settings: {result.output}"
    return True, "Opened System Settings > Desktop & Dock > Windows (no confirmed safe API for this exists yet)"


register(Tweak(
    "window-tiling-info", "finder", "Configure window tiling",
    "Opens System Settings -- there's no publicly confirmed command for "
    "Sequoia-style window tiling, so this doesn't guess at one.",
    apply_fn=_apply_window_tiling_info,
))

# ---------------------------------------------------------------------------
# Remove Bundled Apps
# ---------------------------------------------------------------------------

REMOVABLE_APPS = ["Pages", "Numbers", "Keynote", "iMovie", "GarageBand"]


def _apply_remove_bundled_apps(run_id: str, param=None):
    trash = Path.home() / ".Trash"
    trash.mkdir(exist_ok=True)
    moved = []
    for name in REMOVABLE_APPS:
        app_path = Path(f"/Applications/{name}.app")
        # Safety guard mirrors MacDebloat.sh: only ever touch /Applications,
        # never the sealed system volume under /System.
        if not str(app_path).startswith("/Applications/"):
            continue
        if not app_path.is_dir():
            continue
        try:
            shutil.move(str(app_path), str(trash / app_path.name))
            moved.append(name)
        except OSError:
            pass
    if not moved:
        return True, "None of Pages/Numbers/Keynote/iMovie/GarageBand were installed -- nothing to do"
    history.record(
        run_id, "remove-bundled-apps", "shell",
        note=f"Moved to Trash: {', '.join(moved)}",
        revert_shell_cmd=f"# moved to ~/.Trash: {', '.join(moved)} -- restore manually before emptying Trash",
    )
    return True, f"Moved to Trash: {', '.join(moved)}"


register(Tweak(
    "remove-bundled-apps", "apps", "Remove Pages / Numbers / Keynote / iMovie / GarageBand",
    "The only bundled Apple apps Apple allows you to delete. Moved to Trash, "
    "not permanently deleted, and all are free to redownload from the App Store.",
    apply_fn=_apply_remove_bundled_apps,
))
