# Elewa Challenge: Workflow Integrity Checker

## Problem statement

An ERP workflow consists of ordered task IDs.

A workflow is considered valid if:

1. It starts with task 1.
2. Every subsequent task increases by exactly 1.
3. No task appears more than once.

Return `True` if the workflow is valid; otherwise return `False`.

The implementation below was modified during a faulty deployment and now incorrectly validates some workflows. Your task is to complete the existing implementation.

```python
def validate_workflow(tasks: list[int]) -> bool:
    ...
```

## Example

```python
validate_workflow([1, 2, 3, 4])  # True
validate_workflow([1, 2, 2, 3])  # False
```
