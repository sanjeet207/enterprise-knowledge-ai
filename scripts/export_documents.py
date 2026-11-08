"""Write the demo company's documents to evaluation/demo_documents.md so a person can read them and write questions.

Usage: python -m scripts.export_documents
"""
from pathlib import Path

from scripts.verify_access import DOCS

LEVEL_NAMES = {1: "Analyst and above", 2: "Manager and above", 3: "Director and above", 4: "Partner only"}


def main() -> None:
    lines = ["# Acme Financial Services: documents (fictional)", "",
             "Everything here is made up for a software project. Each document says who may read it.", ""]
    for key, (tenant, title, level, team, text) in DOCS.items():
        if tenant != "acme":
            continue
        who = LEVEL_NAMES[level] + (", and only members of the Project Titan deal team" if team else "")
        lines += [f"## {title}", f"*Who may read it: {who} (level {level})*", "", text, ""]
    Path("evaluation").mkdir(exist_ok=True)
    Path("evaluation/demo_documents.md").write_text("\n".join(lines))
    print("Wrote evaluation/demo_documents.md")


if __name__ == "__main__":
    main()
