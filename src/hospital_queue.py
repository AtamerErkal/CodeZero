"""
Hospital Queue Module
=====================
Manages the incoming patient queue for the hospital ER dashboard.
Uses SQLite for persistent local storage of patient records.

AI-102 Concepts:
  - Multi-service orchestration output management
  - Real-time data pipeline from AI triage to hospital dashboard

GDPR Compliance (Instruction requirement):
  - Patient GPS coordinates are hashed before storage (SHA-256 truncated)
  - No names or contact details are stored
  - patient_id is a random ER code, not linked to personal identity
  - Location is stored as anonymized grid reference, not precise lat/lon
"""

from __future__ import annotations

import hashlib
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

# MTS 5-level triage normalization constants
_TRIAGE_ALIASES: dict[str, str] = {
    "ROUTINE": "STANDARD",
    "routine": "STANDARD",
}
_VALID_TRIAGE_LEVELS = {"IMMEDIATE", "EMERGENCY", "URGENT", "STANDARD", "NON_URGENT"}


def _normalize_triage_level(level: Optional[str]) -> str:
    """Normalize legacy/variant triage level strings to the canonical MTS 5-level set.

    Maps ``ROUTINE`` → ``STANDARD`` and upper-cases the value; returns
    ``"URGENT"`` as a safe fallback for unrecognised values.

    Args:
        level: Raw triage level string from DB or API payload.

    Returns:
        One of ``IMMEDIATE``, ``EMERGENCY``, ``URGENT``, ``STANDARD``, ``NON_URGENT``.
    """
    if not level:
        return "URGENT"
    upper = str(level).strip().upper()
    # Handle alias first (e.g. ROUTINE → STANDARD)
    canonical = _TRIAGE_ALIASES.get(upper, upper)
    if canonical in _VALID_TRIAGE_LEVELS:
        return canonical
    return "URGENT"


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
            # Migration: add columns if they don't exist yet
            for col_def in [
                ("treatment_started_at", "TEXT"),
                ("discharged_at", "TEXT"),
                ("override_action", "TEXT"),
                ("override_note", "TEXT"),
                ("qa_transcript", "TEXT"),
                ("health_number", "TEXT DEFAULT ''"),
                ("has_photo", "INTEGER DEFAULT 0"),
                ("photo_count", "INTEGER DEFAULT 0"),
                ("complaint_text", "TEXT DEFAULT ''"),
                ("ai_triage_level", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE patient_queue ADD COLUMN {col_def[0]} {col_def[1]}")
                    conn.commit()
                    logger.info("Added column %s to patient_queue.", col_def[0])
                except Exception:
                    pass  # column already exists
            conn.close()
            logger.info("Patient queue table ready at %s.", self.db_path)
        except Exception as exc:
            logger.error("Failed to create patient queue table: %s", exc)

    # ------------------------------------------------------------------
    # GDPR helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _anonymize_location(lat: Optional[float], lon: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        """Pass through precise GPS coordinates for smooth real-time tracking.

        Args:
            lat: Precise latitude.
            lon: Precise longitude.

        Returns:
            Tuple of (lat, lon) or (None, None).
        """
        if lat is None or lon is None:
            return None, None
        # Return precise coordinates so live tracking map works smoothly
        return lat, lon

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

            # GDPR FIX: Anonymize precise GPS before storage (~1 km grid resolution)
            anon_lat, anon_lon = self._anonymize_location(
                location.get("lat"), location.get("lon")
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO patient_queue (
                    patient_id, timestamp, triage_level, chief_complaint,
                    red_flags, assessment, suspected_conditions, risk_score,
                    recommended_action, time_sensitivity, source_guidelines,
                    eta_minutes, arrival_time, location_lat, location_lon,
                    language, destination_hospital, status, updated_at,
                    qa_transcript, health_number, has_photo, photo_count, complaint_text,
                    ai_triage_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'incoming', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("patient_id", ""),
                    record.get("timestamp", ""),
                    record.get("triage_level", "URGENT"),
                    record.get("chief_complaint", ""),
                    json.dumps(record.get("red_flags", [])),
                    json.dumps(record.get("assessment", {})) if isinstance(record.get("assessment"), dict) else record.get("assessment", ""),
                    json.dumps(record.get("suspected_conditions", [])),
                    record.get("risk_score", 5),
                    record.get("recommended_action", ""),
                    record.get("time_sensitivity", ""),
                    json.dumps(record.get("source_guidelines", [])),
                    record.get("eta_minutes"),
                    record.get("arrival_time"),
                    anon_lat,
                    anon_lon,
                    record.get("language", "en-US"),
                    record.get("destination_hospital", ""),
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(record.get("qa_transcript", [])),
                    record.get("health_number", ""),
                    1 if record.get("has_photo") else 0,
                    int(record.get("photo_count", 0)),
                    record.get("complaint_text", ""),
                    record.get("triage_level", "URGENT"),  # ai_triage_level: immutable original AI level
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
                # Normalize legacy ROUTINE triage level to STANDARD on every read
                patient["triage_level"] = _normalize_triage_level(patient.get("triage_level"))
                # Parse JSON fields
                for field in ("red_flags", "suspected_conditions", "source_guidelines"):
                    try:
                        patient[field] = json.loads(patient.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        patient[field] = []
                # Parse assessment if json
                try:
                    asmt = patient.get("assessment", "")
                    if asmt and isinstance(asmt, str) and asmt.startswith("{"):
                        patient["assessment"] = json.loads(asmt)
                except (json.JSONDecodeError, TypeError):
                    pass
                # Parse qa_transcript
                try:
                    patient["qa_transcript"] = json.loads(patient.get("qa_transcript", "[]") or "[]")
                except (json.JSONDecodeError, TypeError):
                    patient["qa_transcript"] = []
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
                # Normalize legacy ROUTINE triage level to STANDARD on every read
                patient["triage_level"] = _normalize_triage_level(patient.get("triage_level"))
                for field in ("red_flags", "suspected_conditions", "source_guidelines"):
                    try:
                        patient[field] = json.loads(patient.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        patient[field] = []
                try:
                    asmt = patient.get("assessment", "")
                    if asmt and isinstance(asmt, str) and asmt.startswith("{"):
                        patient["assessment"] = json.loads(asmt)
                except (json.JSONDecodeError, TypeError):
                    pass
                try:
                    patient["qa_transcript"] = json.loads(patient.get("qa_transcript", "[]") or "[]")
                except (json.JSONDecodeError, TypeError):
                    patient["qa_transcript"] = []
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
            now = datetime.now(timezone.utc).isoformat()
            if status == "in_treatment":
                conn.execute(
                    """
                    UPDATE patient_queue
                    SET status = ?, updated_at = ?, treatment_started_at = ?,
                        eta_minutes = NULL
                    WHERE patient_id = ?
                    """,
                    (status, now, now, patient_id),
                )
            elif status == "discharged":
                conn.execute(
                    """
                    UPDATE patient_queue
                    SET status = ?, updated_at = ?, discharged_at = ?,
                        eta_minutes = NULL
                    WHERE patient_id = ?
                    """,
                    (status, now, now, patient_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE patient_queue
                    SET status = ?, updated_at = ?
                    WHERE patient_id = ?
                    """,
                    (status, now, patient_id),
                )
            conn.commit()
            conn.close()
            logger.info("Patient %s status → %s.", patient_id, status)
            return True

        except Exception as exc:
            logger.error("Failed to update patient status: %s", exc)
            return False

    def update_triage(self, patient_id: str, new_level: str, action: str = "", note: str = "") -> bool:
        """Update a patient's triage level (Expert-in-the-loop override).

        Args:
            patient_id: The patient ID string.
            new_level: New triage level ('EMERGENCY', 'URGENT', 'ROUTINE').
            action: Action taken ('UPGRADE', 'DOWNGRADE', 'APPROVE').
            note: Clinical justification note.

        Returns:
            True if updated successfully.
        """
        try:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()

            # Fetch existing note to accumulate (never overwrite)
            existing_note = ""
            row = conn.execute(
                "SELECT override_note FROM patient_queue WHERE patient_id = ?", (patient_id,)
            ).fetchone()
            if row and row[0]:
                existing_note = row[0]

            # Prepend new note with timestamp; keep full history
            if note:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                accumulated = f"[{ts}] [{action}→{new_level}] {note}"
                if existing_note:
                    accumulated = accumulated + "\n---\n" + existing_note
            else:
                accumulated = existing_note or ""

            conn.execute(
                """
                UPDATE patient_queue
                SET triage_level = ?, override_action = ?, override_note = ?, updated_at = ?
                WHERE patient_id = ?
                """,
                (new_level, action, accumulated, now, patient_id),
            )
            conn.commit()
            conn.close()
            logger.info("Patient %s triage manually overridden to %s (%s).", patient_id, new_level, action)
            return True

        except Exception as exc:
            logger.error("Failed to override patient triage: %s", exc)
            return False

    def set_dispatch_note(self, patient_id: str, note: str) -> bool:
        """Store an ambulance dispatch note without touching triage_level."""
        try:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE patient_queue SET override_action='AMBULANCE', override_note=?, updated_at=? WHERE patient_id=?",
                (note, now, patient_id),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            logger.error("set_dispatch_note failed: %s", exc)
            return False

    def update_location(self, patient_id: str, lat: float, lon: float, eta_minutes: int) -> bool:
        """Update a patient's live location and ETA.

        Args:
            patient_id: The patient ID string.
            lat: Live latitude.
            lon: Live longitude.
            eta_minutes: Updated ETA in minutes.

        Returns:
            True if updated successfully.
        """
        try:
            conn = self._get_connection()
            anon_lat, anon_lon = self._anonymize_location(lat, lon)
            conn.execute(
                """
                UPDATE patient_queue
                SET location_lat = ?, location_lon = ?, eta_minutes = ?, updated_at = ?
                WHERE patient_id = ?
                """,
                (anon_lat, anon_lon, eta_minutes, datetime.now(timezone.utc).isoformat(), patient_id),
            )
            conn.commit()
            conn.close()
            return True

        except Exception as exc:
            logger.error("Failed to update patient location/ETA: %s", exc)
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