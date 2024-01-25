import csv
import itertools
import os
import shutil
from time import time, ctime

from icalendar import Calendar
from mip import Model as MIPModel, xsum, maximize, BINARY
from tqdm import tqdm

from data_types import Meeting, Phase, TimeSlot, AbsoluteTime, Day, AvailabilityType, Event
from model import Model
from students import read_students_from
from professors import read_professors_from
from specifics import FIFTEEN_MINUTE_SLOTS, THIRTY_FIVE_MINUTE_SLOTS, OFFICE_HOURS_SLOTS, MAIN_EVENTS, \
    group_meeting_professors, output_path
from specifics import input_path, student_input_path, professor_input_path
from specifics import meetings_to_keep_path, meetings_no_need_to_keep_path
from specifics import minimum_meetings_per_student, maximum_meetings_per_professor, maximum_meetings_per_student


### Read inputs and initialize model. ###
students = read_students_from(student_input_path)
faculty = read_professors_from(professor_input_path)
model = Model(students, faculty)


### Force the model to retain meetings stored in meetings_to_keep_path ###
# except those at meetings_no_need_to_keep_path
# Useful for fine-tuning (retain most meetings from a previous run).
def read_meetings(path):
    meetings = []
    with open(path,
              'r', encoding="utf-8-sig") as meetings_file:
        reader = csv.DictReader(meetings_file)
        for row in reader:
            student_name = row["Student"]
            faculty_name = row["Professor"]
            start_minutes = int(row["Start"])
            duration = int(row["Duration"])
            if student_name not in model.students_by_name:
                print(student_name)
                continue
            if faculty_name not in model.professors_by_name:
                print(faculty_name)
                continue
            s = model.students_by_name[student_name]
            p = model.professors_by_name[faculty_name]
            meetings.append(Meeting(TimeSlot(AbsoluteTime(start_minutes), duration),
                                            s, p, Phase.SOLVER))
    return meetings


meetings_to_keep = read_meetings(meetings_to_keep_path)
meetings_no_need_to_keep = read_meetings(meetings_no_need_to_keep_path)
sticky_meetings = [m for m in meetings_to_keep if m not in meetings_no_need_to_keep]


### Initialize the solver ###
solver = MIPModel("solver")
solver.seed = 0
meeting_slots = FIFTEEN_MINUTE_SLOTS + THIRTY_FIVE_MINUTE_SLOTS

all_triples = [(s, p, t) for s in model.students() for p in model.professors() for t in meeting_slots]
viable_triples = set((s, p, t) for (s, p, t) in all_triples if s.offering_at(t) and p.offering_at(t))

# Add variables to the solver
meeting_variables = {(s, p, t): solver.add_var(var_type=BINARY, name=str((s, p, t)))
                     for (s, p, t) in all_triples}

office_hours_variables = {(p, t): solver.add_var(var_type=BINARY, name=str((p, t)))
                          for p in model.professors()
                          for t in OFFICE_HOURS_SLOTS}

# Add an objective to the solver
solver.objective = maximize(xsum([
    model.value(p, s, t) * meeting_variables[s, p, t]
    for p in model.professors()
    for s in model.students()
    for t in meeting_slots if s.offering_at(t) and p.offering_at(t)
])
                            + xsum([model.office_hours_value(p, o) * office_hours_variables[p, o]
                                    for p in model.professors() for o in OFFICE_HOURS_SLOTS if p.offering_at(o)]))

# Add constraints to the solver

for (s, p, t) in all_triples:  # This is a bit of a hack, but it should be optimized away.
    if not model.feasible(s, p, t):  # This gives you a way to programmatically add no-go conditions
        solver += meeting_variables[s, p, t] == 0
    elif Meeting(t, s, p, None) in sticky_meetings:
        solver += meeting_variables[s, p, t] == 1

# Any given student and professor can meet at most once.
for s in model.students():
    for p in model.professors():
        solver += xsum(meeting_variables[s, p, t] for t in meeting_slots) <= 1

