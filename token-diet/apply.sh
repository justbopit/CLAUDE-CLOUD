#!/usr/bin/env bash
# Trims what every Claude Code session loads on this computer:
#   1. writes the token-budget rules (CLAUDE.md of this repo) into ~/.claude/CLAUDE.md, between markers
#   2. disables plugins that are broken, duplicate others, or start a server or hook in every session
#   3. moves rarely used user skills from ~/.claude/skills to ~/.claude/skills-disabled
# Why each plugin and skill goes: README.md next to this script.
#
# Usage:  bash apply.sh             # apply (re-running is safe)
#         bash apply.sh --restore   # undo all three steps
# Piped:  curl -fsSL <url>/apply.sh | bash  (add `-s -- --restore` to undo)
#
# Run it while no Claude session is working: a config change resets the prompt cache of every running session.
set -euo pipefail

REF="${TOKEN_DIET_REF:-claude/tender-dijkstra-kkrx81}"
RULES_URL="https://raw.githubusercontent.com/justbopit/CLAUDE-CLOUD/$REF/CLAUDE.md"

PLUGINS="claude-mem@thedotmack agent-skills@addy-agent-skills superpowers@synced rea@rea
ui-ux-pro-max@ui-ux-pro-max-skill diagram-design@diagram-design claude-code-setup@anthropic-plugin-directory"

SKILLS="threejs-animation threejs-asset-pipeline threejs-fundamentals threejs-geometry threejs-interaction
threejs-lighting threejs-loaders threejs-materials threejs-performance threejs-postprocessing
threejs-react-three-fiber threejs-shaders threejs-textures
cli-compression cli-cost-usage cli-models cli-providers cli-routing cli-serve cli-setup
omni-auth omni-budget omni-combos-routing omni-inference"

# rules <dest>: the rules text from a local clone, or from GitHub when the script is piped
rules() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"
  if [ -n "$here" ] && [ -f "$here/../CLAUDE.md" ] && [ -f "$here/apply.sh" ]; then
    cp "$here/../CLAUDE.md" "$1"
  else
    curl -fsSL "$RULES_URL" -o "$1"
  fi
}

# Everything runs from main so that a truncated `curl | bash` download executes nothing.
main() {
  MODE=apply
  for arg in "$@"; do
    case "$arg" in
      --restore) MODE=restore ;;
      *) echo "Unknown option: $arg (supported: --restore)" >&2; exit 2 ;;
    esac
  done
  command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

  CONF="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  mkdir -p "$CONF/skills"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Claude config: $CONF ($MODE)"

  : > "$TMP/rules.md"
  [ "$MODE" = apply ] && rules "$TMP/rules.md"

  # CLAUDE.md block and enabledPlugins. The state file keeps each plugin's previous value for --restore.
  python3 -I - "$MODE" "$CONF" "$TMP/rules.md" $PLUGINS <<'PY'
import json, os, sys
mode, conf, rules_path, plugins = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
START, END = '<!-- token-diet:start -->', '<!-- token-diet:end -->'

md = os.path.join(conf, 'CLAUDE.md')
text = open(md).read() if os.path.exists(md) else ''
if START in text and END in text:
    a, b = text.index(START), text.index(END) + len(END)
    text = (text[:a].rstrip('\n') + '\n' + text[b:].lstrip('\n')).strip('\n')
    text = text + '\n' if text else ''
if mode == 'apply':
    if os.path.exists(md) and not os.path.exists(md + '.bak-token-diet'):
        open(md + '.bak-token-diet', 'w').write(open(md).read())
    block = START + '\n' + open(rules_path).read().strip('\n') + '\n' + END + '\n'
    text = (text.rstrip('\n') + '\n\n' if text.strip() else '') + block
if mode == 'apply' or os.path.exists(md):
    open(md, 'w').write(text)
print('  CLAUDE.md:', 'rules block written' if mode == 'apply' else 'rules block removed')

path = os.path.join(conf, 'settings.json')
state_path = os.path.join(conf, 'token-diet-state.json')
if mode == 'restore' and not os.path.exists(state_path):
    print('  plugins restored: nothing to restore')
    sys.exit(0)
settings = json.load(open(path)) if os.path.exists(path) else {}
enabled = settings.setdefault('enabledPlugins', {})
if mode == 'apply':
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    for p in plugins:
        state.setdefault(p, enabled.get(p))
        enabled[p] = False
    json.dump(state, open(state_path, 'w'), indent=2)
    print('  plugins disabled:', ' '.join(plugins))
else:
    state = json.load(open(state_path))
    for p, prev in state.items():
        if prev is None:
            enabled.pop(p, None)
        else:
            enabled[p] = prev
    os.remove(state_path)
    print('  plugins restored:', ' '.join(state))
if not enabled:
    settings.pop('enabledPlugins')
json.dump(settings, open(path, 'w'), indent=2, ensure_ascii=False)
open(path, 'a').write('\n')
PY

  # Skill folders move, never get deleted: --restore moves them back.
  OFF="$CONF/skills-disabled"
  moved=""
  for s in $SKILLS; do
    if [ "$MODE" = apply ] && [ -d "$CONF/skills/$s" ]; then
      mkdir -p "$OFF"
      rm -rf "${OFF:?}/$s"
      mv "$CONF/skills/$s" "$OFF/$s"
      moved="$moved $s"
    elif [ "$MODE" = restore ] && [ -d "$OFF/$s" ]; then
      if [ -e "$CONF/skills/$s" ]; then
        echo "  skip $s: $CONF/skills/$s already exists"
      else
        mv "$OFF/$s" "$CONF/skills/$s"
        moved="$moved $s"
      fi
    fi
  done
  [ "$MODE" = restore ] && rmdir "$OFF" 2>/dev/null || true
  echo "  skills $([ "$MODE" = apply ] && echo moved to "$OFF" || echo moved back):${moved:- none found}"

  echo
  echo "Done. Open a new Claude session to load the change; running sessions keep their old setup."
}

main "$@"
