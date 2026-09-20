"""`fob report`: reports/final_report.md and PNG figures, from artefacts only (SPEC §10).

The text states what PREREG.md asks to be stated and nothing more; a missing artefact is printed as
missing, never filled in. Wording: «LIF-симуляция коннектома», «арбитр», «политика» (SPEC §14).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flight_or_bite.report import analyses, figures

OUT = Path("reports/final_report.md")
MISSING = "_Нет данных: артефакт ещё не получен._"
G6_SENTENCE = "выводы зависят от ручных параметров"
EXPLORATORY = ["probe_looming.md", "probe_jev.md", "probe_interaction.md", "probe_r5.md", "grid_loss.md",
               "env_sweep.md", "calibration.md", "jev_mode_selection.md", "eval_dev.md", "perf.md"]  # fmt: skip


def _ci(v: list[float] | None, fmt: str = "+.1f") -> str:
    return "—" if not v else f"[{v[0]:{fmt}}, {v[1]:{fmt}}]"


def _p(p: float | None) -> str:
    return "—" if p is None else (f"{p:.2g}" if p < 0.001 else f"{p:.4f}")


def _yes(flag: bool) -> str:
    return "**подтверждена**" if flag else "**не подтверждена**"


def _fig(path: str | None, caption: str) -> list[str]:
    return ["", f"![{caption}]({path})", f"*{caption}*", ""] if path else []


def main_metric(s: dict | None, title: str, primary: bool) -> list[str]:
    out = [f"## {title}", ""]
    if not s:
        return out + [MISSING, ""]
    out += [f"Парных эпизодов: **{s['episodes']}**; остановок по политике сбоев Jev (PREREG §2b): **{len(s['stops'])}**; "
            f"решений с повтором после сетевой ошибки: {s['retried_decisions'] or 'нет'}.", "",
            "| Арбитр | Жизнь, триалов: среднее [95% ДИ] | медиана | % от оракула [95% ДИ] | смерти: хищник / голод / "
            "токсин / дожил | EAT / ESCAPE / IDLE | средняя энергия | итоговая энергия |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for n, r in s["arbiters"].items():
        c, a = r["causes"], r["actions"]
        alive = 1 - c["predator"] - c["starvation"] - c["toxin"] - c.get("missed_deadline", 0)
        out.append(f"| `{n}` | {r['lifetime_mean']:.1f} {_ci(r['lifetime_ci95'], '.1f')} | {r['lifetime_median']:.0f} | "
                   f"{r['percent_of_oracle']:.1%} {_ci([100 * x for x in r['percent_of_oracle_ci95']], '.0f')} | "
                   f"{c['predator']:.0%} / {c['starvation']:.0%} / {c['toxin']:.0%} / {alive:.0%} | "
                   f"{a['eat']:.0%} / {a['escape']:.0%} / {a['idle']:.0%} | {r['mean_energy']:.1f} | "
                   f"{r['final_energy_mean']:.1f} |")  # fmt: skip
    pairs = s["paired_differences"]
    key = next((k for k in pairs if set(k.split(" - ")) == set(analyses.MAIN)), None)
    if key:
        d = pairs[key]
        verdict = ("ДИ не включает ноль — по правилу PREREG §2 победитель: `"
                   + (key.split(" - ")[0] if d["mean_diff"] > 0 else key.split(" - ")[1]) + "`"
                   if d["significant"] else "ДИ включает ноль — по правилу PREREG §2 победитель не объявляется")  # fmt: skip
        label = "Основное сравнение (единственное, по которому объявляется победитель)" if primary else "Сравнение"
        out += ["", f"**{label}: {key} = {d['mean_diff']:+.1f} триала, 95% ДИ {_ci(d['ci95'])}.** {verdict}."]
    out += ["", "Остальные парные разницы (описательные):", "", "| Сравнение | Разница | 95% ДИ | ДИ не включает ноль |",
            "|---|---|---|---|"]  # fmt: skip
    out += [f"| {k} | {d['mean_diff']:+.1f} | {_ci(d['ci95'])} | {'да' if d['significant'] else 'нет'} |"
            for k, d in pairs.items() if k != key]  # fmt: skip
    for stop in s["stops"]:
        out.append(f"- остановка {stop['ts']}: `{stop['arbiter']}`, сид {stop['seed']}: {stop['error'][:160]}")
    return out + [""]


def mcnemar_table(h: dict, outcome: str) -> list[str]:
    out = [
        f"| looming | пар | «{outcome}»: контроль | условие | b | c | p | p (Холм) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    out += [f"| {lv} | {x['n']} | {x['control_yes']} | {x['condition_yes']} | {x['b']} | {x['c']} | {_p(x['p'])} | "
            f"{_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    return out


def hypotheses(c: dict | None, h5: dict | None) -> list[str]:
    out = ["## 3. Подтверждающие гипотезы о LIF-симуляции коннектома (RQ1; PREREG §3)", ""]
    if not c:
        return out + [MISSING, ""]
    out += [f"Посчитаны один раз на сидах из PREREG; {c['n_pairs']} пар на уровень looming; поправка Холма по трём "
            f"уровням внутри гипотезы; α = 0.05. Прогон: `{c.get('run_dir', '?')}`.", ""]  # fmt: skip
    h = c["H1"]
    out += [f"### H1. Сахар 0.6 снижает вероятность спайка DNp01 — {_yes(h['confirmed'])}", "",
            f"Наименьший p с поправкой Холма: {_p(h['min_p_holm'])}; b > c на всех уровнях с дискордантными парами: "
            f"{'да' if h['b_gt_c_wherever_discordant'] else 'нет'}.", "", *mcnemar_table(h, "DNp01 дал спайк"), ""]  # fmt: skip
    h = c["H2"]
    doses = list(next(iter(h["levels"].values()))["spiked_by_dose"])
    out += [f"### H2. Подавление монотонно растёт с дозой сахара — {_yes(h['confirmed'])}", "",
            f"Перестановочный тест тренда, односторонний; наименьший p (Холм): {_p(h['min_p_holm'])}.", "",
            "| looming | " + " | ".join(f"спайков DNp01 при sugar {d}" for d in doses) + " | из | p | p (Холм) |",
            "|---|" + "---|" * (len(doses) + 3)]  # fmt: skip
    out += [f"| {lv} | " + " | ".join(str(x["spiked_by_dose"][d]) for d in doses) +
            f" | {x['n']} | {_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    h = c["H3"]
    out += ["", f"### H3. Абляция M_loom снимает эффект — {_yes(h['confirmed'])}", "",
            f"Знаковый тест по ненулевым d; наименьший p (Холм): {_p(h['min_p_holm'])}. Доля эффекта, сохранённая при "
            f"абляции (по всем уровням): {h['retained_fraction'] if h['retained_fraction'] is None else round(h['retained_fraction'], 3)}"
            f", 95% ДИ {_ci(h['retained_ci95'], '.3f')}.", "",
            "| looming | эффект без абляции (контроль − условие) | эффект при абляции | d > 0 | d < 0 | Σd | p | p (Холм) |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    out += [f"| {lv} | {x['effect_intact']} | {x['effect_ablated']} | {x['d_positive']} | {x['d_negative']} | {x['sum_d']} | "
            f"{_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    h = c["H4"]
    add = h["additional_outcome_dnp01_spiked"]
    out += ["", f"### H4. Голод 1 против 0 при сахаре 0.6 снижает P(ESCAPE) — {_yes(h['confirmed'])}", "",
            f"Основной исход — «декодер назвал ESCAPE»; наименьший p (Холм): {_p(h['min_p_holm'])}.", "",
            *mcnemar_table(h, "ESCAPE"), "",
            f"Дополнительный исход «DNp01 дал спайк» (в критерий не входит): наименьший p (Холм) {_p(add['min_p_holm'])}; "
            f"тот же критерий дал бы: {'да' if add['confirmed'] else 'нет'}.", "", *mcnemar_table(add, "DNp01 дал спайк"), ""]  # fmt: skip
    out += ["## 4. Плановый анализ устойчивости H1 (PREREG §4; не подтверждающий)", "",
            "| № | Вариант | исход | «да» в контроле / в условии (из 100) по уровням looming | b / c по уровням looming | знак сохранён (b > c) | наименьший p (Холм) | значимо |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in sorted(c["robustness"], key=lambda r: r["variant"]):
        bc = "; ".join(f"{lv}: {x['b']} / {x['c']}" for lv, x in r["levels"].items())
        yes = "; ".join(f"{lv}: {x['control_yes']} / {x['condition_yes']}" for lv, x in r["levels"].items())
        out.append(f"| {r['variant']} | {r['name']} | {r['outcome']} | {yes} | {bc} | "
                   f"{'да' if r['b_gt_c_wherever_discordant'] else 'нет'} | {_p(r['min_p_holm'])} | "
                   f"{'да' if r['min_p_holm'] < 0.05 else 'нет'} |")  # fmt: skip
    out += ["", "Варианты ослабления ×0.5 (`r_max_sugar × 0.5`, `w_syn × 0.5`) в анализ не входят: **«сеть молчит»** "
            "(PREREG §4).", ""]  # fmt: skip
    out += ["## 5. H5: сдвиг кривой побега сахаром у Jev (RQ3; PREREG §5)", ""]
    if not h5:
        return out + [MISSING, ""]
    out += [f"Подтверждающее утверждение Δ_Jev ≠ 0 — {_yes(h5['confirmed'])}. Режим `{h5['jev_mode']}`, модель "
            f"{', '.join(h5['jev_models'])}; вызовов с повтором: {h5['jev_retried_calls']}.", "",
            "| Арбитр | Δ (среднее по 11 уровням looming) | 95% ДИ | знак | Δ − Δ_oracle | 95% ДИ |", "|---|---|---|---|---|---|",
            f"| oracle | {h5['delta_oracle']:+.4f} | — | {'−' if h5['delta_oracle'] < 0 else '+'} | — | — |"]  # fmt: skip
    for n in ("jev", "connectome"):
        d = h5[f"delta_{n}"]
        out.append(f"| {n} | {d:+.4f} | {_ci(h5[f'delta_{n}_ci95'], '+.4f')} | {'−' if d < 0 else '+' if d > 0 else '0'} | "
                   f"{h5[f'delta_{n}_minus_oracle']:+.4f} | {_ci(h5[f'delta_{n}_minus_oracle_ci95'], '+.4f')} |")  # fmt: skip
    out += ["", "`p_escape` по уровням looming (bitter 0, hunger 0.5):", "",
            "| арбитр, sugar | " + " | ".join(f"{x:.1f}" for x in h5["looming"]) + " |", "|---|" + "---|" * len(h5["looming"])]  # fmt: skip
    for n in ("oracle", "jev", "connectome"):
        out += [f"| {n}, {s} | " + " | ".join(f"{v:.2f}" for v in row) + " |" for s, row in h5[f"p_escape_{n}"].items()]
    return out + [""]


def gates(g: dict) -> list[str]:
    out = [
        "## 6. Ворота валидности (SPEC §5; результат M3, PREREG §6)",
        "",
        "| Ворота | метрика | порог | статус |",
        "|---|---|---|---|",
    ]
    out += [f"| {k} | {v['metric']:.4g} | {v['threshold']:.4g} | {'пройдены' if v['passed'] else '**НЕ пройдены**'} |"
            for k, v in g.items()]  # fmt: skip
    return out + ["", f"G6 не пройдены (9 вариантов из 11): **«{G6_SENTENCE}»**. Уточнение (D41): оба упавших варианта — "
                  "ослабление ×0.5 (`r_max_sugar × 0.5`, `w_syn × 0.5`); при них сеть молчит, смены знака нет. Пороги ворот "
                  "после просмотра результатов не менялись. Ворота посчитаны до перевода декодера на целые шаги (E13) и не "
                  "пересчитывались. Подробности — `reports/gates.md`.", ""]  # fmt: skip


def tables_section(t: dict | None, figs: dict) -> list[str]:
    out = ["## 7. Психометрика и калибровка (RQ3, RQ4; табличный режим, PREREG §7)", ""]
    if not t:
        return out + [MISSING, ""]
    out += ["| Таблица | строк | запрошено (без копий) | с повтором | проходы |", "|---|---|---|---|---|"]
    out += [
        f"| `{n}` | {r['rows']} | {r['queried']} | {r['retried']} | {r['sessions']} |" for n, r in t["rows"].items()
    ]
    missing = [f"jev_{m}" for m in analyses.JEV_MODES if f"jev_{m}" not in t["available"]]
    if missing or "connectome" not in t["available"]:
        out += ["", f"**Неполные или отсутствующие таблицы в анализ не входят:** {', '.join(missing) or '—'}"
                f"{'' if 'connectome' in t['available'] else ', connectome'}."]  # fmt: skip
    psy = t["psychometrics"]
    for key, title in (("escape_vs_looming", "p_escape(looming)"), ("eat_vs_bitter", "p_eat(bitter)")):
        out += [
            "",
            f"Логистический фит среза **{title}**:",
            "",
            "| Арбитр | порог x0 | крутизна k | примечание |",
            "|---|---|---|---|",
        ]
        for n, r in psy[key].items():
            th = "—" if r["threshold"] is None else f"{r['threshold']:.3f}"
            k = "—" if r["slope"] is None else f"{r['slope']:.2f}"
            out.append(f"| `{n}` | {th} | {k} | {'ступенька: середина между узлами' if r['degenerate'] else ''} |")
    out += ["", "Средняя дивергенция Дженсена—Шеннона по сетке B (основание 2):", "", "| Пара | JS |", "|---|---|"]
    out += [f"| {k} | {v:.4f} |" for k, v in psy["js_mean"].items()]
    out += [
        "",
        "Стабильность сервиса во времени — JS между политиками прохода 1 и прохода 2 (≥ 12 ч):",
        "",
        "| Режим | JS |",
        "|---|---|",
    ]
    out += [f"| `{n}` | {'один проход' if v is None else f'{v:.4f}'} |" for n, v in t["sessions_js"].items()]
    out += _fig(figs.get("psychometric"), "Психометрические срезы")
    out += _fig(figs.get("heatmaps"), "p_escape(sugar, looming) при bitter 0, hunger 0.5")
    out += ["### RQ4. Калибровка `p_escape` Jev относительно «ESCAPE оптимально по оракулу»", "",
            "| Режим | Brier | Brier константного прогноза (базовая частота) | базовая частота | прогнозов |", "|---|---|---|---|---|"]  # fmt: skip
    out += [f"| `{n}` | {c['brier']:.4f} | {c['brier_of_base_rate']:.4f} | {c['base_rate']:.3f} | {c['n']} |"
            for n, c in t["calibration"].items()]  # fmt: skip
    for n, c in t["calibration"].items():
        out += [
            "",
            f"Reliability-таблица, `{n}`:",
            "",
            "| интервал p | n | средняя p | доля «ESCAPE оптимально» |",
            "|---|---|---|---|",
        ]
        out += [
            f"| {r['bin']} | {r['n']} | {r['mean_p']:.3f} | {r['share_optimal']:.3f} |"
            for r in c["reliability"]
            if r["n"]
        ]
    return out + _fig(figs.get("reliability"), "Reliability-диаграмма") + [""]


def time_section(d: dict[str, Any], figs: dict) -> list[str]:
    out = ["## 8. Время решения (RQ5; PREREG §8)", "",
           "`t_wall` — эксплуатационная величина: у Jev она включает сеть и переход через OpenRouter, у LIF-симуляции "
           "коннектома зависит от этого компьютера; это не свойства моделей (SPEC §6.1). Заявления TypeSafe о скорости "
           "этот проект не проверяет. `t_sim` — симулированное время до события декодера.", "",
           "### 8.1 Замер по протоколу (`fob latency bench`, запускал автор)", ""]  # fmt: skip
    if d["latency"] and d["latency"]["arbiters"]:
        from flight_or_bite.timing.bench import render

        runs = (d["latency"]["meta"] or {}).get("runs", [])
        out += [render(d["latency"]), ""] + [f"- запуск `{r['run_dir']}`: питание «{r['throttle']['power']}», таймеры "
                                             f"троттлятся: {'да' if r['throttle']['timer_throttled'] else 'нет'}, t_load "
                                             f"{r['t_load_s']}" for r in runs] + [""]  # fmt: skip
    else:
        out += [MISSING, ""]
    out += ["### 8.2 Латентность решений главного онлайн-прогона", ""]
    m = d["main"]
    if m:
        out += ["| Арбитр | n | t_wall p50, мс | p95, мс | t_sim p50 / p95, мс | RTF | среднее t_wall, мс | t_wall на эпизод, с |",
                "|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for n, a in m["latency"].items():
            sim = f"{a['t_sim_p50_ms']:.1f} / {a['t_sim_p95_ms']:.1f}" if "rtf" in a else "—"
            rtf = f"{a['rtf']:.2f}" if "rtf" in a else "—"
            out.append(f"| `{n}` | {a['n']} | {a['p50_ms']:.3g} | {a['p95_ms']:.3g} | {sim} | {rtf} | "
                       f"{a['mean_ms']:.3g} | {a['per_episode_s']:.3g} |")  # fmt: skip
        out += _fig(figs.get("latency_ecdf"), "ECDF времени решения")
        out += ["### 8.3 Свип по дедлайну: доля решений, успевших к дедлайну", ""]
        for track in ("wall", "native"):
            names = list(m["deadline_share"][track])
            out += [
                f"Трек `{track}`:",
                "",
                "| дедлайн, мс | " + " | ".join(f"`{n}`" for n in names) + " |",
                "|---|" + "---|" * len(names),
            ]
            out += [f"| {dl:g} | " + " | ".join(f"{m['deadline_share'][track][n][str(dl)]:.1%}" for n in names) + " |"
                    for dl in d["deadlines"]] + [""]  # fmt: skip
        out += _fig(
            figs.get("deadline_sweep"),
            "Свип по дедлайну, два трека; линии `oracle`, `fixed_priority` и `random` совпадают, если все их решения укладываются в дедлайн",
        )
        out += _fig(figs.get("speed_vs_quality"), "Скорость против качества")
    else:
        out += [MISSING, ""]
    out += ["### 8.4 Хронометрическая гипотеза H6", ""]
    c = d["confirm"]
    if c:
        h = c["H6"]
        out += [f"**Основной тест (сахар задерживает первый спайк DNp01) — {_yes(h['confirmed'])}**; парный критерий Уилкоксона "
                f"по парам H1 со спайком в обоих плечах; наименьший p (Холм): {_p(h['min_p_holm'])}.", "",
                "| looming | пар | медиана t_sim: контроль, мс | условие, мс | медиана разностей, мс | p | p (Холм) |",
                "|---|---|---|---|---|---|---|"]  # fmt: skip
        out += [f"| {lv} | {x['n_pairs']} | {x['median_control_ms']:.1f} | {x['median_condition_ms']:.1f} | "
                f"{x['median_diff_ms']:+.1f} | {_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()
                if x["n_pairs"]] + [""]  # fmt: skip
    else:
        out += [MISSING, ""]
    t = d["tables"] or {}
    if "h6_secondary_connectome" in t:
        r = t["h6_secondary_connectome"]
        out += [f"Вторичный анализ (LIF-симуляция коннектома): ρ Спирмена между d и медианой `t_sim` в узле = "
                f"**{r['rho']:+.3f}**, 95% ДИ {_ci(r['ci95'], '+.3f')}; узлов {r['n_points']} (IDLE-триалы исключены, "
                "p_eat + p_escape ≥ 0.5).", ""]  # fmt: skip
    if "h6_jev" in t:
        r = t["h6_jev"]
        out += [f"Jev (`informed`), эквивалентность: ρ между d и медианой `t_wall` в узле = **{r['rho']:+.3f}**, 95% ДИ "
                f"{_ci(r['ci95'], '+.3f')}; узлов {r['n_points']}. Граница эквивалентности [−0.1, 0.1]: "
                f"**{'эквивалентность показана' if r['equivalence_shown'] else 'эквивалентность не показана'}**. "
                f"Дополнительно (в критерий не входит): ρ по отдельным вызовам = {r['per_call_rho']:+.3f} (n = {r['per_call_n']}).", ""]  # fmt: skip
    return out + _fig(figs.get("chronometric"), "Хронометрические кривые") + [""]


def build(out_path: Path = OUT) -> Path:
    d = analyses.collect()
    figs = figures.make_all(d)
    parts = {"главный онлайн-прогон (test)": d["main"], "вторичный прогон с сэмплированием": d["sampled"],
             "H1–H4, H6, устойчивость": d["confirm"], "H5": d["h5"], "таблицы политик": d["tables"],
             "замер латентности": d["latency"] and d["latency"]["arbiters"]}  # fmt: skip
    missing = [k for k, v in parts.items() if not v]
    lines = ["# Flight or Bite: итоговый отчёт", "",
             f"Собран {datetime.now().astimezone().isoformat(timespec='minutes')} командой `fob report` только из артефактов "
             "(без симуляций и без вызовов API). Предрегистрация — `PREREG.md` (заморожена 2026-09-20); всё, чего в ней нет, "
             "вынесено в раздел «Exploratory». Термины: «LIF-симуляция коннектома», «арбитр», «политика»; коннектом — "
             "статичная карта, вся динамика задана исполнителями (`docs/ENGINEERED.md`).", ""]  # fmt: skip
    if missing:
        lines += [f"> **ПРОМЕЖУТОЧНАЯ ВЕРСИЯ.** Ещё нет артефактов: {'; '.join(missing)}.", ""]
    lines += main_metric(d["main"], "1. Главная метрика (RQ2; PREREG §2): онлайн, нативное действие, test", True)
    lines += _fig(figs.get("survival"), "Кривые выживания")
    lines += main_metric(d["sampled"], "2. Вторичный анализ: действие сэмплируется из `probs` (100 эпизодов)", False)
    lines += (
        hypotheses(d["confirm"], d["h5"])
        + gates(d["gates"])
        + tables_section(d["tables"], figs)
        + time_section(d, figs)
    )
    ledger = d["ledger"] or {}
    lines += ["## 9. Не выяснялось и не утверждается", "", "См. `PREREG.md` §10 — список действует без изменений.", "",
              "## 10. Ограничения и отклонения", "",
              f"- G6 не пройдены: «{G6_SENTENCE}» (раздел 6).",
              "- Jev доступен только через alpha-эндпоинт OpenRouter Decisions; `t_wall` Jev включает этот переход (D12).",
              "- Таблицы политик Jev и LIF-симуляции коннектома строил агент из своего процесса; их `t_wall` не является замером "
              "по протоколу (используется только в анализе H6 для Jev). Замеры раздела 8.1 и главный прогон выполнял автор (D5).",
              "- Отклонения от SPEC перечислены в `docs/decisions.md` (D1–D62), ручные допущения — в `docs/ENGINEERED.md`.",
              f"- Расход вызовов Jev: {ledger.get('calls', '?')} из {ledger.get('max_calls', '?')}.",
              f"- Обращений к тестовому сплиту (строк `runs/test_access.log`): {len(d['test_access'])}.", "",
              "Прочтения там, где PREREG молчит (зафиксированы коммитом до просмотра таблиц и тестовых результатов):", ""]  # fmt: skip
    lines += [f"- {r}" for r in d["readings"]]
    lines += [
        "",
        "## 11. Exploratory",
        "",
        "Не подтверждающие материалы; ни один вывод отчёта на них не опирается:",
        "",
    ]
    lines += [f"- `reports/{name}`" for name in EXPLORATORY if (Path("reports") / name).is_file()]
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
