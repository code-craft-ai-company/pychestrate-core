import unittest

from automojo.pychestrate.core.storage.orm import BuildTemplate, BuildJob


class BuildOrmTests(unittest.TestCase):

    def test_build_template_tablename(self):
        self.assertEqual(BuildTemplate.__tablename__, "build_template")

    def test_build_job_tablename(self):
        self.assertEqual(BuildJob.__tablename__, "build_job")

    def test_build_template_has_no_jobs_relationship(self):
        self.assertFalse(hasattr(BuildTemplate, "jobs"))

    def test_build_job_has_no_template_relationship(self):
        self.assertNotIn("btmp_id", BuildJob.__table__.columns.keys())


if __name__ == "__main__":
    unittest.main()
