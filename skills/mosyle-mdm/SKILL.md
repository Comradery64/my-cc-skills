---
name: mosyle-mdm
description: Mosyle Business MDM operations — Custom Commands, app deployment, device management, Installomator/Patchomator/Nudge. Use when creating MDM profiles, deploying apps to macOS fleet, troubleshooting MDM command delivery, working with Installomator/Patchomator, or configuring Nudge for macOS updates. Trigger phrases include "Mosyle", "MDM", "deploy app", "Custom Command", "Installomator", "Patchomator", "Nudge", "push to device", "macOS update".
---

# Mosyle Business MDM Operations

## Fleet Context
- 18 macOS devices, ALL Apple Silicon (arm64) — no Intel
- Mosyle Business (Fuse) subscription
- Mix of DEP and manually enrolled devices
- Standard apps: Chrome, Slack, 1Password, Tailscale, LarkSuite, Nudge (macOS update reminders)

## Critical Rules

### NEVER deploy without explicit approval
- "Set up configurations" means CREATE profiles only — do NOT assign to devices
- The admin decides when to deploy. Always confirm before assigning.

### NEVER interrupt user work
- `BLOCKING_PROCESS_ACTION=silent_fail` for background patching
- `BLOCKING_PROCESS_ACTION=prompt_user` for gentle nudges (user can always decline)
- NEVER use `tell_user_then_kill`, `quit_kill`, or `kill`

## Custom Commands — Checklist

When creating a new Custom Command profile:

1. **Set Profile Name** first
2. **Enter code** via the Code Edit dialog
3. **Click Execution Settings tab** and configure:
   - Execute command: "Immediately when saving the profile, upon assignment, or based on schedule or events"
   - Check "Every start up of the Mac"
   - **UNCHECK "Only once (Event Required)"** — this is the #1 gotcha
   - Optionally set "Every X minutes" for recurring (360 = 6hr, 1440 = daily)
4. **Uncheck Self-Service** checkboxes for mandatory apps
5. **Add Assignment** (Specific Devices for testing, All Devices for fleet)
6. **Save** — then verify assignment persisted (it can get lost on save)

## Forcing Re-execution on a Device

When a command needs to re-run (script updated, previous run failed):

1. Custom Commands → profile → "View results" → **"Clear Results"** → CONFIRM
2. Devices Overview → select device checkbox → **"Send Push"** → CONFIRM
3. Both steps required. Clear resets delivery state; Push triggers APNs wake.

Note: "Immediately when saving" does NOT re-send to devices that already received the command.

## Installomator / Patchomator

### Installing Patchomator
Patchomator's pkg is UNNOTARIZED. Do NOT use Installomator to install it.
```bash
PKG_URL=$(curl -sfL "https://api.github.com/repos/Mac-Nerd/patchomator/releases/latest" \
    | grep "browser_download_url.*pkg" | head -1 | cut -d '"' -f 4)
curl -sfL -o /tmp/patchomator.pkg "$PKG_URL"
installer -pkg /tmp/patchomator.pkg -target / -allowUntrusted
```

### Label Names (case-sensitive)
- `swiftdialog` (all lowercase)
- `googlechromepkg` (not `googlechrome`)
- `slack`, `1password8`, `tailscale`

### Patchomator CLI Syntax
```bash
# CORRECT:
"$PATCHOMATOR_PATH" --yes --write --required "googlechromepkg slack 1password8 tailscale swiftdialog" --ignored RECOMMENDED

# WRONG:
--ignored=RECOMMENDED  # creates label "=RECOMMENDED"
--required swiftDialog  # case mismatch, label not found
```

### Non-Interruptive Options
```bash
# Tier 1 — Silent background (runs every 6 hours)
--options "BLOCKING_PROCESS_ACTION=silent_fail, NOTIFY=silent, LOGO=mosyleb, INTERRUPT_DND=no, REOPEN=no"

# Tier 2 — Gentle nudge (runs daily/weekly)
--options "BLOCKING_PROCESS_ACTION=prompt_user, NOTIFY=success, LOGO=mosyleb, PROMPT_TIMEOUT=300, INTERRUPT_DND=no, REOPEN=yes"
```

