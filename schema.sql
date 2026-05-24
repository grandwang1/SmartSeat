PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    student_name TEXT NOT NULL,
    department_grade TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS classrooms (
    classroom_id INTEGER PRIMARY KEY,
    room_name TEXT NOT NULL,
    max_rows INTEGER NOT NULL,
    max_cols INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seats (
    seat_id INTEGER PRIMARY KEY,
    classroom_id INTEGER NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    is_usable INTEGER NOT NULL CHECK (is_usable IN (0, 1)),
    block_note TEXT,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE CASCADE,
    UNIQUE (classroom_id, grid_x, grid_y)
);

CREATE TABLE IF NOT EXISTS exams (
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    classroom_id INTEGER NOT NULL,
    col_reverse INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS exam_classrooms (
    exam_id INTEGER NOT NULL,
    classroom_id INTEGER NOT NULL,
    PRIMARY KEY (exam_id, classroom_id),
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS seating_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    seat_id INTEGER NOT NULL,
    violation_flag INTEGER NOT NULL DEFAULT 0 CHECK (violation_flag IN (0, 1)),
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT,
    FOREIGN KEY (seat_id) REFERENCES seats(seat_id) ON DELETE RESTRICT,
    UNIQUE (exam_id, student_id),
    UNIQUE (exam_id, seat_id)
);
