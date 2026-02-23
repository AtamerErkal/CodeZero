"""
Hospital Queue Module
=====================
Manages the incoming patient queue for the hospital ER dashboard.
Uses SQLite for persistent local storage of patient records.

AI-102 Concepts:
  - Multi-service orchestration output management
  - Real-time data pipeline from AI triage to hospital dashboard
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Database file location
DB_PATH = Path(__file__).parent.parent / "patient_queue.db"


class HospitalQueue:
    """Manages the queue of incoming triaged patients.

    Stores patient records in a local SQLite database. The hospital
    dashboard reads from this queue to display incoming patients
    with countdown timers and pre-arrival preparation checklists.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the Hospital Queue.

        Args:
            db_path: Optional custom path to the SQLite database.
        """
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row_factory.

        Returns:
            SQLite connection with dict-like row access.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _create_table(self) -> None:
        """Create the patient queue table if it doesn't exist."""
        try:
            conn = self._get_connection()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patient_queue (
                    patient_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    triage_level TEXT NOT NULL,
                    chief_complaint TEXT NOT NULL,
                    red_flags TEXT,
                    assessment TEXT,
                    suspected_conditions TEXT,
                    risk_score INTEGER DEFAULT 5,
                    recommended_action TEXT,
                    time_sensitivity TEXT,
                    source_guidelines TEXT,
                    eta_minutes INTEGER,
                    arrival_time TEXT,
                    location_lat REAL,
                    location_lon REAL,
                    language TEXT DEFAULT 'en-US',
                    destination_hospital TEXT DEFAULT '',
                    status TEXT DEFAULT 'incoming',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            conn.close()
            logger.info("Patient queue table ready at %s.", self.db_path)
        except Exception as exc:
            logger.error("Failed to create patient queue table: %s", exc)

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def add_patient(self, record: dict) -> bool:
        """Add a new patient record to the queue.

        Args:
            record: Patient record dict from TriageEngine.create_patient_record().

        Returns:
            True if the patient was added successfully.
        """
        try:
            conn = self._get_connection()
            location = record.get("location") or {}
            conn.execute(
                """
                INSERT OR REPLACE INTO patient_queue (
                    patient_id, timestamp, triage_level, chief_complaint,
                    red_flags, assessment, suspected_conditions, risk_score,
                    recommended_action, time_sensitivity, source_guidelines,
                    eta_minutes, arrival_time, location_lat, location_lon,
                    language, destination_hospital, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'incoming', ?)
                """,
                (
                    record.get("patient_id", ""),
                    record.get("timestamp", ""),
                    record.get("triage_level", "URGENT"),
                    record.get("chief_complaint", ""),
                    json.dumps(record.get("red_flags", [])),
                    record.get("assessment", ""),
                    json.dumps(record.get("suspected_conditions", [])),
                    record.get("risk_score", 5),
                    record.get("recommended_action", ""),
                    record.get("time_sensitivity", ""),
                    json.dumps(record.get("source_guidelines", [])),
                    record.get("eta_minutes"),
                    record.get("arrival_time"),
                    location.get("lat"),
                    location.get("lon"),
                    record.get("language", "en-US"),
                    record.get("destination_hospital", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            logger.info("Patient %s added to queue.", record.get("patient_id"))
            return True

        except Exception as exc:
            logger.error("Failed to add patient to queue: %s", exc)
            return False

    def get_incoming_patients(self, limit: int = 20) -> list[dict]:
        """Get all incoming (not yet arrived) patients, ordered by priority.

        Emergency patients appear first, then by ETA.

        Args:
            limit: Maximum number of records.

        Returns:
            List of patient record dicts.
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """
                SELECT * FROM patient_queue
                WHERE status = 'incoming'
                ORDER BY
                    CASE triage_level
                        WHEN 'EMERGENCY' THEN 1
                        WHEN 'URGENT' THEN 2
                        WHEN 'ROUTINE' THEN 3
                        ELSE 4
                    END,
                    eta_minutes ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()

            patients = []
            for row in rows:
                patient = dict(row)
                # Parse JSON fields
                for field in ("red_flags", "suspected_conditions", "source_guidelines"):
                    try:
                        patient[field] = json.loads(patient.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        patient[field] = []
                patients.append(patient)

            return patients

        except Exception as exc:
            logger.error("Failed to get incoming patients: %s", exc)
            return []

    def get_all_patients(self, limit: int = 50) -> list[dict]:
        """Get all patients regardless of status.

        Args:
            limit: Maximum number of records.

        Returns:
            List of patient record dicts.
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """
                SELECT * FROM patient_queue
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()

            patients = []
            for row in rows:
                patient = dict(row)
                for field in ("red_flags", "suspected_conditions", "source_guidelines"):
                    try:
                        patient[field] = json.loads(patient.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        patient[field] = []
                patients.append(patient)

            return patients

        except Exception as exc:
            logger.error("Failed to get all patients: %s", exc)
            return []

    def update_status(self, patient_id: str, status: str) -> bool:
        """Update a patient's status.

        Args:
            patient_id: The patient ID string.
            status: New status ('incoming', 'arrived', 'in_treatment', 'discharged').

        Returns:
            True if updated successfully.
        """
        try:
            conn = self._get_connection()
            conn.execute(
                """
                UPDATE patient_queue
                SET status = ?, updated_at = ?
                WHERE patient_id = ?
                """,
                (status, datetime.now(timezone.utc).isoformat(), patient_id),
            )
            conn.commit()
            conn.close()
            logger.info("Patient %s status → %s.", patient_id, status)
            return True

        except Exception as exc:
            logger.error("Failed to update patient status: %s", exc)
            return False

    def get_queue_stats(self) -> dict:
        """Get summary statistics for the current queue.

        Returns:
            Dict with counts by triage level and status.
        """
        try:
            conn = self._get_connection()

            # Count by triage level (incoming only)
            cursor = conn.execute(
                """
                SELECT triage_level, COUNT(*) as count
                FROM patient_queue
                WHERE status = 'incoming'
                GROUP BY triage_level
                """
            )
            level_counts = {row["triage_level"]: row["count"] for row in cursor.fetchall()}

            # Count by status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM patient_queue
                GROUP BY status
                """
            )
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Total incoming
            total_incoming = sum(level_counts.values())

            conn.close()

            return {
                "total_incoming": total_incoming,
                "by_level": level_counts,
                "by_status": status_counts,
            }

        except Exception as exc:
            logger.error("Failed to get queue stats: %s", exc)
            return {"total_incoming": 0, "by_level": {}, "by_status": {}}

    def clear_queue(self) -> bool:
        """Clear all patients from the queue. Used for testing.

        Returns:
            True if cleared successfully.
        """
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM patient_queue")
            conn.commit()
            conn.close()
            logger.info("Patient queue cleared.")
            return True
        except Exception as exc:
            logger.error("Failed to clear queue: %s", exc)
            return False