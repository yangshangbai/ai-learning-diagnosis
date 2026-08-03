"""
Snapshot service — automatically captures student progress after each AI diagnosis run.
Creates a StudentSnapshot with aggregated KP mastery, ability radar, and error causes.
"""
import json
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.student import Student, StudentSnapshot
from models.diagnosis import QuestionResult


async def take_snapshot(db: AsyncSession, student_id: int) -> StudentSnapshot:
    """Take a diagnostic snapshot for one student. Call after run-ai completes."""

    # ── Get all diagnoses for this student ──
    diag_result = await db.execute(
        select(QuestionResult).where(QuestionResult.student_id == student_id)
    )
    diagnoses = diag_result.scalars().all()

    if not diagnoses:
        return None

    # ── KP mastery: per-KP correct rate ──
    kp_mastery = {}
    kp_totals = {}
    for d in diagnoses:
        kp = d.kp_name or ""
        if not kp:
            continue
        if kp not in kp_totals:
            kp_totals[kp] = {"total": 0, "correct": 0}
        kp_totals[kp]["total"] += 1
        if d.verdict == "correct":
            kp_totals[kp]["correct"] += 1

    for kp, v in kp_totals.items():
        kp_mastery[kp] = round(v["correct"] / max(v["total"], 1) * 100, 1)

    # ── Ability radar: per-dimension avg confidence ──
    ability_radar = {}
    dim_counts = {}
    for d in diagnoses:
        dim = d.ability_dimension or ""
        if not dim:
            continue
        if dim not in dim_counts:
            dim_counts[dim] = {"total": 0.0, "count": 0}
        dim_counts[dim]["total"] += d.ai_confidence or 0.5
        dim_counts[dim]["count"] += 1

    for dim, v in dim_counts.items():
        ability_radar[dim] = round(v["total"] / max(v["count"], 1) * 100, 1)

    # ── Error causes: per-cause count ──
    error_causes = {}
    for d in diagnoses:
        cause = d.error_cause or d.skill_cause or ""
        if not cause or cause in ("无", ""):
            continue
        error_causes[cause] = error_causes.get(cause, 0) + 1

    error_causes_list = sorted(
        [{"cause": k, "count": v} for k, v in error_causes.items()],
        key=lambda x: -x["count"]
    )

    # ── Trend: compare with previous snapshot ──
    prev_result = await db.execute(
        select(StudentSnapshot)
        .where(StudentSnapshot.student_id == student_id)
        .order_by(StudentSnapshot.snapshot_date.desc())
        .limit(1)
    )
    prev = prev_result.scalar_one_or_none()

    trend = "stable"
    if prev and prev.kp_mastery_json:
        try:
            prev_mastery = json.loads(prev.kp_mastery_json) if isinstance(prev.kp_mastery_json, str) else prev.kp_mastery_json
            prev_avg = sum(prev_mastery.values()) / max(len(prev_mastery), 1)
            curr_avg = sum(kp_mastery.values()) / max(len(kp_mastery), 1)
            if curr_avg > prev_avg + 2:
                trend = "up"
            elif curr_avg < prev_avg - 2:
                trend = "down"
        except Exception:
            pass

    # ── Also update student's mastery and trend on their record ──
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if student:
        avg_mastery = sum(kp_mastery.values()) / max(len(kp_mastery), 1)
        student.mastery = int(round(avg_mastery))
        student.trend = trend
        # Update weak_points
        weak = [kp for kp, v in sorted(kp_mastery.items(), key=lambda x: x[1])[:5] if v < 70]
        student.weak_points = json.dumps(weak, ensure_ascii=False)

    # ── Create snapshot ──
    snapshot = StudentSnapshot(
        student_id=student_id,
        snapshot_date=date.today(),
        kp_mastery_json=json.dumps(kp_mastery, ensure_ascii=False),
        ability_radar_json=json.dumps(ability_radar, ensure_ascii=False),
        error_causes_json=json.dumps(error_causes_list, ensure_ascii=False),
        trend=trend,
    )
    db.add(snapshot)
    return snapshot


async def take_snapshots_for_task(db: AsyncSession, task_id: int) -> int:
    """Take snapshots for all students who have diagnoses in this task."""
    student_ids_result = await db.execute(
        select(QuestionResult.student_id)
        .where(QuestionResult.task_id == task_id)
        .distinct()
    )
    student_ids = [row[0] for row in student_ids_result.all()]

    count = 0
    for sid in student_ids:
        snap = await take_snapshot(db, sid)
        if snap:
            count += 1
    return count
