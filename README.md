# Purpose

This is the 
Cornell University Bowers CIS Department's 
PhD Visit Days scheduling software.
Its goal is mainly to schedule meetings between visiting students and Cornell faculty.

### Note to future visit days scheduling czars
Read this entire README several times before starting!
It's also recommended to at least skim the entire codebase and example input data.
Bonne chance!

### Credits 
The current version, which uses mixed integer linear programming, is entirely written by Spencer Peters.
(Bits of an earlier implementation, which used a SAT solver, were replaced one by one until nothing of the original remained!)

Much credit is due to Sam Hopkins, who began the tradition of automated scheduling within Cornell CIS, 
and to Alexa Van Hattum, who wrote most of the first implementation
([in this private repo](https://github.com/avanhatt/visit-schedule-scripts/tree/visitday2023-2)),
and coordinated its first few real uses in PhD Visit Days.

# To run the example
You'll need
1. A Python 3 environment with the packages in requirements.txt
2. A copy of [Gurobi](https://www.gurobi.com/academia/academic-program-and-licenses/). Once installed, it 
should be
[automatically discovered]([https://python-mip.readthedocs.io/en/latest/install.html#gurobi-installation-and-configuration-optional]
(Gurobi)) 
by the Python-MIP package.
3. (Optional) The detailed 2023 specifics.py file, redacted from this repo for privacy reasons. 
Request access 
[here](https://drive.google.com/file/d/1qJLTmYzKPWQpQf0qjWe7aZb87qhoFqeQ/view?usp=sharing).

Then run main.py.

# Technical overview
The scheduler works by setting up and solving a Mixed Integer Linear Program (MIP), using Gurobi 
(or another backend solver if desired). The MIP involves
*variables*
(e.g., student s is meeting professor p in timeslot t),
*constraints*
(e.g., a student cannot be in two meetings at once)
and an *objective*
(e.g., scheduling a meeting between a student and their faculty advocate is worth 250 points).
The MIP solver will in almost all cases *provably* find an assignment to the variables that
maximizes the objective, subject to satisfying the constraints. 
Fun note: the 2023 MIP had almost 400,000 variables, 
but setting up the MIP (using Python for loops)
often took longer than solving it.


### Organization
- main.py is the entry point, which actually sets up the MIP and solves it.
- model.py defines the Model class, which is the scheduler's model of the world. 
- students.py and professors.py contain the Student and Professor classes.
- data_types.py contains data types used by the model.
- specifics.py contains values that should be thought of as specific to a particular year's scheduling task,
including time slots for meetings, visit days events, and several categories of special cases.

The scheduler takes as input four CSVs:
- student-data.csv and faculty-data.csv are the main input sources, and contain data about the visiting students and Cornell faculty
for whom the meetings are being scheduled.
- sticky_meetings.csv and broken_meetings.csv are less important. They contain meeting data. 
The scheduler will attempt to retain meetings in sticky_meetings.csv not in broken_meetings.csv.

Running students.py (professors.py) will attempt only to parse student-data.csv (professors.py),
which is useful for debugging. Similarly, running model.py will attempt only to parse and sanity-check 
the input data, without attempting to schedule meetings.

### Main Features

The scheduler supports scheduling meetings in a-priori fixed timeslots (possibly overlapping). 
Meetings involve a professor and typically one student (but see group_meeting_professors in specifics.py).
The scheduler also support scheduling office hours, again, in a-priori fixed timeslots. 
These are intended for students to drop in and meet with professors 
that they were not specifically scheduled to meet with.

# Suggested workflow
0. **Get involved early in the process of collecting input data from the department admins.**
The better designed the data collection process is and the higher quality the resulting data, 
the easier your life will be come scheduling time.
I recommend using shared [Cornell Box](https://it.cornell.edu/box) spreadsheets for the input data--
it has high-quality version control, and you'll need to do manual cleaning and editing.
Also, **start scheduling early, as soon as the inputs are available**!
1. Follow the steps in "To run the example". I recommend a [pyenv virtualenv](https://realpython.com/intro-to-pyenv/) for step 1. 
2. Make yourself a new Git branch to avoid any confusion.
3. Use the data types in specifics.py to match your input data colums to the schema expected by the scheduler.
4. Make other necessary edits to specifics.py until main.py runs successfully.
5. Manually inspect the results (in the newly created ''output'' directory under the root directory), 
in particular output/all_meetings.csv.
   (Alternatively, I prefer to run the scheduler in a Jupyter Notebook,
and inspect the resulting Model object, which
represents essentially all relevant input and output data in convenient,
programmatically accessible form.)
6. Implement code that tells you how well the results are doing on metrics you care about.
7. Tweak the solver constraints and objective until you have schedules you're happy with!
8. Share them with some faculty and admins and continue step 7 until all parties are happy.

Again, bonne chance! I commend and salute you.

# Things to improve

1. Don't concatenate strings like a naïf, use Pathlib to join paths.
2. Add more automated checks that the results satisfy various conditions.
Now that the Model object contains all the input data and output information in easily
accessible form, this should be easy to get started on.
3. 