# No professor can meet more than 1 student in any timeslot (except Kilian)
for p in model.professors():
    for t in meeting_slots:
        max_students_per_meeting = 1
        if p.full_name in group_meeting_professors:
            max_students_per_meeting = 3
        solver += xsum(meeting_variables[s, p, t] for s in model.students()
                       if s.offering_at(t) and p.offering_at(t)) <= max_students_per_meeting

# No student can meet more than 1 professor in any timeslot
for s in model.students():
    for t in meeting_slots:
        solver += xsum(meeting_variables[s, p, t] for p in model.professors()) <= 1

# Each student must meet at least x and at most y professors.
for s in model.students():
    solver += xsum(meeting_variables[s, p, t] for p in model.professors()
                   for t in meeting_slots if s.offering_at(t) and p.offering_at(t)) >= minimum_meetings_per_student

    solver += xsum(meeting_variables[s, p, t] for p in model.professors()
                   for t in meeting_slots if s.offering_at(t) and p.offering_at(t)) <= maximum_meetings_per_student

# No professor can meet more than z students.
for p in model.professors():
    maximum = maximum_meetings_per_professor
    solver += xsum(meeting_variables[s, p, t] for s in model.students()
                   for t in meeting_slots) <= maximum

adjacent_timeslot_pairs = [(t1, t2) for (t1, t2) in itertools.combinations(meeting_slots, 2)
                           if t1.distance(t2) < 10]
for s in tqdm(model.students()):
    for p1, p2 in itertools.combinations(model.professors(), 2):
        for t1, t2 in adjacent_timeslot_pairs:
            if (s, p1, t1) in viable_triples and (s, p2, t1) in viable_triples:
                if (not p1.would_meeting_be_virtual(s, t1)) and (not p2.would_meeting_be_virtual(s, t2)):
                    if p1.building != p2.building:
                        solver += meeting_variables[s, p1, t1] + meeting_variables[s, p2, t2] <= 1

overlapping_meeting_slots = [(t1, t2) for t1, t2 in itertools.combinations(meeting_slots, 2)
                             if t1.conflicts(t2)]

for s in tqdm(model.students()):
    for p1 in model.professors():
        for t1, t2 in overlapping_meeting_slots:
            solver += meeting_variables[s, p1, t1] + xsum(meeting_variables[s, p2, t2]
                                                          for p2 in model.professors() if p2 != p1) <= 1

for p in tqdm(model.professors()):
    for s1 in model.students():
        for t1, t2 in overlapping_meeting_slots:
            solver += meeting_variables[s1, p, t1] + xsum(meeting_variables[s2, p, t2]
                                                          for s2 in model.students() if s2 != s1) <= 1

# No professor can have more than 1 office hour.
for p in model.professors():
    solver += xsum([office_hours_variables[p, t] for t in OFFICE_HOURS_SLOTS]) <= 1

# No professor can have both an office hours and a meeting that conflicts with it.
for o in OFFICE_HOURS_SLOTS:
    for t in meeting_slots:
        if t.conflicts(o):
            for p in model.professors():
                for s in model.students():
                    solver += office_hours_variables[p, o] + meeting_variables[s, p, t] <= 1


### Run the solver! ###
solver.optimize()
print(len(model.students()) * len(model.professors()))
print(len(model.students()) * len(meeting_slots))
print(len(model.professors()) * len(meeting_slots))
print(len([(p, t) for p in model.professors() for t in meeting_slots if p.offering_at(t)]))


### Add the resulting meetings and office hours to our model. ###
for (s, p, t) in viable_triples:
    if meeting_variables[s, p, t].x == 1:
        model.add_meeting(Meeting(t, s, p, Phase.SOLVER))

for p in model.professors():
    for o in OFFICE_HOURS_SLOTS:
        if office_hours_variables[p, o].x == 1:
            model.add_office_hours(p, o)

# Add more sanity checks here if desired.
model.check_schedule()


