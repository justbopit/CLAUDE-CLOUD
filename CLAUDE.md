# Token budget

Every model call resends the whole context, and all sessions share one 5-hour limit. Treat context as a budget.

## Model and effort

- Delegate grunt work (searches, bulk reads, log scans, mechanical edits) to a subagent with `model: "haiku"` or `"sonnet"`; it returns a conclusion of 20 lines or fewer.
- When the task is routine (posting, config, installs, one-file fixes), say once per session that `/model sonnet` and `/effort medium` cover it. Opus at high effort is for hard debugging and architecture.

## Lean context

- Read narrowly: `grep -n`, `sed -n 'A,Bp'`, `head`. Pipe long command output through `tail` or `grep` before it lands in context.
- Screenshots: one, at the final check. Browser page text: `max_chars` 3000 or less.

## Session hygiene

- One task per session. When the task is done, or `/context` passes ~150k, write a five-line handoff (goal, state, next step, key files; the `handoff` skill) and suggest a fresh session.
- After an hour idle the prompt cache is gone and the next turn rewrites the whole context: offer the handoff and a fresh session first.
- Global config (`~/.claude/settings.json`, plugins, skills, mods, `~/.claude/CLAUDE.md`) is part of every running session's prompt, so changing it resets all their caches. Change it while other sessions are idle, and tell the user before you do.

## Process weight

- Scale process to the task: a one-line fix is the fix plus its check. Plans, brainstorms and review subagents are for multi-file features.
- Load a skill when its trigger clearly matches the task in front of you.
