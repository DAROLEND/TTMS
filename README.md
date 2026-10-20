# TTMS: система управління завданнями команди

Університетський проєкт: консольний застосунок на чистому Python для ведення проєкту,
учасників і завдань, плюс дашборд аналітики на Streamlit.

- Стан зберігається в JSON (`data/state.json`), бази даних немає.
- Без фреймворків: доменна модель — звичайні класи з наслідуванням,
  абстрактним базовим класом і поліморфізмом.
- Детальний план робіт — [PLAN.md](PLAN.md), контракти між напрямами —
  [docs/CONTRACTS.md](docs/CONTRACTS.md), правила роботи з репозиторієм —
  [CONTRIBUTING.md](CONTRIBUTING.md).

## Команда

| Напрям | Що робить | Відповідальний |
|---|---|---|
| 1. Архітектура та ООП | `task_manager/domain/`, `task_manager/exceptions.py`, `docs/CONTRACTS.md` | `<ІМʼЯ 1>` |
| 2. Інфраструктура та якість | `task_manager/storage/`, `task_manager/cli.py`, `tests/` | `<ІМʼЯ 2>` |
| 3. Аналітика | `task_manager/analytics/`, `task_manager/dashboard.py` | `<ІМʼЯ 3>` |

## Як запустити

Потрібен Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m task_manager.cli                        # консольний застосунок (Напрям 2)
python -m streamlit run task_manager/dashboard.py # дашборд (Напрям 3)
python -m pytest                                  # тести (Напрям 2)
```

Усі команди запускаються **з кореня репозиторію** і через `python -m`: так корінь потрапляє
в `sys.path`, і працює `import task_manager`.

## Структура

```
task_manager/
  exceptions.py        ієрархія винятків (TaskManagerError і нащадки)
  domain/              Напрям 1: доменні класи
    enums.py           Status, Priority
    notifiable.py      абстрактний клас Notifiable
    task.py            Task + таблиця переходів статусів
    team_member.py     TeamMember
    project.py         Project
  storage/             Напрям 2
    serializer.py      to_dict / from_dict, save_state / load_state
  analytics/           Напрям 3
    stats.py           pandas-метрики
    decorators.py      @log_status_change
  cli.py               Напрям 2: точка входу
  dashboard.py         Напрям 3: Streamlit
tests/                 Напрям 2: pytest
docs/CONTRACTS.md      публічні сигнатури й формат JSON
data/                  state.json (не комітиться)
logs/                  *.log (не комітяться)
```

Головне архітектурне правило: **`domain/` нічого не знає про JSON, pandas і консоль.**
Зберігання, аналітика й інтерфейс залежать від домену, але не навпаки.
