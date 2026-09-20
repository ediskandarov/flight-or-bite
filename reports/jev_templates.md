# Шаблоны запросов Jev — версия v1

Сгенерировано `scripts/jev_templates_report.py` из `configs/jev_prompts/*.yaml`; тексты дословные. **v1 утверждена автором спецификации 2026-09-20 с правками; на `dev` не настраивалась.** Хэши файлов входят в `PREREG.md`.

Модель: `typesafe/jev-1.13` (ответ не из этого семейства прерывает прогон). Эндпоинт: `POST https://openrouter.ai/api/alpha/decisions`, заголовок `X-OpenRouter-Cache: false`. Один вопрос типа `choice` с идентификатором `action`. Действие арбитра — поле `choice` ответа (D27); вероятности — поле `probabilities`.

## Дизайн 2 × 2

| | наблюдение числами | наблюдение уровнями |
|---|---|---|
| **без пакета правил** | `naive` | `bucketed` |
| **с пакетом правил** | `informed` | `informed_bucketed` |

- **Фактор «правила» — пакет:** текст правил среды **и** описания вариантов в `criteria`; появляются и исчезают вместе, по отдельности не варьируются (D46).
- Правила идут в поле `instructions` **перед вопросом**; `state` содержит только наблюдение (D46).
- Вопрос одинаков во всех четырёх режимах: «Which action should the agent take on this trial?»
- Числа наблюдения округляются до 2 знаков.
- Уровни (5 равных по ширине): ровно 0 → `none`; (0, 0.2) → `very low`; [0.2, 0.4) → `low`; [0.4, 0.6) → `medium`; [0.6, 0.8) → `high`; [0.8, 1] → `very high`.
- Числа в правилах — из `configs/env.yaml`: `p_food` 0.3, `eat_gain` 8, `escape_cost` 1, `toxic_cost` 15, `p_toxic` 0.25, `p_threat` 0.2, `p_death_eat` 0.6, `p_death_idle` 0.3; совпадение проверяется тестом.
- В бакетных режимах запрашиваются только уникальные комбинации уровней (D47): на сетке B (1225 точек) это 900 разных запросов; остальные точки получают копии ответов с пометкой `cache_hit` и в статистику латентности не входят.

## `naive`

Файл `configs/jev_prompts/naive.yaml`, версия v1, SHA-256 `910c0642f29b36e6c0dec1c6610471b2456add7afe2ac01962f3caadf70781d8`.

**criteria:**

- `EAT`: `null` (без описания)
- `ESCAPE`: `null` (без описания)
- `IDLE`: `null` (без описания)

**instructions** (целиком, как уходит в запрос):

> Which action should the agent take on this trial?

Тело HTTP-запроса для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": null,
        "ESCAPE": null,
        "IDLE": null
      },
      "instructions": "Which action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": 0.05,
    "hunger": 0.5,
    "looming": 0.5,
    "sugar": 0.6
  }
}
```

## `informed`

Файл `configs/jev_prompts/informed.yaml`, версия v1, SHA-256 `6eb536568b51b7645cfccac878b8acc333336db5003857b7abd083a2262cebdb`.

**criteria:**

- `EAT`: «Eat the food that is present on this trial.»
- `ESCAPE`: «Flee from a possible predator.»
- `IDLE`: «Do nothing on this trial.»

**instructions** (целиком, как уходит в запрос):

> An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.
>
> Which action should the agent take on this trial?

Тело HTTP-запроса для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": "Eat the food that is present on this trial.",
        "ESCAPE": "Flee from a possible predator.",
        "IDLE": "Do nothing on this trial."
      },
      "instructions": "An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.\n\nWhich action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": 0.05,
    "hunger": 0.5,
    "looming": 0.5,
    "sugar": 0.6
  }
}
```

## `bucketed`

Файл `configs/jev_prompts/bucketed.yaml`, версия v1, SHA-256 `66d4c17ab751e32a2ca695700f28ab23f1677bcbf743a5ebf216298688407f0e`.

**criteria:**

- `EAT`: `null` (без описания)
- `ESCAPE`: `null` (без описания)
- `IDLE`: `null` (без описания)

**instructions** (целиком, как уходит в запрос):

> Which action should the agent take on this trial?

Тело HTTP-запроса для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": null,
        "ESCAPE": null,
        "IDLE": null
      },
      "instructions": "Which action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": "very low",
    "hunger": "medium",
    "looming": "medium",
    "sugar": "high"
  }
}
```

## `informed_bucketed`

Файл `configs/jev_prompts/informed_bucketed.yaml`, версия v1, SHA-256 `36166bffca8afe8eb092c997198147d34cf2b44461c4b2c1b70434085f4d2b74`.

**criteria:**

- `EAT`: «Eat the food that is present on this trial.»
- `ESCAPE`: «Flee from a possible predator.»
- `IDLE`: «Do nothing on this trial.»

**instructions** (целиком, как уходит в запрос):

> An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1). `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.
>
> Which action should the agent take on this trial?

Тело HTTP-запроса для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": "Eat the food that is present on this trial.",
        "ESCAPE": "Flee from a possible predator.",
        "IDLE": "Do nothing on this trial."
      },
      "instructions": "An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1). `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.\n\nWhich action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": "very low",
    "hunger": "medium",
    "looming": "medium",
    "sugar": "high"
  }
}
```

## Чем `informed_bucketed` отличается от `informed`

Только фразой, описывающей наблюдение; остальной текст правил и `criteria` совпадают посимвольно (проверяется тестом).

- `informed`: «On every trial it observes four numbers between 0 and 1 and takes one action.»
- `informed_bucketed`: «On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1).»
