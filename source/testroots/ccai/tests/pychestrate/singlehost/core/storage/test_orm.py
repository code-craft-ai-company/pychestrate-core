import ccai.testbase as testbase

from ccai.pychestrate.core.storage.orm import BuildTemplate, BuildJob


def test_build_template_tablename():
    testbase.assert_equal(BuildTemplate.__tablename__, "build_template")
    return


def test_build_job_tablename():
    testbase.assert_equal(BuildJob.__tablename__, "build_job")
    return


def test_build_template_has_no_jobs_relationship():
    testbase.assert_equal(hasattr(BuildTemplate, "jobs"), False)
    return


def test_build_job_has_no_template_relationship():
    columns = BuildJob.__table__.columns.keys()
    testbase.assert_equal("btmp_id" in columns, False)
    return


if __name__ == "__main__":
    from ccai.testbase.entrypoints import generic_test_entrypoint

    generic_test_entrypoint()
