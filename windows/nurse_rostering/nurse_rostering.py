"""
Nurse Rostering Problem Solver
================================
Master EUNICE IT4SSM - Optimization Fundamentals 2025-2026
Group Project

This module provides:
  1. read_instance(filepath)           - Parse a .txt instance file
  2. build_schedule(data)              - Build a feasible schedule (greedy heuristic)
  3. evaluate_solution(data, sol)      - Compute the penalty value of a solution
  4. check_feasibility(data, sol)      - Verify all hard constraints
  5. save_ros(data, sol, filepath)     - Export solution to .ros XML format
  6. solve_with_cplex(data, ...)       - Solve via OR-Tools CP-SAT (MIP equivalent)
"""

import re, math, time, os
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


# DATA STRUCTURES
class ShiftType:
    def __init__(self, sid, duration, forbidden_after):
        self.id = sid
        self.duration = duration            # minutes
        self.forbidden_after = forbidden_after  # list of shift IDs


class Employee:
    def __init__(self, eid, max_shifts, max_total, min_total,
                 max_consec, min_consec, min_consec_off, max_weekends):
        self.id = eid
        self.max_shifts = max_shifts        # {shift_id: max_count}
        self.max_total = max_total
        self.min_total = min_total
        self.max_consec = max_consec
        self.min_consec = min_consec
        self.min_consec_off = min_consec_off
        self.max_weekends = max_weekends
        self.days_off: List[int] = []


class InstanceData:
    def __init__(self):
        self.horizon = 0
        self.shifts: Dict[str, ShiftType] = {}
        self.employees: Dict[str, Employee] = {}
        self.shift_on_requests = defaultdict(lambda: defaultdict(dict))
        self.shift_off_requests = defaultdict(lambda: defaultdict(dict))
        self.cover = defaultdict(dict)


#DATA READER
def read_instance(filepath: str) -> InstanceData:
    data = InstanceData()
    with open(filepath, 'r') as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]

    section = None
    for line in lines:
        if line.startswith('SECTION_'):
            section = line
            continue

        if section == 'SECTION_HORIZON':
            data.horizon = int(line)

        elif section == 'SECTION_SHIFTS':
            parts = line.split(',')
            sid = parts[0].strip()
            dur = int(parts[1].strip())
            forbidden = []
            if len(parts) > 2 and parts[2].strip():
                forbidden = [x.strip() for x in parts[2].split('|') if x.strip()]
            data.shifts[sid] = ShiftType(sid, dur, forbidden)

        elif section == 'SECTION_STAFF':
            parts = [p.strip() for p in line.split(',')]
            eid = parts[0]
            max_shifts = {}
            for item in parts[1].split('|'):
                item = item.strip()
                if '=' in item:
                    s, v = item.split('=')
                    max_shifts[s.strip()] = int(v.strip())
            data.employees[eid] = Employee(
                eid=eid, max_shifts=max_shifts,
                max_total=int(parts[2]), min_total=int(parts[3]),
                max_consec=int(parts[4]), min_consec=int(parts[5]),
                min_consec_off=int(parts[6]), max_weekends=int(parts[7])
            )

        elif section == 'SECTION_DAYS_OFF':
            parts = line.split(',')
            eid = parts[0].strip()
            day = int(parts[1].strip())
            if eid in data.employees:
                data.employees[eid].days_off.append(day)

        elif section == 'SECTION_SHIFT_ON_REQUESTS':
            parts = line.split(',')
            data.shift_on_requests[parts[0].strip()][int(parts[1].strip())][parts[2].strip()] = int(parts[3].strip())

        elif section == 'SECTION_SHIFT_OFF_REQUESTS':
            parts = line.split(',')
            data.shift_off_requests[parts[0].strip()][int(parts[1].strip())][parts[2].strip()] = int(parts[3].strip())

        elif section == 'SECTION_COVER':
            parts = line.split(',')
            data.cover[int(parts[0].strip())][parts[1].strip()] = (
                int(parts[2].strip()), int(parts[3].strip()), int(parts[4].strip())
            )

    return data



