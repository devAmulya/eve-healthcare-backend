"""
Populates a few diagnostic centres and tests so the API has something to
list/book against out of the box. Safe to re-run: it skips seeding if any
centre already exists.

Usage:
    python seed.py
"""

from app.database import Base, SessionLocal, engine
from app.models import DiagnosticCentre, DiagnosticTest

Base.metadata.create_all(bind=engine)

CENTRES = [
    {
        "name": "Apollo Diagnostics — Karol Bagh",
        "location": "Karol Bagh, Delhi",
        "tests": [
            ("Complete Blood Count (CBC)", 299.0),
            ("Lipid Profile", 599.0),
            ("Thyroid Panel (T3, T4, TSH)", 799.0),
        ],
    },
    {
        "name": "MedLife Labs — Saket",
        "location": "Saket, Delhi",
        "tests": [
            ("HbA1c (Diabetes)", 449.0),
            ("Vitamin D Test", 999.0),
            ("Liver Function Test", 649.0),
        ],
    },
]


def run():
    db = SessionLocal()
    try:
        if db.query(DiagnosticCentre).first() is not None:
            print("Centres already exist, skipping seed.")
            return

        for centre_data in CENTRES:
            centre = DiagnosticCentre(name=centre_data["name"], location=centre_data["location"])
            db.add(centre)
            db.flush()  # get centre.id before creating tests

            for test_name, price in centre_data["tests"]:
                db.add(DiagnosticTest(centre_id=centre.id, name=test_name, price=price))

        db.commit()
        print("Seeded diagnostic centres and tests.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
