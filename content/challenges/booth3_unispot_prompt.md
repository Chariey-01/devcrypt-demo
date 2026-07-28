# Unispot Consultants Challenge: Spot the Forged Applicant Profile

## Problem statement

Unispot receives an applicant profile whose submitted details may not agree with the supporting documents. Build a small validation function that identifies the inconsistencies a consultant should review.

Edit `submission.py` and complete:

```python
def find_profile_issues(profile: dict) -> list[str]:
    ...
```

A profile contains:

- `application_name`: name entered on the application
- `passport_name`: name shown on the passport
- `subject_scores`: list of scores from 0 to 100
- `claimed_average`: average claimed by the applicant
- `graduation_year`: year shown on the academic document
- `application_year`: year the application was submitted

Return the following issue codes, in this exact order when they apply:

1. `NAME_MISMATCH` — the names differ after converting to lowercase, trimming outside spaces, and collapsing repeated internal spaces.
2. `INVALID_SCORE` — the score list is empty or at least one score is outside 0–100.
3. `AVERAGE_MISMATCH` — all scores are valid, but the claimed average differs from the calculated mean by more than `0.5` points.
4. `FUTURE_GRADUATION` — `graduation_year` is later than `application_year`.

Return `[]` when the profile has no issues. Do not mutate the input.

## Example

```python
profile = {
    "application_name": "Amina Noor",
    "passport_name": "  amina   noor ",
    "subject_scores": [80, 70, 90],
    "claimed_average": 80,
    "graduation_year": 2025,
    "application_year": 2026,
}

find_profile_issues(profile)  # []
```