#FEASIBLE SCHEDULE BUILDER (Greedy Heuristic)

def build_schedule(data: InstanceData) -> Dict[str, Dict[int, Optional[str]]]:
    """
    dict  sol[emp_id][day] = shift_id or None
    """
    E = list(data.employees.keys())
    P = list(data.shifts.keys())
    H = data.horizon

    sol = {e: {j: None for j in range(H)} for e in E}
    total_min = {e: 0 for e in E}
    shift_cnt = {e: {s: 0 for s in P} for e in E}
    weekend_wkd = {e: set() for e in E}  # set of week indices worked

    def prev_shift(e, j):
        return sol[e][j-1] if j > 0 else None

    def consec_work_before(e, j):
        c, d = 0, j - 1
        while d >= 0 and sol[e][d] is not None:
            c += 1; d -= 1
        return c

    def consec_off_before(e, j):
        c, d = 0, j - 1
        while d >= 0 and sol[e][d] is None:
            c += 1; d -= 1
        return c

    def consec_work_after(e, j):
        c, d = 0, j + 1
        while d < H and sol[e][d] is not None:
            c += 1; d += 1
        return c

    def consec_off_after(e, j):
        c, d = 0, j + 1
        while d < H and sol[e][d] is None:
            c += 1; d += 1
        return c

    def week_of(j):
        return j // 7

    def dow(j):  # 0=Mon..5=Sat,6=Sun
        return j % 7

    def can_assign(e, j, p):
        emp = data.employees[e]
        s = data.shifts[p]
        if j in emp.days_off: return False
        if sol[e][j] is not None: return False
        # Shift rotation
        prev = prev_shift(e, j)
        if prev and p in data.shifts[prev].forbidden_after: return False
        # Max shifts of type
        if shift_cnt[e][p] >= emp.max_shifts.get(p, 0): return False
        # Max total minutes
        if total_min[e] + s.duration > emp.max_total: return False
        # Max consecutive shifts
        cw = consec_work_before(e, j)
        if cw >= emp.max_consec: return False
        # Min consecutive days off: if a day-off run just ended, it must be >= min_consec_off
        co = consec_off_before(e, j)
        if 0 < co < emp.min_consec_off: return False
        # Max weekends
        d = dow(j)
        if d in (5, 6):
            w = week_of(j)
            if w not in weekend_wkd[e] and len(weekend_wkd[e]) >= emp.max_weekends:
                return False
        return True

    # Sort (day, shift) pairs by coverage requirement descending
    pairs = []
    for j in range(H):
        for p in P:
            req = data.cover.get(j, {}).get(p, (0,))[0]
            pairs.append((j, p, req))
    pairs.sort(key=lambda x: -x[2])

    assigned = {(j, p): 0 for j in range(H) for p in P}

    for (j, p, req) in pairs:
        if p not in data.shifts: continue
        s = data.shifts[p]
        candidates = [e for e in E if can_assign(e, j, p)]
        # Prioritise those with more remaining budget
        candidates.sort(key=lambda e: -(data.employees[e].max_total - total_min[e]))
        for e in candidates:
            if assigned[(j, p)] >= req: break
            sol[e][j] = p
            total_min[e] += s.duration
            shift_cnt[e][p] += 1
            assigned[(j, p)] += 1
            d = dow(j)
            if d in (5, 6):
                weekend_wkd[e].add(week_of(j))

    # Fill min_total gaps
    for e in E:
        emp = data.employees[e]
        for j in range(H):
            if total_min[e] >= emp.min_total: break
            if sol[e][j] is not None: continue
            for p in P:
                if can_assign(e, j, p):
                    s = data.shifts[p]
                    if total_min[e] + s.duration <= emp.max_total:
                        sol[e][j] = p
                        total_min[e] += s.duration
                        shift_cnt[e][p] += 1
                        d = dow(j)
                        if d in (5, 6):
                            weekend_wkd[e].add(week_of(j))
                        break

    return sol