### OUTPUT SCHEDULES in lots of different forms ###
def location(meeting):
    if meeting.is_virtual:
        result = "Zoom"
    else:
        result = meeting.professor.office
    if result.strip() == "":
        result = "TBA"
    return result


def student_location(meeting):
    if meeting.is_virtual:
        result = f"on Zoom ({meeting.professor.zoom_link})"
    else:
        result = f"in {meeting.professor.office}"
    if result.strip() == "":
        result = "TBA"
    return result


def office_hours_location(professor, student):
    oh = professor.office_hours[0]
    if student.modes_offered[oh.start.day().value] == AvailabilityType.ONLY_ZOOM \
            or professor.modes_offered[oh.start.day().value] == AvailabilityType.ONLY_ZOOM:
        return f"on Zoom ({professor.zoom_link})"
    else:
        return f"in {professor.office}"


os.makedirs(output_path, exist_ok=True)
output_folder_path = output_path + f"{ctime(time())}/"
os.mkdir(output_folder_path)

with open(output_folder_path + f"all_meetings.csv", "w") as f:
    f.write(f"Student,Professor,Start,Duration\n")
    for meeting in sorted(model.meetings, key=lambda m: (m.start, m.student.full_name)):
        f.write(
            f"{meeting.student.full_name},{meeting.professor.full_name},{meeting.timeslot.start.minutes},{meeting.timeslot.duration}\n")

with open(output_folder_path + "meetings-by-student.txt", "w") as f:
    for student in model.students():
        for meeting in sorted(student.meetings, key=lambda m: m.timeslot.start):
            f.write(f"{meeting.student.full_name},{meeting.professor},{meeting.timeslot},{location(meeting)}\n")

with open(output_folder_path + "meetings-by-faculty.txt", "w") as f:
    for professor in model.professors():
        for meeting in sorted(professor.meetings, key=lambda m: m.timeslot.start):
            f.write(f"{meeting.professor},{meeting.student.full_name},{meeting.timeslot},{location(meeting)}\n")

with open(output_folder_path + "meetings-and-OH-by-faculty.txt", "w") as f:
    for professor in model.professors():
        for meeting in sorted(professor.meetings, key=lambda m: m.timeslot.start):
            f.write(f"{meeting.professor},{meeting.student.full_name},{meeting.timeslot},{location(meeting)}\n")

        if professor.has_office_hours():
            f.write(f"{professor},Office Hours: {professor.office_hours[0]}\n")
        else:
            f.write(f"No Office Hours scheduled for {professor}\n")

os.mkdir(output_folder_path + "faculty_schedules/")
for professor in model.professors():
    with open(output_folder_path + f"faculty_schedules/{professor.full_name}.txt", "w") as f:
        for meeting in sorted(professor.meetings, key=lambda m: m.timeslot.start):
            f.write(f"{meeting.professor},{meeting.student.full_name},{meeting.timeslot},{location(meeting)}\n")
        if professor.has_office_hours():
            f.write(f"\n{professor},Office Hours: {professor.office_hours[0]}\n")
        else:
            f.write(f"No Office Hours scheduled for {professor}\n")

os.mkdir(output_folder_path + "faculty_calendars/")
for professor in model.professors():
    with open(output_folder_path + f"faculty_calendars/{professor.full_name}.ics", "wb") as f:
        f.write(professor.ical_string())

with open(output_folder_path + "office_hours.txt", "w") as f:
    for professor in model.professors():
        if professor.has_office_hours():
            f.write(f"{professor},Office Hours: {professor.office_hours[0]}\n")
        else:
            f.write(f"No Office Hours scheduled for {professor}\n")

with open(output_folder_path + "visiting-students.txt", "w") as f:
    for s in model.students():
        f.write(f"{s.full_name},{s.email_address}\n")

with open(output_folder_path + "zoom-links.txt", "w") as f:
    for p in model.professors():
        f.write(
            f"{p.full_name},{p.zoom_link if p.zoom_link is not None and p.zoom_link.strip() != '' else 'Not available on Zoom.'}\n")

