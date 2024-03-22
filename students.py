import csv
from pprint import pprint

from data_types import Person, TimeInterval, AvailabilityType, AbsoluteTime
from data_types import ResearchArea
from specifics import StudentDataKeys as sdk, EARLY_DEPARTURES, MONDAY_MEETING_TIMES, \
    TUESDAY_MEETING_TIMES, WEDNESDAY_MEETING_TIMES, too_late_intervals, student_input_path, \
    LEAP_BREAKFAST_STUDENTS


def read_students_from(filename):
    students = []
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        raw_student_rows = []
        for row in reader:
            each = {key: row[key].strip() for key in row}
            if each[sdk.FIRST_NAME.value] != "":
                raw_student_rows.append(each)

    for i, row in enumerate(raw_student_rows):
        if row[sdk.FIRST_NAME.value] == "Samuel":
            pass
        students.append(Student.make_student_from_raw(row))

    return students


class Student(Person):
    def __init__(self,
                 full_name,
                 primary_area,
                 secondary_area,
                 times_offered,
                 times_excluded,
                 modes_offered,
                 email_address,
                 nickname,
                 offset_from_est,
                 primary_advocate,
                 other_advocates,
                 preferred_professors):
        super().__init__(full_name, primary_area, secondary_area, times_offered, times_excluded, modes_offered, email_address)

        self.nickname = nickname
        self.primary_advocate = primary_advocate
        self.other_advocates = other_advocates
        self.email_address = email_address
        self.offset_from_est = offset_from_est
        self.preferred_professors = preferred_professors
        self.requested_not_attending = []


    def num_meetings(self):
        return len(self.meetings)

    def faculty_meeting_with(self):
        return [meeting.professors for meeting in self.meetings]

    def timeslots_meeting_with_faculty(self):
        return [meeting.timeslot for meeting in self.meetings]

    def is_meeting_professor(self, faculty):
        return faculty in self.faculty_meeting_with()

    @staticmethod
    def make_student_from_raw(raw_dictionary):
        needs_one_off = False
        full_name = raw_dictionary[sdk.FIRST_NAME.value] + " " + raw_dictionary[sdk.LAST_NAME.value]
        nickname = raw_dictionary[sdk.NICKNAME.value]
        if nickname.strip() == "":
            nickname = None

        research_areas_raw = raw_dictionary[sdk.AREAS.value].split(",")
        research_areas = [ResearchArea(raw.strip().upper()) for raw in research_areas_raw]
        primary_area = research_areas[0]
        secondary_area = None if len(research_areas) == 1 else research_areas[1]

        primary_advocate = raw_dictionary[sdk.PRIMARY_ADVOCATE.value].strip()

        # other_advocates = [raw_dictionary[key].strip() for key in [
        #     sdk.ADVOCATE2.value, sdk.ADVOCATE3.value, sdk.ADVOCATE4.value
        #         ]
        #         if raw_dictionary[key].strip() != ""
        # ]
        other_advocates = [raw_dictionary[key].strip() for key in [sdk.ADVOCATE2.value]
                if raw_dictionary[key].strip() != ""
        ]

        email_address = raw_dictionary[sdk.EMAIL.value]

        offset_from_est = raw_dictionary[sdk.TIME_ZONE.value].strip()
        if offset_from_est == "":
            offset_from_est = None
        else:
            offset_from_est = int(float(offset_from_est) * 60)

        monday_mode = AvailabilityType(raw_dictionary[sdk.MONDAY_TYPE.value])
        tuesday_mode = AvailabilityType(raw_dictionary[sdk.TUESDAY_TYPE.value])
        wednesday_mode = AvailabilityType(raw_dictionary[sdk.WEDNESDAY_TYPE.value])
        modes_offered = {
            0: monday_mode,
            1: tuesday_mode,
            2: wednesday_mode,
        }

        times_offered = []
        if monday_mode != AvailabilityType.NOT_AVAILABLE:
            times_offered += MONDAY_MEETING_TIMES
        if tuesday_mode != AvailabilityType.NOT_AVAILABLE:
            times_offered += TUESDAY_MEETING_TIMES
        if wednesday_mode != AvailabilityType.NOT_AVAILABLE:
            times_offered += WEDNESDAY_MEETING_TIMES

        times_excluded = []
        times_excluded = too_late_intervals(offset_from_est)

        # One-off for folks leaving early
        if full_name in EARLY_DEPARTURES.keys():
            large_number = 1e6
            times_excluded.append(TimeInterval(EARLY_DEPARTURES[full_name], large_number))

        # One-off for students that should be free during the LEAP Breakfast
        if full_name in LEAP_BREAKFAST_STUDENTS:
            times_excluded.append(TimeInterval(AbsoluteTime.fromDaysHoursMinutes(1, 9, 0), 60))

        # Don't schedule afternoon meetings on Tuesday for students who will be in CTech on Wednesday
        if tuesday_mode == AvailabilityType.ITHACA and wednesday_mode == AvailabilityType.CORNELL_TECH:
            times_excluded.append(TimeInterval(AbsoluteTime.fromDaysHoursMinutes(1, 12, 0), 12*60))

        preferred_professors = []
        for key in [
            sdk.PREFERENCE1,
            sdk.PREFERENCE2,
            sdk.PREFERENCE3,
            sdk.PREFERENCE4,
            sdk.PREFERENCE5,
            sdk.PREFERENCE6,
            # sdk.PREFERENCE7,
            # sdk.PREFERENCE8,
        ]:
            preference = raw_dictionary[key.value].strip()
            if preference != "":
                preferred_professors.append(preference)
        #additional faculity
        # for key in sdk.ADDITIONAL_FACULTY:
        #     preference = raw_dictionary[key.value].strip()
        #     if preference != "":
        #         preference.split(",")
        #         preferred_professors.append(preference)
        return Student(full_name,
                       primary_area,
                       secondary_area,
                       times_offered,
                       times_excluded,
                       modes_offered,
                       email_address,
                       nickname,
                       offset_from_est,
                       primary_advocate,
                       other_advocates,
                       preferred_professors)

    def update_references(self, model):
        preferred_and_available = []
        for professor_name in self.preferred_professors:
            if professor_name in model.professors_by_name:
                preferred_and_available.append(model.professors_by_name[professor_name])
            else:
                print(f"Professor {professor_name} was requested but doesn't seem to be attending.")
                self.requested_not_attending.append(professor_name)

        secondary_advocates = []
        for professor_name in self.other_advocates:
            if professor_name in model.professors_by_name:
                secondary_advocates.append(model.professors_by_name[professor_name])
            else:
                print(f"Professor {professor_name} a secondary advocate but doesn't seem to be attending.")
        self.other_advocates = secondary_advocates

        self.preferred_professors = preferred_and_available
        if self.primary_advocate in model.professors_by_name:
            self.primary_advocate = model.professors_by_name[self.primary_advocate]
        else:
            # print(f"Advocate {self.advocate} was requested but doesn't seem to be attending.")
            self.primary_advocate = None

    def __str__(self):
        return "Student " + self.full_name

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return self.full_name < other.full_name

    def __eq__(self, other):
        return self.full_name == other.full_name

    def __hash__(self):
        return hash(self.full_name)


if __name__ == "__main__":
    students = read_students_from(student_input_path)
    pprint(students)
    print(f"Read {len(students)} students.")


