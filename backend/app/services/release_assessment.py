"""Deterministic release readiness. This module does not call a model or run a command."""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

CHECKLIST: tuple[tuple[str, str], ...] = (
    ("code_review", "Code review completion"),
    ("critical_high", "Critical and high-severity findings"),
    ("automated_tests", "Automated tests"),
    ("database_changes", "Database schema and data patches"),
    ("dependencies", "Dependency and composer.lock changes"),
    ("configuration", "Configuration changes"),
    ("cache_indexers", "Cache and indexer implications"),
    ("api_compatibility", "API and backward compatibility"),
    ("rollback_plan", "Rollback plan"),
    ("deployment_verification", "Deployment and post-deployment verification"),
)
CHECKLIST_KEYS = frozenset(key for key, _label in CHECKLIST)
HUMAN_KEYS = frozenset(
    {
        "database_changes",
        "dependencies",
        "configuration",
        "cache_indexers",
        "api_compatibility",
        "rollback_plan",
        "deployment_verification",
    }
)
STATEMENT = (
    "This report does not approve the release. AI findings are suggestions, "
    "and a passing model review cannot make a release ready. A technical lead must decide."
)
_QUALITY_TOOLS = ("phpcs", "phpstan", "phpunit", "composer", "magento")
_QUALITY_LABELS = {
    "phpcs": "PHP_CodeSniffer",
    "phpstan": "PHPStan",
    "phpunit": "PHPUnit",
    "composer": "Composer validation",
    "magento": "Magento check",
}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_DATABASE_MARKERS = (
    "db_schema.xml",
    "/Patch/",
    "UpgradeSchema.php",
    "UpgradeData.php",
    "InstallSchema.php",
    "InstallData.php",
    "db_schema_whitelist.json",
)
_DEPENDENCY_MARKERS = ("composer.json", "composer.lock")
_CONFIG_MARKERS = ("config.php", "system.xml", "config.xml", "crontab.xml", "communication.xml")


@dataclass(frozen=True)
class FindingInput:
    id: str
    severity: str
    title: str
    file_path: str
    category: str


@dataclass(frozen=True)
class DecisionInput:
    finding_id: str
    decision: str
    reason: str
    reviewer: str


@dataclass(frozen=True)
class ChecklistInput:
    key: str
    status: str
    reason: str
    reviewer: str


@dataclass(frozen=True)
class QualityInput:
    tool: str
    result: str


@dataclass(frozen=True)
class ModelInput:
    name: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: int


@dataclass(frozen=True)
class AssessmentInput:
    project_id: str
    project_name: str
    review_id: str
    review_status: str
    base_ref: str
    head_sha: str
    repository_head_sha: str
    dirty: bool
    generated_at: datetime
    model: ModelInput
    findings: tuple[FindingInput, ...] = ()
    decisions: tuple[DecisionInput, ...] = ()
    checklist: tuple[ChecklistInput, ...] = ()
    quality: tuple[QualityInput, ...] = ()
    reviewed_files: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Entry:
    text: str
    reason: str = ""
    reviewer: str = ""


@dataclass(frozen=True)
class ChecklistRow:
    key: str
    label: str
    status: str
    evidence: str
    reason: str
    reviewer: str
    counts_as_pass: bool = True


@dataclass(frozen=True)
class FindingRow:
    id: str
    severity: str
    title: str
    file_path: str
    decision: str
    reason: str
    reviewer: str


@dataclass(frozen=True)
class Assessment:
    readiness: str
    statement: str
    blockers: tuple[Entry, ...]
    warnings: tuple[Entry, ...]
    passed: tuple[Entry, ...]
    waivers: tuple[Entry, ...]
    missing: tuple[Entry, ...]
    checklist: tuple[ChecklistRow, ...]
    findings: tuple[FindingRow, ...]
    quality: tuple[QualityInput, ...]
    model: ModelInput
    project_id: str
    project_name: str
    review_id: str
    review_status: str
    base_ref: str
    head_sha: str
    repository_head_sha: str
    dirty: bool
    generated_at: datetime
    limitations: tuple[str, ...] = field(default_factory=tuple)


