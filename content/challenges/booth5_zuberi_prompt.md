# Zuberi Interactive Challenge: Boda Escape — Fix the Getaway Sequence

## Problem statement

In BodaLands, the player escapes through a series of checkpoints. Each checkpoint has a difficulty score.

A valid getaway sequence must satisfy the following rules:

- The next checkpoint must be strictly more difficult than the previous one.
- Duplicate or lower values break the streak.

Return the length of the longest valid consecutive getaway sequence.

```python
def longest_getaway(checkpoints: list[int]) -> int:
    ...
```

## Example

```python
checkpoints = [2, 3, 4, 1, 2, 5]
longest_getaway(checkpoints)  # 3
# The longest valid sequence is: 2 -> 3 -> 4
```
