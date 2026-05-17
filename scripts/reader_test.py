from __future__ import annotations

import argparse
from pathlib import Path
import sys

from _common import ROOT, now_iso, read_json, write_json, write_text


GATE_QUESTIONS = {
    "A": [
        "主角想要什么？",
        "哪段最想继续看？",
        "哪段想跳过？",
        "世界观看得懂吗？",
        "最想知道下一章什么？",
        "会继续看第 4 章吗？",
    ],
    "B": [
        "主角欲望是否稳定？",
        "主要阻力是否稳定？",
        "每 3 章是否有继续动机？",
        "最大的阅读阻力是什么？",
        "会继续看第 11 章吗？",
    ],
}


def response_dir(gate: str) -> Path:
    return ROOT / "reader_tests" / "responses" / f"gate_{gate.lower()}"


def validate_answers(gate: str, answers: dict) -> list[str]:
    errors: list[str] = []
    for question in GATE_QUESTIONS[gate]:
        answer = str(answers.get(question, "")).strip()
        if not answer or answer in {"待填", "待定", "TODO"}:
            errors.append(f"missing answer for: {question}")
    return errors


def command_add(args: argparse.Namespace) -> int:
    answers = read_json(Path(args.answers), None) if args.answers else None
    if answers is None:
        answers = {question: "待填" for question in GATE_QUESTIONS[args.gate]}
    errors = validate_answers(args.gate, answers)
    if args.target_reader.strip() in {"", "unknown"} and not args.allow_unknown:
        errors.append("target reader must be identified; use --target-reader with a concrete value.")
    if errors and not args.allow_incomplete:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    record = {
        "gate": args.gate,
        "reader_id": args.reader,
        "target_reader": args.target_reader,
        "recorded_at": now_iso(),
        "answers": answers,
    }
    out = response_dir(args.gate) / f"{args.reader}.json"
    write_json(out, record)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


def command_summarize(args: argparse.Namespace) -> int:
    directory = response_dir(args.gate)
    responses = []
    for path in sorted(directory.glob("*.json")):
        responses.append(read_json(path, {}))

    out = ROOT / "reader_tests" / f"gate_{args.gate.lower()}_synthesis.md"
    lines = [
        f"# Gate {args.gate} Reader Synthesis",
        "",
        f"generated_at: {now_iso()}",
        f"response_count: {len(responses)}",
        "",
        "## 样本",
        "",
    ]
    if responses:
        for item in responses:
            lines.append(f"- {item.get('reader_id', 'unknown')} target_reader={item.get('target_reader', 'unknown')}")
    else:
        lines.append("无真实读者反馈。不得写留存率预测。")

    lines.extend(["", "## 读者回答摘要", ""])
    if responses:
        for item in responses:
            lines.append(f"### {item.get('reader_id', 'unknown')}")
            answers = item.get("answers", {})
            for question in GATE_QUESTIONS[args.gate]:
                lines.append(f"- {question} {answers.get(question, '未回答')}")
    else:
        lines.append("无。")

    lines.extend(
        [
            "",
            "## 留存风险",
            "",
            args.risk.strip() or "待人类根据反馈填写。",
            "",
            f"## Gate {args.gate} 建议",
            "",
            args.recommendation.strip() or "待人类裁决。",
        ]
    )
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and summarize reader-test evidence for gates.")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--gate", required=True, choices=sorted(GATE_QUESTIONS))
    add.add_argument("--reader", required=True)
    add.add_argument("--answers", default=None, help="Optional JSON file mapping questions to answers.")
    add.add_argument("--target-reader", default="unknown")
    add.add_argument("--allow-incomplete", action="store_true")
    add.add_argument("--allow-unknown", action="store_true")
    add.set_defaults(func=command_add)

    summarize = sub.add_parser("summarize")
    summarize.add_argument("--gate", required=True, choices=sorted(GATE_QUESTIONS))
    summarize.add_argument("--risk", default="")
    summarize.add_argument("--recommendation", default="")
    summarize.set_defaults(func=command_summarize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