def build_assessment(data: AssessmentInput) -> Assessment:
    """Combine findings, checks, and human decisions into one readiness result."""
    decisions = {item.finding_id: item for item in data.decisions}
    humans = {item.key: item for item in data.checklist}
    quality = _latest_quality(data.quality)
    blockers: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []
    waivers: list[Entry] = []
    missing: list[str] = []
    finding_rows = _finding_rows(data.findings, decisions, blockers, warnings, waivers)
    rows = _checklist_rows(
        data,
        humans,
        quality,
        finding_rows,
        blockers,
        warnings,
        passed,
        waivers,
        missing,
    )
    _quality_notes(quality, blockers, passed, missing)
    for limitation in data.limitations:
        if limitation.strip():
            missing.append(limitation.strip())
    if not data.head_sha.strip():
        blockers.append("The review has no Git commit identifier.")
    if not data.repository_head_sha.strip():
        missing.append("The current repository commit could not be read.")
    if data.dirty:
        warnings.append(
            "The work tree has uncommitted changes, so the recorded commit may not be "
            "the tree that would ship."
        )
    readiness = _readiness(blockers, warnings, waivers, missing, rows)
    return Assessment(
        readiness=readiness,
        statement=STATEMENT,
        blockers=tuple(Entry(text) for text in _unique(blockers)),
        warnings=tuple(Entry(text) for text in _unique(warnings)),
        passed=tuple(Entry(text) for text in _unique(passed)),
        waivers=tuple(_unique_entries(waivers)),
        missing=tuple(Entry(text) for text in _unique(missing)),
        checklist=rows,
        findings=finding_rows,
        quality=tuple(
            QualityInput(tool, quality[tool])
            for tool in _QUALITY_TOOLS
            if tool in quality
        ),
        model=data.model,
        project_id=data.project_id,
        project_name=data.project_name,
        review_id=data.review_id,
        review_status=data.review_status,
        base_ref=data.base_ref,
        head_sha=data.head_sha,
        repository_head_sha=data.repository_head_sha,
        dirty=data.dirty,
        generated_at=data.generated_at,
        limitations=data.limitations,
    )


def render_markdown(report: Assessment) -> str:
    """Render one stored assessment. The same assessment always renders the same text."""
    lines = [
        f"# Release readiness — {report.project_name}",
        "",
        report.statement,
        "",
        f"Readiness: {_label(report.readiness)}",
        f"Generated: {report.generated_at.isoformat()}",
        "",
        "## Git",
        "",
        f"- Repository: {report.project_name}",
        f"- Base: {report.base_ref or 'unknown'}",
        f"- Reviewed commit: {report.head_sha or 'missing'}",
        f"- Repository HEAD at generation: {report.repository_head_sha or 'missing'}",
        f"- Uncommitted changes: {'yes' if report.dirty else 'no'}",
        "",
        "## Model and review configuration",
        "",
        f"- Review: {report.review_id}",
        f"- Review status: {report.review_status}",
        f"- Model: {report.model.name}",
        f"- Context length: {report.model.context_length}",
        f"- Temperature: {report.model.temperature}",
        f"- Max output tokens: {report.model.max_output_tokens}",
        f"- Timeout seconds: {report.model.timeout_seconds}",
        "",
        "## Blockers",
        "",
        *_bullets(entry.text for entry in report.blockers),
        "",
        "## Warnings",
        "",
        *_bullets(entry.text for entry in report.warnings),
        "",
        "## Passed checks",
        "",
        *_bullets(entry.text for entry in report.passed),
        "",
        "## Waivers",
        "",
        *_waiver_lines(report.waivers),
        "",
        "## Missing evidence",
        "",
        *_bullets(entry.text for entry in report.missing),
        "",
        "## Checklist",
        "",
    ]
    for row in report.checklist:
        lines.append(f"- {_label(row.status)} — {row.label}. {row.evidence}".rstrip())
        if row.reason or row.reviewer:
            lines.append(f"  Reason: {row.reason or 'none'}. Reviewer: {row.reviewer or 'none'}.")
    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("- None.")
    for row in report.findings:
        decision = _label(row.decision or "unresolved")
        lines.append(f"- {row.severity}: {row.title} ({row.file_path}) — {decision}")
        if row.reason or row.reviewer:
            lines.append(f"  Reason: {row.reason or 'none'}. Reviewer: {row.reviewer or 'none'}.")
    lines.extend(["", "## Quality checks", ""])
    if not report.quality:
        lines.append("- None.")
    for item in report.quality:
        lines.append(f"- {_QUALITY_LABELS[item.tool]}: {item.result}")
    lines.append("")
    return "\n".join(lines)


