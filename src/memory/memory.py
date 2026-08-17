import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple


class Memory:
    """
    JARVIS V6 – dauerhaftes Langzeitgedächtnis.

    Verantwortlichkeiten:
    - lokale SQLite-Datenbank
    - Memories speichern
    - Memories suchen
    - Memories ändern
    - Memories löschen
    - Kategorien verwalten
    - Konflikte erkennen
    - Duplikate verhindern

    Wichtig:
    Diese Klasse entscheidet NICHT selbst, was der Benutzer meint.
    Das übernimmt der JarvisBrain / LLM-Analyzer.

    Die Datenbank bleibt deterministisch.
    """

    # ============================================================
    # ERLAUBTE WERTE
    # ============================================================

    CATEGORIES = {
        "Persönlichkeit",
        "Musik",
        "Spiele",
        "Arbeit",
        "Schule",
        "Familie",
        "Freunde",
        "Hobbys",
        "Vorlieben",
        "Abneigungen",
        "Ziele",
        "Gewohnheiten",
        "Sonstiges",
    }

    MEMORY_TYPES = {
        "Vorliebe",
        "Abneigung",
        "Fakt",
        "Ziel",
        "Gewohnheit",
    }

    ENTITY_TYPES = {
        "Person",
        "Künstler",
        "Band",
        "Song",
        "Album",
        "Spiel",
        "Film",
        "Serie",
        "Hobby",
        "Tätigkeit",
        "Ort",
        "Gegenstand",
        "Tier",
        "Sonstiges",
    }

    # ============================================================
    # INITIALISIERUNG
    # ============================================================

    def __init__(self, database_path=None):

        if database_path is None:
            data_folder = Path("data")
            data_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            database_path = (
                data_folder / "memory.db"
            )

        self.database = Path(database_path)

        self.database.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            self.database
        )

        # SQLite soll bei Problemen nicht einfach
        # endlos warten.
        self.connection.execute(
            "PRAGMA busy_timeout = 5000"
        )

        # Foreign Keys aktivieren.
        self.connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        self._create_structure()

        print(
            f"[MEMORY] Datenbank: "
            f"{self.database}"
        )

    # ============================================================
    # DATENBANKSTRUKTUR
    # ============================================================

    def _create_structure(self):

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                category TEXT NOT NULL,

                memory_type TEXT NOT NULL,

                entity_type TEXT,

                information TEXT NOT NULL,

                time_context TEXT,

                created_at TEXT
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self._ensure_structure()

        # Sinnvolle Indizes.
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_memories_category
            ON memories(category)
            """
        )

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_memories_information
            ON memories(information)
            """
        )

        self.connection.commit()

    # ============================================================
    # BESTEHENDE DATENBANK MIGRIEREN
    # ============================================================

    def _ensure_structure(self):

        columns = self.connection.execute(
            "PRAGMA table_info(memories)"
        ).fetchall()

        column_names = {
            column[1]
            for column in columns
        }

        if "entity_type" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN entity_type TEXT
                """
            )

        if "time_context" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN time_context TEXT
                """
            )

        if "created_at" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN created_at TEXT
                """
            )

            self.connection.execute(
                """
                UPDATE memories
                SET created_at = CURRENT_TIMESTAMP
                WHERE created_at IS NULL
                """
            )

        if "updated_at" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN updated_at TEXT
                """
            )

            self.connection.execute(
                """
                UPDATE memories
                SET updated_at = CURRENT_TIMESTAMP
                WHERE updated_at IS NULL
                """
            )

    # ============================================================
    # VALIDIERUNG
    # ============================================================

    def _validate(
        self,
        category,
        memory_type,
        entity_type,
        information
    ):
        """
        Verhindert ungültige Daten in der Datenbank.
        """

        if category not in self.CATEGORIES:
            raise ValueError(
                f"Ungültige Kategorie: {category}"
            )

        if memory_type not in self.MEMORY_TYPES:
            raise ValueError(
                f"Ungültiger Memory-Typ: "
                f"{memory_type}"
            )

        if entity_type:
            if entity_type not in self.ENTITY_TYPES:
                raise ValueError(
                    f"Ungültiger Entity-Typ: "
                    f"{entity_type}"
                )

        if not information:
            raise ValueError(
                "Information darf nicht leer sein."
            )

        if not isinstance(
            information,
            str
        ):
            raise TypeError(
                "Information muss ein String sein."
            )

    # ============================================================
    # NORMALISIERUNG
    # ============================================================

    @staticmethod
    def _normalize(value):
        """
        Einheitliche Vergleichsform.

        Beispiel:

        '  Deftones '
        'deftones'

        werden gleich behandelt.
        """

        if value is None:
            return ""

        return " ".join(
            str(value).strip().lower().split()
        )

    # ============================================================
    # SPEICHERN
    # ============================================================

    def save(
        self,
        category,
        memory_type,
        entity_type,
        information,
        time_context=None
    ):
        """
        Speichert eine neue Memory.

        Gibt zurück:

        True
            neue Memory gespeichert

        False
            bereits vorhandene Memory gefunden
        """

        self._validate(
            category,
            memory_type,
            entity_type,
            information
        )

        information = information.strip()

        existing = self.find_by_information(
            information
        )

        # --------------------------------------------------------
        # EXAKTES DUPLIKAT
        # --------------------------------------------------------

        if existing:

            memory_id = existing[0]

            updates = []
            values = []

            # Fehlenden Entity-Typ ergänzen.
            if (
                entity_type
                and not existing[3]
            ):
                updates.append(
                    "entity_type = ?"
                )
                values.append(
                    entity_type
                )

            # Fehlenden Zeitkontext ergänzen.
            if (
                time_context
                and not existing[5]
            ):
                updates.append(
                    "time_context = ?"
                )
                values.append(
                    time_context
                )

            if updates:

                updates.append(
                    "updated_at = CURRENT_TIMESTAMP"
                )

                values.append(
                    memory_id
                )

                self.connection.execute(
                    f"""
                    UPDATE memories
                    SET {", ".join(updates)}
                    WHERE id = ?
                    """,
                    values
                )

                self.connection.commit()

            return False

        # --------------------------------------------------------
        # NEUE MEMORY
        # --------------------------------------------------------

        self.connection.execute(
            """
            INSERT INTO memories (
                category,
                memory_type,
                entity_type,
                information,
                time_context,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                category,
                memory_type,
                entity_type,
                information,
                time_context
            )
        )

        self.connection.commit()

        return True

    # ============================================================
    # ÄNDERN
    # ============================================================

    def update(
        self,
        memory_id,
        category=None,
        memory_type=None,
        entity_type=None,
        information=None,
        time_context=None
    ):
        """
        Ändert eine Memory anhand ihrer ID.

        Die ID ist entscheidend:
        Das LLM darf nicht direkt Datensätze
        anhand eines unsicheren Textes verändern.
        """

        existing = self.get_by_id(
            memory_id
        )

        if not existing:
            return False

        new_category = (
            category
            if category
            else existing[1]
        )

        new_memory_type = (
            memory_type
            if memory_type
            else existing[2]
        )

        new_entity_type = (
            entity_type
            if entity_type
            else existing[3]
        )

        new_information = (
            information.strip()
            if information
            else existing[4]
        )

        new_time_context = (
            time_context
            if time_context is not None
            else existing[5]
        )

        self._validate(
            new_category,
            new_memory_type,
            new_entity_type,
            new_information
        )

        # --------------------------------------------------------
        # Prüfen, ob die Änderung einen vorhandenen
        # Datensatz duplizieren würde.
        # --------------------------------------------------------

        duplicate = self.find_by_information(
            new_information
        )

        if (
            duplicate
            and duplicate[0] != memory_id
        ):
            return False

        self.connection.execute(
            """
            UPDATE memories

            SET
                category = ?,
                memory_type = ?,
                entity_type = ?,
                information = ?,
                time_context = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                new_category,
                new_memory_type,
                new_entity_type,
                new_information,
                new_time_context,
                memory_id
            )
        )

        self.connection.commit()

        return True

    # ============================================================
    # EINZELNE MEMORY
    # ============================================================

    def get_by_id(
        self,
        memory_id
    ):
        cursor = self.connection.execute(
            """
            SELECT
                id,
                category,
                memory_type,
                entity_type,
                information,
                time_context,
                created_at,
                updated_at

            FROM memories

            WHERE id = ?
            """,
            (memory_id,)
        )

        return cursor.fetchone()

    # ============================================================
    # ALLE MEMORY
    # ============================================================

    def get_all(self):

        cursor = self.connection.execute(
            """
            SELECT
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            ORDER BY id ASC
            """
        )

        return cursor.fetchall()

    # ============================================================
    # ALLE MEMORY MIT ID
    # ============================================================

    def get_all_with_ids(self):

        cursor = self.connection.execute(
            """
            SELECT
                id,
                category,
                memory_type,
                entity_type,
                information,
                time_context,
                created_at,
                updated_at

            FROM memories

            ORDER BY id ASC
            """
        )

        return cursor.fetchall()

    # ============================================================
    # INFORMATION EXAKT SUCHEN
    # ============================================================

    def find_by_information(
        self,
        information
    ):
        """
        Exakte Suche.

        Wird hauptsächlich für
        Duplikaterkennung verwendet.
        """

        cursor = self.connection.execute(
            """
            SELECT
                id,
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            WHERE LOWER(TRIM(information))
                = LOWER(TRIM(?))

            LIMIT 1
            """,
            (information,)
        )

        return cursor.fetchone()

    # ============================================================
    # ÄHNLICHE MEMORY-KANDIDATEN
    # ============================================================

    def search_candidates(
        self,
        information,
        category=None,
        memory_type=None,
        entity_type=None,
        limit=10
    ):
        """
        Liefert mögliche bestehende Memories.

        Wichtig:
        Diese Methode entscheidet NICHT,
        welche Memory gemeint ist.

        Sie liefert nur Kandidaten.
        """

        query = """
            SELECT
                id,
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            WHERE 1 = 1
        """

        parameters = []

        # --------------------------------------------------------
        # Kategorie
        # --------------------------------------------------------

        if category:

            query += """
                AND LOWER(TRIM(category))
                    = LOWER(TRIM(?))
            """

            parameters.append(
                category
            )

        # --------------------------------------------------------
        # Memory-Typ
        # --------------------------------------------------------

        if memory_type:

            query += """
                AND LOWER(TRIM(memory_type))
                    = LOWER(TRIM(?))
            """

            parameters.append(
                memory_type
            )

        # --------------------------------------------------------
        # Entity-Typ
        # --------------------------------------------------------

        if entity_type:

            query += """
                AND LOWER(TRIM(entity_type))
                    = LOWER(TRIM(?))
            """

            parameters.append(
                entity_type
            )

        # --------------------------------------------------------
        # Information
        # --------------------------------------------------------

        if information:

            query += """
                AND LOWER(information)
                    LIKE LOWER(?)
            """

            parameters.append(
                f"%{information.strip()}%"
            )

        query += """
            ORDER BY id ASC
            LIMIT ?
        """

        parameters.append(
            int(limit)
        )

        cursor = self.connection.execute(
            query,
            parameters
        )

        return cursor.fetchall()

    # ============================================================
    # KATEGORIE
    # ============================================================

    def get_by_category(
        self,
        category
    ):

        cursor = self.connection.execute(
            """
            SELECT
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            WHERE LOWER(TRIM(category))
                = LOWER(TRIM(?))

            ORDER BY id ASC
            """,
            (category,)
        )

        return cursor.fetchall()

    # ============================================================
    # MEMORY-TYP
    # ============================================================

    def get_by_type(
        self,
        memory_type
    ):

        cursor = self.connection.execute(
            """
            SELECT
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            WHERE LOWER(TRIM(memory_type))
                = LOWER(TRIM(?))

            ORDER BY id ASC
            """,
            (memory_type,)
        )

        return cursor.fetchall()

    # ============================================================
    # ENTITY
    # ============================================================

    def get_by_entity_type(
        self,
        entity_type
    ):

        cursor = self.connection.execute(
            """
            SELECT
                category,
                memory_type,
                entity_type,
                information,
                time_context

            FROM memories

            WHERE LOWER(TRIM(entity_type))
                = LOWER(TRIM(?))

            ORDER BY id ASC
            """,
            (entity_type,)
        )

        return cursor.fetchall()

    # ============================================================
    # ZEITKONTEXT
    # ============================================================

    def get_time_context(
        self,
        information
    ):

        cursor = self.connection.execute(
            """
            SELECT
                time_context

            FROM memories

            WHERE LOWER(TRIM(information))
                = LOWER(TRIM(?))

            LIMIT 1
            """,
            (information,)
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    # ============================================================
    # LÖSCHEN PER ID
    # ============================================================

    def delete(
        self,
        memory_id
    ):
        """
        Sicherstes Löschen.

        Eine ID = genau eine Memory.
        """

        cursor = self.connection.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            """,
            (memory_id,)
        )

        self.connection.commit()

        return cursor.rowcount

    # ============================================================
    # LÖSCHEN PER INFORMATION
    # ============================================================

    def delete_by_information(
        self,
        information
    ):
        """
        Kompatibilitätsfunktion für deinen
        bisherigen JarvisBrain.

        Löscht die exakt passende Information.

        Für die endgültige V6-Logik sollte später
        bevorzugt delete(memory_id) verwendet werden.
        """

        cursor = self.connection.execute(
            """
            DELETE FROM memories

            WHERE LOWER(TRIM(information))
                = LOWER(TRIM(?))
            """,
            (information,)
        )

        self.connection.commit()

        return cursor.rowcount

    # ============================================================
    # ANZAHL
    # ============================================================

    def count(self):

        cursor = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM memories
            """
        )

        row = cursor.fetchone()

        return row[0] if row else 0

    # ============================================================
    # DATENBANK SCHLIESSEN
    # ============================================================

    def close(self):

        if self.connection:

            self.connection.close()

    # ============================================================
    # KONTEXTMANAGER
    # ============================================================

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):
        self.close()