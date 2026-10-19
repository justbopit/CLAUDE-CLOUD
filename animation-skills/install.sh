#!/usr/bin/env bash
# Installs five Claude Code animation skills at user level (available in every project):
#   Three.js       CloudAI-X/threejs-skills         -> ~/.claude/skills/threejs-*
#   GSAP           greensock/gsap-skills            -> plugin gsap-skills@gsap-skills
#   Design DNA     zanwei/design-dna                -> ~/.claude/skills/design-dna
#   Motion Design  LottieFiles/motion-design-skill  -> ~/.claude/skills/motion-design
#   Genjutsu       AThevon/genjutsu                 -> plugin genjutsu@genjutsu
#
# Usage:  bash install.sh             # audited commits pinned below
#         bash install.sh --latest    # newest commits instead (not audited)
# Piped:  curl -fsSL <url>/install.sh | bash -s -- --latest
#
# Re-running is safe: skill folders are replaced, plugins already present are kept.
set -euo pipefail

# Commits reviewed on 2026-10-19 (no hooks, no MCP servers, no hidden instructions).
THREEJS_SHA=0e181866f095b5f06d005133876e926515390d95
DESIGN_DNA_SHA=593e39bc9e3652734653bd75544a333d7d43615e
MOTION_DESIGN_SHA=f9a8a041b85185ee4881b3471d3415e939aac772

# fetch <owner/repo> <sha> <dest>: shallow checkout of the pinned commit (or the default branch with --latest)
fetch() {
  if [ "$LATEST" = 1 ]; then
    git clone -q --depth 1 "https://github.com/$1" "$3"
  else
    git init -q "$3"
    git -C "$3" fetch -q --depth 1 "https://github.com/$1" "$2"
    git -C "$3" checkout -q FETCH_HEAD
  fi
}

# install_dir <src> <name>: replace ~/.claude/skills/<name> with a copy of <src>
install_dir() {
  rm -rf "${SKILLS_DIR:?}/$2"
  cp -R "$1" "$SKILLS_DIR/$2"
  rm -rf "$SKILLS_DIR/$2/.git"
  echo "    + $2"
}

# Everything runs from main so that a truncated `curl | bash` download executes nothing.
main() {
  LATEST=0
  for arg in "$@"; do
    case "$arg" in
      --latest) LATEST=1 ;;
      *) echo "Unknown option: $arg (supported: --latest)" >&2; exit 2 ;;
    esac
  done

  command -v git >/dev/null 2>&1 || { echo "git is required: https://git-scm.com/downloads" >&2; exit 1; }

  SKILLS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
  mkdir -p "$SKILLS_DIR"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT

  echo "Skills folder: $SKILLS_DIR"

  echo "==> Three.js"
  fetch CloudAI-X/threejs-skills "$THREEJS_SHA" "$TMP/threejs"
  for d in "$TMP"/threejs/skills/*/; do
    d="${d%/}"  # BSD cp copies only the contents of a source path that ends in /
    install_dir "$d" "$(basename "$d")"
  done

  echo "==> Design DNA"
  fetch zanwei/design-dna "$DESIGN_DNA_SHA" "$TMP/design-dna"
  install_dir "$TMP/design-dna" design-dna

  echo "==> Motion Design"
  fetch LottieFiles/motion-design-skill "$MOTION_DESIGN_SHA" "$TMP/motion-design"
  install_dir "$TMP/motion-design/skills/motion-design" motion-design

  # GSAP and Genjutsu ship as Claude Code plugins, so they go through the plugin marketplace.
  # `failed` is a string, not an array: empty arrays trip `set -u` in macOS's bash 3.2.
  # </dev/null keeps claude from reading the rest of a piped script as its input.
  failed=""
  if command -v claude >/dev/null 2>&1; then
    for p in "greensock/gsap-skills gsap-skills@gsap-skills" "AThevon/genjutsu genjutsu@genjutsu"; do
      set -- $p
      echo "==> plugin $2"
      if ! { claude plugin marketplace add "$1" </dev/null && claude plugin install "$2" </dev/null; }; then
        failed="$failed$1 $2
"
      fi
    done
  else
    echo
    echo "!! 'claude' was not found in PATH, so the GSAP and Genjutsu plugins were not installed."
    echo "   Type these inside Claude Code instead:"
    echo "     /plugin marketplace add greensock/gsap-skills"
    echo "     /plugin install gsap-skills@gsap-skills"
    echo "     /plugin marketplace add AThevon/genjutsu"
    echo "     /plugin install genjutsu@genjutsu"
  fi

  if [ -n "$failed" ]; then
    echo
    echo "!! These plugins failed to install (see errors above). Retry inside Claude Code:"
    printf '%s' "$failed" | while read -r src id; do
      echo "     /plugin marketplace add $src"
      echo "     /plugin install $id"
    done
    exit 1
  fi

  echo
  echo "Done. Restart Claude Code (or open a new session) to load the skills."
  echo "Try: /genjutsu:cast, /motion-design, /design-dna, /threejs-fundamentals, /gsap-skills:gsap-core"
}

main "$@"
