"""Build reports/gates.md from reports/gates/G*.json (facts only)."""

from __future__ import annotations

import json
from pathlib import Path

G = {
    n: json.loads(Path(f"reports/gates/{n}.json").read_text())
    for n in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
}
TITLE = {
    "G1": "Сахар → MN9",
    "G2": "Горькое подавляет сахар",
    "G3": "Looming → DNp01",
    "G4": "Настоящая против перемешанной",
    "G5": "Абляция",
    "G6": "Устойчивость",
    "G7": "Конфликт против независимой гонки",
}
yes = lambda b: "**пройдены**" if b else "**НЕ пройдены**"  # noqa: E731
fmt = lambda x: "—" if x is None else (f"{x:.3g}" if isinstance(x, float) else str(x))  # noqa: E731


def mc(x: dict) -> str:
    holm = f", p(Холм) = {x['p_holm']:.2g}" if "p_holm" in x else ""
    return f"{x['control_yes']}/{x['n']} → {x['condition_yes']}/{x['n']}; b = {x['b']}, c = {x['c']}; p = {x['p']:.2g}{holm}"


L = [
    "# Ворота валидности (M3)",
    "",
    f"Протокол — `configs/gates.yaml`, зафиксирован коммитом `921ffaf` **до** прогона; до него выполнялась только проверка на падения на посторонних сидах (вывод не просматривался). Прогон: `{G['G1']['run_dir']}`. Коннектом v783, бэкенд `event`, замороженное частотное кодирование (D36), декодер D25, полные триалы 500 мс. После просмотра результатов ничего не менялось. Сырые результаты — `reports/gates/G*.json`.",
    "",
    "| # | Ворота | Метрика | Порог | Статус |",
    "|---|---|---|---|---|",
]
for n, r in G.items():
    L.append(
        f"| {n} | {TITLE[n]} | {r['metric']:.4g} | {r['threshold']:.4g} | {yes(r['passed'])} |"
    )

d = G["G1"]["details"]
L += [
    "",
    "## G1. Сахар → MN9",
    "",
    f"ρ Спирмена по всем {len(d['sugar']) * d['n_rep']} триалам: **{G['G1']['metric']:.3f}** (по средним уровней: {d['rho_over_level_means']:.3f}).",
    "",
    "| sugar | " + " | ".join(f"{s:g}" for s in d["sugar"]) + " |",
    "|---|" + "---|" * len(d["sugar"]),
    "| MN9, Гц | " + " | ".join(f"{x:g}" for x in d["mn9_rate_hz_mean"]) + " |",
]
d = G["G2"]["details"]
L += [
    "",
    "## G2. Горькое подавляет сахар",
    "",
    f"sugar = 0.6, {d['n_rep']} парных триалов на уровень. Снижение `p_eat` от bitter 0 к bitter 1: **{G['G2']['metric']:.0%}**.",
    "",
    "| bitter | " + " | ".join(f"{b:g}" for b in d["bitter"]) + " |",
    "|---|" + "---|" * len(d["bitter"]),
    "| p_eat | " + " | ".join(f"{x:.2f}" for x in d["p_eat"]) + " |",
    "| MN9, Гц | " + " | ".join(f"{x:.1f}" for x in d["mn9_rate_hz_mean"]) + " |",
]
d = G["G3"]["details"]
L += [
    "",
    "## G3. Looming → DNp01",
    "",
    f"ρ Спирмена между looming и `p_escape` по {len(d['looming'])} уровням ({d['n_rep']} триалов на уровень): **{G['G3']['metric']:.3f}**.",
    "",
    "| looming | " + " | ".join(f"{s:g}" for s in d["looming"]) + " |",
    "|---|" + "---|" * len(d["looming"]),
    "| p_escape | " + " | ".join(f"{x:.2f}" for x in d["p_escape"]) + " |",
    "| t_sim ESCAPE p50, мс | " + " | ".join(fmt(x) for x in d["t_sim_ms_p50"]) + " |",
]
d = G["G4"]["details"]
L += [
    "",
    "## G4. Настоящая против перемешанной",
    "",
    "20 перемешиваний с сохранением степеней и знаков (сиды 1–20), тот же протокол, те же сиды триалов, то же кодирование (без повторной калибровки). Неопределённая метрика (постоянный отклик) считается равной 0.",
    "",
    "| Метрика | Настоящий граф | 95-й процентиль нулевых | максимум нулевых | нулевых > 0 | вне нулевого распределения |",
    "|---|---|---|---|---|---|",
]
for g in ("G1", "G2", "G3"):
    x = d[g]
    L.append(
        f"| {g} | {x['real']:.3f} | {x['null_percentile']:.3f} | {x['null_max']:.3f} | {sum(v > 0 for v in x['null'])} из {len(x['null'])} | {'да' if x['outside'] else 'нет'} |"
    )
