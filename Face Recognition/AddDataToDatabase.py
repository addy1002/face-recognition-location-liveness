import firebase_admin
from firebase_admin import credentials, db
from prettytable import PrettyTable  # pip install prettytable

print(" Starting Firebase Database Upload...")


#  Firebase Initialization

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL':  #firebase url
    })
    print(" Firebase connection successful!\n")
except Exception as e:
    print(" Firebase connection failed:", e)
    exit()


#  STUDENT DATA (Table-Like Format)
students_data = {
    "6208": {
        "name": "Addy Shrivastav",
        "major": "IT",
        "starting_year": 2023,
        "total_attendance": 6,
        "standing": "6",
        "year": "4",
        "last_attendance": "2022-12-11 00:54:34"
    },
    "6221": {
        "name": "Shreeman",
        "major": "Science",
        "starting_year": 2019,
        "total_attendance": 6,
        "standing": "2",
        "year": "4",
        "last_attendance": "2022-12-11 00:54:34"
    },
    "963852": {
        "name": "Elon",
        "major": "Physics",
        "starting_year": 2020,
        "total_attendance": 6,
        "standing": "8",
        "year": "4",
        "last_attendance": "2022-12-11 00:54:34"
    }
}

ref_students = db.reference("students")
ref_students.set(students_data)

print(" Student data uploaded to Firebase!\n")

# Print table view in terminal
student_table = PrettyTable()
student_table.field_names = ["ID", "Name", "Major", "Year", "Standing", "Attendance", "Last Attendance"]

for sid, info in students_data.items():
    student_table.add_row([
        sid,
        info["name"],
        info["major"],
        info["year"],
        info["standing"],
        info["total_attendance"],
        info["last_attendance"]
    ])

print(" STUDENT DATABASE TABLE:")
print(student_table)


# 3️ TIMETABLE DATA (Table-Like Format)
timetable_data = {
    "Monday": {
        "10:00-11:00": "AI Lecture",
        "11:00-12:00": "DBMS Lecture",
        "2:00-4:00": "Python Practical"
    },
    "Tuesday": {
        "10:00-11:00": "Maths Lecture",
        "11:00-12:00": "Operating Systems",
        "2:00-4:00": "Networking Practical"
    },
    "Wednesday": {
        "10:00-11:00": "Machine Learning",
        "11:00-12:00": "Computer Networks",
        "2:00-4:00": "DBMS Practical"
    },
    "Thursday": {
        "10:00-11:00": "Cloud Computing",
        "11:00-12:00": "AI Lecture",
        "2:00-4:00": "Mini Project Lab"
    },
    "Friday": {
        "10:00-11:00": "Software Engineering",
        "11:00-12:00": "Data Science",
        "2:00-4:00": "Python Lab"
    },
    "Saturday": {
        "10:00-12:00": "Seminar / Workshop"
    }
}

ref_timetable = db.reference("Timetable")
ref_timetable.set(timetable_data)
print("\n Timetable uploaded to Firebase!\n")

# Print timetable as tables
for day, slots in timetable_data.items():
    print(f"\n {day.upper()}")
    table = PrettyTable(["Time Slot", "Subject"])
    for slot, subject in slots.items():
        table.add_row([slot, subject])
    print(table)


# Finished
print("\n All data uploaded successfully! Check your Firebase Realtime Database now.")
