# Workforce Africa Challenge: Ghosts on the Payroll

## Problem statement

A client suspects that its payroll file may contain ghost or invalid employees. Implement a function that flags suspicious employee records before payroll is released.

Edit `submission.py` and complete:

```python
def flag_suspicious_employees(records: list[dict]) -> list[str]:
    ...
```

Each record contains:

- `employee_id`: unique employee identifier
- `national_id`: national identification number, or a missing value
- `bank_account`: destination bank/mobile-money account, or a missing value
- `employment_status`: `active` or `inactive`
- `net_pay`: amount to be paid

An employee is suspicious when **at least one** rule is true:

1. `national_id` is `None`, empty, or contains only spaces.
2. The employee is `inactive` (case-insensitive) but has `net_pay > 0`.
3. The same non-empty bank account is shared by more than one **different** employee.

For bank-account comparison, remove all spaces and ignore letter case. Repeated rows for the same employee must not, by themselves, trigger rule 3.

Return a **sorted list of unique employee IDs**. Do not mutate the input.

## Example

```python
records = [
    {
        "employee_id": "E001",
        "national_id": "12345678",
        "bank_account": "KE 001",
        "employment_status": "active",
        "net_pay": 45000,
    },
    {
        "employee_id": "E002",
        "national_id": " ",
        "bank_account": "KE002",
        "employment_status": "active",
        "net_pay": 32000,
    },
]

flag_suspicious_employees(records)  # ["E002"]
```