os.mkdir(output_folder_path + "student_schedules/")
os.mkdir(output_folder_path + "student_calendars/")
for student in model.students():
    suggested = []
    with open(output_folder_path + f"student_schedules/{student.full_name}.txt", "w") as f:
        for day in Day:
            mode = student.modes_offered[day.value]
            if mode == AvailabilityType.ONLY_ZOOM:
                f.write(f"Visiting virtually on {day.name()}.\n")
            elif mode in [AvailabilityType.ITHACA, AvailabilityType.CORNELL_TECH]:
                f.write(f"Visiting campus on {day.name()}.\n")
        f.write("\n")
        for meeting in sorted(student.meetings, key=lambda m: m.timeslot.start):
            f.write(
                f"Meeting with {meeting.professor} on {meeting.timeslot.start.day().name()} {meeting.timeslot.start}-{meeting.timeslot.end()} {student_location(meeting)}\n")
        f.write("\n")

        # Note: this code suggests office hours to attend for each student.
        # It is pretty gross and procedural but gets the job done.
        total = len(student.meetings)
        for professor in student.preferred_professors:
            if professor not in [m.professor for m in student.meetings] and all(
                    oh.disjoint(p.office_hours[0]) for p in suggested):
                if professor.has_office_hours():
                    oh = professor.office_hours[0]
                    if all(oh.disjoint(m) for m in student.meetings):
                        if student.offering_at(oh):
                            suggested.append(professor)
                            total += 1
        area_profs = list(student.primary_area.professors)
        if student.secondary_area:
            area_profs += list(student.secondary_area.professors)
        while total < 6 and len(area_profs) > 0:
            professor = area_profs[0]
            del area_profs[0]
            if professor not in [m.professor for m in student.meetings] + suggested:
                if professor.has_office_hours():
                    oh = professor.office_hours[0]
                    if all(oh.disjoint(m) for m in student.meetings) and all(
                            oh.disjoint(p.office_hours[0]) for p in suggested):
                        if student.offering_at(oh):
                            suggested.append(professor)
                            total += 1
        for p in sorted(suggested, key=lambda p: p.office_hours[0].start):
            f.write(
                f"Suggested: attend {p.full_name}'s office hours {p.office_hours[0]} {office_hours_location(p, student)}.\n")

    with open(output_folder_path + f"student_calendars/{student.full_name}.ics", "wb") as f:
        cal = Calendar()
        cal.add("summary", "Cornell Visit Day 1:1s")
        for meeting in student.meetings:
            component = meeting.as_ical_component("Meeting with " +
                                                  meeting.professor.full_name)
            cal.add_component(component)

        for p in suggested:
            oh = p.office_hours[0]
            location = office_hours_location(p, student)
            office_hours = Event(oh.start, oh.duration, "", location, None)
            component = office_hours.as_ical_component(f"{p}'s Office Hours")
            cal.add_component(component)

        f.write(cal.to_ical())

with open(output_folder_path + "event_calendar.ics", "wb") as f:
    cal = Calendar()
    cal.add("summary", "Cornell Visit Day Events")
    for event in MAIN_EVENTS:
        component = event.as_ical_component(None)
        cal.add_component(component)

    f.write(cal.to_ical())

with open(output_folder_path + "office_hours_for_students.txt", "w") as f:
    oh_ps = [p for p in model.professors() if p.has_office_hours()]
    for p in sorted(oh_ps, key=lambda p: p.office_hours[0].start):
        oh = p.office_hours[0]
        if p.modes_offered[oh.start.day().value] != AvailabilityType.ONLY_ZOOM:
            location_string = f"{p.office} OR {p.zoom_link}"
        else:
            location_string = f"{p.zoom_link}"
        f.write(f"{p}: Office Hours {oh}, {location_string}\n")

shutil.copytree(input_path, output_folder_path + "input_that_produced_this_output")