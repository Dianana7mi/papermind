# Prior systems and project scope

Checked public repository descriptions on 2026-10-19:

| System | Publicly documented focus | Implication for PaperMind |
| --- | --- | --- |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Scientific-document RAG with citations | Citation QA is established functionality, not a novelty claim |
| [Ai2 ScholarQA](https://github.com/allenai/ai2-scholarqa-lib) | Library/application code for scholar QA | Research QA products already exist |
| [OpenScholar](https://github.com/AkariAsai/OpenScholar) | Retrieval-augmented scientific literature synthesis | Literature synthesis is prior work |
| [STORM](https://github.com/stanford-oval/storm) | Topic research and long cited reports | Agentic report generation is prior work |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Autonomous research over data/providers | General research-agent orchestration is prior work |
| [Docling](https://github.com/docling-project/docling) | Document conversion for generative AI | Layout/table parsing is reused infrastructure |

PaperMind chooses structured experiment conditions, explicit comparability rules and cell-linked verification as its engineering focus. This table does not assert that competing systems cannot implement those ideas, does not establish academic novelty, and is not a head-to-head performance comparison. No competitor benchmark was executed.

The implemented business modules are independent code. Their local regression/pilot results are in the evaluation report; a broad novelty/quality claim would require a separately designed comparison with real independent labels.
