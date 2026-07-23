from __future__ import annotations

import unittest
from pathlib import Path

from tools.extract_requirements import component_for, parse_pdf


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/source/FirstBrief_Master_Requirements_TwoSections.pdf"


@unittest.skipUnless(
    SOURCE.exists(),
    "controlled requirements PDF is not present in this checkout",
)
class RequirementsExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requirements, cls.page_count = parse_pdf(SOURCE)

    def test_expected_source_coverage(self) -> None:
        self.assertEqual(self.page_count, 52)
        self.assertEqual(len(self.requirements), 121)
        self.assertEqual(len({item.requirement_id for item in self.requirements}), 121)
        self.assertEqual(self.requirements[0].requirement_id, "FR-A01")
        self.assertEqual(self.requirements[-1].requirement_id, "FR-J04")

    def test_required_fields_are_complete(self) -> None:
        for item in self.requirements:
            with self.subTest(requirement_id=item.requirement_id):
                self.assertTrue(item.theme)
                self.assertTrue(item.role)
                self.assertTrue(item.need)
                self.assertTrue(item.outcome)
                self.assertTrue(item.source_reference)
                self.assertTrue(item.acceptance_criteria)
                self.assertNotIn("SOURCE_PAGE", repr(item))

    def test_both_source_sections_are_represented(self) -> None:
        operational = [
            item for item in self.requirements if int(item.source_pages.split(";")[0]) < 36
        ]
        administration = [
            item for item in self.requirements if int(item.source_pages.split(";")[0]) >= 36
        ]
        self.assertEqual(len(operational), 69)
        self.assertEqual(len(administration), 52)

    def test_every_requirement_has_a_bounded_component(self) -> None:
        for item in self.requirements:
            with self.subTest(requirement_id=item.requirement_id):
                self.assertTrue(component_for(item.requirement_id))


if __name__ == "__main__":
    unittest.main()
