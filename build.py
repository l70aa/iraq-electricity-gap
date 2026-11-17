import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "outputs"


def read_csv(name):
    with (RAW / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def build():
    OUTPUT.mkdir(exist_ok=True)
    with sqlite3.connect(OUTPUT / "electricity.sqlite") as db:
        db.executescript("""
            DROP VIEW IF EXISTS grid_target;
            DROP VIEW IF EXISTS grid_delta;
            DROP VIEW IF EXISTS comparable_grid;
            DROP TABLE IF EXISTS power_common_scope;
            CREATE TABLE power_common_scope (
                year INTEGER PRIMARY KEY CHECK (year = 2025),
                governorate_count INTEGER NOT NULL CHECK (governorate_count = 13),
                demand_mw INTEGER NOT NULL CHECK (demand_mw > 0),
                supplied_mw INTEGER NOT NULL CHECK (supplied_mw BETWEEN 0 AND demand_mw),
                source_url TEXT NOT NULL
            );
            DROP VIEW IF EXISTS matched_scope;
            DROP VIEW IF EXISTS governorate_metrics;
            DROP TABLE IF EXISTS population;
            DROP TABLE IF EXISTS electricity;
            CREATE TABLE population (
                area TEXT, governorate TEXT NOT NULL,
                year INTEGER CHECK (year = 2024),
                population INTEGER NOT NULL CHECK (population > 0),
                PRIMARY KEY (area, year)
            );
            CREATE TABLE electricity (
                governorate TEXT, year INTEGER CHECK (year = 2024),
                demand_mw INTEGER NOT NULL CHECK (demand_mw > 0),
                supplied_mw INTEGER NOT NULL CHECK (supplied_mw BETWEEN 0 AND demand_mw),
                source_url TEXT NOT NULL,
                PRIMARY KEY (governorate, year)
            );
        """)
        db.executemany(
            "INSERT INTO population VALUES (:area,:governorate,:year,:population)",
            read_csv("population-2024.csv"),
        )
        db.executemany(
            "INSERT INTO electricity VALUES (:governorate,:year,:demand_mw,:supplied_mw,:source_url)",
            read_csv("power-2024.csv"),
        )
        db.executemany(
            "INSERT INTO power_common_scope VALUES (:year,:governorate_count,:demand_mw,:supplied_mw,:source_url)",
            read_csv("power-common-scope-2025.csv"),
        )
        unmatched = db.execute("""
            SELECT governorate, year FROM electricity
            EXCEPT SELECT governorate, year FROM population
        """).fetchall()
        if unmatched:
            raise ValueError(f"Electricity rows without population keys: {unmatched}")
        db.executescript((ROOT / "analysis.sql").read_text(encoding="utf-8-sig"))
        for view in ("governorate_metrics", "matched_scope", "comparable_grid", "grid_delta", "grid_target"):
            cursor = db.execute(f"SELECT * FROM {view}")
            with (OUTPUT / f"{view}.csv").open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.writer(target)
                writer.writerow(column[0] for column in cursor.description)
                writer.writerows(cursor)
        print(db.execute("SELECT status, COUNT(*) FROM governorate_metrics GROUP BY status").fetchall())
        print(db.execute("SELECT * FROM matched_scope").fetchall())


if __name__ == "__main__":
    build()