#SOLUTION EVALUATOR

def evaluate_solution(data: InstanceData,
                      sol: Dict[str, Dict[int, Optional[str]]]) -> int:
    penalty = 0
    for e, day_dict in data.shift_on_requests.items():
        for j, shift_dict in day_dict.items():
            for p, w in shift_dict.items():
                if sol.get(e, {}).get(j) != p:
                    penalty += w
    for e, day_dict in data.shift_off_requests.items():
        for j, shift_dict in day_dict.items():
            for p, w in shift_dict.items():
                if sol.get(e, {}).get(j) == p:
                    penalty += w
    for j in range(data.horizon):
        for p, (req, wu, wo) in data.cover.get(j, {}).items():
            assigned = sum(1 for e in data.employees if sol.get(e, {}).get(j) == p)
            if assigned < req:   penalty += (req - assigned) * wu
            elif assigned > req: penalty += (assigned - req) * wo
    return penalty



#FEASIBILITY CHECKER

def check_feasibility(data: InstanceData,
                      sol: Dict[str, Dict[int, Optional[str]]]) -> Tuple[bool, List[str]]:
    """
    Verify all hard constraints of a solution.

    Parameters
    ----------
    data : InstanceData
    sol  : dict

    Returns
    -------
    (is_feasible : bool, violations : List[str])
    """
    violations = []
    H = data.horizon

    for eid, emp in data.employees.items():
        sched = [sol.get(eid, {}).get(j) for j in range(H)]

        # C9: mandatory days off
        for d in emp.days_off:
            if sched[d] is not None:
                violations.append(f"[C9] {eid}: worked on mandatory off day {d}")

        # C2: shift rotation
        for j in range(1, H):
            if sched[j-1] and sched[j]:
                if sched[j] in data.shifts[sched[j-1]].forbidden_after:
                    violations.append(f"[C2] {eid}: forbidden rotation {sched[j-1]}->{sched[j]} days {j-1}-{j}")

        # C3: max shifts per type
        cnt = defaultdict(int)
        for s in sched:
            if s: cnt[s] += 1
        for p, n in cnt.items():
            lim = emp.max_shifts.get(p, 0)
            if n > lim:
                violations.append(f"[C3] {eid}: {n} shifts of type {p}, max {lim}")

        # C4: total minutes
        total = sum(data.shifts[s].duration for s in sched if s)
        if total > emp.max_total:
            violations.append(f"[C4] {eid}: total {total} min > max {emp.max_total}")
        if total < emp.min_total:
            violations.append(f"[C4] {eid}: total {total} min < min {emp.min_total}")

        # C5, C6, C7: run-based constraints
        j = 0
        while j < H:
            if sched[j] is not None:
                rs = j
                while j < H and sched[j] is not None: j += 1
                rlen = j - rs
                if rlen > emp.max_consec:
                    violations.append(f"[C5] {eid}: {rlen} consecutive shifts from day {rs}, max {emp.max_consec}")
                if rs > 0 and j < H and rlen < emp.min_consec:
                    violations.append(f"[C6] {eid}: {rlen} consecutive shifts from day {rs}, min {emp.min_consec}")
            else:
                rs = j
                while j < H and sched[j] is None: j += 1
                rlen = j - rs
                if rs > 0 and j < H and rlen < emp.min_consec_off:
                    violations.append(f"[C7] {eid}: {rlen} consecutive days off from day {rs}, min {emp.min_consec_off}")

        # C8: max weekends
        ww = 0
        for w in range(H // 7):
            sat, sun = w*7+5, w*7+6
            if (sat < H and sched[sat]) or (sun < H and sched[sun]):
                ww += 1
        if ww > emp.max_weekends:
            violations.append(f"[C8] {eid}: {ww} weekends worked, max {emp.max_weekends}")

    return len(violations) == 0, violations


# 5. ROS FILE WRITER
def save_ros(data: InstanceData,
             sol: Dict[str, Dict[int, Optional[str]]],
             filepath: str,
             instance_ros_path: str = None) -> None:
    """

    Parameters
    ----------
    data               : InstanceData
    sol                : dict   sol[emp_id][day] = shift_id or None
    filepath           : str    Output .ros file path
    instance_ros_path  : str    Path to the original instance .ros file.
                                If None or file not found, falls back to
                                a basic standalone XML format.
    """
    import re

    
    if instance_ros_path and os.path.exists(instance_ros_path):
        with open(instance_ros_path, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = []
        for eid in data.employees:
            for j in range(data.horizon):
                shift = sol.get(eid, {}).get(j)
                if shift:  # only write working days
                    lines.append(
                        f'        <Employee>'
                        f'<EmployeeID>{eid}</EmployeeID>'
                        f'<Assign><Shift>{shift}</Shift>'
                        f'<Day>{j}</Day></Assign>'
                        f'</Employee>'
                    )

        solution_block = '\n'.join(lines)
        new_fixed = (
            f'    <FixedAssignments>\n'
            f'{solution_block}\n'
            f'    </FixedAssignments>'
        )

        content = re.sub(
            r'<FixedAssignments>.*?</FixedAssignments>',
            new_fixed,
            content,
            flags=re.DOTALL
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return


    from xml.dom import minidom
    from datetime import date, timedelta

    sd = date.fromisoformat("2014-01-06")
    ed = sd + timedelta(days=data.horizon - 1)

    root = ET.Element("SchedulingPeriod")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "SchedulingPeriod-3.0.xsd")

    ET.SubElement(root, "StartDate").text = str(sd)
    ET.SubElement(root, "EndDate").text = str(ed)

    colors = ["Chartreuse", "CornflowerBlue", "LightSalmon", "Plum",
              "Gold", "Aquamarine", "Coral", "LightSkyBlue"]
    st_el = ET.SubElement(root, "ShiftTypes")
    for i, (sid, s) in enumerate(data.shifts.items()):
        sh = ET.SubElement(st_el, "Shift")
        sh.set("ID", sid)
        ET.SubElement(sh, "Color").text = colors[i % len(colors)]
        ET.SubElement(sh, "StartTime").text = "9:0"
        ET.SubElement(sh, "Duration").text = str(s.duration)

    emps_el = ET.SubElement(root, "Employees")
    for eid in data.employees:
        e = ET.SubElement(emps_el, "Employee")
        e.set("ID", eid)
        ET.SubElement(e, "Name").text = eid

    fa_el = ET.SubElement(root, "FixedAssignments")
    for eid in data.employees:
        for j in range(data.horizon):
            shift = sol.get(eid, {}).get(j)
            if shift:
                emp_el = ET.SubElement(fa_el, "Employee")
                ET.SubElement(emp_el, "EmployeeID").text = eid
                asgn = ET.SubElement(emp_el, "Assign")
                ET.SubElement(asgn, "Shift").text = shift
                ET.SubElement(asgn, "Day").text = str(j)

    rough = ET.tostring(root, encoding='unicode')
    pretty = minidom.parseString(rough).toprettyxml(
        indent="    ", encoding="UTF-8"
    )
    with open(filepath, 'wb') as f:
        f.write(pretty)

def solve_with_cplex(data: InstanceData,
                     time_limit: int = 120,
                     verbose: bool = False) -> Tuple[Optional[Dict], int, str]:

    from ortools.sat.python import cp_model

    E = list(data.employees.keys())
    P = list(data.shifts.keys())
    H = data.horizon
    J = list(range(H))
    W = list(range(H // 7))

    model = cp_model.CpModel()

    # ---- Decision Variables ----
    x = {}
    for e in E:
        for j in J:
            for p in P:
                x[e, j, p] = model.new_bool_var(f"x_{e}_{j}_{p}")

    t = {}
    for e in E:
        for w in W:
            t[e, w] = model.new_bool_var(f"t_{e}_{w}")

    y_minus, y_plus = {}, {}
    for j in J:
        for p in P:
            y_minus[j, p] = model.new_int_var(0, len(E), f"ym_{j}_{p}")
            y_plus[j, p]  = model.new_int_var(0, len(E), f"yp_{j}_{p}")

    obj_terms = []

    for e, day_dict in data.shift_on_requests.items():
        for j, sd in day_dict.items():
            for p, w in sd.items():
                if p in P and j in J:
                    # penalise if not assigned: w * (1 - x[e,j,p])
                    not_x = model.new_bool_var(f"notx_{e}_{j}_{p}")
                    model.add_bool_xor([x[e, j, p], not_x])
                    obj_terms.append(not_x * w)

    for e, day_dict in data.shift_off_requests.items():
        for j, sd in day_dict.items():
            for p, w in sd.items():
                if p in P and j in J:
                    obj_terms.append(x[e, j, p] * w)

    for j in J:
        for p in P:
            cover_info = data.cover.get(j, {}).get(p)
            if cover_info:
                _, wu, wo = cover_info
                obj_terms.append(y_minus[j, p] * wu)
                obj_terms.append(y_plus[j, p]  * wo)

    model.minimize(cp_model.LinearExpr.sum(obj_terms))

    # ---- Hard Constraints ----

    # C1: at most one shift per day per employee
    for e in E:
        for j in J:
            model.add(sum(x[e, j, p] for p in P) <= 1)

    # C2: shift rotation
    for e in E:
        for j in range(1, H):
            for p in P:
                for p2 in data.shifts[p].forbidden_after:
                    if p2 in P:
                        model.add(x[e, j-1, p] + x[e, j, p2] <= 1)

    # C3: max shifts per type
    for e in E:
        emp = data.employees[e]
        for p in P:
            lim = emp.max_shifts.get(p, 0)
            model.add(sum(x[e, j, p] for j in J) <= lim)

    # C4: total minutes
    for e in E:
        emp = data.employees[e]
        total = sum(data.shifts[p].duration * x[e, j, p] for j in J for p in P)
        model.add(total <= emp.max_total)
        model.add(total >= emp.min_total)

    # C5: max consecutive shifts
    for e in E:
        L = data.employees[e].max_consec + 1
        for j in range(H - L + 1):
            model.add(sum(x[e, d, p] for d in range(j, j+L) for p in P) <= data.employees[e].max_consec)

    # C6: min consecutive shifts (interior runs only)
    for e in E:
        m = data.employees[e].min_consec
        if m <= 1: continue
        for j in range(1, H - 1):
            start = max(0, j - m + 1)
            # if working on j and off on j+1, must have worked on all days [start..j]
            # i.e. m*(work_j - work_{j+1}) <= sum_{k=start}^{j} work_k
            # => m*work_j - m*work_{j+1} <= sum work
            work_j  = sum(x[e, j, p] for p in P)
            work_j1 = sum(x[e, j+1, p] for p in P)
            work_w  = sum(x[e, k, p] for k in range(start, j+1) for p in P)
            model.add(m * work_j <= work_w + m * work_j1)

    # C7: min consecutive days off (interior off-runs)
    for e in E:
        r = data.employees[e].min_consec_off
        if r <= 1: continue
        for j in range(1, H - 1):
            start = max(0, j - r + 1)
            work_j  = sum(x[e, j, p] for p in P)
            work_j1 = sum(x[e, j+1, p] for p in P)
            work_w  = sum(x[e, k, p] for k in range(start, j+1) for p in P)
            # if off on j and working on j+1, the preceding r days must all be off
            # r*(work_{j+1} - work_j) <= r - sum_{k=start}^{j} work_k
            model.add(r * work_j1 <= r - work_w + r * work_j)

    # C8: max weekends
    for e in E:
        emp = data.employees[e]
        for w in W:
            sat, sun = w*7+5, w*7+6
            if sat < H:
                for p in P:
                    model.add(t[e, w] >= x[e, sat, p])
            if sun < H:
                for p in P:
                    model.add(t[e, w] >= x[e, sun, p])
        model.add(sum(t[e, w] for w in W) <= emp.max_weekends)

    # C9: mandatory days off
    for e in E:
        for d in data.employees[e].days_off:
            for p in P:
                model.add(x[e, d, p] == 0)

    # C10: coverage
    for j in J:
        for p in P:
            cover_info = data.cover.get(j, {}).get(p)
            if cover_info:
                req, _, _ = cover_info
                assigned = sum(x[e, j, p] for e in E)
                model.add(assigned + y_minus[j, p] - y_plus[j, p] == req)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose
    solver.parameters.num_search_workers = 4

    status = solver.solve(model)
    status_str = solver.status_name(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, -1, status_str

    sol = {e: {j: None for j in J} for e in E}
    for e in E:
        for j in J:
            for p in P:
                if solver.value(x[e, j, p]) == 1:
                    sol[e][j] = p
                    break

    obj_val = int(round(solver.objective_value))
    return sol, obj_val, status_str


# DISPLAY UTILITIES

def print_schedule(data, sol):
    H = data.horizon
    print(f"{'':>6}", end="")
    for j in range(H):
        print(f" {['Mo','Tu','We','Th','Fr','Sa','Su'][j%7]:>3}", end="")
    print()
    for eid in data.employees:
        print(f"{eid:>6}", end="")
        for j in range(H):
            s = sol.get(eid, {}).get(j)
            print(f" {s if s else '-':>3}", end="")
        print()

def print_coverage(data, sol):
    H = data.horizon
    P = list(data.shifts.keys())
    print(f"\n{'Day':>4} {'DoW':>3}", end="")
    for p in P: print(f"  {p:>7}", end="")
    print()
    for j in range(H):
        print(f"{j:>4} {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][j%7]:>3}", end="")
        for p in P:
            asgn = sum(1 for e in data.employees if sol.get(e,{}).get(j)==p)
            req  = data.cover.get(j,{}).get(p,(0,))[0]
            print(f"  {asgn:>3}/{req:<3}", end="")
        print()


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "instances/Instance1.txt"
    use_mip = "--mip" in sys.argv
    tl = int(sys.argv[sys.argv.index("--tl")+1]) if "--tl" in sys.argv else 60

    print(f"Reading: {path}")
    data = read_instance(path)
    print(f"  {data.horizon}d | {len(data.employees)} employees | {len(data.shifts)} shifts")

    if use_mip:
        print(f"Solving with CP-SAT (time limit {tl}s)...")
        sol, obj, status = solve_with_cplex(data, time_limit=tl, verbose=True)
        if sol is None:
            print(f"No solution found. Status: {status}"); sys.exit(1)
        print(f"Status: {status} | Objective: {obj}")
    else:
        print("Building greedy schedule...")
        sol = build_schedule(data)
        obj = evaluate_solution(data, sol)
        print(f"Greedy penalty: {obj}")

    ok, viol = check_feasibility(data, sol)
    if ok:
        print("FEASIBLE")
    else:
        for v in viol: print(f"  VIOLATION: {v}")

    print_schedule(data, sol)
    print_coverage(data, sol)

    name = os.path.splitext(os.path.basename(path))[0]
    ros_instance = path.replace('.txt', '.ros')
    out_ros = f"{name}_solution.ros"
    save_ros(data, sol, out_ros, ros_instance)
    print(f"\nSaved: {out_ros}")
