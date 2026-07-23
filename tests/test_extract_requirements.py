from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from tools.extract_requirements import (
    Requirement,
    component_for,
    parse_pdf,
    write_traceability,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/source/FirstBrief_Master_Requirements_TwoSections.pdf"


class TraceabilityWriterTests(unittest.TestCase):
    def test_regeneration_preserves_implementation_evidence(self) -> None:
        requirement = Requirement(
            requirement_id="FR-A01",
            theme="Updated source theme",
            role="User",
            need="Access",
            outcome="Work",
            dependencies="",
            requirement_owner="Product",
            source_reference="Updated source",
            acceptance_criteria="Given, when, then",
            source_pages="7",
        )
        fieldnames = [
            "requirement_id",
            "theme",
            "source_pages",
            "source_reference",
            "design_component",
            "code_path",
            "automated_test",
            "manual_test",
            "status",
            "notes",
        ]

        with TemporaryDirectory() as directory:
            output = Path(directory) / "traceability.csv"
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "requirement_id": "FR-A01",
                        "theme": "Old source theme",
                        "source_pages": "1",
                        "source_reference": "Old source",
                        "design_component": "Implemented component",
                        "code_path": "firstbrief/core/views.py",
                        "automated_test": "tests/test_foundation.py",
                        "manual_test": "GET /",
                        "status": "Partial",
                        "notes": "Foundation evidence",
                    }
                )

            write_traceability([requirement], output)

            with output.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["theme"], "Updated source theme")
        self.assertEqual(row["source_reference"], "Updated source")
        self.assertEqual(row["design_component"], "Implemented component")
        self.assertEqual(row["code_path"], "firstbrief/core/views.py")
        self.assertEqual(row["automated_test"], "tests/test_foundation.py")
        self.assertEqual(row["manual_test"], "GET /")
        self.assertEqual(row["status"], "Partial")
        self.assertEqual(row["notes"], "Foundation evidence")


@unittest.skipUnless(
    SOURCE.exists(),
    "controlled requirements PDF is not present in this checkout",
)
class RequirementsExtractionTests(unittest.TestCase):
    requirements: ClassVar[list[Requirement]]
    page_count: ClassVar[int]

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
