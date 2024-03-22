import re
import itertools
from enum import Enum
from pprint import pprint

from data_types import TimeSlot, AbsoluteTime, TimeInterval, Event

input_path = "/Users/gemmechu/Documents/Cornell/CornellCISVisitDaysScheduler/2024/input/"
output_path = "/Users/gemmechu/Documents/Cornell/CornellCISVisitDaysScheduler/2024/output/"
student_input_path = input_path + "student-data.csv"
professor_input_path = input_path + "faculty-data.csv"
student_text_schedule_path = output_path + "studentTextSchedules/"
student_latex_schedule_path = output_path + "studentLatexSchedules/"
professor_text_schedule_path = output_path + "facultyTextSchedules/"
student_availability_path = output_path + "studentAvailability.csv"
scheduler_log_path = output_path + "log.txt"
meetings_to_keep_path = input_path + "sticky_meetings.csv"
meetings_no_need_to_keep_path = input_path + "broken_meetings.csv"

minimum_meetings_per_student = 3
maximum_meetings_per_student = 6
maximum_meetings_per_professor = 10

group_meeting_professors = ["Kilian Weinberger"]

class StudentDataKeys(Enum):
    EMAIL = 'Email Address'
    AREAS = 'Areas'
    FIRST_NAME = 'First Name'
    LAST_NAME = 'Last Name'
    NICKNAME = 'Nickname'
    MONDAY_TYPE = '25th'
    TUESDAY_TYPE = '26th'
    WEDNESDAY_TYPE = '27th'
    TIME_ZONE = 'Time Zone'
    PREFERENCE1 = 'Preference 1'
    PREFERENCE2 = 'Preference 2'
    PREFERENCE3 = 'Preference 3'
    PREFERENCE4 = 'Preference 4'
    PREFERENCE5 = 'Preference 5'
    PREFERENCE6 = 'Preference 6'
    ADDITIONAL_FACULTY = 'Additional Faculty'
    PRIMARY_ADVOCATE = 'Advocate 1'
    ADVOCATE2 = 'Advocate 2'
    
    


EARLY_DEPARTURES = {
    # Example:
    # "Student Name": AbsoluteTime.fromDaysHoursMinutes(2, 14, 30),
}

LEAP_BREAKFAST_STUDENTS = [
    # Example:
    # "Student Name"
]

class ProfessorDataKeys(Enum):
    NAME = 'FacultyName'
    MONDAY_TYPE = 'MondayType'
    TUESDAY_TYPE = 'TuesdayType'
    WEDNESDAY_TYPE = 'WednesdayType'
    EMAIL = 'EmailAddress'
    ZOOM_LINK = 'ZoomLink'
    OFFICE = 'Office'
    MONDAY_TIMES = 'MondaySlots'
    TUESDAY_TIMES = 'TuesdaySlots'
    WEDNESDAY_TIMES = 'WednesdaySlots'
    LONGER_MEETINGS = 'LongerMeetings'
    AREA1 = 'Area 1'
    AREA2 = 'Area 2'
    BUILDING = 'Building'


def parse_times(day, raw_times_string):
    raw_times_string = raw_times_string.strip()
    if len(raw_times_string) == 0:
        return []

    time_strings = raw_times_string.split(",")

    def get_start_time_of(time_string):
        hhmmregex = re.compile("(\d+):(\d+)")
        match = hhmmregex.search(time_string)
        assert match is not None, f"Time string is {time_string}"
        hours = int(match.group(1))
        if hours < 6:
            hours += 12
        minutes = int(match.group(2))
        time = AbsoluteTime.fromDaysHoursMinutes(day, hours, minutes)
        return time
    start_times = [get_start_time_of(time_string) for time_string in time_strings if time_string != ""]

    def remove_first_interval(start_times_list):
        start = start_times_list[0]
        duration = 15

        while len(start_times_list) > 1 and start_times_list[1] - start_times_list[0] == 15:
            duration += 15
            del start_times_list[0]

        del start_times_list[0]
        return TimeInterval(start, duration)

    intervals = []
    while len(start_times) > 0:
        intervals.append(remove_first_interval(start_times))

    return intervals

