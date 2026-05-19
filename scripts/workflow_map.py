from __future__ import annotations

import argparse


FULL_STEPS = [
    ("idea", "DeepSeek idea lab"),
    ("agents", "product_founder / technical_lead / qa_release"),
    ("manifest", "idea-agent-manifest"),
    ("synthesis", "codex_synthesis A/B/C"),
    ("freeze", "idea-select + core_setting_freeze"),
    ("brief_pack", "brief-candidates pack"),
    ("brief_candidates", "Codex/DeepSeek brief candidates"),
    ("brief_landing", "select-brief + land-brief"),
    ("context", "start: derived state + context pack + quality"),
    ("drafts", "Codex/DeepSeek chapter candidates"),
    ("candidate_selection", "select-candidate"),
    ("chapter_landing", "official chapter landing provenance"),
    ("reviews", "Codex/DeepSeek reviews + model disagreement"),
    ("events", "human-confirmed event ledger entries"),
    ("close", "chapter evidence + close"),
    ("gates", "Gate A/B/C/E/F/G/H"),
]

GATES = [
    ("A", "3 chapters"),
    ("B", "10 chapters"),
    ("C", "25 chapters"),
    ("E", "125 chapters"),
    ("F", "200 chapters"),
    ("G", "500 chapters"),
    ("H", "800 chapters"),
]


def print_text(gates_only: bool) -> None:
    print("# Workflow Map")
    print()
    if not gates_only:
        for index, (_key, label) in enumerate(FULL_STEPS, 1):
            print(f"{index}. {label}")
        print()
    print("## Gates")
    for gate, threshold in GATES:
        print(f"- Gate {gate}: after {threshold}; evidence check first, human decision only.")


def print_mermaid(gates_only: bool) -> None:
    print("flowchart TD")
    if gates_only:
        previous = None
        for gate, threshold in GATES:
            node = f"G{gate}"
            print(f'  {node}["Gate {gate}: {threshold}"]')
            if previous:
                print(f"  {previous} --> {node}")
            previous = node
        return
    for key, label in FULL_STEPS:
        print(f'  {key}["{label}"]')
    for (left, _), (right, _) in zip(FULL_STEPS, FULL_STEPS[1:]):
        print(f"  {left} --> {right}")
    print('  gates --> GA["Gate A: 3 chapters"]')
    print('  GA --> GB["Gate B: 10 chapters"]')
    print('  GB --> GC["Gate C: 25 chapters"]')
    print('  GC --> GE["Gate E: 125 chapters"]')
    print('  GE --> GF["Gate F: 200 chapters"]')
    print('  GF --> GG["Gate G: 500 chapters"]')
    print('  GG --> GH["Gate H: 800 chapters"]')


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the workflow dependency map.")
    parser.add_argument("--format", choices=["text", "mermaid"], default="text")
    parser.add_argument("--gates-only", action="store_true")
    args = parser.parse_args()
    if args.format == "mermaid":
        print_mermaid(args.gates_only)
    else:
        print_text(args.gates_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