d = G["G5"]["details"]
L += [
    "",
    "## G5. Абляция",
    "",
    "Аблированный нейрон не может дать спайк.",
    "",
    f"- DNp01 (оба) аблированы, looming = 1.0: `p_escape` = **{d['dnp01_ablated']['p_escape']:.2f}** (без абляции {d['dnp01_ablated']['p_escape_intact']:.2f}; критерий ≤ {d['dnp01_ablated']['max']}) — {'выполнен' if d['criteria']['dnp01'] else 'НЕ выполнен'}.",
    f"- MN9 аблирован, sugar = 1.0: `p_eat` = **{d['mn9_ablated']['p_eat']:.2f}** (без абляции {d['mn9_ablated']['p_eat_intact']:.2f}; критерий ≤ {d['mn9_ablated']['max']}) — {'выполнен' if d['criteria']['mn9'] else 'НЕ выполнен'}.",
    f"- M_loom (25 нейронов): доля сохранённого эффекта **{d['m_loom_ablated']['retained']:.2f}** (критерий ≤ {d['m_loom_ablated']['max_retained']}) — {'выполнен' if d['criteria']['m_loom'] else 'НЕ выполнен'}.",
    f"- Один cL20: доля сохранённого эффекта **{d['cl20_ablated']['retained']:.2f}** (без критерия).",
    "",
    "Эффект = b − c по трём уровням looming вместе (исход «DNp01 дал спайк», looming-only против sugar 0.6 + looming, одни сиды; абляция в обоих плечах). Формат: контроль → условие.",
    "",
    "| Условие | looming 0.6 | looming 0.8 | looming 1.0 | вместе | b − c |",
    "|---|---|---|---|---|---|",
]
for label, key in (
    ("без абляции", "suppression_intact"),
    ("M_loom аблирован", "m_loom_ablated"),
    ("cL20 аблирован", "cl20_ablated"),
):
    x = d[key]
    L.append(
        f"| {label} | "
        + " | ".join(mc(x["levels"][lv]) for lv in ("0.6", "0.8", "1.0"))
        + f" | {mc(x['pooled'])} | {x['effect_b_minus_c']} |"
    )
d = G["G6"]["details"]
L += [
    "",
    "## G6. Устойчивость",
    "",
    f"Вариант проходит, если затронутые ворота сохраняют знак и монотонность: G1 ρ > 0.8, G3 ρ > 0.8, G2 снижение > 0. Прошло **{int(G['G6']['metric'])} из {int(G['G6']['threshold'])}**. Число повторов меньше, чем в основных воротах (G1 10, G2 20, G3 20); сиды сдвинуты на 100 000.",
    "",
    "| Вариант | G1: ρ | G2: снижение p_eat (p_eat при bitter 0 → 1) | G3: ρ | проходит |",
    "|---|---|---|---|---|",
]
for v in d["variants"]:
    g2 = (
        "—"
        if "G2" not in v
        else f"{v['G2']['metric']:.2f} ({v['G2']['p_eat'][0]:.2f} → {v['G2']['p_eat'][-1]:.2f})"
    )
    L.append(
        f"| `{v['variant']}` | {fmt(v.get('G1', {}).get('metric'))} | {g2} | {fmt(v.get('G3', {}).get('metric'))} | {'да' if v['passed'] else '**нет**'} |"
    )
failed = [v for v in d["variants"] if not v["passed"]]
for v in failed:
    L += ["", f"Подробно `{v['variant']}`:"]
    if "G1" in v:
        L.append(
            "- MN9, Гц по уровням sugar: "
            + " / ".join(f"{x:g}" for x in v["G1"]["mn9_rate_hz_mean"])
        )
    if "G3" in v:
        L.append(
            "- p_escape по уровням looming: " + " / ".join(f"{x:.2f}" for x in v["G3"]["p_escape"])
        )
d = G["G7"]["details"]
L += [
    "",
    "## G7. Конфликт против независимой гонки (RQ1)",
    "",
    "Нулевая модель: контуры независимы, значит сахарный вход не может изменить, даст ли DNp01 спайк. sugar = 0.6, контроль — looming-only на тех же сидах, 40 пар на уровень, точный двусторонний тест Макнемара, поправка Холма по трём уровням.",
    "",
    "| looming | DNp01 дал спайк: контроль → условие; b, c; p | решения в контроле EAT / ESCAPE / IDLE | решения в условии |",
    "|---|---|---|---|",
]
for lv, x in d["levels"].items():
    a, b = x["decisions_control"], x["decisions_condition"]
    L.append(
        f"| {lv} | {mc(x)} | {a['EAT']} / {a['ESCAPE']} / {a['IDLE']} | {b['EAT']} / {b['ESCAPE']} / {b['IDLE']} |"
    )
L += [
    f"| вместе | {mc(d['pooled'])} | | |",
    "",
    f"Наименьший p с поправкой Холма: **{G['G7']['metric']:.2g}** (порог {G['G7']['threshold']}).",
]
L += [
    "",
    "## Что следует из статусов по SPEC §5",
    "",
    "- Провал G1–G3 или G5 → стоп и вопрос человеку. Провал G4 → публикуется негатив. Провал G6 → в отчёте «выводы зависят от ручных параметров». Непройденный G7 → «коннектом = гонка рефлексов».",
    "- Не сделано в M3: G1 на Brian2 при замороженном кодировании (эталон проверен в M1 при `R_max` = 200 Гц: `reports/gates/G1_m1_r200.json`); повторная калибровка на перемешанных графах.",
    "",
]
Path("reports/gates.md").write_text("\n".join(L))
print("wrote reports/gates.md")
