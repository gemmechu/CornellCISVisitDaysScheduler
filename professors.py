import csv
from icalendar import Calendar
from pprint import pprint

from specifics import parse_times, ProfessorDataKeys as pdk, professor_input_path
from data_types import Person, ResearchArea, AvailabilityType, Event


def read_professors_from(filename):
    professors = []
    with open(filename, 'r', encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_faculty_rows = []
        for row in reader:
            each = {key: row[key].strip() for key in row}
            raw_faculty_rows.append(each)

    for row in raw_faculty_rows:
        professors.append(Professor.make_professors_from_raw(row))

    return professors


class Professor(Person):
    def __init__(
        self,
        full_name,
        primary_area,
        secondary_area,
        email_address,
        zoom_link,
        office,
        modes_offered,
        times_offered,
        wants_longer_meetings,
        building,
    ):
        super().__init__(full_name, primary_area, secondary_area, times_offered, [], modes_offered, email_address)
        self.zoom_link = zoom_link
        self.office = office
        self.wants_longer_meetings = wants_longer_meetings
        self.office_hours = []
        self.building = building

        primary_area.professors.append(self)
        if secondary_area:  secondary_area.professors.append(self)

    def would_meeting_be_virtual(self, student, timeslot):
        self_type = self.modes_offered[timeslot.start.day_number()]
        student_type = student.modes_offered[timeslot.start.day_number()]
        assert self_type != AvailabilityType.NOT_AVAILABLE
        assert student_type != AvailabilityType.NOT_AVAILABLE
        return self_type == AvailabilityType.ONLY_ZOOM \
                or student_type == AvailabilityType.ONLY_ZOOM \
                or self_type != student_type

    def students_meeting_with(self):
        return [meeting.student for meeting in self.meetings]

    def is_meeting_student(self, student):
        return student in self.students_meeting_with()

    def timeslots_meeting_with_students(self):
        return [meeting.timeslot for meeting in self.meetings]

    def in_gates(self):
        return "gates" in self.office.lower()

    def in_rhodes(self):
        return "rhodes" in self.office.lower()

    def not_near_gates(self):
        return (not self.in_gates()) and (not self.in_rhodes())

    @staticmethod
    def make_professors_from_raw(raw_dictionary):
        full_name = raw_dictionary[pdk.NAME.value]
        primary_area = ResearchArea(raw_dictionary[pdk.AREA1.value])
        raw = raw_dictionary[pdk.AREA2.value].strip()
        secondary_area = None if len(raw) == 0 else ResearchArea(raw)
        email_address = raw_dictionary[pdk.EMAIL.value]
        monday_availability_type = AvailabilityType(raw_dictionary[pdk.MONDAY_TYPE.value])
        tuesday_availability_type = AvailabilityType(raw_dictionary[pdk.TUESDAY_TYPE.value])
        wednesday_availability_type = AvailabilityType(raw_dictionary[pdk.WEDNESDAY_TYPE.value])
        intervals_available = parse_times(0, raw_dictionary[pdk.MONDAY_TIMES.value]) + \
                              parse_times(1, raw_dictionary[pdk.TUESDAY_TIMES.value]) + \
                              parse_times(2, raw_dictionary[pdk.WEDNESDAY_TIMES.value])

        building = raw_dictionary[pdk.BUILDING.value].strip().lower()

        zoom_link = raw_dictionary[pdk.ZOOM_LINK.value].strip()
        office = raw_dictionary[pdk.OFFICE.value].strip()

        wants_longer_meetings = raw_dictionary[pdk.LONGER_MEETINGS.value].strip() == "1"

        return Professor(full_name=full_name,
                         primary_area=primary_area,
                         secondary_area=secondary_area,
                         email_address=email_address,
                         zoom_link=zoom_link,
                         office=office,
                         modes_offered={
                                 0: monday_availability_type,
                                 1: tuesday_availability_type,
                                 2: wednesday_availability_type
                             },
                         times_offered=intervals_available,
                         wants_longer_meetings=wants_longer_meetings,
                         building=building)

    def ical_string(self):
        cal = Calendar()
        cal.add("summary", "Visit Day 1:1s")
        for meeting in self.meetings:
            component = meeting.as_ical_component("Meeting with " +
                                                  meeting.student.full_name)
            cal.add_component(component)
        if self.has_office_hours():
            oh = self.office_hours[0]
            if self.office is None:
                location = self.zoom_link
            elif self.zoom_link is None:
                location = self.office
            else:
                location = self.office + " AND " + self.zoom_link
            office_hours = Event(oh.start, oh.duration, "", location, None)
            component = office_hours.as_ical_component("Office Hours")
            cal.add_component(component)

        return cal.to_ical()

    def name(self):
        return self.full_name

    def __repr__(self):
        return self.name()

    def __lt__(self, other):
        return self.name() < other.name()

    def __eq__(self, other):
        return self.name() == other.name()

    def __hash__(self):
        return hash(self.name())

    def add_office_hours(self, time_interval):
        self.office_hours.append(time_interval)

    def has_office_hours(self):
        return len(self.office_hours) > 0


if __name__ == "__main__":
    professors = read_professors_from(professor_input_path)
    print(f"Read data for {len(professors)} professors.")
    pprint(professors)
