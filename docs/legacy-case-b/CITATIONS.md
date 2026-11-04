# Citations and licences (PS Rule 3)

| Resource | Use here | Licence / terms | Citation |
|---|---|---|---|
| Open University Learning Analytics Dataset (OULAD) | dropout validation (`ml/public_validation`) | CC BY 4.0 | Kuzilek, J., Hlosta, M., Zdrahal, Z. (2017). Open University Learning Analytics dataset. *Scientific Data* 4, 170171. |
| ASSISTments 2009-2010 skill builder | knowledge-tracing validation | free for research, no explicit licence; not redistributed | Feng, M., Heffernan, N., Koedinger, K. (2009). Addressing the assessment challenge with an online system that tutors as it assesses. *User Modeling and User-Adapted Interaction* 19(3). |
| pyKT benchmark protocol and reference AUCs | comparison protocol (DKT 0.7541, SAKT 0.7246, AKT 0.7853 on AS2009) | paper | Liu, Z. et al. (2022). pyKT: A Python Library to Benchmark Deep Learning based Knowledge Tracing Models. NeurIPS Datasets & Benchmarks. arXiv:2206.11460 |
| OULAD early-withdrawal anchors | comparison numbers (0.727 / 0.794 / 0.804 at days 14 / 28 / 42) | paper | Wu, S., Duan, J., Luo, M. (2026). *PLOS ONE* 21(7): e0352867 (see also correction e0355736). **Verify the numbers in the paper itself before putting them on a slide.** |
| JEEBench (planned: question tagging) | public question text for tagging evaluation | MIT | Arora, D., Singh, H., Mausam (2023). Have LLMs Advanced Enough? A Challenging Problem Solving Benchmark For LLMs. EMNLP. |
| Noto Sans Devanagari font | offline Hindi PDF rendering | SIL OFL 1.1 (licence file bundled in `backend/templates/fonts/`) | Google / Noto Project |
| DPDP Act 2023, DPDP Rules 2025, MoE Coaching Guidelines 2024, Rajasthan Coaching Centres Act 2025 | design constraints | public law | clause-level citations in `docs/TECH_PLAN.md` §24 |
| LightGBM, NumPy, SciPy, pandas, scikit-learn, FastAPI, OpenCV, Ollama, Qwen3, Gemma 3 | tooling | respective open-source licences (Qwen3 Apache-2.0, Gemma terms) | pinned versions in each module's `requirements.txt` |

## AI-tool disclosure (must also appear on the final slide, PS Rule 2)
Claude (planning, code review, documentation), Google Antigravity agents (code generation), Perplexity / Gemini Deep Research (literature and regulation research). All outputs were reviewed and tested by the team and can be explained by it; research claims were checked against primary sources where possible (`TECH_PLAN.md` §24 lists the claims we did not trust).