MONDAY_MEETING_TIMES = parse_times(0, "11:15-11:30 a.m., 11:35-11:50 a.m.,1:30-1:45 p.m.,1:50-2:05 p.m.,2:10-2:25 p.m.,2:30-2:45 p.m.,2:50-3:05 p.m.,3:10-3:25 p.m.")
TUESDAY_MEETING_TIMES = parse_times(1, "10:00-10:15 a.m.,10:20-10:35 a.m.,10:40-10:55 a.m.,11:00-11:15 a.m.,11:20-11:35 a.m.,11:40-11:55 a.m.,2:00-2:15 p.m.,2:20-2:35 p.m.,2:40-2:55 p.m.,3:00-3:15 p.m.,3:20-3:35 p.m.,3:40-3:55 p.m.")

WEDNESDAY_MEETING_TIMES = parse_times(2, "10:20-10:35 a.m.,10:40-10:55 a.m.,11:00-11:15 a.m.,1:30-1:45 p.m.,1:50-2:05 p.m.,2:10-2:25 p.m.,2:30-2:45 p.m.")
# WEDNESDAY_MEETING_TIMES = [TimeInterval(AbsoluteTime.fromDaysHoursMinutes(2, 10, 20), 35),
#                            TimeInterval(AbsoluteTime.fromDaysHoursMinutes(2, 13, 30), 90)]


ALL_MEETING_TIMES = MONDAY_MEETING_TIMES + TUESDAY_MEETING_TIMES + WEDNESDAY_MEETING_TIMES

def make_slots(intervals, duration, break_duration):
    for i, j in itertools.combinations(intervals, 2):
            assert i.disjoint(j), f"{i} {j}"

    slots = []
    for interval in intervals:
        start = interval.start
        while start <= interval.end() + (-duration):
            slots.append(TimeSlot(start, duration))
            start += duration + break_duration

    return slots

FIFTEEN_MINUTE_SLOTS = make_slots(ALL_MEETING_TIMES, 15, 5)
THIRTY_FIVE_MINUTE_SLOTS = make_slots(ALL_MEETING_TIMES, 35, 5)
OFFICE_HOURS_SLOTS = [TimeSlot(AbsoluteTime.fromDaysHoursMinutes(0, 11, 15), 45)] + \
                     make_slots(MONDAY_MEETING_TIMES, 55, 5) + \
                     make_slots(TUESDAY_MEETING_TIMES, 55, 5) + \
                     make_slots(WEDNESDAY_MEETING_TIMES, 35, 5)
ALL_SLOTS = FIFTEEN_MINUTE_SLOTS + THIRTY_FIVE_MINUTE_SLOTS + OFFICE_HOURS_SLOTS


def too_late_intervals(minutes_offset_from_est):
    # return []
    if minutes_offset_from_est is None:
        return []

    if minutes_offset_from_est == 12 * 60:
        latest_minutes = 14 * 60
    elif minutes_offset_from_est == int(9.5 * 60):
        latest_minutes = int(15.5 * 60)
    elif minutes_offset_from_est == 9 * 60 or minutes_offset_from_est == 8 * 60 or minutes_offset_from_est == 6 * 60:
        latest_minutes = 16 * 60
    else:
        assert minutes_offset_from_est <= 0
        latest_minutes = 24 * 60
    intervals = []
    for day in [0, 1, 2]:
        latest_absolute_minutes = day * AbsoluteTime.MINUTES_PER_DAY + latest_minutes
        duration = AbsoluteTime.MINUTES_PER_DAY - latest_minutes
        intervals.append(TimeInterval(AbsoluteTime(latest_absolute_minutes), duration))
    return intervals

def log_error(message):
    print(message)

def log_warning(message):
    print(message)

def log(message):
    print(message)


MAIN_EVENTS = {
    # Example:
    # Event(
    #     AbsoluteTime.fromDaysHoursMinutes(0, 10, 50),
    #     20,
    #     "Intro to Cornell Tech",
    #     r"Statler Ballroom",
    #     r"Same Zoom link as Welcome; please do not disconnect",
    # ),
}

if __name__ == "__main__":
    pprint(f"Fifteen minute slots: {FIFTEEN_MINUTE_SLOTS}")
    pprint(f"Thirty five minute slots: {THIRTY_FIVE_MINUTE_SLOTS}")
    pprint(f"Office hours slots: {OFFICE_HOURS_SLOTS}")
    pprint(f"Events: {MAIN_EVENTS}")
