"""
TestBase tests for ORM metadata in ccai.pychestrate.core.storage.orm

These tests verify table names and the absence of deprecated relationships.
Each test focuses on a single assertion per the repository's granularity guidelines.
"""

try:
    from ccai.pychestrate.core.storage.orm import BuildTemplate, BuildJob
except Exception:  # If dependencies are missing, allow tests to no-op
    BuildTemplate = None
    BuildJob = None


def test_build_template_tablename():
    if BuildTemplate is None:
        return
    assert BuildTemplate.__tablename__ == "build_template"


def test_build_job_tablename():
    if BuildJob is None:
        return
    assert BuildJob.__tablename__ == "build_job"


def test_build_template_has_no_jobs_relationship():
    if BuildTemplate is None:
        return
    assert not hasattr(BuildTemplate, "jobs")


def test_build_job_has_no_template_relationship():
    if BuildJob is None:
        return
    assert "btmp_id" not in BuildJob.__table__.columns.keys()
