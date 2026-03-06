"""
Seed script to populate the database with departments.

Usage:
    python -m scripts.seeders.seed_departments
    OR
    python scripts/seeders/seed_departments.py

Departments seeded: 15 common university departments
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from api.db.database import get_db_with_ctx_manager, create_database
from api.v1.models.department import Department


DEPARTMENTS = [
    {
        "name": "Computer Science",
        "code": "CSC",
        "description": "Study of computation, algorithms, data structures, and software engineering.",
    },
    {
        "name": "Electrical & Electronics Engineering",
        "code": "EEE",
        "description": "Design and application of electrical systems, circuits, and electronic devices.",
    },
    {
        "name": "Mechanical Engineering",
        "code": "MEE",
        "description": "Design, analysis, and manufacturing of mechanical systems.",
    },
    {
        "name": "Civil Engineering",
        "code": "CVE",
        "description": "Planning, design, and construction of infrastructure and buildings.",
    },
    {
        "name": "Information Technology",
        "code": "IFT",
        "description": "Application of computing technologies to manage and process information.",
    },
    {
        "name": "Software Engineering",
        "code": "SEN",
        "description": "Systematic approach to the design, development, and maintenance of software.",
    },
    {
        "name": "Cyber Security",
        "code": "CYB",
        "description": "Protection of computer systems, networks, and data from digital threats.",
    },
    {
        "name": "Mathematics",
        "code": "MTH",
        "description": "Study of numbers, structures, patterns, and quantitative reasoning.",
    },
    {
        "name": "Physics",
        "code": "PHY",
        "description": "Study of matter, energy, and the fundamental forces of nature.",
    },
    {
        "name": "Chemistry",
        "code": "CHM",
        "description": "Study of substances, their properties, reactions, and transformations.",
    },
    {
        "name": "Biochemistry",
        "code": "BCH",
        "description": "Study of chemical processes and substances within living organisms.",
    },
    {
        "name": "Business Administration",
        "code": "BUS",
        "description": "Management principles, organisational behaviour, and business strategy.",
    },
    {
        "name": "Economics",
        "code": "ECO",
        "description": "Study of production, distribution, and consumption of goods and services.",
    },
    {
        "name": "Mass Communication",
        "code": "MAC",
        "description": "Study of media, journalism, public relations, and communication theory.",
    },
    {
        "name": "Architecture",
        "code": "ARC",
        "description": "Design and planning of buildings and physical structures.",
    },
]


def seed_departments():
    """Insert seed departments into the database, skipping any that already exist."""

    created = 0
    skipped = 0

    with get_db_with_ctx_manager() as db:
        for dept_data in DEPARTMENTS:
            # Check by code (unique)
            existing = Department.fetch_one_by_field(
                db, throw_error=False, code=dept_data["code"]
            )
            if existing:
                print(f"  [SKIP] {dept_data['code']} — {dept_data['name']} (already exists)")
                skipped += 1
                continue

            Department.create(
                db=db,
                name=dept_data["name"],
                code=dept_data["code"],
                description=dept_data["description"],
            )
            print(f"  [OK]   {dept_data['code']} — {dept_data['name']}")
            created += 1

    print(f"\nDone — {created} created, {skipped} skipped.")


if __name__ == "__main__":
    print("=" * 50)
    print("  ProjectHub — Department Seeder")
    print("=" * 50)
    print()

    # Ensure tables exist
    create_database()

    seed_departments()
