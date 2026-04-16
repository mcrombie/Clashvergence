from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BEFORE = ROOT / "reports/maintenance_strategy_comparison.txt"
DEFAULT_AFTER = ROOT / "reports/combat_doctrine_comparison.txt"
DEFAULT_OUTPUT = ROOT / "reports/pre_post_attack_balance_report.txt"


def parse_numeric(token):
    if token.endswith("%"):
        return float(token[:-1])
    return float(token)


def parse_report(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    results = {}
    current_map = None
    current_turns = None
    in_table = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("Map: "):
            current_map = line.split(": ", 1)[1]
            continue

        if line.startswith("Turns: "):
            current_turns = int(line.split(": ", 1)[1])
            continue

        if line.startswith("Faction") and ("Strategy" in line or "Doctrine" in line) and "Win" in line:
            in_table = True
            results[(current_map, current_turns)] = {}
            continue

        if in_table and set(line) == {"-"}:
            continue

        if in_table:
            if line.startswith("=") or line.startswith("Skipped Maps") or line.startswith("Map: "):
                in_table = False
                continue

            parts = line.split()
            if not parts or not parts[0].startswith("Faction"):
                in_table = False
                continue

            faction_name = parts[0]
            doctrine = parts[1]
            values = [parse_numeric(token) for token in parts[2:]]

            entry = {
                "doctrine": doctrine,
                "win_rate": values[0],
                "shared_rate": values[1],
                "treasury": values[2],
                "regions": values[3],
            }

            if len(values) == 7:
                entry["attacks"] = 0.0
                entry["income"] = values[4]
                entry["scale"] = 0.0
                entry["maintenance"] = values[5]
                entry["net"] = values[6]
            elif len(values) == 8:
                entry["attacks"] = values[4]
                entry["income"] = values[5]
                entry["scale"] = 0.0
                entry["maintenance"] = values[6]
                entry["net"] = values[7]
            else:
                entry["attacks"] = values[4]
                entry["income"] = values[5]
                entry["scale"] = values[6]
                entry["maintenance"] = values[7]
                entry["net"] = values[8]

            results[(current_map, current_turns)][faction_name] = entry

    return results


def build_delta_report(before_results, after_results, before_label, after_label):
    shared_keys = sorted(set(before_results) & set(after_results))
    lines = []
    lines.append("Pre/Post Attack Balance Report")
    lines.append("")
    lines.append(f"Before: {before_label}")
    lines.append(f"After: {after_label}")
    lines.append("")

    for map_name, turns in shared_keys:
        before = before_results[(map_name, turns)]
        after = after_results[(map_name, turns)]
        faction_names = sorted(before)

        before_winner = max(faction_names, key=lambda name: before[name]["win_rate"])
        after_winner = max(faction_names, key=lambda name: after[name]["win_rate"])
        biggest_win_shift = max(
            faction_names,
            key=lambda name: abs(after[name]["win_rate"] - before[name]["win_rate"]),
        )
        biggest_treasury_shift = max(
            faction_names,
            key=lambda name: abs(after[name]["treasury"] - before[name]["treasury"]),
        )

        lines.append(f"Map: {map_name} | Turns: {turns}")
        lines.append(
            f"Leader shift: {before_winner} ({before[before_winner]['win_rate']:.2f}%) -> "
            f"{after_winner} ({after[after_winner]['win_rate']:.2f}%)"
        )
        lines.append(
            f"Largest win-rate swing: {biggest_win_shift} "
            f"({after[biggest_win_shift]['win_rate'] - before[biggest_win_shift]['win_rate']:+.2f} pts)"
        )
        lines.append(
            f"Largest treasury swing: {biggest_treasury_shift} "
            f"({after[biggest_treasury_shift]['treasury'] - before[biggest_treasury_shift]['treasury']:+.2f})"
        )
        lines.append(
            f"{'Faction':<10} {'Doctrine':<13} {'WinDiff':>8} {'TreasDiff':>10} {'RegDiff':>8} {'NetDiff':>9} {'AtkAfter':>9}"
        )
        lines.append("-" * 74)

        for faction_name in faction_names:
            before_entry = before[faction_name]
            after_entry = after[faction_name]
            lines.append(
                f"{faction_name:<10} "
                f"{after_entry['doctrine']:<13} "
                f"{after_entry['win_rate'] - before_entry['win_rate']:>+7.2f} "
                f"{after_entry['treasury'] - before_entry['treasury']:>+9.2f} "
                f"{after_entry['regions'] - before_entry['regions']:>+8.2f} "
                f"{after_entry['net'] - before_entry['net']:>+9.2f} "
                f"{after_entry['attacks']:>9.2f}"
            )

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare pre-attack and post-attack balance reports."
    )
    parser.add_argument("--before", type=Path, default=DEFAULT_BEFORE)
    parser.add_argument("--after", type=Path, default=DEFAULT_AFTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    before_results = parse_report(args.before)
    after_results = parse_report(args.after)
    report_text = build_delta_report(
        before_results,
        after_results,
        before_label=args.before.name,
        after_label=args.after.name,
    )
    print(report_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
