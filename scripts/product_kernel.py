from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_json

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROUTE_VERSION = 1
ROUTES = {"fast", "normal", "heavy", "gate"}
SOURCE_PRIORITY = [
    "human decision",
    "event_ledger",
    "official chapter evidence",
    "official brief",
    "review artifacts",
    "generated suggestions",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    else:
        item["sha256"] = ""
    return item


def official_chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def official_brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def context_manifest_path(chapter: str) -> Path:
    return ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"


def event_ledger_path() -> Path:
    return ROOT / "state" / "event_ledger.jsonl"


def review_dir(chapter: str) -> Path:
    return ROOT / "reviews" / chapter


def review_route_path(chapter: str) -> Path:
    return review_dir(chapter) / "review_route.json"


def load_yaml_config(path: Path) -> tuple[dict[str, Any], list[str]]:
    if yaml is None:
        return {}, [f"{rel(path)}: PyYAML is required"]
    if not path.exists():
        return {}, [f"missing config: {rel(path)}"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"{rel(path)}: invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{rel(path)}: top-level value must be a mapping"]
    return data, []


def load_personal_mode() -> tuple[dict[str, Any], list[str]]:
    return load_yaml_config(ROOT / "ops" / "personal_mode.yaml")


def personal_mode_runtime_failures() -> list[str]:
    data, errors = load_personal_mode()
    if errors:
        return errors
    failures: list[str] = []
    mode = str(data.get("mode", "")).strip()
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    ship = data.get("ship_gates") if isinstance(data.get("ship_gates"), dict) else {}
    literary = data.get("literary_reviews") if isinstance(data.get("literary_reviews"), dict) else {}
    feedback = data.get("reader_feedback") if isinstance(data.get("reader_feedback"), dict) else {}
    infra = data.get("infrastructure") if isinstance(data.get("infrastructure"), dict) else {}
    if mode not in {"personal_noncommercial", "commercial_serial"}:
        failures.append("ops/personal_mode.yaml: mode must be personal_noncommercial or commercial_serial")
    if mode == "personal_noncommercial":
        if scope.get("main_goal") != "personal_writing_pilot":
            failures.append("ops/personal_mode.yaml: personal mode main_goal must be personal_writing_pilot")
        for key in (
            "commercial_advisory_enabled",
            "platform_adaptation_enabled",
            "monetization_optimization_enabled",
            "ranking_optimization_enabled",
            "paid_conversion_enabled",
            "retention_optimization_enabled",
            "treat_legacy_commercial_tools_as_main_flow",
        ):
            if scope.get(key) is not False:
                failures.append(f"ops/personal_mode.yaml: personal mode scope.{key} must be false")
    if mode == "commercial_serial":
        if scope.get("main_goal") != "commercial_serial_monetization":
            failures.append("ops/personal_mode.yaml: commercial mode main_goal must be commercial_serial_monetization")
        for key in (
            "commercial_advisory_enabled",
            "platform_adaptation_enabled",
            "monetization_optimization_enabled",
            "ranking_optimization_enabled",
            "paid_conversion_enabled",
            "retention_optimization_enabled",
            "treat_legacy_commercial_tools_as_main_flow",
        ):
            if scope.get(key) is not True:
                failures.append(f"ops/personal_mode.yaml: commercial mode scope.{key} must be true")
    if ship.get("always_required") is not True:
        failures.append("ops/personal_mode.yaml: ship_gates.always_required must be true")
    if ship.get("allow_route_to_skip_ship_gates") is not False:
        failures.append("ops/personal_mode.yaml: routes must not skip Ship gates")
    if literary.get("default_blocking") is not False:
        failures.append("ops/personal_mode.yaml: literary_reviews.default_blocking must be false")
    if feedback.get("simulated_reader_must_be_labeled") is not True:
        failures.append("ops/personal_mode.yaml: simulated reader feedback must be labeled")
    for key in ("sqlite_enabled", "vector_memory_enabled", "knowledge_graph_enabled"):
        if infra.get(key) is not False:
            failures.append(f"ops/personal_mode.yaml: infrastructure.{key} must remain false")
    return failures


def personal_mode_is_noncommercial() -> bool:
    data, errors = load_personal_mode()
    if errors:
        return False
    return str(data.get("mode", "")).strip() == "personal_noncommercial"


def project_mode() -> str:
    data, errors = load_personal_mode()
    if errors:
        return "unknown"
    value = str(data.get("mode", "")).strip()
    return value if value else "unknown"


def commercial_mode_enabled() -> bool:
    return project_mode() == "commercial_serial"


def load_review_routing() -> tuple[dict[str, Any], list[str]]:
    return load_yaml_config(ROOT / "ops" / "review_routing.yaml")


def current_ref_failures(item: Any, expected_path: Path, label: str) -> list[str]:
    if not isinstance(item, dict):
        return [f"{label} missing file reference"]
    failures: list[str] = []
    expected_rel = rel(expected_path)
    if item.get("path") != expected_rel:
        failures.append(f"{label} path mismatch: expected {expected_rel}")
    if not expected_path.exists():
        failures.append(f"{label} missing source file: {expected_rel}")
    elif item.get("sha256") != sha256(expected_path):
        failures.append(f"{label} hash is stale: {expected_rel}")
    return failures


def recorded_ref_failures(item: Any, label: str) -> list[str]:
    if not isinstance(item, dict):
        return [f"{label} missing file reference"]
    rel_path = str(item.get("path", "")).strip()
    recorded_sha = str(item.get("sha256", "")).strip()
    if not rel_path or not recorded_sha:
        return [f"{label} missing path/sha256"]
    path = ROOT / rel_path
    if not path.exists():
        return [f"{label} missing source file: {rel_path}"]
    if sha256(path) != recorded_sha:
        return [f"{label} hash is stale: {rel_path}"]
    return []


def derived_ledger_source_failures(item: Any, label: str) -> list[str]:
    if not isinstance(item, dict):
        return []
    rel_path = str(item.get("path", "")).strip()
    if rel_path not in {
        "state/derived/thread_debt_ledger.json",
        "state/derived/character_arc_ledger.json",
        "state/derived/style_voice_ledger.json",
    }:
        return []
    path = ROOT / rel_path
    if not path.exists():
        return []
    try:
        data = read_json(path, {})
    except Exception as exc:
        return [f"{label} derived ledger invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{label} derived ledger must be a JSON object"]
    failures = current_ref_failures(
        data.get("source_event_ledger"),
        event_ledger_path(),
        f"{label} source_event_ledger",
    )
    for chapter_index, chapter in enumerate(data.get("chapters", []) if isinstance(data.get("chapters"), list) else [], start=1):
        if not isinstance(chapter, dict):
            failures.append(f"{label} chapters[{chapter_index}] must be a JSON object")
            continue
        refs = chapter.get("source_refs")
        if refs is None:
            continue
        if not isinstance(refs, list):
            failures.append(f"{label} chapters[{chapter_index}].source_refs must be a list")
            continue
        chapter_id = str(chapter.get("chapter", f"chapter#{chapter_index}"))
        for ref_index, ref in enumerate(refs, start=1):
            failures.extend(recorded_ref_failures(ref, f"{label} {chapter_id} source_refs[{ref_index}]"))
    return failures


def route_label(route: str) -> str:
    return route.upper() if route in ROUTES else "HEAVY"


def route_config(route: str) -> dict[str, Any]:
    config, errors = load_review_routing()
    if errors:
        return {}
    routes = config.get("routes")
    if not isinstance(routes, dict):
        return {}
    item = routes.get(route)
    return item if isinstance(item, dict) else {}


def configured_additional_reviews(route: str) -> list[str]:
    item = route_config(route)
    values = item.get("additional_literary_reviews", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def always_required_ship_gates() -> list[str]:
    config, errors = load_review_routing()
    if errors:
        return []
    values = config.get("always_required_ship_gates", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def gate_chapters() -> set[int]:
    config, errors = load_review_routing()
    if errors:
        return {3, 10, 25, 125, 200, 500, 800}
    values = config.get("gate_chapters", [])
    if not isinstance(values, list):
        return {3, 10, 25, 125, 200, 500, 800}
    return {int(value) for value in values if isinstance(value, int)}


def route_for_chapter_number(chapter: str) -> str:
    return "gate" if chapter_number(chapter) in gate_chapters() else "fast"


def route_input_refs(chapter: str) -> dict[str, dict[str, Any]]:
    return {
        "official_chapter": file_ref(official_chapter_path(chapter)),
        "official_brief": file_ref(official_brief_path(chapter)),
        "context_manifest": file_ref(context_manifest_path(chapter)),
        "source_event_ledger": file_ref(event_ledger_path()),
    }


def route_artifact_status(chapter: str) -> tuple[str, list[str], dict[str, Any]]:
    path = review_route_path(chapter)
    if not path.exists():
        return "heavy", [f"{chapter}: missing review_route.json"], {}
    try:
        data = read_json(path, {})
    except Exception as exc:
        return "heavy", [f"{chapter}: review_route.json invalid JSON: {exc}"], {}
    failures: list[str] = []
    if not isinstance(data, dict):
        return "heavy", [f"{chapter}: review_route.json must be a JSON object"], {}
    route = str(data.get("route", "heavy")).lower()
    if route not in ROUTES:
        failures.append(f"{chapter}: review_route route is invalid: {route or 'MISSING'}")
        route = "heavy"
    if data.get("route_version") != ROUTE_VERSION:
        failures.append(f"{chapter}: review_route route_version is stale or missing")
    refs = route_input_refs(chapter)
    for key, expected in refs.items():
        expected_path = ROOT / str(expected["path"])
        failures.extend(current_ref_failures(data.get(key), expected_path, f"{chapter}: review_route {key}"))
    if data.get("status") == "BLOCKED":
        failures.append(f"{chapter}: review_route status is BLOCKED")
    if data.get("fail_closed") is True:
        failures.append(f"{chapter}: review_route fail_closed requires rerun before Ship")
    routing_inputs = data.get("routing_inputs")
    if isinstance(routing_inputs, list):
        for index, item in enumerate(routing_inputs, start=1):
            label = f"{chapter}: review_route routing_inputs[{index}]"
            failures.extend(recorded_ref_failures(item, label))
            failures.extend(derived_ledger_source_failures(item, label))
    elif routing_inputs is not None:
        failures.append(f"{chapter}: review_route routing_inputs must be a list")

    config, config_errors = load_review_routing()
    failures.extend(config_errors)
    expected = set(configured_additional_reviews(route))
    actual_raw = data.get("additional_literary_reviews")
    if not isinstance(actual_raw, list):
        failures.append(f"{chapter}: review_route additional_literary_reviews must be a list")
    else:
        actual = {str(item) for item in actual_raw if str(item).strip()}
        missing = sorted(expected - actual)
        if missing:
            failures.append(f"{chapter}: review_route missing configured literary reviews: {', '.join(missing)}")
    return route, failures, data


def review_json_stale_failures(chapter: str, name: str) -> list[str]:
    path = review_dir(chapter) / name
    if not path.exists():
        return []
    try:
        data = read_json(path, {})
    except Exception as exc:
        return [f"{chapter}: {name} cannot be parsed: {exc}"]
    if not isinstance(data, dict):
        return [f"{chapter}: {name} must be a JSON object"]
    failures: list[str] = []
    official = data.get("official_chapter")
    if isinstance(official, dict) and official.get("sha256"):
        failures.extend(current_ref_failures(official, official_chapter_path(chapter), f"{chapter}: {name} official_chapter"))
    brief = data.get("official_brief")
    if isinstance(brief, dict) and brief.get("sha256"):
        failures.extend(current_ref_failures(brief, official_brief_path(chapter), f"{chapter}: {name} official_brief"))
    input_hashes = data.get("input_hashes")
    if isinstance(input_hashes, list):
        for item in input_hashes:
            if not isinstance(item, dict):
                failures.append(f"{chapter}: {name} input_hashes contains malformed entry")
                continue
            rel_path = str(item.get("path", "")).strip()
            expected = str(item.get("sha256", "")).strip()
            if not rel_path or not expected:
                failures.append(f"{chapter}: {name} input_hashes entry missing path/sha256")
                continue
            source = ROOT / rel_path
            if not source.exists():
                failures.append(f"{chapter}: {name} input source missing {rel_path}")
            elif sha256(source) != expected:
                failures.append(f"{chapter}: {name} input hash mismatch {rel_path}")
    return failures


def read_event_ledger() -> list[dict[str, Any]]:
    path = event_ledger_path()
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events
