from nurse_rostering import read_instance, solve_with_cplex
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from xml.dom import minidom

data = read_instance('instances/Instance1.txt')
sol, obj, status = solve_with_cplex(data, time_limit=60, verbose=False)

sd = date.fromisoformat('2014-01-06')
ed = sd + timedelta(days=data.horizon - 1)

root = ET.Element('SchedulingPeriod')
root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
root.set('xsi:noNamespaceSchemaLocation', 'SchedulingPeriod-3.0.xsd')

ET.SubElement(root, 'StartDate').text = str(sd)
ET.SubElement(root, 'EndDate').text = str(ed)

st_el = ET.SubElement(root, 'ShiftTypes')
colors = ['Chartreuse', 'CornflowerBlue', 'LightSalmon', 'Plum']
for i, (sid, s) in enumerate(data.shifts.items()):
    sh = ET.SubElement(st_el, 'Shift')
    sh.set('ID', sid)
    ET.SubElement(sh, 'Color').text = colors[i % len(colors)]
    ET.SubElement(sh, 'StartTime').text = '9:0'
    ET.SubElement(sh, 'Duration').text = str(s.duration)

emps_el = ET.SubElement(root, 'Employees')
for eid in data.employees:
    e = ET.SubElement(emps_el, 'Employee')
    e.set('ID', eid)
    ET.SubElement(e, 'Name').text = eid

fa_el = ET.SubElement(root, 'FixedAssignments')
for eid in data.employees:
    emp_el = ET.SubElement(fa_el, 'Employee')
    emp_el.set('ID', eid)
    for j in range(data.horizon):
        shift = sol.get(eid, {}).get(j)
        asgn = ET.SubElement(emp_el, 'Assign')
        ET.SubElement(asgn, 'Day').text = str(sd + timedelta(days=j))
        ET.SubElement(asgn, 'Shift').text = shift if shift else '-'

rough = ET.tostring(root, encoding='unicode')
pretty = minidom.parseString(rough).toprettyxml(indent='    ', encoding='UTF-8')
with open('results/Instance1_viewer.ros', 'wb') as f:
    f.write(pretty)
print('Done - open results/Instance1_viewer.ros in the tool')