# ABB Warehouse Slotting Research Pack

This folder is a Claude Code handoff pack for the ABB "智储优控" competition.

Primary report:

- `deep_research_report.md`

Raw and supporting files:

- `research_scope.md` - original scope and contest constraints used for research.
- `parallel/abb-warehouse-slotting-parallel-api-result.md` - Parallel deep-research raw Markdown result.
- `parallel/abb-warehouse-slotting-parallel-api-result.json` - Parallel API JSON result.
- `sources/sources.jsonl` - source registry.
- `sources/evidence.jsonl` - evidence summaries.
- `sources/claims.jsonl` - claim ledger with support and risk.
- `sources/pdf_text/*.txt` - extracted text from downloaded PDFs.
- `papers/*.pdf` - downloaded papers and ABB WebVisu PDF.
- `projects/*` - cloned open-source reference projects.
- `downloads/*.html` - downloaded ABB/CODESYS web references.
- `logs/*_access_denied.html` - MDPI access-denied responses; do not treat these as PDF originals.

Recommended Claude Code first action:

1. Read `deep_research_report.md`.
2. Read `sources/sources.jsonl`.
3. Inspect `projects/warehouse-simulator`, `projects/MetaSimOpt`, and `projects/Warehouse-Optimization`.
4. Build a Python prototype before writing ST code.
5. Treat paywalled/link-only claims as hypotheses until manually verified.
