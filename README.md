# MacDebloat

MacDebloat is a lightweight shell script that declutters and customizes macOS — no installation required. It's a macOS-flavored take on [Win11Debloat](https://github.com/Raphire/Win11Debloat): same idea (a menu-driven script that turns off telemetry, strips a handful of bundled apps, and tidies up the UI), rebuilt from scratch for a completely different OS.

> [!Warning]
> This changes system settings on your Mac. Every change is logged so it can be undone with `--revert`, but as with the project this is based on: use at your own risk, and consider a Time Machine backup first if you're running everything at once.

## Usage

### Quick method

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/<your-username>/<your-repo>/main/MacDebloat.sh)"
```

Replace `<your-username>/<your-repo>` once this is pushed to your own repo. Use `bash -c "$(curl ...)"`, **not** `curl ... | bash` — piping the script into bash consumes the same input stream the interactive menu needs to read your choices from, so the menu breaks. `bash -c` downloads the script into a string first and leaves your terminal's input alone.

### Traditional method

1. Download `MacDebloat.sh` (or `git clone` this repo).
2. Open Terminal and `cd` into the folder.
3. Run:
   ```bash
   bash MacDebloat.sh
   ```
4. Follow the on-screen menu.

### Command-line flags

For scripting or repeat use, skip the menu entirely:

```bash
bash MacDebloat.sh --help              # see all flags
bash MacDebloat.sh --list              # see every tweak without running anything
bash MacDebloat.sh --dry-run --all     # preview everything with no changes made
bash MacDebloat.sh --disable-analytics --disable-ads --show-hidden-files
bash MacDebloat.sh --revert            # undo the most recent run
bash MacDebloat.sh --user jane --dock-autohide   # apply a per-user tweak to another account
```

## Features

| Category | What it does |
|---|---|
| **Privacy & Analytics** | Turn off Mac analytics/crash-report sharing, personalized Apple advertising, Siri data sharing, Siri Suggestions in Spotlight, and Trash's 30-day auto-delete. |
| **Siri & Apple Intelligence** | Disable Siri outright, or (experimentally) Apple Intelligence itself. |
| **System, Power & Input** | Kill mouse acceleration, disable Power Nap and Wake-for-network during sleep, swap the accent-character popup for plain key repeat. |
| **Software Update** | Stop background update *checking* and *downloading* nagging — critical security patches are deliberately left alone (see below). |
| **Appearance** | Dark Mode, reduced transparency, reduced motion, battery percentage in the menu bar. |
| **Dock & Menu Bar** | Auto-hide, hide recents, minimize-to-icon, reposition, reset Launchpad's layout. |
| **Finder & Windows** | Show all extensions and hidden files, full path in the title bar, path/status bars, default window location, list view by default. |
| **Remove Bundled Apps** | Pages, Numbers, Keynote, iMovie, GarageBand — see below for why only these five. |

Run `bash MacDebloat.sh --list` for the exact, current list at any time.

## Why this isn't a 1:1 port

Windows and macOS simply don't expose the same knobs, so a few Win11Debloat features have no macOS equivalent and are intentionally left out rather than faked:

- **BitLocker auto-encryption** — macOS doesn't silently auto-enable FileVault the way Windows can auto-enable Device Encryption, so there's nothing to turn off.
- **Fast Startup** — macOS has no hybrid shutdown/hibernation mode to disable.
- **Delivery Optimization** (P2P update sharing) and **auto-installing companion apps** — no macOS analog.
- **Xbox Game Bar** — no macOS analog.

And a couple of things are handled more conservatively than you might expect, on purpose:

- **App removal is limited to Pages, Numbers, Keynote, iMovie, and GarageBand.** Every other bundled Apple app (Safari, Mail, Photos, Notes, etc.) lives on the cryptographically sealed system volume and cannot be safely deleted — full stop. That's a macOS security feature (introduced to harden the OS against tampering), not a limitation of this script, and this script will never ask you to disable System Integrity Protection to work around it. Removed apps are moved to the Trash, not permanently deleted, so you can put them back before emptying it — and they're all free to redownload from the App Store regardless.
- **Software Update tweaks only touch the nagging/timing**, not critical security patches (XProtect/Gatekeeper data updates are left on). This mirrors the spirit of the original tool, which also never touches Windows Defender.
- **Apple Intelligence's toggle is marked experimental.** Unlike everything else in this script, there's no Apple-documented Terminal command for it — the one that exists is a reverse-engineered preference key that has changed across macOS point updates in the past. The reliable path is always System Settings → Apple Intelligence & Siri.
- **Window tiling** (Sequoia's drag-to-edge snapping) doesn't have a publicly confirmed `defaults` key either, so the script opens System Settings to the right pane instead of guessing at a command that might silently do nothing.

## Reverting changes

Every change is logged to `~/.macdebloat_backup/`. To undo the most recent run:

```bash
bash MacDebloat.sh --revert
```

Or point at a specific log:

```bash
bash MacDebloat.sh --revert ~/.macdebloat_backup/changes-20260911-141200.log
```

## Requirements

- macOS Sonoma (14) or later recommended; most tweaks work on older versions too.
- Apple Silicon for the Apple Intelligence toggle specifically (it isn't available on Intel Macs regardless of macOS version).
- Admin (sudo) password for the handful of tweaks that change machine-wide settings — the script tells you which ones before it asks.

## What this script will never do

Same philosophy as the original: no telemetry of its own, no bundled installers, and nothing that weakens your Mac's actual security. Specifically, it will never touch System Integrity Protection, the sealed system volume, Gatekeeper, or FileVault.

## Credits

Concept and menu-driven feel inspired by [Win11Debloat](https://github.com/Raphire/Win11Debloat) by Raphire. No code is shared between the two projects — Windows and macOS are configured through entirely different mechanisms (registry/Group Policy vs. `defaults`/`launchctl`).

## License

MIT — see [LICENSE](LICENSE).
