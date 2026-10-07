#!/usr/bin/env bash
# Run by launchd on the 1st of each month: notify and open the inbox folder.
cd "$(dirname "$0")/.." || exit 1
osascript -e 'display notification "Download last month'"'"'s statements into inbox/, then run ./run.sh" with title "Beli sync"'
open inbox
