"""Batch runner: solve all 24 instances, collect results."""
import os, sys, time, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nurse_rostering import (read_instance, build_schedule, evaluate_solution,
                              check_feasibility, solve_with_cplex, save_ros)

INST_DIR = os.path.join(os.path.dirname(__file__), "instances")
RES_DIR  = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RES_DIR, exist_ok=True)

MIP_TIME = 60  # seconds per instance

results = []
for i in range(1, 25):
    path     = os.path.join(INST_DIR, f"Instance{i}.txt")
    ros_path = os.path.join(INST_DIR, f"Instance{i}.ros")
    if not os.path.exists(path):
        print(f"Instance{i}: NOT FOUND"); continue

    print(f"\n=== Instance {i} ===", flush=True)
    data = read_instance(path)
    print(f"  {data.horizon}d | {len(data.employees)}e | {len(data.shifts)}s")

    # Greedy
    t0 = time.time()
    g_sol = build_schedule(data)
    g_time = time.time() - t0
    g_pen  = evaluate_solution(data, g_sol)
    g_ok, g_viol = check_feasibility(data, g_sol)
    print(f"  Greedy : pen={g_pen:>6}  feasible={g_ok}  t={g_time:.3f}s")
    save_ros(data, g_sol,
             os.path.join(RES_DIR, f"Instance{i}_greedy.ros"),
             ros_path)

    # MIP
    t0 = time.time()
    m_sol, m_pen, m_status = solve_with_cplex(data, time_limit=MIP_TIME, verbose=False)
    m_time = time.time() - t0
    if m_sol is not None:
        m_ok, m_viol = check_feasibility(data, m_sol)
        print(f"  MIP    : pen={m_pen:>6}  status={m_status:<12}  t={m_time:.1f}s  feasible={m_ok}")
        save_ros(data, m_sol,
                 os.path.join(RES_DIR, f"Instance{i}_mip.ros"),
                 ros_path)
    else:
        m_ok = False; m_viol = []
        print(f"  MIP    : NO SOLUTION  status={m_status}  t={m_time:.1f}s")

    results.append(dict(
        instance=i, horizon=data.horizon,
        employees=len(data.employees), shifts=len(data.shifts),
        greedy_pen=g_pen, greedy_feasible=g_ok, greedy_violations=len(g_viol), greedy_time=round(g_time,3),
        mip_pen=m_pen if m_sol else "N/A", mip_status=m_status,
        mip_feasible=m_ok, mip_time=round(m_time,1)
    ))

csv_path = os.path.join(RES_DIR, "results_summary.csv")
with open(csv_path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader(); w.writerows(results)

print(f"\n\n{'='*100}")
print(f"RESULTS SUMMARY (MIP time limit: {MIP_TIME}s/instance)")
print(f"{'='*100}")
print(f"{'#':>3} | {'H':>4} | {'E':>3} | {'S':>2} | {'Greedy Pen':>10} | {'G.Feas':>6} | {'G.T(s)':>6} | {'MIP Pen':>8} | {'Status':>12} | {'M.T(s)':>6}")
print("-"*100)
for r in results:
    print(f"{r['instance']:>3} | {r['horizon']:>4} | {r['employees']:>3} | {r['shifts']:>2} | "
          f"{str(r['greedy_pen']):>10} | {str(r['greedy_feasible']):>6} | {r['greedy_time']:>6.3f} | "
          f"{str(r['mip_pen']):>8} | {str(r['mip_status']):>12} | {r['mip_time']:>6.1f}")
print(f"\nFull results saved to: {csv_path}")
