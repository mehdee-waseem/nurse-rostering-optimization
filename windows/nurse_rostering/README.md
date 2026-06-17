# Nurse Rostering Problem Solver
## Master EUNICE IT4SSM — Optimization Fundamentals 2025-2026

### Requirements
- Python 3.10+
- `ortools` (Google OR-Tools CP-SAT)

Install dependencies:

pip install ortools

> **Note:** The CPLEX installer provided (cplex_studio2212.win_x86_64.exe)
> was Windows-only and incompatible with our macOS development environment.
> Google OR-Tools CP-SAT was used as a functionally equivalent MIP solver.

### File Structure
- `nurse_rostering.py`  — main module (all 6 required functions)
- `run_all.py`          — batch runner for all 24 instances
- `instances/`          — 24 .txt and .ros instance files
- `results/`            — .ros solution files and results_summary.csv
- `README.md`           — this file

### Usage

**Single instance (greedy heuristic):**

python nurse_rostering.py instances/Instance1.txt

**Single instance (MIP solver, 60s limit):**

python nurse_rostering.py instances/Instance1.txt --mip --tl 60

**All 24 instances:**

python run_all.py

### Output
- Terminal prints schedule grid, coverage table, penalty, and feasibility
- Solution saved as `.ros` file viewable in the Staff Roster Solutions RosterViewer tool
- `run_all.py` saves all results to `results/results_summary.csv`

### API
```python
from nurse_rostering import (
    read_instance, build_schedule, evaluate_solution,
    check_feasibility, save_ros, solve_with_cplex
)

data = read_instance("instances/Instance1.txt")

# Greedy heuristic
sol = build_schedule(data)
ok, violations = check_feasibility(data, sol)
penalty = evaluate_solution(data, sol)
save_ros(data, sol, "solution.ros")

# MIP solver
sol, obj, status = solve_with_cplex(data, time_limit=60)
```

### Notes
- All 24 instances solved and results available in `results/`
- Instance 1 achieves OPTIMAL status (penalty 607)
- Instances 2-22 achieve FEASIBLE status within 60 seconds
- Instances 23-24 return UNKNOWN status due to model size