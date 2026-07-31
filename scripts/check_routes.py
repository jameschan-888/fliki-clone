"""Static FastAPI router mount gate used by local and GitHub CI."""
import argparse
import re
import sys
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parent.parent
IGNORED_NAMES = {"__init__.py", "main.py", "errors.py", "config.py"}

QUOTE = chr(34)
SINGLE = chr(39)
STRING_QUOTES = QUOTE + SINGLE
RE_PREFIX = re.compile(
    r"APIRouter\s*\([^)]*?prefix\s*=\s*[" + STRING_QUOTES + r"]([^" + STRING_QUOTES + r"]+)[" + STRING_QUOTES + r"]",
    re.DOTALL,
)
RE_GLOBAL = re.compile(r"^(\w+)\s*=\s*APIRouter\s*\(", re.MULTILINE)
RE_FACTORY = re.compile(r"^def\s+create_router\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:", re.MULTILINE)
RE_ROUTER_HINT = re.compile(r"\bAPIRouter\s*\(")


def should_ignore(path: Path) -> bool:
    name = path.name
    return name in IGNORED_NAMES or name.startswith("test_") or "_backup" in name


def imported_aliases(main_source: str, module_name: str, symbol: str) -> list[str]:
    pattern = re.compile(
        r"from\s+" + re.escape(module_name) + r"\s+import\s+([^#\n]+)",
        re.MULTILINE,
    )
    aliases: list[str] = []
    for match in pattern.finditer(main_source):
        for item in match.group(1).split(","):
            parts = item.strip().split()
            if not parts or parts[0] != symbol:
                continue
            if len(parts) >= 3 and parts[1] == "as":
                aliases.append(parts[2])
            else:
                aliases.append(parts[0])
    return aliases


def is_included(main_source: str, aliases: list[str]) -> bool:
    return any(
        re.search(r"app\.include_router\s*\(\s*" + re.escape(alias) + r"\b", main_source)
        for alias in aliases
    )


def scan_routes(root: Path):
    backend = root / "backend"
    main_path = backend / "main.py"
    if not main_path.exists():
        raise FileNotFoundError("main.py not found: " + str(main_path))

    main_source = main_path.read_text(encoding="utf-8")
    report: list[dict[str, object]] = []
    warnings: list[dict[str, str]] = []

    for path in sorted(backend.glob("*.py")):
        if should_ignore(path):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        factory_match = RE_FACTORY.search(source)
        global_match = RE_GLOBAL.search(source)
        has_router_hint = bool(RE_ROUTER_HINT.search(source))
        if not factory_match and not global_match:
            if has_router_hint:
                warnings.append({
                    "module": path.stem,
                    "code": "UNRECOGNIZED_ROUTER_STYLE",
                    "message": "APIRouter found, but no create_router() factory or module-level router was detected",
                })
            continue

        module_name = path.stem
        prefix_match = RE_PREFIX.search(source)
        prefix = prefix_match.group(1) if prefix_match else "(no prefix)"
        if factory_match:
            style = "create_router"
            aliases = imported_aliases(main_source, module_name, "create_router")
        else:
            style = "global_router"
            aliases = imported_aliases(main_source, module_name, global_match.group(1))

        has_import = bool(aliases)
        has_include = is_included(main_source, aliases)
        if has_import and has_include:
            status = "OK"
        elif has_import:
            status = "INCLUDE_MISSING"
        elif has_include:
            status = "IMPORT_MISSING"
        else:
            status = "ORPHAN"

        if not prefix_match:
            warnings.append({
                "module": module_name,
                "code": "PREFIX_UNKNOWN",
                "message": "router prefix could not be determined statically",
            })

        report.append({
            "module": module_name,
            "prefix": prefix,
            "style": style,
            "import": has_import,
            "include": has_include,
            "status": status,
        })

    modules_by_prefix: dict[str, list[str]] = {}
    for row in report:
        prefix = str(row["prefix"])
        if prefix == "(no prefix)":
            continue
        modules_by_prefix.setdefault(prefix, []).append(str(row["module"]))
    for prefix, modules in sorted(modules_by_prefix.items()):
        if len(modules) > 1:
            warnings.append({
                "module": ",".join(modules),
                "code": "DUPLICATE_PREFIX",
                "message": prefix + " is declared by multiple router modules",
            })

    return report, warnings


def print_report(root: Path, report, warnings) -> int:
    print("=" * 88)
    print("check_routes.py: " + str(len(report)) + " router modules in " + str(root / "backend"))
    print("=" * 88)
    print("STATUS              PREFIX                      STYLE             MODULE")
    print("-" * 88)

    missing_count = 0
    for row in sorted(report, key=lambda item: (item["status"] == "OK", item["module"])):
        print("{:<20} {:<28} {:<17} {:<28}".format(
            row["status"], row["prefix"], row["style"], row["module"],
        ))
        if row["status"] != "OK":
            missing_count += 1

    print("-" * 88)
    print(
        "total: " + str(len(report))
        + "  healthy: " + str(len(report) - missing_count)
        + "  action needed: " + str(missing_count)
        + "  warnings: " + str(len(warnings))
    )

    if warnings:
        print("\n=== WARNINGS ===")
        for warning in warnings:
            print("[WARN] " + warning["code"] + " " + warning["module"] + ": " + warning["message"])

    if missing_count:
        print("\n=== ACTION NEEDED ===")
        for row in report:
            if row["status"] == "OK":
                continue
            print("\n" + str(row["module"]) + " (" + str(row["prefix"]) + "): " + str(row["status"]))
            if row["status"] == "ORPHAN":
                print("  add: from " + str(row["module"]) + " import create_router as create_" + str(row["module"]))
                print("  add: app.include_router(create_" + str(row["module"]) + "(...))")
            elif row["status"] == "INCLUDE_MISSING":
                print("  add: app.include_router(<imported router alias>(...))")
            elif row["status"] == "IMPORT_MISSING":
                print("  add the matching import from " + str(row["module"]))
    return missing_count


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Check that FastAPI router modules are imported and mounted")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root containing backend/main.py")
    parser.add_argument("--fail-on-warn", action="store_true", help="return exit 1 for static-analysis warnings")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        report, warnings = scan_routes(root)
    except FileNotFoundError as error:
        print("[fatal] " + str(error))
        return 2
    missing_count = print_report(root, report, warnings)
    return 1 if missing_count or (args.fail_on_warn and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
