"""Turn questionnaire answers into a readable natural-language profile string
that the embedding model can match against real job ads. We deliberately use the
chosen option labels (not raw JSON) so the query reads like a person describing
themselves, e.g. "I am very comfortable writing code daily. I am excited by ...".
"""
from app.data import load_questions


def build_profile(answers: dict[str, int | None]) -> str:
    questions = {q["id"]: q for q in load_questions()}
    phrases: list[str] = []

    for qid, value in answers.items():
        if value is None:
            continue
        q = questions.get(qid)
        if not q:
            continue
        options = q["options"]
        if 0 <= value < len(options):
            phrases.append(options[value])

    if not phrases:
        # Shouldn't happen (submission validation requires one answer) but stay safe.
        return "a motivated person exploring tech careers"

    return "I am " + ". I am ".join(phrases) + "."
