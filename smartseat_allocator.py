from __future__ import annotations


def assign_seats_serial_checkerboard(
    students: list[dict],
    usable_seats: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Place students in a true checkerboard (梅花座) pattern.

    A seat at (grid_x, grid_y) is a valid checkerboard position when
    (grid_x + grid_y) % 2 == chosen_parity.  Because any two orthogonally
    adjacent cells always have *different* parity, this guarantees that no
    two assigned seats are ever directly adjacent — regardless of where
    obstacles are placed.

    Unusable cells (pillars, blackboard rows, etc.) are simply absent from
    usable_seats; their removal does NOT affect which remaining seats are
    valid checkerboard positions.  In particular, both neighbours of a pillar
    can still receive students.

    The parity with the larger number of available usable seats is chosen
    (ties default to parity 0, which starts from the top-left corner when
    grid coordinates begin at 1).

    Seats are filled left-to-right, top-to-bottom (row-major order).

    Returns (assignments, unassigned_students).
    """
    if not students:
        return [], []

    parity_0 = [s for s in usable_seats if (s["grid_x"] + s["grid_y"]) % 2 == 0]
    parity_1 = [s for s in usable_seats if (s["grid_x"] + s["grid_y"]) % 2 == 1]
    checkerboard_seats = parity_0 if len(parity_0) >= len(parity_1) else parity_1

    ordered = sorted(checkerboard_seats, key=lambda s: (s["grid_y"], s["grid_x"]))

    assignments: list[dict] = []
    unassigned: list[dict] = []

    for i, student in enumerate(students):
        if i < len(ordered):
            assignments.append(
                {
                    "student_id": student["student_id"],
                    "seat_id": ordered[i]["seat_id"],
                    "violation_flag": 0,
                }
            )
        else:
            unassigned.append(student)

    return assignments, unassigned
