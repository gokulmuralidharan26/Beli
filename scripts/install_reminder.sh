#!/usr/bin/env bash
# Installs (or with --uninstall removes) a macOS launchd job: a notification at
# 10:00 on the 1st of every month.  It only reminds you; the review step is
# interactive, so the run itself stays a manual ./run.sh.
set -euo pipefail
LABEL=com.beli-sync.reminder
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
if [ "${1:-}" = "--uninstall" ]; then rm -f "$PLIST"; echo "Removed."; exit 0; fi

chmod +x "$DIR/scripts/monthly_reminder.sh" "$DIR/run.sh"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$DIR/scripts/monthly_reminder.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
</dict></plist>
PLISTEOF
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed: reminder at 10:00 on the 1st of each month."
echo "Test it now with:  launchctl kickstart $DOMAIN/$LABEL"
