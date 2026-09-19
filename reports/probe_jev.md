# Разведка Jev на черновых шаблонах v0 (exploratory)

Дата: 2026-09-20. Разведочный прогон (SPEC §8: exploratory), не таблица политик и не замер по протоколу §6.2. Шаблоны запросов закоммичены **до** первого вызова по ним (`713fe97`), границы бакетов заданы вслепую. Ничего не подгонялось; после просмотра этих данных шаблоны не менялись.

Модель: запрошена `typesafe/jev-1.13`, во всех 300 ответах — `typesafe/jev-1.13-20260917`. Стоимость прогона: $0.00592. Сырые обмены: `runs/jev_raw/20260920.jsonl` (300 строк); сводные записи: `runs/20260920T012605_probe-jev/probe.json`. Воспроизведение: `uv run python scripts/probe_jev.py`.

Срез: sugar = 0.6, bitter = 0.05, hunger = 0.5 (фон конфликтного среза коннектома из `reports/probe_looming.md` §5), looming от 0 до 1. По 20 одинаковых запросов в точках 0.2 / 0.5 / 0.8, по 5 в остальных.

## 1. Точные запросы (тело HTTP, looming = 0.5)

Файлы шаблонов: `configs/jev_prompts/{naive,informed,bucketed}.yaml`. Числа наблюдения округляются до 2 знаков. В `bucketed` пять равных уровней: [0, 0.2) very low, [0.2, 0.4) low, [0.4, 0.6) medium, [0.6, 0.8) high, [0.8, 1] very high; ровно 0 → none. `bucketed` = `naive` с заменой чисел словами (без правил среды) — чтобы отличие от `naive` было одно.

