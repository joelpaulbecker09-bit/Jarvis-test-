import sqlite3
from pathlib import Path

from src.memory.memory import Memory


TEST_DATABASE = Path("data/test_memory.db")


if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()


connection = sqlite3.connect(TEST_DATABASE)

connection.execute("""
    CREATE TABLE memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        memory_type TEXT NOT NULL,
        entity_type TEXT,
        information TEXT NOT NULL,
        time_context TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

connection.commit()


memory = Memory.__new__(Memory)

memory.database = TEST_DATABASE
memory.connection = connection


memory.save(
    category="Musik",
    memory_type="Vorliebe",
    entity_type="Künstler",
    information="Testkünstler"
)


print("Vor dem Update:")


for memory_id, category, memory_type, entity_type, information in memory.connection.execute(
    "SELECT id, category, memory_type, entity_type, information FROM memories"
):
    print(
        f"- ID: {memory_id} | "
        f"{category} | {memory_type} | {entity_type} | {information}"
    )


row = memory.connection.execute(
    """
    SELECT id
    FROM memories
    WHERE information = ?
    """,
    ("Testkünstler",)
).fetchone()


if row:
    memory.update(
        memory_id=row[0],
        category="Musik",
        memory_type="Abneigung",
        entity_type="Künstler",
        information="Testkünstler"
    )


print()
print("Nach dem Update:")


for memory_id, category, memory_type, entity_type, information in memory.connection.execute(
    "SELECT id, category, memory_type, entity_type, information FROM memories"
):
    print(
        f"- ID: {memory_id} | "
        f"{category} | {memory_type} | {entity_type} | {information}"
    )


connection.close()