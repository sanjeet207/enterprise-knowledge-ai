# Reproducibility run 20261123-181559

- Commit: 847a0a8 (8 uncommitted changes)
- Python: Python 3.12.2
- Model: default from config ; Ollama: ollama version is 0.40.13
- Machine: Darwin arm64

| Check | Result | Last line |
|---|---|---|
| unit_tests | ok | 455 passed, 1 warning in 1.58s |
| access_checks | ok | 160/160 access checks passed |
| seed_demo | ok | see log |
| validator_check | ok | see log |
| inspector_check | exit 1 | ok  unseen staff rules 2       expected PASS  got PASS  [neither] |
| crash_test | ok | 8/8 checks passed |
| smoke_test | ok | 83/83 checks passed |
| security_probe | ok | 57/57 attacks defended |
| evaluation_86 | ok | [86/86] PASS general    analyst          What is compound interest? |
| evaluation_independent | ok | [27/27] PASS off_topic  analyst          Who won the cricket match yesterday? |
| evaluation_research | ok | Coverage: report 5/6, single question 1/6. Leaks: 0. Wrote evaluation/RESEARCH_EVAL.md |
