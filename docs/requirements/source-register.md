# Requirements source register

Reviewed on 2026-07-23.

## Controlling source

- File: `docs/source/FirstBrief_Master_Requirements_TwoSections.pdf`
- Classification marking: NATS Internal
- Pages: 52 (all processed)
- SHA-256: `1d40779b51a245b58a5a29dceef5d0f2ba441ad0816fead8a9a3290b60336e04`
- Sections: Operational / Functional User Stories (pages 1–30); Admin / Configuration User Stories (pages 30–52)
- Detailed authoritative stories: pages 7–30 and 36–52
- Unique detailed requirement IDs: 121
- Extraction: `pypdf` text extraction, with page-aware validation by `tools/extract_requirements.py`

## Implementation guide

- File reviewed: `FirstBrief_Codex_Implementation_and_User_Guide_Updated.docx`
- Location at review: controlled attachment outside the repository
- SHA-256: `7de4e3607903467e26e29092e3fa115f14fff05bdc6937d372f8d88818ef617e`
- Purpose: sequencing, architectural recommendations, proposed NFRs/FR-K requirements, acceptance strategy, and draft guides
- Authority: useful implementation guidance; it does not replace the controlling PDF

## Parser limitations

- Summary tables on pages 1–6 and 31–35 split IDs and words across visual table cells. They were reviewed for coverage but not used as the authoritative field source.
- The detailed stories were extracted successfully. Cross-page stories retain all affected source page numbers.
- Bullets are preserved as plain text in CSV cells. Their order is preserved, but nested visual indentation is not represented.
- The source names every dependency `None` and every owner `TBD`; these are source-quality issues, not parser omissions.
- Visual DOCX rendering was unavailable because LibreOffice is not installed. Structural inspection and complete text extraction succeeded.
