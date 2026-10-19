# 5 скиллов анимации для Claude Code

Ставит на ваш компьютер пять скиллов из подборки «5 скиллов — и Claude начнёт анимировать». Они устанавливаются на уровне пользователя, поэтому работают в любом проекте.

| Скилл | Источник | Как ставится | Как вызвать |
|---|---|---|---|
| **Three.js** | [CloudAI-X/threejs-skills](https://github.com/CloudAI-X/threejs-skills) | 13 папок в `~/.claude/skills/threejs-*` | автоматически или `/threejs-fundamentals` |
| **GSAP** (официальный, от GreenSock) | [greensock/gsap-skills](https://github.com/greensock/gsap-skills) | плагин `gsap-skills@gsap-skills` (8 скиллов) | автоматически или `/gsap-skills:gsap-core` |
| **Design DNA** | [zanwei/design-dna](https://github.com/zanwei/design-dna) | `~/.claude/skills/design-dna` | `/design-dna` + ссылка или скриншот сайта |
| **Motion Design** (от LottieFiles) | [LottieFiles/motion-design-skill](https://github.com/LottieFiles/motion-design-skill) | `~/.claude/skills/motion-design` | автоматически или `/motion-design` |
| **Genjutsu** | [AThevon/genjutsu](https://github.com/AThevon/genjutsu) | плагин `genjutsu@genjutsu` | автоматически или `/genjutsu:cast`, `/genjutsu:paint`, `/genjutsu:bunshin` |

## Установка

Нужны `git` и Claude Code. Скрипт работает на macOS и Linux. В терминале выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/justbopit/CLAUDE-CLOUD/claude/eloquent-brahmagupta-f2nq6v/animation-skills/install.sh | bash
```

После установки перезапустите Claude Code или откройте новую сессию. Чтобы проверить, наберите `/` в Claude Code: в списке появятся `/design-dna`, `/motion-design`, `/genjutsu:cast` и остальные. Плагины также видны в выводе `claude plugin list`.

Повторный запуск безопасен: папки скиллов перезаписываются, уже установленные плагины остаются как есть.

Если на macOS нет git, выполните `xcode-select --install` и повторите команду.

### Если хотите сначала прочитать скрипт

```bash
git clone -b claude/eloquent-brahmagupta-f2nq6v https://github.com/justbopit/CLAUDE-CLOUD
less CLAUDE-CLOUD/animation-skills/install.sh
bash CLAUDE-CLOUD/animation-skills/install.sh
```

### Без скрипта, прямо в Claude Code

Плагины можно поставить командами внутри Claude Code:

```
/plugin marketplace add greensock/gsap-skills
/plugin install gsap-skills@gsap-skills
/plugin marketplace add AThevon/genjutsu
/plugin install genjutsu@genjutsu
```

Остальные три репозитория плагинами не являются. Их нужно скопировать в `~/.claude/skills/`, и это делает скрипт.

## Версии и безопасность

Three.js, Design DNA и Motion Design скрипт ставит из зафиксированных коммитов. Код этих коммитов проверен 19.10.2026: хуков, MCP-серверов и скрытых инструкций в нём нет.

| Репозиторий | Коммит |
|---|---|
| CloudAI-X/threejs-skills | `0e18186` |
| zanwei/design-dna | `593e39b` |
| LottieFiles/motion-design-skill | `f9a8a04` |

Чтобы взять самые свежие версии, добавьте флаг `--latest`:

```bash
curl -fsSL https://raw.githubusercontent.com/justbopit/CLAUDE-CLOUD/claude/eloquent-brahmagupta-f2nq6v/animation-skills/install.sh | bash -s -- --latest
```

Свежие версии никто не проверял. Плагины GSAP и Genjutsu всегда ставятся в последней версии; на момент проверки это были `aed9cfd` и `1f518a7` (v4.1.1).

Что стоит знать:

- **Genjutsu**: все три скилла (`cast`, `paint`, `bunshin`) разрешают себе запускать команды в Bash и править файлы без подтверждения, пока скилл активен. Claude может включить их сам, без слэш-команды. `bunshin` вдобавок запускает субагентов и ходит в интернет. Он собирает целый сайт параллельными агентами и стоит очень дорого: по оценке автора, от ~6 до ~13 млн токенов в зависимости от выбранного уровня. Перед запуском он называет стоимость и просит выбрать уровень.
- **Design DNA**: при анализе картинок может попросить `npm install` пакета `sharp`, чтобы точно измерять цвета. Claude Code спросит разрешение. Без Node.js цвета оцениваются на глаз.
- **Three.js**: в скилле `threejs-asset-pipeline` есть примеры с `npx @gltf-transform/cli`. Claude Code спросит разрешение, прежде чем их запускать.
- **GSAP**: если библиотеку анимации вы не указали, скилл советует GSAP.
- **Motion Design**: это руководство по таймингам, easing и хореографии анимаций. Lottie-файлы он не генерирует, хотя в подборке написано иначе.

## Обновление и удаление

```bash
# обновить плагины
claude plugin marketplace update genjutsu && claude plugin update genjutsu@genjutsu
# у GSAP версия в манифесте не меняется (всегда 1.0.0), поэтому `plugin update` его не обновит: переустановите
claude plugin marketplace update gsap-skills && claude plugin uninstall gsap-skills@gsap-skills && claude plugin install gsap-skills@gsap-skills
# Three.js, Design DNA и Motion Design: повторите команду установки (с `bash -s -- --latest` для свежих версий)

# удалить
claude plugin uninstall gsap-skills@gsap-skills && claude plugin marketplace remove gsap-skills
claude plugin uninstall genjutsu@genjutsu && claude plugin marketplace remove genjutsu
rm -rf ~/.claude/skills/threejs-* ~/.claude/skills/design-dna ~/.claude/skills/motion-design
```

Если у вас задана переменная `CLAUDE_CONFIG_DIR`, скиллы ставятся в `$CLAUDE_CONFIG_DIR/skills`, а не в `~/.claude/skills`.