def serialize(report: Assessment) -> dict[str, object]:
    """JSON object for a stored snapshot. Key order is fixed by ``sort_keys`` on write."""
    return {
        "schema_version": 1,
        "readiness": report.readiness,
        "statement": report.statement,
        "blockers": [entry.text for entry in report.blockers],
        "warnings": [entry.text for entry in report.warnings],
        "passed": [entry.text for entry in report.passed],
        "waivers": [
            {"text": entry.text, "reason": entry.reason, "reviewer": entry.reviewer}
            for entry in report.waivers
        ],
        "missing": [entry.text for entry in report.missing],
        "checklist": [
            {
                "key": row.key,
                "label": row.label,
                "status": row.status,
                "evidence": row.evidence,
                "reason": row.reason,
                "reviewer": row.reviewer,
            }
            for row in report.checklist
        ],
        "findings": [
            {
                "id": row.id,
                "severity": row.severity,
                "title": row.title,
                "file_path": row.file_path,
                "decision": row.decision,
                "reason": row.reason,
                "reviewer": row.reviewer,
            }
            for row in report.findings
        ],
        "quality": [{"tool": item.tool, "result": item.result} for item in report.quality],
        "model": {
            "name": report.model.name,
            "context_length": report.model.context_length,
            "temperature": report.model.temperature,
            "max_output_tokens": report.model.max_output_tokens,
            "timeout_seconds": report.model.timeout_seconds,
        },
        "project_id": report.project_id,
        "project_name": report.project_name,
        "review_id": report.review_id,
        "review_status": report.review_status,
        "base_ref": report.base_ref,
        "head_sha": report.head_sha,
        "repository_head_sha": report.repository_head_sha,
        "dirty": report.dirty,
        "generated_at": report.generated_at.isoformat(),
        "limitations": list(report.limitations),
    }


def dump_json(report: Assessment) -> str:
    return json.dumps(serialize(report), indent=2, sort_keys=True) + "\n"


def _finding_rows(
    findings: tuple[FindingInput, ...],
    decisions: dict[str, DecisionInput],
    blockers: list[str],
    warnings: list[str],
    waivers: list[Entry],
) -> tuple[FindingRow, ...]:
    rows: list[FindingRow] = []
    for finding in sorted(findings, key=_finding_sort):
        decision = decisions.get(finding.id)
        choice = decision.decision if decision is not None else ""
        reason = decision.reason.strip() if decision is not None else ""
        reviewer = decision.reviewer.strip() if decision is not None else ""
        named = bool(reason and reviewer)
        if finding.severity == "critical":
            _critical(finding, choice, reason, reviewer, named, blockers, warnings, waivers)
        elif finding.severity == "high":
            _high(finding, choice, reason, reviewer, named, blockers, waivers)
        elif finding.severity == "medium":
            _medium(finding, choice, named, reason, reviewer, warnings, waivers)
        elif choice == "waived" and named:
            waivers.append(_waiver(finding, reason, reviewer))
        rows.append(
            FindingRow(
                finding.id,
                finding.severity,
                finding.title,
                finding.file_path,
                choice,
                reason,
                reviewer,
            )
        )
    return tuple(rows)


