from data_types import Phase, AvailabilityType
from specifics import student_input_path, professor_input_path, minimum_meetings_per_student, \
    LEAP_BREAKFAST_STUDENTS, group_meeting_professors

from specifics import log_error, log_warning
from students import read_students_from
from professors import read_professors_from


class Model:
    minimum_meetings = 6
    maximum_meetings = 10

    def __init__(self, students, professors):
        self.students_by_name = {
            student.full_name: student
            for student in students
        }
        self.professors_by_name = {
            professor.full_name: professor
            for professor in professors
        }

        for student in self.students():
            student.update_references(self)

        self.meetings = []
        self.office_hours = []

        self.missing_meetings = set()

        self.check_model()

    def students(self):
        return sorted(list(self.students_by_name.values()))

    def professors(self):
        return sorted(list(self.professors_by_name.values()))

    def add_office_hours(self, professor, time_interval):
        self.office_hours.append(time_interval)
        professor.add_office_hours(time_interval)

    def add_meeting(self, meeting):
        for same_slot_meeting in meeting.timeslot.meetings:
            if same_slot_meeting is not meeting:
                if meeting.professor.full_name not in group_meeting_professors:
                    assert meeting.professor != same_slot_meeting.professor, \
                        "Professor " + meeting.professor.full_name + " double-booked in meetings \n" + \
                        str(meeting) + "\n" + "and " + str(same_slot_meeting)
                assert meeting.student != same_slot_meeting.student, \
                    "Student " + meeting.student.full_name + " double-booked in meetings \n" + str(meeting) + "\n" + \
                    "and " + str(same_slot_meeting)

        meeting.student.add_meeting(meeting)
        meeting.professor.add_meeting(meeting)
        meeting.timeslot.add_meeting(meeting)
        self.meetings.append(meeting)

    def check_model(self):
        for name in LEAP_BREAKFAST_STUDENTS:
            assert name in self.students_by_name, name

    def check_schedule(self):
        for meeting in self.meetings:
            student = meeting.student
            professor = meeting.professor
            timeslot = meeting.timeslot
            if not student.offering_at(timeslot):
                log_error("Student " + student.full_name +
                          " not available at their scheduled timeslot " +
                          str(timeslot))
            if (not professor.offering_at(timeslot)
            ) and meeting.phase != Phase.STUDENT_AVAILABILITY:
                log_error("Faculty member " + professor.full_name +
                          " not available at their scheduled timeslot " +
                          str(timeslot))

            if student.primary_advocate is None or professor != student.primary_advocate:
                if professor not in student.other_advocates:
                    if professor not in student.preferred_professors:
                        if {student.primary_area, student.secondary_area}.isdisjoint(
                                {professor.primary_area, professor.secondary_area}):
                            log_error(f"Areas of student {student} and professor {professor} don't overlap")

        for student in self.students():
            if student.num_meetings() < minimum_meetings_per_student:
                log_warning("Only " + str(student.num_meetings()) + "/" +
                            str(self.minimum_meetings) +
                            " meetings for student " + student.full_name)

        for student in self.students():
            for i, professor in enumerate(student.preferred_professors[:2]):
                if not professor.is_meeting_student(student) and \
                        (not professor.has_office_hours() or not student.is_available(professor.office_hours[0])):
                    print(f"""Did not schedule requested meeting between {student.full_name} 
                    and top {i + 1} choice {professor.full_name}""")
                    self.missing_meetings.add((student, professor))
            if student.primary_advocate is not None and not student.primary_advocate.is_meeting_student(student):
                print(f"""Did not schedule requested meeting between {student.full_name} 
                and advocate {student.primary_advocate.full_name}""")
                self.missing_meetings.add((student, student.primary_advocate))
            for p in student.other_advocates:
                if not p.is_meeting_student(student):
                    print(f"""Did not schedule requested meeting between {student.full_name} 
                           and secondary advocate {p.full_name}""")

    def get_student(self, student):
        return self.students_by_name[student.full_name]

    def get_professor(self, professor):
        return self.professors_by_name[professor.full_name]

    def feasible(self, s, p, t):
        if not s.offering_at(t):
            return False
        if not p.offering_at(t):
            return False
        # Consider something like this?
        # else:
        #     if p.wants_longer_meetings:
        #         if t.duration == 15:
        #             return False
        #     else:
        #         if t.duration == 35:
        #             return False
        return True

    def office_hours_value(self, p, o):
        if p.mode_at(o) == AvailabilityType.ITHACA and o.start.day_number() in [0, 1]:
            return 200
        elif p.mode_at(o) == AvailabilityType.CORNELL_TECH and o.start.day_number == 2:
            return 200
        else:
            return 150

    # This is a good function to play with to tweak the results.
    def value(self, professor, student, timeslot):
        if student.primary_advocate is not None and professor == student.primary_advocate:
            if timeslot.duration == 35:
                value = 250
            else:
                value = 150
        elif professor in student.other_advocates:
            if timeslot.duration == 35:
                value = 240
            else:
                value = 130
        elif professor in student.preferred_professors:
            rank = student.preferred_professors.index(professor)
            value = 100 - 10 * rank
        elif professor.primary_area == student.primary_area:
            value = 30
        elif student.secondary_area is not None and student.secondary_area in [professor.secondary_area,
                                                                               professor.primary_area] or \
                professor.secondary_area is not None and professor.secondary_area == student.primary_area:
            value = 20
        else:
            value = -1000
        if professor.would_meeting_be_virtual(student, timeslot) \
                and student.modes_offered[timeslot.start.day_number()] != AvailabilityType.ONLY_ZOOM:
            value = value - value // 4
        return value

    def faculty_names(self):
        return [faculty.name() for faculty in self.professors()]


if __name__ == "__main__":
    students = read_students_from(student_input_path)
    faculty = read_professors_from(professor_input_path)
    m = Model(students, faculty)

