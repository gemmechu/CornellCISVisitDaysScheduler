from enum import Enum
import datetime
import functools
from icalendar import Event as CalEvent
import pytz
ET = pytz.timezone('US/Eastern')

MONTH = 3
YEAR = 2023

class Day(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2

    def name(self):
        names = {
            Day.MONDAY: "Monday",
            Day.TUESDAY: "Tuesday",
            Day.WEDNESDAY: "Wednesday",
        }
        return names[self]

    def date(self):
        dates = {
            Day.MONDAY: 27,
            Day.TUESDAY: 28,
            Day.WEDNESDAY: 29,
        }
        return dates[self]

@functools.total_ordering
class AbsoluteTime:

    MINUTES_PER_HOUR = 60
    HOURS_PER_DAY = 24
    MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY

    # 0 is Monday at midnight EST
    def __init__(self, minutes):
        self.minutes = minutes

    @staticmethod
    def fromDaysHoursMinutes(days, hours, minutes):
        return AbsoluteTime(days * AbsoluteTime.MINUTES_PER_DAY + hours * AbsoluteTime.MINUTES_PER_HOUR + minutes)

    def day_number(self):
        return self.minutes // AbsoluteTime.MINUTES_PER_DAY

    def day(self):
        return Day(self.day_number())

    def hour(self):
        return (self.minutes - self.day_number() * AbsoluteTime.MINUTES_PER_DAY) // AbsoluteTime.MINUTES_PER_HOUR

    def minute(self):
        return (self.minutes -
                self.day_number() * AbsoluteTime.MINUTES_PER_DAY -
                self.hour() * AbsoluteTime.MINUTES_PER_HOUR)

    def minutes_string(self):
        minutes_string = str(self.minute())
        if self.minute() < 10:
            minutes_string = "0" + minutes_string
        return minutes_string

    def __str__(self):
        return str(self.hour()) + ":" + self.minutes_string()

    def __lt__(self, other):
        return self.minutes < other.minutes

    def __eq__(self, other):
        return self.minutes == other.minutes

    def __add__(self, minutes):
        return AbsoluteTime(self.minutes + minutes)

    def __sub__(self, time):
        return self.minutes - time.minutes

    def __hash__(self):
        return hash(self.minutes)


class TimeInterval:

    def __init__(self, start, duration):
        self.start = start
        self.duration = duration

    def end(self):
        return self.start + self.duration

    def __contains__(self, anotherInterval):
        return anotherInterval.start >= self.start and anotherInterval.end() <= self.end()

    def __repr__(self):
        return f"{self.start.day().name()}-{self.start}-{self.end()}"

    def __eq__(self, other):
        return self.start == other.start and self.duration == other.duration

    def __hash__(self):
        return hash(self.start)*37 + hash(self.duration)

    def disjoint(self, other):
        return self.start >= other.end() or other.start >= self.end()

    def conflicts(self, other):
        return not self.disjoint(other)

    def distance(self, other):
        if self.conflicts(other):
            return 0
        else:
            return min(abs(self.start - other.end()), abs(self.end() - other.start))


class TimeSlot(TimeInterval):

    def __init__(self, start, duration):
        super().__init__(start, duration)
        self.meetings = set()

    def add_meeting(self, meeting):
        self.meetings.add(meeting)


class Event(TimeInterval):
    def __init__(self,
                 start,
                 duration,
                 description,
                 location_string,
                 zoom_link):
        super().__init__(start, duration)
        self.description = description
        self.location_string = location_string
        self.zoom_link = zoom_link

    def as_ical_component(self, description=None):
        start_time = ET.localize(
            datetime.datetime(YEAR, MONTH,
                              self.start.day().date(), self.start.hour(),
                              self.start.minute()))

        end_time = ET.localize(
            datetime.datetime(YEAR, MONTH,
                              self.end().day().date(), self.end().hour(),
                              self.end().minute()))

        event = CalEvent()
        summary = description if description is not None else self.description
        event.add("summary", summary)
        event.add("dtstart", start_time)
        event.add("dtend", end_time)
        event.add("location",
                  self.location_string + "\n" if self.location_string else "" + \
                  self.zoom_link if self.zoom_link else "TBA")

        return event

    def has_virtual(self):
        return self.zoom_link is not None

    def has_in_person(self):
        return self.location_string is not None



class Meeting(Event):
    def __init__(self, timeslot, student, professor, phase):
        self.phase = phase
        self.student = student
        self.professor = professor
        self.is_virtual = professor.would_meeting_be_virtual(student, timeslot)
        self.timeslot = timeslot
        description = f"{student.full_name}<>{professor.full_name}"
        location_string = None if self.is_virtual else professor.office
        zoom_link = None if not self.is_virtual else professor.zoom_link

        super().__init__(timeslot.start, timeslot.duration, description, location_string, zoom_link)

    def location(self):
        if self.is_virtual:
            return self.zoom_link
        else:
            return self.professor.office

    def __repr__(self):
        return self.description + " " + str(self.timeslot) + " " + str(self.location_string)

    def __eq__(self, other):
        return self.student == other.student and self.professor == other.professor and self.timeslot == other.timeslot

    def __hash__(self):
        return 31 * (hash(self.student) + 31 *
                     (hash(self.professor) + 31 * hash(self.timeslot)))

    def __lt__(self, other):
        return self.timeslot < other.timeslot


class TimeZone(Enum):
    CHINA = 12
    INDIA = 10
    PACIFIC = -3
    IN_BETWEEN = "In-between"

class AvailabilityType(Enum):
    ITHACA = "Ithaca"
    CORNELL_TECH = "CT"
    ONLY_ZOOM = "Zoom Only"
    NOT_AVAILABLE = "Not Available"

class MatchType(Enum):
    ADVOCATE = 0
    PREFERENCE1 = 1
    PREFERENCE2 = 2
    PREFERENCE3 = 3
    PREFERENCE4 = 4
    PREFERENCE5 = 5
    PREFERENCE6 = 6
    ADDITIONAL = 7
    ADVOCATE_AND_PREFERENCE1 = 8

# Note: This is currently redundant (as of 2023). All meetings have phase = Phase.SOLVER.
class Phase(Enum):
    STICKY = 0
    SOLVER = 1
    MISSED = 2
    AREA = 3
    STUDENT_AVAILABILITY = 4

class ResearchArea(Enum):
    THEORY_OF_COMPUTING = "Theory"
    ARTIFICIAL_INTELLIGENCE = "AI"
    COMPUTATIONAL_BIOLOGY = "Computational Biology"
    HUMAN_INTERACTION = "HCI"
    NATURAL_LANGUAGE_PROCESSING = "NLP"
    PROGRAMMING_LANGUAGES = "PL"
    ROBOTICS = "Robotics"
    SECURITY = "Security"
    SYSTEMS_AND_NETWORKING = "Systems"
    VISION = "Vision"
    GRAPHICS = "Graphics"
    ARCHITECTURE = "Architecture"
    SCIENTIFIC_COMPUTING = "Scientific Computing"
    SOFTWARE_ENGINEERING = "Software Engineering"
    MACHINE_LEARNING = "ML"

    def __init__(self, ignored_value):
        self.students = []
        self.professors = []


class Person:
    def __init__(self, full_name, primary_area, secondary_area, times_offered, times_excluded, modes_offered, email_address):
        self.full_name = full_name
        self.primary_area = primary_area
        self.secondary_area = secondary_area
        self.times_offered = times_offered
        self.times_excluded = times_excluded
        self.modes_offered = modes_offered
        self.email_address = email_address
        self.events = set()
        self.meetings = set()
        self.meeting_variables = []

    def mode_at(self, time_interval):
        for interval in self.times_offered:
            if time_interval in interval:
                offering = self.modes_offered[time_interval.start.day_number()]
                assert offering != AvailabilityType.NOT_AVAILABLE, str(self)
                return offering
        else:
            return AvailabilityType.NOT_AVAILABLE

    def offering_at(self, time_interval):
        if self.mode_at(time_interval) == AvailabilityType.NOT_AVAILABLE:
            return False
        for excluded_interval in self.times_excluded:
            if excluded_interval.conflicts(time_interval):
                return False
        return True

    def is_available(self, time_interval):
        if not self.offering_at(time_interval):
            return False
        for meeting in self.meetings:
            if time_interval.conflicts(meeting):
                return False

        return True

    def add_meeting(self, meeting):
        self.events.add(meeting)
        self.meetings.add(meeting)

    def add_meeting_variable(self, variable):
        self.meeting_variables.append(variable)

    def get_meeting_variables(self):
        return self.meeting_variables

