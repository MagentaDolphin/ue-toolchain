# Unreal Engine design-review toolchain

[English](#english) · [Русский](#русский)

## English

### What this is

Design-review skills for Unreal Engine 5.6 projects, written for LLM agents such as Claude Code and other agent harnesses.

The repository currently ships one self-contained bundle: norms for designing UE systems plus reproducible recipes for detecting silent architectural failures. The skills are Markdown with YAML frontmatter, indexed by a vendor-neutral JSON catalog. They can be read directly, loaded as agent context, or routed by a harness; the Claude Code manifest is only one distribution adapter.

### Why it exists

Many costly architecture defects do not crash, fail compilation, or announce themselves in the editor. A tag typo can produce an empty lookup, a feature can activate correctly but fail to roll back, a client can own a fact that only the server should trust, and a quality setting can be silently overridden. The bundle turns those failure shapes into review invariants, observable symptoms, runnable detection recipes, and guardrails intended to prevent recurrence.

Each failure-mode entry separates six questions: mechanism, why the failure is silent, why the obvious check misses it, symptom, detection, and guardrail. An empty search result is evidence about the search pattern—not proof that a defect is absent.

### Repository contents

```text
.
├── .claude-plugin/
│   └── marketplace.json             Claude Code marketplace adapter
├── plugins/
│   └── ue-design-skills/            self-contained shipping bundle
│       ├── .claude-plugin/
│       │   └── plugin.json          Claude Code plugin manifest
│       ├── catalog.json             harness-neutral source of truth
│       ├── skills/                   design-review skill directories
│       ├── _gate/                    delivery gate, clean fixture, and self-test
│       ├── README.md                 bundle-level usage and provenance
│       └── LICENSE                   prose license and additional permissions
├── docs/
│   ├── architecture/decisions/      accepted MADR decision records
│   ├── handoff.md                    historical project handoff and plan
│   └── licensing-options.md          analysis that preceded ADR-0003
├── CONTRIBUTING.md                  evidence and contribution requirements
├── LICENSE                          repository-level Apache-2.0 boundary
└── README.md                        this bilingual overview
```

Every skill directory contains a `SKILL.md` entry point and `references/failure-modes.md`; supporting documents such as `patterns.md` are listed by that skill's catalog entry when present.

### Skills

This table contains every current directory under `plugins/ue-design-skills/skills/`. Its summaries follow `catalog.json` and the corresponding `SKILL.md` frontmatter.

| Skill | What it reviews |
|---|---|
| `ue-reference-project-adoption` | Classifies borrowed sample or reference-project elements as defects, showcase stubs, scope narrowing, architecture tax, or foreign legacy, then supports a copy/close/skip decision. |
| `ue-multiplayer-authority` | Ownership of networked facts, prediction, replication, validation, RPC discipline, hit registration, relevancy, replication cost, and the cheat surface. |
| `ue-gameplay-cues` | GameplayCue forms and addressing, static versus actor notifies, dedicated-server exclusion, discovery and loading, feature-plugin paths, teardown, and tag-to-asset validation. |
| `ue-gameplay-tag-governance` | Tag declaration sources, namespaces, constrained inputs, exact versus hierarchical matching, redirects, replicated tag sets, counters, and inventory audits. |
| `ue-gameplay-messaging` | Typed tag-addressed publish/subscribe messaging: scope, payload checks, channel matching, listener ownership, C++/Blueprint parity, and the local/network boundary. |
| `ue-modular-gameplay` | Experience definitions, feature plugins, action sets and rollback, actor extensions, initialization states, asset bundles, activation, and deactivation. |
| `ue-gas-architecture` | Production Gameplay Ability System structure: grant packages and receipts, buffered input, activation policy, attributes, effect contexts, tag policy, phases, health, and death. |
| `ue-input-architecture` | Enhanced Input layers, mapping contexts and actions, semantic tags, native and ability paths, buffering, rebinding, device switching, and feature-owned input. |
| `ue-ui-architecture` | Per-player root layouts, tagged layer stacks, feature extension points, focus and input policy, loading screens, ordering, and teardown. |
| `ue-data-driven-architecture` | Definition and composition layers, data assets, class defaults, instanced fragments, reference semantics, asset bundles, validation, and the code/data boundary. |
| `ue-cosmetics-and-teams` | Replicated cosmetic intent and local realization, selection ownership, server exclusion, mesh and animation choice, authoritative teams, and shared damage policy. |
| `ue-game-settings-architecture` | Widget-independent setting models, reflected property paths, edit conditions, transactional apply/cancel, persistence, scalability, device profiles, benchmarks, and sampled statistics. |
| `ue-asset-loading-and-memory` | Asset-manager identifiers, reference semantics, bundles and cook rules, load-handle ownership, synchronous hitches, startup order, garbage collection, retention, and unloading. |
| `ue-streaming-and-platform-budgets` | Disk, CPU-memory, video-memory, and streaming-pool boundaries; texture groups, scalability, device profiles, console-variable priority, and streamed-level lifetime. |
| `ue-runtime-allocation-and-caching` | Allocation churn, pooling, bounded caches, pointers into container storage, retention, replication structures, dormancy, relevancy, and dedicated-server exclusions. |
| `ue-architecture-guardrails` | Cross-system ownership, lifecycle transactions, context, data-graph validation, temporal dependencies, observability, false genericity, and risk-based integration gates. |
| `ue-evidence-discipline` | Evidence quality: measured versus derived versus open claims, negative-search limits, independent verification, delegated findings, and recipes that have actually been run. |

### Catalog

`plugins/ue-design-skills/catalog.json` uses schema `ue-skills-catalog/1`. It is the harness-neutral source of truth for bundle identity and routing: each entry provides an ID, path, Markdown entry point, description, usage condition, and reference paths. The catalog contains **17 entries**, matching the **17 skill directories**.

Reproduce both counts from the repository root:

```bash
python3 -c 'import json; from pathlib import Path; p=Path("plugins/ue-design-skills"); print(len(json.loads((p/"catalog.json").read_text())["skills"]), sum(x.is_dir() for x in (p/"skills").iterdir()))'
```

To add a skill, create a kebab-case directory under `skills/`, add `SKILL.md` with matching `name` and a non-empty `description`, add and link `references/failure-modes.md`, and add a matching catalog entry with the required routing fields. Failure-mode IDs must be sequential and their prefixes unique across skills. Run the delivery gate and its self-test before proposing the change; the contribution guide asks that a new skill be discussed first and that every detection recipe be run against a real tree.

### Delivery gate

`plugins/ue-design-skills/_gate/gate.py` declares **17 rules** (`P01`–`P17`). They reject:

- absolute workstation paths, source file-and-line citations, donor naming outside provenance, Cyrillic text, and unresolved wiki-style links;
- missing or invalid skill frontmatter, missing or unlinked failure-mode documents, incomplete six-field entries, broken or escaping relative links, non-sequential entry IDs, and duplicate entry-ID prefixes;
- unexpected top-level bundle files, junk or binary artifacts, harness/vendor names inside skills, catalog/directory mismatches, and names from the experimental engine tool surface inside skill content.

The gate also validates the Claude Code manifest shape. Its scan surface is a whitelist, and an unexpected top-level path is itself a violation. A green result proves delivery form, links, structure, and portability constraints; it does **not** prove that a technical claim is true.

List the rules and reproduce their count:

```bash
cd plugins/ue-design-skills
python3 _gate/gate.py --list-rules
python3 -c 'import sys; sys.path.insert(0, "_gate"); import gate; print(len(gate.RULES))'
```

Run the gate and self-test:

```bash
cd plugins/ue-design-skills
python3 _gate/gate.py .
python3 _gate/test_gate.py
```

The self-test starts from `_gate/fixtures/clean`, applies one deliberate poison for every declared rule, and requires that rule to turn red. It separately verifies that each declared root file reaches the line-level checks. These poisoned fixtures exist because a validator that cannot be made to fail provides no protection.

### Architecture decisions

There are **5 accepted MADR records**. Reproduce the count with `find docs/architecture/decisions -maxdepth 1 -type f -name '*.md' | wc -l`.

- [ADR-0001 — Discovery over PID file](docs/architecture/decisions/0001-discovery-over-pid-file.md): establishes process liveness, automatic recovery, and graceful editor-less operation instead of trusting a stale PID file; its custom transport design is narrowed by ADR-0005.
- [ADR-0002 — Harness-neutral skill bundle](docs/architecture/decisions/0002-harness-neutral-skill-bundle.md): makes the catalog authoritative, vendor manifests adapters, and harness neutrality an enforced property of skill content.
- [ADR-0003 — Split licensing](docs/architecture/decisions/0003-split-licensing-prose-and-code.md): places bundle prose under CC BY-ND 4.0 and code and metadata under Apache-2.0, with explicit additional permissions.
- [ADR-0004 — Engine tool surface stays out of skills](docs/architecture/decisions/0004-engine-tool-surface-out-of-skill-content.md): keeps experimental, version-bound toolset, meta-tool, and endpoint names out of skill content through gate rule P17.
- [ADR-0005 — Native transport narrows ADR-0001](docs/architecture/decisions/0005-native-transport-narrows-adr-0001.md): drops the planned custom editor server, UDP discovery, and heartbeat in favor of probing the engine's own transport while retaining the liveness contract.

### Installation and use

For Claude Code, add this repository as a marketplace and then install the single plugin:

```text
/plugin marketplace add https://github.com/MagentaDolphin/ue-toolchain
/plugin install ue-design-skills@ue-toolchain
```

For another harness, no Claude-specific adapter is required. Read `plugins/ue-design-skills/catalog.json`, match a task against each entry's `use_when`, and load its `entry`; alternatively load a selected skill directory as context or open its `SKILL.md` directly. This works because ADR-0002 keeps vendor vocabulary outside `skills/` and the gate enforces that boundary.

### Licensing

Copyright is held under the pseudonym **MagentaDolphin**; `catalog.json` names **MagentaDolphin** as publisher.

| Surface | License or permission |
|---|---|
| Root documentation and repository software or machine-readable material outside the prose bundle | [Apache License 2.0](LICENSE) |
| `plugins/ue-design-skills/skills/**`, reference prose, and the bundle README | [CC BY-ND 4.0](plugins/ue-design-skills/LICENSE) |
| `catalog.json`, `.claude-plugin/plugin.json`, and everything under `_gate/` | Apache-2.0 under the bundle's explicit carve-outs |
| Shell commands inside `Detect` fields | Apache-2.0; the surrounding prose remains CC BY-ND 4.0 |

The bundle license permits reading and commercial use, private adaptation, and unchanged redistribution with attribution. Its additional permissions allow publication of format adapters and faithful, clearly marked unofficial translations under the stated conditions, as well as forks or patches made to contribute changes back. It does not permit publishing modified prose as a separate product. Nothing in either license claims a user's game, source code, documentation, internal standards, or revenue. Credit for use is welcomed but is not a license condition; attribution is required when redistributing the material itself. Read the license files for the governing terms; the repository does not present its licensing analysis as legal advice.

### Requirements and boundaries

- **Engine scope:** the shipped skills target Unreal Engine **5.6**. They are design-review material, not an engine plugin, and do not need the editor to be open in order to be read or routed.
- **For Claude Code:** install Claude Code with plugin marketplace support, then use the two commands above. No minimum Claude Code version is documented in this repository.
- **For other harnesses:** the harness must be able to read Markdown and JSON context. No agent runtime is required for direct reading.
- **For maintainers:** Python 3 runs the delivery gate and self-test. A minimum Python minor version is not documented.

This repository does **not** currently contain an editor bridge, an MCP server, an installer, a UE C++ module, or a sample UE project. The marketplace description mentions an editor bridge and an MCP server, but their implementations are absent from this tree; ADR-0005 also records that the custom bridge design was dropped before it was built. The remaining standalone file/analysis server and runtime-game tool layer are architectural work still to be built, not shipped features.

The bundle does not execute reviews automatically, modify a UE project, prove that an architecture is correct, certify performance or security, or guarantee that a detection recipe covers a user's codebase. The gate checks packaging and form, not the truth of the claims. The material records reusable failure shapes derived from a source-reading research process; it is not a defect list for every UE project or engine version.

### Links

- Repository: [https://github.com/MagentaDolphin/ue-toolchain](https://github.com/MagentaDolphin/ue-toolchain)
- Author: **MagentaDolphin**; publisher recorded by the catalog: **Kodlo.art**

## Русский

### Что это

Скиллы для архитектурного design review проектов на Unreal Engine 5.6, рассчитанные на LLM-агентов — Claude Code и другие агентные харнесы.

Сейчас репозиторий поставляет один самодостаточный бандл: нормы проектирования систем UE и воспроизводимые рецепты поиска тихих архитектурных отказов. Скиллы написаны на Markdown с YAML-фронтматтером и собраны в нейтральном к конкретному вендору JSON-каталоге. Их можно читать напрямую, загружать в контекст агента или маршрутизировать средствами харнеса; манифест Claude Code — лишь один адаптер поставки.

### Зачем

Многие дорогие архитектурные дефекты не приводят к падению, не ломают компиляцию и никак не проявляются в редакторе. Опечатка в теге может дать пустой результат, фича — корректно активироваться, но не откатиться, клиент — владеть фактом, которому должен доверять только сервер, а настройка качества — молча проиграть более приоритетному значению. Бандл превращает такие формы отказов в инварианты для ревью, наблюдаемые симптомы, запускаемые рецепты обнаружения и защитные правила против повторения дефекта.

Каждая запись о режиме отказа отвечает на шесть отдельных вопросов: механизм, почему отказ остаётся тихим, почему очевидная проверка его пропускает, симптом, способ обнаружения и защитное правило. Пустой результат поиска считается свидетельством о поисковом шаблоне, но не доказательством отсутствия дефекта.

### Состав репозитория

```text
.
├── .claude-plugin/
│   └── marketplace.json             адаптер маркетплейса Claude Code
├── plugins/
│   └── ue-design-skills/            самодостаточный поставляемый бандл
│       ├── .claude-plugin/
│       │   └── plugin.json          манифест плагина Claude Code
│       ├── catalog.json             харнес-нейтральный источник истины
│       ├── skills/                   каталоги скиллов для design review
│       ├── _gate/                    гейт поставки, чистая фикстура и самотест
│       ├── README.md                 использование и происхождение бандла
│       └── LICENSE                   лицензия прозы и дополнительные разрешения
├── docs/
│   ├── architecture/decisions/      принятые решения в формате MADR
│   ├── handoff.md                    исторический хэнд-офф и план проекта
│   └── licensing-options.md          анализ, предшествовавший ADR-0003
├── CONTRIBUTING.md                  требования к доказательствам и вкладам
├── LICENSE                          граница Apache-2.0 на уровне репозитория
└── README.md                        этот двуязычный обзор
```

В каждом каталоге скилла есть точка входа `SKILL.md` и `references/failure-modes.md`; дополнительные справочные документы, например `patterns.md`, перечислены в записи конкретного скилла в каталоге, если они присутствуют.

### Скиллы

В таблице перечислены все текущие каталоги из `plugins/ue-design-skills/skills/`. Краткое назначение сверено с `catalog.json` и фронтматтером соответствующего `SKILL.md`.

| Скилл | Что проверяет |
|---|---|
| `ue-reference-project-adoption` | Классифицирует заимствования из примеров и референсных проектов как дефекты, демонстрационные заглушки, сужение области, архитектурный налог или чужое наследие и помогает решить: копировать, завершать или пропускать. |
| `ue-multiplayer-authority` | Владение сетевыми фактами, предсказание, репликацию, валидацию, дисциплину RPC, регистрацию попаданий, relevancy, стоимость репликации и поверхность для читов. |
| `ue-gameplay-cues` | Формы и адресацию GameplayCue, static- и actor-notify, исключение dedicated server, обнаружение и загрузку, пути feature-плагинов, teardown и валидацию связи тегов с ассетами. |
| `ue-gameplay-tag-governance` | Источники объявления тегов, пространства имён, ограничения ввода, точное и иерархическое сопоставление, редиректы, реплицируемые наборы тегов, счётчики и аудит инвентаря. |
| `ue-gameplay-messaging` | Типизированную publish/subscribe-шину с адресацией тегами: область жизни, проверку payload, сопоставление каналов, владение listener-ами, паритет C++/Blueprint и границу локального и сетевого. |
| `ue-modular-gameplay` | Experience-описания, feature-плагины, action set и откат действий, расширения акторов, состояния инициализации, asset bundle, активацию и деактивацию. |
| `ue-gas-architecture` | Промышленную архитектуру Gameplay Ability System: пакеты выдачи и квитанции отзыва, буферизованный ввод, политики активации, атрибуты, контексты эффектов, теги, фазы, здоровье и смерть. |
| `ue-input-architecture` | Слои Enhanced Input, mapping context и input action, семантические теги, нативные и ability-пути, буферизацию, переназначение, смену устройства и ввод, которым владеет фича. |
| `ue-ui-architecture` | Корневые layout для каждого локального игрока, стеки слоёв с тегами, точки расширения фич, политику фокуса и ввода, экраны загрузки, порядок и teardown. |
| `ue-data-driven-architecture` | Слои определений и композиции, data asset, значения по умолчанию классов, инстансированные фрагменты, семантику ссылок, asset bundle, валидацию и границу кода и данных. |
| `ue-cosmetics-and-teams` | Реплицируемое намерение косметики и локальную реализацию, владение выбором, исключение сервера, выбор мешей и анимации, авторитетные команды и общую политику урона. |
| `ue-game-settings-architecture` | Независимые от виджетов модели настроек, reflection-пути, условия редактирования, транзакцию apply/cancel, хранение, scalability, device profile, бенчмарки и выборочную статистику. |
| `ue-asset-loading-and-memory` | Идентификаторы Asset Manager, семантику ссылок, bundle и cook-правила, владение load handle, синхронные задержки, порядок старта, сборку мусора, удержание и выгрузку. |
| `ue-streaming-and-platform-budgets` | Границы диска, CPU-памяти, видеопамяти и streaming pool; группы текстур, scalability, device profile, приоритет консольных переменных и время жизни загруженных уровней. |
| `ue-runtime-allocation-and-caching` | Аллокации, пулы, ограниченные кеши, указатели в память контейнеров, удержание, структуры репликации, dormancy, relevancy и исключения dedicated server. |
| `ue-architecture-guardrails` | Межсистемное владение, транзакции жизненного цикла, контекст, валидацию графа данных, временные зависимости, наблюдаемость, ложную универсальность и риск-ориентированные интеграционные гейты. |
| `ue-evidence-discipline` | Качество доказательств: измеренные, выведенные и открытые утверждения, пределы отрицательного поиска, независимую проверку, делегированные находки и реально запущенные рецепты. |

### Каталог

`plugins/ue-design-skills/catalog.json` использует схему `ue-skills-catalog/1`. Это харнес-нейтральный источник истины о составе и маршрутизации бандла: каждая запись содержит ID, путь, точку входа Markdown, описание, условие применения и пути к справочным материалам. В каталоге **17 записей**, соответствующих **17 каталогам скиллов**.

Обе цифры можно воспроизвести из корня репозитория:

```bash
python3 -c 'import json; from pathlib import Path; p=Path("plugins/ue-design-skills"); print(len(json.loads((p/"catalog.json").read_text())["skills"]), sum(x.is_dir() for x in (p/"skills").iterdir()))'
```

Чтобы добавить скилл, создайте каталог с kebab-case-именем внутри `skills/`, добавьте `SKILL.md` с совпадающим полем `name` и непустым `description`, добавьте и свяжите ссылкой `references/failure-modes.md`, затем внесите в каталог соответствующую запись с обязательными полями маршрутизации. ID режимов отказа должны идти последовательно, а их префиксы — быть уникальными между скиллами. Перед предложением изменения запустите гейт поставки и его самотест; руководство для контрибьюторов просит сначала обсудить новый скилл и запускать каждый рецепт обнаружения на реальном дереве.

### Гейт поставки

`plugins/ue-design-skills/_gate/gate.py` объявляет **17 правил** (`P01`–`P17`). Они запрещают:

- абсолютные пути рабочих машин, ссылки вида «исходный файл и строка», имя донорского проекта вне раздела происхождения, кириллицу и неразрешимые wiki-ссылки;
- отсутствующий или некорректный фронтматтер скилла, отсутствующий или не связанный ссылкой документ с режимами отказа, неполные записи из шести полей, сломанные или выходящие за каталог относительные ссылки, непоследовательные ID и повторяющиеся префиксы ID;
- неожиданные файлы верхнего уровня бандла, мусорные и бинарные артефакты, имена харнесов и вендоров внутри скиллов, расхождение каталога с каталогами скиллов и имена экспериментальной поверхности инструментов движка в содержимом скиллов.

Гейт также проверяет форму манифеста Claude Code. Поверхность сканирования задана белым списком, а неожиданный путь верхнего уровня сам считается нарушением. Зелёный результат подтверждает форму поставки, ссылки, структуру и ограничения переносимости, но **не** истинность технических утверждений.

Вывести набор правил и воспроизвести их количество:

```bash
cd plugins/ue-design-skills
python3 _gate/gate.py --list-rules
python3 -c 'import sys; sys.path.insert(0, "_gate"); import gate; print(len(gate.RULES))'
```

Запустить гейт и самотест:

```bash
cd plugins/ue-design-skills
python3 _gate/gate.py .
python3 _gate/test_gate.py
```

Самотест начинает с `_gate/fixtures/clean`, вносит по одному намеренному «яду» для каждого объявленного правила и требует, чтобы это правило покраснело. Отдельно он проверяет, что каждый заявленный корневой файл действительно доходит до построчных проверок. Отравленные фикстуры нужны потому, что валидатор, который невозможно заставить упасть, ничего не защищает.

### Архитектурные решения

В репозитории **5 принятых решений MADR**. Количество воспроизводится командой `find docs/architecture/decisions -maxdepth 1 -type f -name '*.md' | wc -l`.

- [ADR-0001 — Discovery over PID file](docs/architecture/decisions/0001-discovery-over-pid-file.md): фиксирует живость процесса, автоматическое восстановление и корректную работу без редактора вместо доверия устаревающему PID-файлу; проект собственного транспорта сужен ADR-0005.
- [ADR-0002 — Harness-neutral skill bundle](docs/architecture/decisions/0002-harness-neutral-skill-bundle.md): назначает каталог источником истины, вендорские манифесты — адаптерами, а нейтральность скиллов к харнесу — проверяемым свойством.
- [ADR-0003 — Split licensing](docs/architecture/decisions/0003-split-licensing-prose-and-code.md): разделяет лицензии — CC BY-ND 4.0 для прозы бандла и Apache-2.0 для кода и метаданных — и задаёт явные дополнительные разрешения.
- [ADR-0004 — Engine tool surface stays out of skills](docs/architecture/decisions/0004-engine-tool-surface-out-of-skill-content.md): через правило P17 не допускает в скиллы экспериментальные и привязанные к версии имена тулсетов, мета-инструментов и эндпоинтов.
- [ADR-0005 — Native transport narrows ADR-0001](docs/architecture/decisions/0005-native-transport-narrows-adr-0001.md): отказывается от запланированных собственного сервера в редакторе, UDP-discovery и heartbeat в пользу проверки нативного транспорта движка, сохраняя контракт живости.

### Установка и использование

В Claude Code добавьте репозиторий как маркетплейс, затем установите единственный плагин:

```text
/plugin marketplace add https://github.com/MagentaDolphin/ue-toolchain
/plugin install ue-design-skills@ue-toolchain
```

Другому харнесу адаптер Claude не нужен. Прочитайте `plugins/ue-design-skills/catalog.json`, сопоставьте задачу с полем `use_when` каждой записи и загрузите её `entry`; другой вариант — целиком загрузить каталог выбранного скилла в контекст или открыть его `SKILL.md`. Это работает потому, что ADR-0002 оставляет вендорскую лексику за пределами `skills/`, а гейт контролирует эту границу.

### Лицензирование

Правообладатель указан под псевдонимом **MagentaDolphin**; издателем в `catalog.json` назван **MagentaDolphin**.

| Область | Лицензия или разрешение |
|---|---|
| Корневая документация, код и машиночитаемые материалы репозитория вне текстового бандла | [Apache License 2.0](LICENSE) |
| `plugins/ue-design-skills/skills/**`, справочная проза и README бандла | [CC BY-ND 4.0](plugins/ue-design-skills/LICENSE) |
| `catalog.json`, `.claude-plugin/plugin.json` и всё внутри `_gate/` | Apache-2.0 по явным исключениям лицензии бандла |
| Shell-команды внутри полей `Detect` | Apache-2.0; окружающая их проза остаётся под CC BY-ND 4.0 |

Лицензия бандла разрешает чтение и коммерческое использование, внутреннюю адаптацию и неизменённое распространение с указанием авторства. Дополнительные разрешения позволяют публиковать адаптеры формата и точные, явно помеченные неофициальные переводы на указанных условиях, а также форки и патчи ради передачи изменений обратно в проект. Публиковать изменённую прозу как отдельный продукт нельзя. Ни одна из лицензий не предъявляет прав на игру пользователя, её исходный код, документацию, внутренние стандарты или выручку. Упоминание при использовании приветствуется, но не является условием лицензии; атрибуция обязательна при распространении самих материалов. Юридическую силу имеют тексты лицензий; репозиторий не выдаёт анализ лицензирования за юридическую консультацию.

### Требования и границы

- **Версия движка:** поставляемые скиллы рассчитаны на Unreal Engine **5.6**. Это материалы для design review, а не плагин движка; для чтения и маршрутизации открытый редактор не нужен.
- **Для Claude Code:** установите Claude Code с поддержкой маркетплейса плагинов и выполните две команды выше. Минимальная версия Claude Code в репозитории не задокументирована.
- **Для других харнесов:** харнес должен уметь читать Markdown и JSON как контекст. Для прямого чтения среда агента не требуется.
- **Для сопровождающих:** гейт поставки и самотест запускаются на Python 3. Минимальная минорная версия Python не задокументирована.

В этом репозитории сейчас **нет** моста редактора, MCP-сервера, установщика, C++-модуля UE и тестового UE-проекта. В описании маркетплейса упомянуты мост редактора и MCP-сервер, но их реализаций в дереве нет; ADR-0005 также фиксирует, что проект собственного моста был снят до реализации. Отдельный сервер файловых и аналитических инструментов и слой инструментов для запущенной вне редактора игры остаются архитектурным планом, а не поставляемыми функциями.

Бандл не запускает ревью автоматически, не изменяет UE-проект, не доказывает корректность архитектуры, не сертифицирует производительность или безопасность и не гарантирует, что рецепт обнаружения покрывает конкретную кодовую базу. Гейт проверяет упаковку и форму, а не истинность утверждений. Материал описывает переносимые формы отказов, полученные в процессе исследования исходников; это не список дефектов для любого проекта или любой версии движка.

### Ссылки

- Репозиторий: [https://github.com/MagentaDolphin/ue-toolchain](https://github.com/MagentaDolphin/ue-toolchain)
- Автор: **MagentaDolphin**; издатель, указанный в каталоге: **Kodlo.art**
