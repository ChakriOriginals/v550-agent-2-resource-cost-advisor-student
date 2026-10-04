#!/bin/sh
set -eu
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

resolve_desktop_executable() {
  if [ -n "${V550_CHATGPT_EXECUTABLE:-}" ]; then
    [ -x "$V550_CHATGPT_EXECUTABLE" ] || { echo "V550_CHATGPT_EXECUTABLE is not executable." >&2; return 1; }
    printf '%s\n' "$V550_CHATGPT_EXECUTABLE"; return 0
  fi
  for candidate in "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT" "$HOME/Applications/ChatGPT.app/Contents/MacOS/ChatGPT"
  do
    if [ -x "$candidate" ]; then printf '%s\n' "$candidate"; return 0; fi
  done
  return 1
}

if [ "${1:-}" = "--check-desktop" ]; then
  resolve_desktop_executable >/dev/null && { echo "ChatGPT Desktop detected."; exit 0; }
  echo "ChatGPT Desktop was not found." >&2; exit 2
fi
desktop_executable=$(resolve_desktop_executable) || { echo "ChatGPT Desktop was not found in a standard macOS location." >&2; exit 2; }
echo "Opening the local V550 Agent 2 workspace: $package_dir"
echo 'Invoke $v550-agent-2-resource-cost-advisor-student after the app opens.'
cd "$package_dir"
exec "$desktop_executable"