def _critical(
    finding: FindingInput,
    choice: str,
    reason: str,
    reviewer: str,
    named: bool,
    blockers: list[str],
    warnings: list[str],
    waivers: list[Entry],
) -> None:
    title = finding.title
    if choice == "waived" and named:
        waivers.append(_waiver(finding, reason, reviewer))
        return
    if choice == "dismissed" and named:
        warnings.append(f"Critical finding was dismissed: {title}. Reason: {reason} ({reviewer})")
        return
    if choice == "waived":
        blockers.append(
            f"Critical finding {title} cannot be waived without a reason and a reviewer."
        )
        return
    if choice == "dismissed":
        blockers.append(
            f"Critical finding {title} cannot be dismissed without a reason and a reviewer."
        )
        return
    if choice == "confirmed":
        blockers.append(f"Critical finding remains open: {title}")
        return
    blockers.append(f"Unresolved critical finding: {title}")


def _medium(
    finding: FindingInput,
    choice: str,
    named: bool,
    reason: str,
    reviewer: str,
    warnings: list[str],
    waivers: list[Entry],
) -> None:
    if choice == "waived" and named:
        waivers.append(_waiver(finding, reason, reviewer))
        return
    if choice == "dismissed":
        return
    if choice == "waived":
        warnings.append(
            f"Medium finding {finding.title} cannot be waived without a reason and a reviewer."
        )
        return
    warnings.append(f"Medium finding is still open: {finding.title}")


def _high(
    finding: FindingInput,
    choice: str,
    reason: str,
    reviewer: str,
    named: bool,
    blockers: list[str],
    waivers: list[Entry],
) -> None:
    title = finding.title
    if choice == "dismissed":
        return
    if choice == "waived" and named:
        waivers.append(_waiver(finding, reason, reviewer))
        return
    if choice == "waived":
        blockers.append(
            f"High-severity finding {title} cannot be waived without a reason and a reviewer."
        )
        return
    if choice == "confirmed":
        blockers.append(f"High-severity finding remains open: {title}")
        return
    blockers.append(f"High-severity finding needs a disposition: {title}")


def _checklist_rows(
    data: AssessmentInput,
    humans: dict[str, ChecklistInput],
    quality: dict[str, str],
    findings: tuple[FindingRow, ...],
    blockers: list[str],
    warnings: list[str],
    passed: list[str],
    waivers: list[Entry],
    missing: list[str],
) -> tuple[ChecklistRow, ...]:
    rows: list[ChecklistRow] = []
    for key, label in CHECKLIST:
        if key == "code_review":
            status, evidence = _code_status(data.review_status)
            row = _with_human(
                key,
                label,
                status,
                evidence,
                humans.get(key),
                allow_pass=status == "passed",
            )
        elif key == "critical_high":
            row = _critical_row(label, findings, humans.get(key), warnings)
        elif key == "automated_tests":
            status, evidence = _test_status(quality.get("phpunit"))
            row = _with_human(
                key,
                label,
                status,
                evidence,
                humans.get(key),
                allow_pass=status == "passed",
            )
        elif key == "dependencies":
            row = _dependency_row(
                label,
                quality.get("composer"),
                data.reviewed_files,
                humans.get(key),
            )
        else:
            row = _with_human(
                key,
                label,
                "pending",
                _item_evidence(key, data),
                humans.get(key),
                allow_pass=True,
            )
        rows.append(row)
        _collect(row, blockers, warnings, passed, waivers, missing)
    return tuple(rows)


def _critical_row(
    label: str,
    findings: tuple[FindingRow, ...],
    human: ChecklistInput | None,
    warnings: list[str],
) -> ChecklistRow:
    if human is not None and human.status in {"passed", "waived", "not_applicable"}:
        warnings.append(
            "A checklist decision cannot close critical or high findings. "
            "Each finding needs its own disposition."
        )
    relevant = [row for row in findings if row.severity in {"critical", "high"}]
    if not relevant:
        return ChecklistRow(
            "critical_high",
            label,
            "passed",
            "No critical or high findings.",
            "",
            "",
        )
    open_items = [
        row
        for row in relevant
        if not (
            (row.decision == "dismissed" and row.reason and row.reviewer)
            or (row.decision == "waived" and row.reason and row.reviewer)
            or (row.severity == "high" and row.decision == "dismissed")
        )
    ]
    if open_items:
        return ChecklistRow(
            "critical_high",
            label,
            "failed",
            "One or more critical or high findings are unresolved.",
            "",
            "",
        )
    if any(row.decision == "waived" for row in relevant):
        return ChecklistRow(
            "critical_high",
            label,
            "waived",
            "Every critical or high finding was waived or dismissed individually.",
            "",
            "",
            False,
        )
    dismissed = any(row.severity == "critical" and row.decision == "dismissed" for row in relevant)
    return ChecklistRow(
        "critical_high",
        label,
        "passed",
        "Dismissed critical findings stay in warnings."
        if dismissed
        else "Every critical or high finding has a disposition.",
        "",
        "",
        not dismissed,
    )


