# How AI assistance was used (and validated)

The JD asks for AI tools used "with sound judgment about validating outputs". This project was built with an AI assistant; this page records how its output is controlled.

| Use | Control |
|---|---|
| Scaffolding generators, parsers, SQL | Round-trip tests (generator renders -> parser recovers attributes), seeded defects with exact counts |
| Matching thresholds | Graded against planted ground truth (precision must be 100%, recall reported); thresholds recorded as decisions DL-005 |
| Reconciliation logic | Recomputes from raw bronze and the load files, not from the pipeline's own numbers; one deliberate source break proves it can fail |
| Bugs found | The readiness gate caught a real stock-key collision during development (DL-009) - evidence the gates work |
| Documentation | Generated from code where possible (`make docs`) so it cannot drift |
| Anything business-specific | Marked as an assumption: IFS field names, SYSPRO/Syteline schemas are simplified placeholders to confirm with the implementation partner |

Rule used: AI output is a draft; nothing is trusted until a test, a reconciliation or a business owner has confirmed it.
