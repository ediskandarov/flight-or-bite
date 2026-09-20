# Шаблоны запросов Jev — на утверждение автору

Сгенерировано из `configs/jev_prompts/*.yaml` (тексты дословные). **Черновик v0**: все четыре шаблона написаны до какого-либо ответа Jev по ним; `naive`, `informed`, `bucketed` — коммит `713fe97`, `informed_bucketed` — `089b526`; числа в правилах обновлены под среду D31 (`20a5dc2`). По SPEC §4.3 шаблоны настраиваются только на `dev` и замораживаются хэшами в `PREREG.md`. **M4 не начинается, пока автор не утвердит тексты.**

Модель: `typesafe/jev-1.13` (ответ не из этого семейства прерывает прогон). Эндпоинт: `POST https://openrouter.ai/api/alpha/decisions`, заголовок `X-OpenRouter-Cache: false`. Один вопрос типа `choice` с идентификатором `action`. Действие арбитра — поле `choice` ответа (D27); вероятности — поле `probabilities`.

## Дизайн 2 × 2

| | наблюдение числами | наблюдение уровнями |
|---|---|---|
| **без правил** | `naive` | `bucketed` |
| **с правилами среды** | `informed` | `informed_bucketed` |

- Числа наблюдения округляются до 2 знаков.
- Уровни (5 равных по ширине, границы заданы до просмотра данных): ровно 0 → `none`; (0, 0.2) → `very low`; [0.2, 0.4) → `low`; [0.4, 0.6) → `medium`; [0.6, 0.8) → `high`; [0.8, 1] → `very high`.
- Числа в правилах взяты из `configs/env.yaml`: `p_food` 0.3, `eat_gain` 8, `escape_cost` 1, `toxic_cost` 15, `p_toxic` 0.25, `p_threat` 0.2, `p_death_eat` 0.6, `p_death_idle` 0.3, looming N(0.7, 0.2) / N(0.2, 0.2). Совпадение проверяется тестом `tests/test_jev_arbiter.py`.

## `naive`

Файл `configs/jev_prompts/naive.yaml`, SHA-256 `9cfb1e2a6335561de42f95545771ffb63cfe06813b9823a47b63034701779fc4`, версия v0.

**instructions:** Which action should the agent take?

**criteria:**

- `EAT`: `null` (без описания)
- `ESCAPE`: `null` (без описания)
- `IDLE`: `null` (без описания)

**state** для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "sugar": 0.6,
  "bitter": 0.05,
  "looming": 0.5,
  "hunger": 0.5
}
```

Тело HTTP-запроса целиком (как уходит в сеть):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6}}
```

## `informed`

Файл `configs/jev_prompts/informed.yaml`, SHA-256 `3f90b023765ef630d94a2180083a8a0c621e7cf947de776020342dd984ca4ef2`, версия v0.

**instructions:** Which action should the agent take on this trial?

**criteria:**

- `EAT`: «Eat the food that is present on this trial.»
- `ESCAPE`: «Flee from a possible predator.»
- `IDLE`: «Do nothing on this trial.»

**rules** (поле `state.rules`):

> An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 1 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3.

**state** для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "rules": "<текст rules выше>",
  "observation": {
    "sugar": 0.6,
    "bitter": 0.05,
    "looming": 0.5,
    "hunger": 0.5
  }
}
```

Тело HTTP-запроса целиком (как уходит в сеть):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":"Eat the food that is present on this trial.","ESCAPE":"Flee from a possible predator.","IDLE":"Do nothing on this trial."},"instructions":"Which action should the agent take on this trial?","type":"choice"}},"state":{"observation":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6},"rules":"An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 1 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3."}}
```

## `bucketed`

Файл `configs/jev_prompts/bucketed.yaml`, SHA-256 `acebaa97f3453c59a49d8b666a74dd4d33bfd2746b415115629f67aa0a1875ba`, версия v0.

**instructions:** Which action should the agent take?

**criteria:**

- `EAT`: `null` (без описания)
- `ESCAPE`: `null` (без описания)
- `IDLE`: `null` (без описания)

**state** для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "sugar": "high",
  "bitter": "very low",
  "looming": "medium",
  "hunger": "medium"
}
```

Тело HTTP-запроса целиком (как уходит в сеть):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":"very low","hunger":"medium","looming":"medium","sugar":"high"}}
```

## `informed_bucketed`

Файл `configs/jev_prompts/informed_bucketed.yaml`, SHA-256 `570473cb584c58e1bb101c5384a8217b7b6481764829158414d92e5a7313af4e`, версия v0.

**instructions:** Which action should the agent take on this trial?

**criteria:**

- `EAT`: «Eat the food that is present on this trial.»
- `ESCAPE`: «Flee from a possible predator.»
- `IDLE`: «Do nothing on this trial.»

**rules** (поле `state.rules`):

> An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1). `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 1 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3.

**state** для наблюдения sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5:

```json
{
  "rules": "<текст rules выше>",
  "observation": {
    "sugar": "high",
    "bitter": "very low",
    "looming": "medium",
    "hunger": "medium"
  }
}
```

Тело HTTP-запроса целиком (как уходит в сеть):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":"Eat the food that is present on this trial.","ESCAPE":"Flee from a possible predator.","IDLE":"Do nothing on this trial."},"instructions":"Which action should the agent take on this trial?","type":"choice"}},"state":{"observation":{"bitter":"very low","hunger":"medium","looming":"medium","sugar":"high"},"rules":"An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1). `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 1 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3."}}
```

## Чем `informed_bucketed` отличается от `informed`

Только фразой, описывающей наблюдение; остальной текст правил совпадает посимвольно (проверяется тестом).

- `informed`: «On every trial it observes four numbers between 0 and 1 and takes one action.»
- `informed_bucketed`: «On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1).»

## Что уже известно о поведении шаблонов

`reports/probe_jev.md` (exploratory, 300 вызовов): срез `p_escape` по looming для `naive`, `informed`, `bucketed`. **Сделан на прежних числах среды** (`p_food` 0.5, `eat_gain` 12, `escape_cost` 3) и без `informed_bucketed`; после утверждения текстов его нужно повторить (≈ 440 вызовов, ≈ $0.01).

## Вопросы к автору

1. Формулировка цели в правилах: «tries to stay alive for as many trials as possible, up to 500» — оставить? Это цель, а не подсказка оптимума.
2. В правилах нет слова о том, что ценность еды зависит от голода: это следствие правил, а не правило. Оставить так?
3. `criteria` в режимах без правил — `null`. Вендор советует описания, «разделяющие варианты»; в `naive` по смыслу SPEC §4.3 («только поля и числа») их нет. Оставить `null`?
4. Пять равных уровней в бакетах — оставить, или выровнять по структуре среды (например, граница 0.3 для `bitter`, где начинается токсичная еда)? Второе — подсказка модели, которой у `naive` нет.
5. Имена полей наблюдения (`sugar`, `bitter`, `looming`, `hunger`) — оставить как в спеке?