**naive** (SHA-256 шаблона `9cfb1e2a6335561d…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6}}
```

**informed** (SHA-256 шаблона `ddfdc346007df9c7…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":"Eat the food that is present on this trial.","ESCAPE":"Flee from a possible predator.","IDLE":"Do nothing on this trial."},"instructions":"Which action should the agent take on this trial?","type":"choice"}},"state":{"observation":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6},"rules":"An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 50% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 12 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 3 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3."}}
```

**bucketed** (SHA-256 шаблона `acebaa97f3453c59…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":"very low","hunger":"medium","looming":"medium","sugar":"high"}}
```

## 2. Срез p_escape по looming

Вероятности — как их вернул API, перенормированные на сумму. Суммы сырых значений по 300 ответам: от 0.99 до 1.0 (0.99: 2 отв., 1.0: 298 отв.).

**naive**

| looming | n | p_escape: среднее (SD) [min–max] | p_eat: среднее (SD) | p_idle: среднее | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.002 (0.004) [0.00–0.01] | 0.914 (0.010) | 0.084 | EAT 5 |
| 0.1 | 5 | 0.016 (0.005) [0.01–0.02] | 0.938 (0.012) | 0.046 | EAT 5 |
| 0.2 | 20 | 0.030 (0.009) [0.02–0.05] | 0.928 (0.013) | 0.042 | EAT 20 |
| 0.3 | 5 | 0.082 (0.023) [0.06–0.11] | 0.890 (0.021) | 0.028 | EAT 5 |
| 0.4 | 5 | 0.156 (0.033) [0.12–0.20] | 0.818 (0.028) | 0.026 | EAT 5 |
| 0.5 | 20 | 0.261 (0.022) [0.22–0.30] | 0.710 (0.022) | 0.030 | EAT 20 |
| 0.6 | 5 | 0.458 (0.029) [0.41–0.50] | 0.518 (0.026) | 0.024 | EAT 4, ESCAPE 1 |
| 0.7 | 5 | 0.584 (0.042) [0.52–0.65] | 0.406 (0.042) | 0.010 | ESCAPE 5 |
| 0.8 | 20 | 0.668 (0.026) [0.62–0.72] | 0.322 (0.026) | 0.010 | ESCAPE 20 |
| 0.9 | 5 | 0.746 (0.019) [0.71–0.76] | 0.246 (0.017) | 0.008 | ESCAPE 5 |
| 1.0 | 5 | 0.742 (0.007) [0.73–0.75] | 0.248 (0.007) | 0.010 | ESCAPE 5 |

**informed**

| looming | n | p_escape: среднее (SD) [min–max] | p_eat: среднее (SD) | p_idle: среднее | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.016 (0.008) [0.01–0.03] | 0.958 (0.015) | 0.026 | EAT 5 |
| 0.1 | 5 | 0.022 (0.004) [0.02–0.03] | 0.932 (0.007) | 0.046 | EAT 5 |
| 0.2 | 20 | 0.035 (0.007) [0.02–0.05] | 0.896 (0.014) | 0.069 | EAT 20 |
| 0.3 | 5 | 0.094 (0.010) [0.08–0.11] | 0.818 (0.021) | 0.088 | EAT 5 |
| 0.4 | 5 | 0.190 (0.025) [0.16–0.22] | 0.700 (0.038) | 0.110 | EAT 5 |
| 0.5 | 20 | 0.324 (0.030) [0.28–0.41] | 0.569 (0.033) | 0.107 | EAT 20 |
| 0.6 | 5 | 0.590 (0.030) [0.54–0.63] | 0.342 (0.033) | 0.068 | ESCAPE 5 |
| 0.7 | 5 | 0.650 (0.013) [0.63–0.66] | 0.302 (0.015) | 0.048 | ESCAPE 5 |
| 0.8 | 20 | 0.742 (0.030) [0.70–0.82] | 0.215 (0.028) | 0.044 | ESCAPE 20 |
| 0.9 | 5 | 0.806 (0.031) [0.77–0.86] | 0.154 (0.030) | 0.040 | ESCAPE 5 |
| 1.0 | 5 | 0.702 (0.040) [0.64–0.75] | 0.262 (0.035) | 0.036 | ESCAPE 5 |

**bucketed**

| looming | n | p_escape: среднее (SD) [min–max] | p_eat: среднее (SD) | p_idle: среднее | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.002 (0.004) [0.00–0.01] | 0.878 (0.023) | 0.120 | EAT 5 |
| 0.1 | 5 | 0.010 (0.000) [0.01–0.01] | 0.896 (0.015) | 0.094 | EAT 5 |
| 0.2 | 20 | 0.010 (0.000) [0.01–0.01] | 0.894 (0.014) | 0.096 | EAT 20 |
| 0.3 | 5 | 0.010 (0.000) [0.01–0.01] | 0.894 (0.016) | 0.096 | EAT 5 |
| 0.4 | 5 | 0.136 (0.016) [0.12–0.16] | 0.820 (0.017) | 0.044 | EAT 5 |
| 0.5 | 20 | 0.142 (0.022) [0.10–0.18] | 0.816 (0.022) | 0.043 | EAT 20 |
| 0.6 | 5 | 0.600 (0.033) [0.55–0.64] | 0.390 (0.033) | 0.010 | ESCAPE 5 |
| 0.7 | 5 | 0.578 (0.024) [0.55–0.62] | 0.412 (0.024) | 0.010 | ESCAPE 5 |
| 0.8 | 20 | 0.742 (0.030) [0.67–0.77] | 0.248 (0.030) | 0.010 | ESCAPE 20 |
| 0.9 | 5 | 0.728 (0.039) [0.67–0.78] | 0.262 (0.039) | 0.010 | ESCAPE 5 |
| 1.0 | 5 | 0.712 (0.052) [0.64–0.78] | 0.278 (0.052) | 0.010 | ESCAPE 5 |

## 3. Разброс по повторам одинакового запроса

| Режим | looming | n | SD p_eat | SD p_escape | SD p_idle | различных векторов |
|---|---|---|---|---|---|---|
| naive | 0.2 | 20 | 0.0135 | 0.0092 | 0.0081 | 11 из 20 |
| naive | 0.5 | 20 | 0.0220 | 0.0223 | 0.0022 | 9 из 20 |
| naive | 0.8 | 20 | 0.0258 | 0.0258 | 0.0000 | 10 из 20 |
| informed | 0.2 | 20 | 0.0139 | 0.0067 | 0.0109 | 10 из 20 |
| informed | 0.5 | 20 | 0.0332 | 0.0301 | 0.0131 | 16 из 20 |
| informed | 0.8 | 20 | 0.0284 | 0.0297 | 0.0065 | 13 из 20 |
| bucketed | 0.2 | 20 | 0.0139 | 0.0000 | 0.0139 | 6 из 20 |
| bucketed | 0.5 | 20 | 0.0222 | 0.0215 | 0.0094 | 16 из 20 |
| bucketed | 0.8 | 20 | 0.0304 | 0.0304 | 0.0022 | 11 из 20 |

## 4. Для сопоставления: оракул и fixed_priority в тех же точках

Оракул детерминирован (SPEC §4.4); апостериор угрозы — по Байесу из looming.

| looming | P(угроза \| looming) | действие оракула | действие fixed_priority |
|---|---|---|---|
| 0.0 | 0.000 | EAT | EAT |
| 0.1 | 0.003 | EAT | EAT |
| 0.2 | 0.011 | EAT | EAT |
| 0.3 | 0.037 | EAT | EAT |
| 0.4 | 0.118 | ESCAPE | EAT |
| 0.5 | 0.318 | ESCAPE | EAT |
| 0.6 | 0.620 | ESCAPE | ESCAPE |
| 0.7 | 0.851 | ESCAPE | ESCAPE |
| 0.8 | 0.952 | ESCAPE | ESCAPE |
| 0.9 | 0.986 | ESCAPE | ESCAPE |
| 1.0 | 0.998 | ESCAPE | ESCAPE |

## 5. Время (клиентское t_wall арбитра: сборка запроса + HTTP + разбор + сэмплирование)

Последовательные вызовы в одной keep-alive-сессии, из процесса агента, ночью; без прогрева, первый вызов каждого режима включён. Это не замер по протоколу §6.2.

| Режим | n | p50, мс | p95, мс | min | max |
|---|---|---|---|---|---|
| naive | 100 | 370.8 | 619.8 | 286.8 | 1342.9 |
| informed | 100 | 361.0 | 483.9 | 295.2 | 1539.6 |
| bucketed | 100 | 364.7 | 492.0 | 294.4 | 567.4 |
| все | 300 | 365.8 | 500.9 | 286.8 | 1539.6 |

## 6. Чего здесь нет

- Других значений sugar, bitter, hunger; срезов по bitter; полной сетки.
- Настройки шаблонов (это черновик v0; по SPEC §4.3 шаблоны настраиваются только на `dev` и замораживаются в `PREREG.md`).
- Режима «informed + бакеты»; решено ли его добавлять — вопрос автору.
- Оценки выживаемости Jev в среде (нужны таблицы политик, веха M4).