def _dependency_row(
    label: str,
    composer: str | None,
    files: tuple[str, ...],
    human: ChecklistInput | None,
) -> ChecklistRow:
    evidence = _paths(files, _DEPENDENCY_MARKERS)
    if evidence == "":
        evidence = "No composer.json or composer.lock was in the review."
    if composer in {"fail", "timed_out"}:
        failed = ChecklistRow(
            "dependencies",
            label,
            "failed",
            "Composer validation failed.",
            "",
            "",
        )
        if human is not None and human.status == "waived" and _named(human):
            return ChecklistRow(
                "dependencies",
                label,
                "waived",
                failed.evidence,
                human.reason.strip(),
                human.reviewer.strip(),
            )
        return failed
    return _with_human("dependencies", label, "pending", evidence, human, allow_pass=True)


def _code_status(status: str) -> tuple[str, str]:
    if status == "completed":
        return "passed", "The review run completed."
    if status in {"failed", "cancelled"}:
        return "failed", f"The review run is {status}."
    return "pending", "The review run is not complete."


def _test_status(result: str | None) -> tuple[str, str]:
    if result == "pass":
        return "passed", "PHPUnit exited 0."
    if result in {"fail", "timed_out"}:
        return "failed", f"PHPUnit result is {result}."
    if result == "skipped":
        return "pending", "PHPUnit was skipped, so there is no test result."
    return "pending", "No PHPUnit result is stored for this review."


def _with_human(
    key: str,
    label: str,
    derived: str,
    evidence: str,
    human: ChecklistInput | None,
    *,
    allow_pass: bool,
) -> ChecklistRow:
    if human is None or human.status == "pending":
        return ChecklistRow(key, label, derived, evidence, "", "")
    reason = human.reason.strip()
    reviewer = human.reviewer.strip()
    if human.status == "passed":
        if allow_pass and reason and reviewer:
            return ChecklistRow(key, label, "passed", evidence, reason, reviewer)
        note = evidence
        if not allow_pass:
            note = f"{evidence} A recorded pass was not accepted."
        return ChecklistRow(key, label, derived, note, "", "")
    if human.status in {"waived", "not_applicable"} and reason and reviewer:
        return ChecklistRow(key, label, human.status, evidence, reason, reviewer)
    if human.status == "failed":
        return ChecklistRow(key, label, "failed", evidence, reason, reviewer)
    if human.status in {"waived", "not_applicable"}:
        return ChecklistRow(
            key,
            label,
            derived,
            f"{evidence} The recorded {human.status} decision has no reason or reviewer.",
            "",
            "",
        )
    return ChecklistRow(key, label, derived, evidence, "", "")


def _collect(
    row: ChecklistRow,
    blockers: list[str],
    warnings: list[str],
    passed: list[str],
    waivers: list[Entry],
    missing: list[str],
) -> None:
    if row.status == "passed":
        if row.counts_as_pass:
            passed.append(row.label)
        return
    if row.status == "waived":
        if row.reason and row.reviewer:
            waivers.append(Entry(row.label, row.reason, row.reviewer))
        return
    if row.status == "not_applicable":
        warnings.append(f"{row.label} is not applicable. Reason: {row.reason} ({row.reviewer})")
        return
    if row.status == "failed":
        blockers.append(f"Required check failed: {row.label}")
        return
    blockers.append(f"Required check is not complete: {row.label}")
    missing.append(f"{row.label} has no passing evidence.")


