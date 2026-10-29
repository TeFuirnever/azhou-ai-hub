#!/usr/bin/env python3
"""Run isolated unit suites and enforce 95% lines for the complete production scope.

Browser end-to-end runs, installed-app probes and manual evidence are not inputs.
Use --language only while developing one suite; it never certifies the package.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MINIMUM = 95
EXTENSIONS = {".js": "javascript", ".mjs": "javascript", ".py": "python",
              ".swift": "swift", ".sh": "shell", ".command": "shell"}
IGNORED_DIRECTORIES = {".git", ".build", ".local", ".azhou", "dist", "assets", "__pycache__",
                       "node_modules", "docs", "plans"}
NATIVE_EXPRESSIONS = ("statusSource", "applyGuardSource", "retrySource", "restoreSource",
                      "inspectExpression", "statusExpression", "disposeExpression", "installExpression")
GENERATED_JAVASCRIPT = tuple(f"generated/Native-Wallpaper.{name}.js" for name in NATIVE_EXPRESSIONS)


def production_sources(root: Path = ROOT) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {name: [] for name in ("javascript", "python", "swift", "shell")}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if set(relative.parts) & IGNORED_DIRECTORIES or path.suffix not in EXTENSIONS:
            continue
        if path.name.startswith("test-") or path.name.endswith((".test.mjs", "Tests.swift")):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"production source must be a regular file: {relative}")
        groups[EXTENSIONS[path.suffix]].append(relative.as_posix())
    # These are real production JavaScript expressions emitted by Swift, not
    # merely the Swift statements that construct their strings. Unit tests
    # compile the current producer and execute every exact emitted expression.
    if (root / "Native/Wallpaper.swift").is_file():
        groups["javascript"].extend(GENERATED_JAVASCRIPT)
    return groups


def canonical_source(name: str, root: Path = ROOT) -> str | None:
    path = Path(name)
    if not path.is_absolute():
        # Coverage.py can retain repository-relative paths after combining data.
        prefix = Path("packages") / root.name
        if path.parts[:2] == prefix.parts:
            path = root.parent.parent / path
        else:
            path = root / path
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        generated_prefix = ".build/unit-generated-sources/"
        if relative.startswith(generated_prefix):
            candidate = "generated/" + relative[len(generated_prefix):]
            return candidate if candidate in GENERATED_JAVASCRIPT else None
        return relative
    except ValueError:
        return None


def parse_lcov(text: str) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    source = None
    lines: dict[int, int] = {}
    for line in text.splitlines():
        if line.startswith("SF:"):
            source = canonical_source(line[3:])
            lines = {}
        elif line.startswith("DA:"):
            number, hits, *_ = line[3:].split(",")
            lines[int(number)] = max(lines.get(int(number), 0), int(hits))
        elif line == "end_of_record" and source:
            if source in result:
                raise ValueError(f"duplicate coverage source: {source}")
            result[source] = {"count": len(lines), "covered": sum(value > 0 for value in lines.values())}
    return result


def parse_python(value: dict) -> dict[str, dict[str, int]]:
    result = {}
    for name, details in value["files"].items():
        source = canonical_source(name)
        if source:
            summary = details["summary"]
            result[source] = {"count": summary["num_statements"], "covered": summary["covered_lines"]}
    return result


def parse_native(value: dict) -> dict[str, dict[str, int]]:
    if "files" in value:
        return {name: details["lines"] for name, details in value["files"].items()}
    result = {}
    for data in value["data"]:
        for details in data["files"]:
            source = canonical_source(details["filename"])
            if source:
                if source in result:
                    raise ValueError(f"native profiles must be merged before reporting: {source}")
                summary = details["summary"]["lines"]
                result[source] = {"count": summary["count"], "covered": summary["covered"]}
    return result


def evaluate(scope: dict[str, list[str]], measured: dict[str, dict[str, dict[str, int]]]) -> dict:
    groups = {}
    for language, sources in scope.items():
        files = {}
        for source in sources:
            value = measured.get(language, {}).get(source)
            if value is None:
                files[source] = {"status": "missing", "percent": None}
                continue
            count, covered = value["count"], value["covered"]
            if type(count) is not int or type(covered) is not int or count <= 0 or not 0 <= covered <= count:
                raise ValueError(f"invalid executable-line counters: {source}")
            files[source] = {"count": count, "covered": covered,
                             "percent": 100 * covered / count, "status": "measured"}
        complete = bool(files) and all(item["status"] == "measured" for item in files.values())
        count = sum(item.get("count", 0) for item in files.values())
        covered = sum(item.get("covered", 0) for item in files.values())
        percent = 100 * covered / count if complete and count else None
        groups[language] = {"files": files, "count": count, "covered": covered, "percent": percent,
                            "passed": complete and 100 * covered >= MINIMUM * count}
    count = sum(group["count"] for group in groups.values())
    covered = sum(group["covered"] for group in groups.values())
    complete = all(group["percent"] is not None for group in groups.values())
    return {"minimumLinePercent": MINIMUM, "languages": groups,
            "count": count, "covered": covered,
            "percent": 100 * covered / count if complete and count else None,
            "passed": bool(groups) and all(group["passed"] for group in groups.values())}


def run(command: list[str], log: Path, *, environment: dict[str, str] | None = None) -> None:
    print("==> " + " ".join(command), flush=True)
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(f"unit command exited {completed.returncode}; see {log}")


def python_coverage(out: Path, sources: list[str]) -> dict:
    import coverage

    for previous in out.glob(".coverage*"):
        if previous.is_file():
            previous.unlink()
    config = out / "coveragerc"
    config.write_text(
        "[run]\nbranch = True\nparallel = True\n"
        f"data_file = {out / '.coverage'}\n"
        f"include =\n    {ROOT}/tools/*.py\n    */source/tools/*.py\n"
        "omit =\n    */test-*.py\n"
        "[paths]\nsource =\n" + f"    {ROOT / 'tools'}\n    */source/tools\n",
        encoding="utf-8",
    )
    suites = ["test-startup-build.py", "test-install-macos.py", "test-codex-pet.py", "test-import-codex-pet.py"]
    suites += sorted(path.name for path in (ROOT / "tools").glob("test-production-*.py"))
    for suite in suites:
        run([sys.executable, "-m", "coverage", "run", "--rcfile", str(config),
             str(ROOT / "tools" / suite)], out / (suite + ".log"))
    collector = coverage.Coverage(config_file=str(config))
    collector.combine(strict=True)
    collector.load()
    collector.get_data().touch_files([str(ROOT / source) for source in sources])
    collector.save()
    report = out / "coverage.json"
    collector.json_report(outfile=str(report))
    return parse_python(json.loads(report.read_text(encoding="utf-8")))


def javascript_coverage(out: Path) -> dict:
    suites = sorted(str(path) for path in (ROOT / "tools").glob("*.test.mjs"))
    report = out / "coverage.lcov"
    run(["node", "--test", "--experimental-test-coverage", "--test-reporter=lcov", *suites], report)
    return parse_lcov(report.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=["all", *EXTENSIONS.values()], default="all")
    parser.add_argument("--out", type=Path, default=ROOT / ".build/unit-coverage")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    scope = production_sources()
    if args.language != "all":
        scope = {args.language: scope[args.language]}
    measured, errors = {}, {}
    for language, sources in scope.items():
        directory = out / language
        directory.mkdir(parents=True, exist_ok=True)
        try:
            if language == "python":
                measured[language] = python_coverage(directory, sources)
            elif language == "javascript":
                measured[language] = javascript_coverage(directory)
            elif language == "swift":
                report = directory / "coverage.json"
                report.unlink(missing_ok=True)
                run([sys.executable, "tools/test-swift-coverage.py", "--out", str(directory)], directory / "tests.log")
                measured[language] = parse_native(json.loads(report.read_text(encoding="utf-8")))
            else:
                report = directory / "coverage.json"
                report.unlink(missing_ok=True)
                environment = os.environ.copy()
                local_bash = ROOT / ".build/bash-5.2.37/bin/bash"
                local_gems = ROOT / ".build/shell-gems"
                if not environment.get("BASHCOV_BASH_PATH") and local_bash.is_file():
                    environment["BASHCOV_BASH_PATH"] = str(local_bash)
                if (local_gems / "bin/bashcov").is_file():
                    environment.setdefault("GEM_HOME", str(local_gems))
                    environment.setdefault("GEM_PATH", str(local_gems))
                    environment["PATH"] = str(local_gems / "bin") + os.pathsep + environment.get("PATH", "")
                run([sys.executable, "tools/test-shell-cli.py", "--report", str(report)], directory / "tests.log",
                    environment=environment)
                measured[language] = parse_native(json.loads(report.read_text(encoding="utf-8")))
        except (ImportError, OSError, ValueError, RuntimeError, KeyError) as error:
            errors[language] = str(error)
    result = evaluate(scope, measured)
    result.update(scope="package" if args.language == "all" else args.language, errors=errors,
                  collection="isolated unit suites only; E2E and manual evidence are excluded")
    if errors:
        result["passed"] = False
    (out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for language, group in result["languages"].items():
        percent = "incomplete" if group["percent"] is None else f"{group['percent']:.2f}%"
        print(f"{language}: {percent} ({group['covered']}/{group['count']}); required >=95%")
    for language, error in errors.items():
        print(f"FAILED {language}: {error}", file=sys.stderr)
    print(f"Report: {out / 'report.json'}")
    print("unit coverage passed" if result["passed"] else "unit coverage FAILED")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
