# Nurse Rostering Problem — ILP Optimization

Solves the **Nurse Rostering Problem (NRP)** as an integer linear program: assign nurses to shifts over a planning horizon while respecting hard constraints (coverage, rest periods, contracted hours) and minimising soft-constraint penalties (preferences, fairness).

**Course:** Optimization Fundamentals — Master IT4SSM, Eunice University, 2025/2026
**Author:** Muhammad Waseem

## Approach

Two solving strategies are implemented and compared across 24 real problem instances (ranging from 8 nurses / 14 days up to 150 nurses / 364 days):

1. **Greedy heuristic** — fast, always returns a result, but generally higher penalty and sometimes infeasible on harder instances.
2. **MIP solver** — formal integer programming model, solved to optimality or to a 60-second time limit. The original plan was IBM CPLEX, but the provided installer was Windows-only; Google OR-Tools CP-SAT was used as a functionally equivalent solver where needed.

The MIP solver beats the greedy baseline on penalty in almost every instance — e.g. Instance 1 drops from penalty 1520 (greedy) to 607 (MIP, solved to provable optimality). The two largest instances (23–24) hit the solver's size limits and return UNKNOWN, an expected and honestly reported scaling limitation.

## Repo layout

This project was developed and run across two different machines, so the repo is split by environment:
nurse-rostering-optimization/

├── windows/    — Windows build/setup, solver run, and results

├── __MACOSX/   — macOS build/setup, solver run, and results

└── NurseRostering_report.pdf   — full writeup: problem formulation, model, and results for all 24 instances

Each folder has its own setup instructions and may differ slightly in solver configuration (see the note on CPLEX vs. OR-Tools above). Open the report PDF for the complete picture — problem formulation, constraints, MIP model, and the full results table across all 24 instances.

## Quick start (general)

```bash
pip install ortools
python nurse_rostering.py instances/Instance1.txt --mip --tl 60
```

See the relevant OS folder for exact paths and any environment-specific notes.