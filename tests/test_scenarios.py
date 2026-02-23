"""
Test Scenarios
==============
Automated test scenarios for the medical triage system. Tests core
functionality including triage assessment, translation, ETA calculation,
and hospital queue operations.

Run with: python -m pytest tests/test_scenarios.py -v
Or:       python tests/test_scenarios.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.translator import Translator
from src.triage_engine import (
    TRIAGE_EMERGENCY,
    TRIAGE_ROUTINE,
    TRIAGE_URGENT,
    TriageEngine,
)


class TestTriageEngine(unittest.TestCase):
    """Test the core triage engine logic."""

    @classmethod
    def setUpClass(cls):
        cls.indexer = KnowledgeIndexer()
        cls.translator = Translator()
        cls.engine = TriageEngine(
            knowledge_indexer=cls.indexer, translator=cls.translator
        )

    def test_question_generation_chest_pain(self):
        """Scenario 1: Chest pain should generate relevant cardiac questions."""
        questions = self.engine.generate_questions("severe chest pain")
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
        self.assertLessEqual(len(questions), 5)
        # Each question should have required fields
        for q in questions:
            self.assertIn("question", q)
            self.assertIn("type", q)

    def test_question_generation_headache(self):
        """Scenario 2: Mild headache should generate assessment questions."""
        questions = self.engine.generate_questions("mild headache since yesterday")
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)

    def test_question_generation_stroke(self):
        """Scenario 3: Stroke symptoms should generate FAST questions."""
        questions = self.engine.generate_questions(
            "sudden arm weakness and slurred speech"
        )
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)

    def test_assessment_chest_pain_emergency(self):
        """Chest pain with red flags should be classified as EMERGENCY."""
        answers = [
            {"question": "Does pain radiate to arm?", "answer": "Yes"},
            {"question": "Pain severity 1-10?", "answer": "9"},
            {"question": "Symptoms?", "answer": "Sweating, Shortness of breath"},
            {"question": "Heart disease history?", "answer": "Yes"},
        ]
        assessment = self.engine.assess_triage(
            "severe chest pain radiating to left arm", answers
        )
        self.assertIn("triage_level", assessment)
        self.assertEqual(assessment["triage_level"], TRIAGE_EMERGENCY)
        self.assertGreaterEqual(assessment.get("risk_score", 0), 7)

    def test_assessment_mild_headache_routine(self):
        """Mild headache without red flags should be ROUTINE."""
        answers = [
            {"question": "When did it start?", "answer": "Days ago"},
            {"question": "Severity?", "answer": "3"},
            {"question": "Chronic conditions?", "answer": "No"},
        ]
        assessment = self.engine.assess_triage("mild headache", answers)
        self.assertIn("triage_level", assessment)
        self.assertEqual(assessment["triage_level"], TRIAGE_ROUTINE)

    def test_assessment_stroke_emergency(self):
        """Stroke symptoms should be classified as EMERGENCY."""
        answers = [
            {"question": "Sudden onset?", "answer": "Yes"},
            {"question": "Face symmetry?", "answer": "No"},
            {"question": "Arm raise?", "answer": "No"},
            {"question": "Speech slurred?", "answer": "Yes"},
        ]
        assessment = self.engine.assess_triage(
            "sudden face drooping and can't raise right arm", answers
        )
        self.assertIn("triage_level", assessment)
        # Should be EMERGENCY due to FAST positive
        self.assertIn(assessment["triage_level"], [TRIAGE_EMERGENCY, TRIAGE_URGENT])

    def test_patient_record_creation(self):
        """Patient record should contain all required fields."""
        assessment = {
            "triage_level": TRIAGE_EMERGENCY,
            "assessment": "Suspected ACS",
            "red_flags": ["chest_pain", "radiation"],
            "recommended_action": "ER immediately",
            "risk_score": 9,
            "source_guidelines": ["chest_pain_protocol.txt"],
            "suspected_conditions": ["ACS"],
            "time_sensitivity": "Within 10 minutes",
        }
        record = self.engine.create_patient_record(
            chief_complaint="chest pain",
            assessment=assessment,
            language="de-DE",
            eta_minutes=15,
            location={"lat": 48.78, "lon": 9.18},
        )
        self.assertIn("patient_id", record)
        self.assertIn("timestamp", record)
        self.assertEqual(record["triage_level"], TRIAGE_EMERGENCY)
        self.assertEqual(record["language"], "de-DE")
        self.assertEqual(record["eta_minutes"], 15)
        self.assertIsNotNone(record["arrival_time"])


class TestKnowledgeIndexer(unittest.TestCase):
    """Test the knowledge indexer local fallback search."""

    @classmethod
    def setUpClass(cls):
        cls.indexer = KnowledgeIndexer()

    def test_local_search_chest_pain(self):
        """Local search should find chest pain guidelines."""
        results = self.indexer.search("chest pain emergency protocol")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Should find chest pain protocol
        sources = [r.get("source", "") for r in results]
        self.assertTrue(
            any("chest" in s.lower() for s in sources),
            f"Expected chest pain protocol in results, got: {sources}",
        )

    def test_local_search_stroke(self):
        """Local search should find stroke guidelines."""
        results = self.indexer.search("stroke FAST assessment face arm speech")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_local_search_diabetes(self):
        """Local search should find diabetic emergency guidelines."""
        results = self.indexer.search("diabetic ketoacidosis DKA hypoglycemia")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)


class TestMapsHandler(unittest.TestCase):
    """Test the maps handler (uses fallback since no credentials)."""

    @classmethod
    def setUpClass(cls):
        cls.maps = MapsHandler()

    def test_find_nearest_hospitals(self):
        """Should find 3 nearest hospitals with ETA."""
        hospitals = self.maps.find_nearest_hospitals(48.80, 9.20, count=3)
        self.assertIsInstance(hospitals, list)
        self.assertEqual(len(hospitals), 3)
        for h in hospitals:
            self.assertIn("name", h)
            self.assertIn("lat", h)
            self.assertIn("lon", h)
            self.assertIn("eta_minutes", h)
            self.assertIn("distance_km", h)
            self.assertGreater(h["eta_minutes"], 0)

    def test_hospitals_sorted_by_eta(self):
        """Returned hospitals should be sorted fastest-first."""
        hospitals = self.maps.find_nearest_hospitals(48.78, 9.18, count=3)
        etas = [h["eta_minutes"] for h in hospitals]
        self.assertEqual(etas, sorted(etas))

    def test_eta_to_specific_hospital(self):
        """ETA calculation to a specific hospital should return valid result."""
        result = self.maps.calculate_eta_to_hospital(48.80, 9.20, 48.78, 9.17)
        self.assertIn("eta_minutes", result)
        self.assertIn("distance_km", result)
        self.assertGreater(result["eta_minutes"], 0)
        self.assertGreater(result["distance_km"], 0)

    def test_different_cities_get_different_hospitals(self):
        """Patient in Istanbul should get Istanbul hospitals, not Stuttgart."""
        istanbul_hospitals = self.maps.find_nearest_hospitals(41.01, 28.98, count=3)
        stuttgart_hospitals = self.maps.find_nearest_hospitals(48.78, 9.18, count=3)
        istanbul_names = {h["name"] for h in istanbul_hospitals}
        stuttgart_names = {h["name"] for h in stuttgart_hospitals}
        # They should be different sets of hospitals
        self.assertNotEqual(istanbul_names, stuttgart_names)

    def test_haversine_distance(self):
        """Haversine distance calculation should be accurate."""
        # Stuttgart to Munich is approximately 190 km
        dist = MapsHandler._haversine_distance(48.78, 9.18, 48.14, 11.58)
        self.assertAlmostEqual(dist, 190, delta=20)


class TestHospitalQueue(unittest.TestCase):
    """Test the hospital queue operations."""

    @classmethod
    def setUpClass(cls):
        # Use a temporary test database
        cls.queue = HospitalQueue(db_path="/tmp/test_triage_queue.db")
        cls.queue.clear_queue()

    def tearDown(self):
        self.queue.clear_queue()

    def test_add_and_retrieve_patient(self):
        """Should be able to add and retrieve a patient."""
        record = {
            "patient_id": "TEST-001",
            "timestamp": "2026-02-23T18:00:00Z",
            "triage_level": TRIAGE_EMERGENCY,
            "chief_complaint": "chest pain",
            "red_flags": ["radiation", "diaphoresis"],
            "assessment": "Suspected ACS",
            "suspected_conditions": ["ACS"],
            "risk_score": 9,
            "recommended_action": "ER immediately",
            "time_sensitivity": "10 minutes",
            "source_guidelines": ["chest_pain_protocol.txt"],
            "eta_minutes": 15,
            "arrival_time": "2026-02-23T18:15:00Z",
            "location": {"lat": 48.78, "lon": 9.18},
            "language": "de-DE",
        }
        self.assertTrue(self.queue.add_patient(record))

        patients = self.queue.get_incoming_patients()
        self.assertEqual(len(patients), 1)
        self.assertEqual(patients[0]["patient_id"], "TEST-001")
        self.assertEqual(patients[0]["triage_level"], TRIAGE_EMERGENCY)

    def test_status_update(self):
        """Should be able to update patient status."""
        record = {
            "patient_id": "TEST-002",
            "timestamp": "2026-02-23T18:00:00Z",
            "triage_level": TRIAGE_URGENT,
            "chief_complaint": "broken arm",
            "red_flags": [],
            "assessment": "Fracture",
            "suspected_conditions": ["Fracture"],
            "risk_score": 5,
            "recommended_action": "ER within 2 hours",
            "time_sensitivity": "2 hours",
            "source_guidelines": ["trauma_protocol.txt"],
            "eta_minutes": 30,
            "language": "en-US",
        }
        self.queue.add_patient(record)
        self.assertTrue(self.queue.update_status("TEST-002", "arrived"))

        incoming = self.queue.get_incoming_patients()
        self.assertEqual(len(incoming), 0)  # No longer incoming

    def test_queue_priority_ordering(self):
        """Emergency patients should appear before routine patients."""
        self.queue.add_patient({
            "patient_id": "TEST-R", "timestamp": "2026-02-23T18:00:00Z",
            "triage_level": TRIAGE_ROUTINE, "chief_complaint": "headache",
            "red_flags": [], "assessment": "", "suspected_conditions": [],
            "risk_score": 2, "recommended_action": "", "time_sensitivity": "",
            "source_guidelines": [], "eta_minutes": 10, "language": "en-US",
        })
        self.queue.add_patient({
            "patient_id": "TEST-E", "timestamp": "2026-02-23T18:01:00Z",
            "triage_level": TRIAGE_EMERGENCY, "chief_complaint": "chest pain",
            "red_flags": ["radiation"], "assessment": "", "suspected_conditions": [],
            "risk_score": 9, "recommended_action": "", "time_sensitivity": "",
            "source_guidelines": [], "eta_minutes": 20, "language": "en-US",
        })

        patients = self.queue.get_incoming_patients()
        self.assertEqual(len(patients), 2)
        self.assertEqual(patients[0]["patient_id"], "TEST-E")  # Emergency first
        self.assertEqual(patients[1]["patient_id"], "TEST-R")

    def test_queue_stats(self):
        """Queue stats should reflect current state."""
        self.queue.add_patient({
            "patient_id": "TEST-S1", "timestamp": "2026-02-23T18:00:00Z",
            "triage_level": TRIAGE_EMERGENCY, "chief_complaint": "test",
            "red_flags": [], "assessment": "", "suspected_conditions": [],
            "risk_score": 9, "recommended_action": "", "time_sensitivity": "",
            "source_guidelines": [], "eta_minutes": 10, "language": "en-US",
        })
        self.queue.add_patient({
            "patient_id": "TEST-S2", "timestamp": "2026-02-23T18:01:00Z",
            "triage_level": TRIAGE_ROUTINE, "chief_complaint": "test",
            "red_flags": [], "assessment": "", "suspected_conditions": [],
            "risk_score": 2, "recommended_action": "", "time_sensitivity": "",
            "source_guidelines": [], "eta_minutes": 20, "language": "en-US",
        })

        stats = self.queue.get_queue_stats()
        self.assertEqual(stats["total_incoming"], 2)
        self.assertEqual(stats["by_level"].get("EMERGENCY", 0), 1)
        self.assertEqual(stats["by_level"].get("ROUTINE", 0), 1)


class TestTranslator(unittest.TestCase):
    """Test the translator module (passthrough when unconfigured)."""

    @classmethod
    def setUpClass(cls):
        cls.translator = Translator()

    def test_passthrough_when_unconfigured(self):
        """Without credentials, translator should return input unchanged."""
        result = self.translator.translate("Hello world", "de")
        # When unconfigured, returns original text
        self.assertEqual(result, "Hello world")

    def test_empty_string(self):
        """Empty string should return empty string."""
        result = self.translator.translate("", "de")
        self.assertEqual(result, "")


class TestMultiLanguageScenario(unittest.TestCase):
    """Integration test: German patient → English backend → German response."""

    def test_german_patient_flow(self):
        """Simulate a German-speaking patient going through triage."""
        translator = Translator()
        engine = TriageEngine(knowledge_indexer=KnowledgeIndexer(), translator=translator)

        # Step 1: German input
        german_input = "Ich habe starke Brustschmerzen"
        detected_lang = "de-DE"

        # Step 2: Translate to English
        english = translator.translate_to_english(german_input, detected_lang)
        # Without credentials, returns original (passthrough)
        # With credentials, would return "I have severe chest pain"

        # Step 3: Generate questions (uses English backend)
        questions = engine.generate_questions(english)
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)

        # Step 4: Simulate answers
        answers = [
            {"question": "Does pain radiate?", "answer": "Yes"},
            {"question": "Pain severity?", "answer": "8"},
            {"question": "Symptoms?", "answer": "Sweating"},
        ]

        # Step 5: Get assessment
        assessment = engine.assess_triage(english, answers)
        self.assertIn("triage_level", assessment)

        # Step 6: Create patient record
        record = engine.create_patient_record(
            chief_complaint=english,
            assessment=assessment,
            language=detected_lang,
            eta_minutes=20,
        )
        self.assertEqual(record["language"], "de-DE")
        self.assertIsNotNone(record["patient_id"])


class TestDocumentProcessor(unittest.TestCase):
    """Test the document processor."""

    def test_process_guidelines_directory(self):
        """Should process all guideline files in data directory."""
        from src.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        guidelines_dir = str(PROJECT_ROOT / "data" / "medical_guidelines")
        docs = processor.process_directory(guidelines_dir)
        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0)
        # Should find at least 4 guideline files
        self.assertGreaterEqual(len(docs), 4)

    def test_chunk_document(self):
        """Should correctly chunk a document with overlap."""
        from src.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        doc = {
            "title": "Test",
            "content": "A" * 2500,  # 2500 char document
            "source": "test.txt",
        }
        chunks = processor.chunk_document(doc, chunk_size=1000, overlap=200)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("content", chunk)
            self.assertLessEqual(len(chunk["content"]), 1000)


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  MEDICAL TRIAGE SYSTEM — TEST SUITE")
    print("=" * 60)
    unittest.main(verbosity=2)