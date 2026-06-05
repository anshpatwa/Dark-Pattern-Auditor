from dpa.models import AuditReport, Finding, Severity


def _finding(sev: Severity, conf: float = 1.0) -> Finding:
    return Finding(
        pattern_key="confirmshaming",
        category="misdirection",
        severity=sev,
        title="t",
        description="d",
        evidence="e",
        recommendation="r",
        confidence=conf,
    )


def test_clean_report_scores_100_grade_a():
    r = AuditReport(url="http://x", engine="heuristic")
    assert r.score == 100
    assert r.grade == "A"
    assert r.risk_level == "minimal"


def test_penalties_reduce_score():
    r = AuditReport(url="http://x", engine="heuristic", findings=[_finding(Severity.CRITICAL)])
    assert r.score == 70  # 100 - 30
    assert r.grade == "C"


def test_score_never_negative():
    findings = [_finding(Severity.CRITICAL) for _ in range(10)]
    r = AuditReport(url="http://x", engine="heuristic", findings=findings)
    assert r.score == 0
    assert r.grade == "F"


def test_unknown_category_is_coerced():
    f = Finding(
        pattern_key="x",
        category="totally-made-up",
        severity=Severity.LOW,
        title="t",
        description="d",
        evidence="e",
        recommendation="r",
    )
    assert f.category == "misdirection"


def test_sorted_findings_worst_first():
    r = AuditReport(
        url="http://x",
        engine="heuristic",
        findings=[_finding(Severity.LOW), _finding(Severity.CRITICAL), _finding(Severity.MEDIUM)],
    )
    severities = [f.severity for f in r.sorted_findings()]
    assert severities[0] == Severity.CRITICAL
    assert severities[-1] == Severity.LOW


def test_counts_by_severity():
    r = AuditReport(
        url="http://x",
        engine="heuristic",
        findings=[_finding(Severity.HIGH), _finding(Severity.HIGH), _finding(Severity.LOW)],
    )
    assert r.counts_by_severity["high"] == 2
    assert r.counts_by_severity["low"] == 1