def _quality_notes(
    quality: dict[str, str],
    blockers: list[str],
    passed: list[str],
    missing: list[str],
) -> None:
    for tool in ("phpcs", "phpstan", "composer", "magento"):
        result = quality.get(tool)
        label = _QUALITY_LABELS[tool]
        if result in {"fail", "timed_out"} and tool != "composer":
            blockers.append(f"Failed mandatory quality check: {label} ({result})")
        elif result == "skipped":
            missing.append(f"{label} was skipped and is not counted as passed.")
        elif result == "pass":
            passed.append(f"{label} passed.")
    if quality.get("phpunit") == "skipped":
        missing.append("PHPUnit was skipped and is not counted as passed.")


def _item_evidence(key: str, data: AssessmentInput) -> str:
    if key == "database_changes":
        found = _paths(data.reviewed_files, _DATABASE_MARKERS)
        return found or "No schema or data-patch path was in the review."
    if key == "configuration":
        found = _paths(data.reviewed_files, _CONFIG_MARKERS)
        return found or "No configuration path was in the review."
    if key == "cache_indexers":
        return "Confirm cache and indexer impact before deployment."
    if key == "api_compatibility":
        return "Confirm service contracts and web API compatibility before deployment."
    if key == "rollback_plan":
        return "Record how this change would be rolled back."
    if key == "deployment_verification":
        return "Record the deployment and post-deployment checks."
    return "A person must record this check."


def _paths(files: tuple[str, ...], markers: tuple[str, ...]) -> str:
    matched = [path for path in files if any(marker in path for marker in markers)]
    if not matched:
        return ""
    return "Reviewed paths: " + ", ".join(matched)


def _readiness(
    blockers: list[str],
    warnings: list[str],
    waivers: list[Entry],
    missing: list[str],
    rows: tuple[ChecklistRow, ...],
) -> str:
    if blockers:
        return "blocked"
    if warnings or waivers or missing or any(row.status != "passed" for row in rows):
        return "needs_review"
    return "ready_for_human_approval"


def _latest_quality(items: tuple[QualityInput, ...]) -> dict[str, str]:
    found: dict[str, str] = {}
    for item in items:
        if item.tool in _QUALITY_TOOLS and item.tool not in found:
            found[item.tool] = item.result
    return found


def _named(item: ChecklistInput) -> bool:
    return bool(item.reason.strip() and item.reviewer.strip())


def _waiver(finding: FindingInput, reason: str, reviewer: str) -> Entry:
    return Entry(f"{finding.severity}: {finding.title}", reason, reviewer)


def _finding_sort(finding: FindingInput) -> tuple[int, str, str, str]:
    return (_SEVERITY_RANK.get(finding.severity, 9), finding.file_path, finding.title, finding.id)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return sorted(ordered)


def _unique_entries(items: list[Entry]) -> list[Entry]:
    seen: set[tuple[str, str, str]] = set()
    ordered: list[Entry] = []
    for item in items:
        key = (item.text, item.reason, item.reviewer)
        if key not in seen:
            seen.add(key)
            ordered.append(item)
    return sorted(ordered, key=lambda item: (item.text, item.reason, item.reviewer))


def _bullets(items: Iterable[str]) -> list[str]:
    values = list(items)
    if not values:
        return ["- None."]
    return [f"- {value}" for value in values]


def _waiver_lines(items: tuple[Entry, ...]) -> list[str]:
    if not items:
        return ["- None."]
    lines: list[str] = []
    for item in items:
        lines.append(f"- {item.text}")
        lines.append(f"  Reason: {item.reason}. Reviewer: {item.reviewer}.")
    return lines


def _label(value: str) -> str:
    labels = {
        "blocked": "Blocked",
        "needs_review": "Needs review",
        "ready_for_human_approval": "Ready for human approval",
        "not_applicable": "Not applicable",
        "pending": "Pending",
        "passed": "Passed",
        "failed": "Failed",
        "waived": "Waived",
        "unresolved": "Unresolved",
        "dismissed": "Dismissed",
        "confirmed": "Confirmed",
    }
    return labels.get(value, value)