## Lark Suite — Special Handling

No Installomator label exists. Custom script required.

### Key Facts
- App name: `LarkSuite.app` (NOT `Lark.app`)
- Process name: `LarkSuite`
- DMG has EULA that blocks `hdiutil attach` headlessly

### EULA Bypass Pattern
```bash
# Convert to remove EULA
hdiutil convert "$DMG" -format UDTO -o "/tmp/Lark_converted" -quiet
# Mount the .cdr (no EULA prompt)
hdiutil attach -noverify -nobrowse -noautoopen "/tmp/Lark_converted.cdr" -quiet
# App is at /Volumes/Lark/LarkSuite.app
```

### JSON Parsing Without python3
Fresh Macs don't have python3 without Xcode CLI tools. Use:
```bash
echo "$JSON" | osascript -l JavaScript -e 'JSON.parse($.NSString.alloc.initWithDataEncoding($.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile, $.NSUTF8StringEncoding).js).url'
```

### Skip SHA256 Verification
Homebrew's SHA frequently mismatches CDN delivery. Use `codesign -v` after install instead.

## macOS Scripting for MDM

### Fresh Mac Gotchas
- `python3` → requires Xcode CLI tools → use `osascript -l JavaScript`
- DMGs with EULAs → `hdiutil convert -format UDTO` then mount `.cdr`
- `curl -sfL` → `-f` silently fails on HTTP errors (remove during debug)
- Scripts run as root, no GUI session, no user profile

### Manually Enrolled Devices
- `sudo profiles renew -type enrollment` → FAILS ("not DEP enabled")
- `sudo mdmclient QueryDeviceInformation` → works, triggers check-in
- `sudo killall mdmclient` → restarts MDM daemon

## Nudge — macOS Update Reminders

[Nudge](https://github.com/macadmins/nudge) prompts users to update macOS. Two-part deployment in Mosyle:

### 1. Install (Custom Command: "Setup - Nudge")
```bash
"$INSTALLOMATOR_PATH" nudgesuite \
    DEBUG=0 \
    LOGO=mosyleb \
    NOTIFY=silent \
    BLOCKING_PROCESS_ACTION=silent_fail
```
- Use label `nudgesuite` (NOT `nudge`) — includes the LaunchAgent + Logger
- `nudge` label only installs the bare app without the LaunchAgent that auto-runs every 30 min
- Requires Installomator (run Setup - Patchomator first)

### 2. Configure (Certificates / Custom Profiles: "Nudge - macOS Update Reminders")
- Deploys `nudge.mobileconfig` as a Custom Profile
- Contains required OS version, deadline dates, messaging, deferral limits
- Mosyle variables enabled (`%SERIAL_NUMBER%`, `%DeviceName%`, etc.)
- Config lives in Certificates / Custom Profiles section (NOT Custom Commands)
- To update Nudge behavior (new OS requirement, deadline change): Replace the `.mobileconfig` file in this profile

### Key Notes
- Nudge runs automatically via LaunchAgent every 30 minutes
- It shows its own UI — does NOT use Installomator's notification system
- `NOTIFY=silent` is correct because Nudge handles its own user-facing prompts
- Nudge respects its own deferral/deadline logic — no need for Patchomator to manage it

## Reference Scripts
All working scripts are in `/Volumes/SD/Work/MDM/scripts/`:
- `setup-patchomator.sh` — Installs Installomator + Patchomator, configures labels
- `patching-silent-background.sh` — Tier 1 silent patching
- `patching-gentle-nudge.sh` — Tier 2 user-prompted patching
- `app-lark-suite.sh` — Lark install via Homebrew Cask API
- `app-swiftdialog.sh` — swiftDialog via Installomator

## Mosyle UI via dev-browser
- `page.evaluate()` is more reliable than Playwright locators in Mosyle's SPA
- Click-by-coordinates for elements not in accessible DOM
- Sessions expire (~24 min) — prepare scripts offline, work fast
- Mosyle's code editor mangles indentation when typing via automation (cosmetic only)
