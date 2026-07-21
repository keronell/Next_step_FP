"""Turn questionnaire answers into a readable natural-language profile string
that the embedding model can match against real job ads. We deliberately use the
chosen option labels (not raw JSON) so the query reads like a person describing
themselves, e.g. "I am very comfortable writing code daily. I am excited by ...".

DEV-60: when the user filled the self-input profile step, their experience,
projects and skills are appended in the same first-person voice. That is the whole
integration for `semantic_similarity` — the query vector moves toward the fields
they actually have background in, which also carries into the learned matcher via
its `<career>_sem` features (no retrain, no FEATURE_VERSION bump).
"""
from common.data import load_questions
from common.models.profile import UserProfile
from common.profile_text import profile_sentences


def build_profile(answers: dict[str, int | None], user_profile: UserProfile | None = None) -> str:
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

    extra = profile_sentences(user_profile)

    if not phrases:
        # Shouldn't happen (submission validation requires one answer) but stay safe.
        quiz = "a motivated person exploring tech careers"
    else:
        quiz = "I am " + ". I am ".join(phrases) + "."

    return " ".join([quiz, *extra]) if extra else quiz
