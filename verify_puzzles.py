"""
verify_puzzles.py
Checks every puzzle in PUZZLE_BANK has the correct number of solutions.
Run with: python3 verify_puzzles.py
"""

import itertools

# ---------------------------------------------------------------------------
# Solver — counts unique expression strings (not permutations)
# ---------------------------------------------------------------------------

def _solve(nums, target):
    """Return set of unique expression strings that reach target."""
    if len(nums) == 1:
        if nums[0] == target:
            return {str(int(nums[0]))}
        return set()
    results = set()
    for i in range(len(nums)):
        for j in range(len(nums)):
            if i == j:
                continue
            a, b = nums[i], nums[j]
            rest = [nums[k] for k in range(len(nums)) if k != i and k != j]
            pairs = [
                (a + b, f"({int(a)}+{int(b)})"),
                (a - b, f"({int(a)}-{int(b)})"),
                (a * b, f"({int(a)}*{int(b)})"),
            ]
            if b != 0 and a % b == 0:
                pairs.append((a // b, f"({int(a)}/{int(b)})"))
            for val, expr in pairs:
                for sub in _solve(rest + [val], target):
                    results.add(sub.replace(str(int(val)), expr, 1))
    return results


def count_solutions(numbers, target):
    return len(_solve([float(n) for n in numbers], float(target)))


# ---------------------------------------------------------------------------
# Puzzle bank (must match server.py exactly)
# ---------------------------------------------------------------------------

PUZZLE_BANK = {
    4: [  # verified: exactly 2 unique solution expressions
        {"numbers": [1, 4, 6, 7], "target": 11},
        {"numbers": [6, 7, 9, 9], "target": 41},
        {"numbers": [3, 8, 8, 8], "target": 23},
        {"numbers": [2, 2, 7, 8], "target": 38},
        {"numbers": [4, 4, 5, 6], "target": 34},
        {"numbers": [2, 3, 4, 9], "target": 22},
        {"numbers": [3, 3, 8, 8], "target": 40},
        {"numbers": [5, 7, 8, 8], "target": 17},
        {"numbers": [3, 6, 7, 8], "target": 40},
        {"numbers": [2, 6, 6, 8], "target": 45},
        {"numbers": [1, 8, 8, 9], "target": 18},
        {"numbers": [1, 1, 5, 7], "target": 27},
    ],
    5: [  # verified: exactly 1 unique solution expression
        {"numbers": [1, 2, 6, 8], "target": 35},
        {"numbers": [1, 2, 7, 7], "target": 24},
        {"numbers": [6, 7, 8, 8], "target": 36},
        {"numbers": [2, 3, 3, 6], "target": 34},
        {"numbers": [3, 6, 7, 9], "target": 49},
        {"numbers": [2, 3, 7, 7], "target": 23},
        {"numbers": [2, 5, 7, 9], "target": 44},
        {"numbers": [1, 4, 5, 5], "target": 11},
        {"numbers": [4, 4, 5, 9], "target": 21},
        {"numbers": [1, 2, 6, 7], "target": 34},
        {"numbers": [3, 6, 7, 9], "target": 29},
        {"numbers": [3, 6, 9, 9], "target": 25},
    ],
}

EXPECTED = {4: 2, 5: 1}

# ---------------------------------------------------------------------------
# Run verification
# ---------------------------------------------------------------------------

def verify():
    all_pass = True

    for level, puzzles in PUZZLE_BANK.items():
        expected = EXPECTED[level]
        print(f"\nLevel {level} — expecting {expected} solution(s) each:")
        print(f"{'#':<4} {'Numbers':<20} {'Target':<8} {'Solutions':<12} {'Status'}")
        print("-" * 58)

        for i, p in enumerate(puzzles, 1):
            nums   = p["numbers"]
            target = p["target"]
            sols   = count_solutions(nums, target)
            ok     = sols == expected
            status = "✓ PASS" if ok else f"✗ FAIL (got {sols})"
            if not ok:
                all_pass = False
            print(f"{i:<4} {str(nums):<20} {target:<8} {sols:<12} {status}")

    print("\n" + "=" * 58)
    if all_pass:
        print("✓ All puzzles passed — safe to deploy.")
    else:
        print("✗ Some puzzles failed — fix them in server.py before deploying.")
    print("=" * 58)

    return all_pass


if __name__ == "__main__":
    verify()
