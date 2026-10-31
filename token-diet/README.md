# Диета для Claude Code: меньше токенов на каждый запрос

Скрипт урезает то, что каждая сессия Claude Code на компьютере грузит в каждый запрос:

1. дописывает правила экономии из [`CLAUDE.md`](../CLAUDE.md) в `~/.claude/CLAUDE.md` между метками `token-diet`, а остальное содержимое файла не трогает;
2. отключает плагины, которые сломаны, дублируют другие или запускают сервер либо хук в каждой сессии;
3. переносит редко нужные скиллы из `~/.claude/skills` в `~/.claude/skills-disabled`.

Ничего не удаляется, всё откатывается одной командой.

## Запуск

**Сначала дождитесь, пока все сессии Claude закончат работу.** Изменение настроек сбрасывает кэш у каждой работающей сессии, и её следующий шаг заново переписывает весь контекст. 31 октября такой сброс за 2 минуты до лимита разом переписал около 0,9 млн токенов в трёх сессиях.

```bash
curl -fsSL https://raw.githubusercontent.com/justbopit/CLAUDE-CLOUD/claude/tender-dijkstra-kkrx81/token-diet/apply.sh | bash
```

Нужен `python3`, на Mac он ставится вместе с `xcode-select --install`. Повторный запуск безопасен. Изменения подхватят новые сессии, уже открытые останутся как были.

Откатить всё:

```bash
curl -fsSL https://raw.githubusercontent.com/justbopit/CLAUDE-CLOUD/claude/tender-dijkstra-kkrx81/token-diet/apply.sh | bash -s -- --restore
```

## Что отключается и почему

| Что | Почему |
|---|---|
| `claude-mem` | Сломан: нет Bun, захват памяти не работает (`CAPTURE_BROKEN`). При этом в каждой сессии он грузит 30 скиллов, MCP-сервер и фоновые процессы |
| `agent-skills` (addyosmani) | 25 скиллов, около 3,4 тыс. токенов в каждом запросе, самый тяжёлый набор. Дублирует `mattpocock-skills` |
| `superpowers` | Хук в начале каждой сессии требует грузить скиллы перед любым ответом и тянет тяжёлый процесс (брейншторм → план → субагенты). Дублирует `mattpocock-skills` |
| `rea` | Запускает MCP-сервер в каждой сессии ради реверс-инжиниринга, который нужен редко |
| `ui-ux-pro-max` | 7 скиллов, около 1 тыс. токенов. Пересекается с `impeccable`, `hallmark` и `design-dna` |
| `diagram-design` | 7 скиллов. Схемы нужны редко, встроенный `artifact-diagramming` их покрывает |
| `claude-code-setup` | Помощник для разовой настройки |
| `threejs-*` (13 скиллов) | Скиллы для 3D-графики. В последних сессиях Three.js не встречался |
| `cli-*`, `omni-*` (11 скиллов) | Скиллы OmniRoute, а сам шлюз OmniRoute не запущен |

**Остаются:** `caveman` и `ponytail` (режимы экономии), `mattpocock-skills`, `playwright`, `impeccable`, `hallmark`, `humanizer`, `last30days`, `gsap-*`, `design-dna`, `motion-design`, `graphify`, `scrapling-official`, `fukkality-ops` и встроенные скиллы Anthropic.

Чтобы вернуть что-то одно, а не всё: плагин включается командой `/plugin` в Claude Code, скилл возвращается переносом его папки из `~/.claude/skills-disabled` обратно в `~/.claude/skills`.

## Если superpowers всё ещё грузится

Плагины `superpowers`, `mattpocock-skills`, `caveman` и `playwright` приходят из аккаунта claude.ai. Скрипт выключает `superpowers@synced`. Если на Mac этот плагин называется иначе, выключите его в `/plugin` или в настройках плагинов на claude.ai. Через claude.ai он выключится сразу везде, в том числе в облачных сессиях.

В облачных сессиях этого репозитория `superpowers` уже выключен в [`.claude/settings.json`](../.claude/settings.json).
