"""
CodeZero Integration Test Suite
================================
Tests all API endpoints and dashboard integration.

Run:
    # Start server first
    python hospital_server.py

    # Then in another terminal:
    python test_integration.py
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime, timezone

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

# Test data
TEST_PATIENT = {
    "complaint": "I have severe chest pain",
    "complaint_en": "I have severe chest pain",
    "detected_language": "en-US",
    "demographics": {
        "age_range": "45-64",
        "sex": "M"
    },
    "assessment": {
        "triage_level": "EMERGENCY",
        "chief_complaint": "Chest pain with radiation to left arm",
        "red_flags": ["Crushing chest pain", "Radiation to arm", "Sweating"],
        "assessment": "Possible acute coronary syndrome - requires immediate evaluation",
        "suspected_conditions": ["Acute Myocardial Infarction", "Unstable Angina"],
        "risk_score": 9,
        "recommended_action": "Call emergency services immediately. Transfer to cardiac catheterization lab.",
        "time_sensitivity": "IMMEDIATE - minutes matter",
        "source_guidelines": ["chest_pain_protocol"]
    },
    "hospital": {
        "name": "Universitätsklinikum Ulm",
        "address": "Albert-Einstein-Allee 23, 89081 Ulm",
        "lat": 48.4037,
        "lon": 9.9669,
        "distance_km": 8.5,
        "eta_minutes": 12,
        "occupancy": "Medium"
    },
    "lat": 48.3936,
    "lon": 10.1208,
    "answers": [
        {
            "question": "When did the chest pain start?",
            "answer": "About 30 minutes ago",
            "original_answer": "About 30 minutes ago"
        },
        {
            "question": "Does the pain radiate anywhere?",
            "answer": "Yes, to my left arm and jaw",
            "original_answer": "Yes, to my left arm and jaw"
        }
    ],
    "has_photo": False,
    "photo_count": 0,
    "reg_number": "TEST-001",
    "data_consent": True
}

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def log_test(name: str):
    """Print test header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST: {name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def log_success(msg: str):
    """Print success message."""
    print(f"{GREEN}✓ {msg}{RESET}")


def log_error(msg: str):
    """Print error message."""
    print(f"{RED}✗ {msg}{RESET}")


def log_info(msg: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {msg}{RESET}")


def test_server_health():
    """Test if server is running."""
    log_test("Server Health Check")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            log_success("Server is running")
            return True
        else:
            log_error(f"Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log_error("Cannot connect to server. Is it running on port 8001?")
        log_info("Start server with: python hospital_server.py")
        return False
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        return False


def test_stats_endpoint():
    """Test /api/stats endpoint."""
    log_test("Stats Endpoint")
    try:
        response = requests.get(f"{API_BASE}/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log_success("Stats endpoint working")
            log_info(f"Total patients: {data.get('total', 0)}")
            log_info(f"Incoming: {data.get('incoming', 0)}")
            log_info(f"Emergencies: {data.get('emergencies', 0)}")
            log_info(f"En route: {data.get('en_route', 0)}")
            return True, data
        else:
            log_error(f"Stats endpoint failed with status {response.status_code}")
            return False, None
    except Exception as e:
        log_error(f"Stats endpoint error: {e}")
        return False, None


def test_patients_endpoint():
    """Test /api/patients endpoint."""
    log_test("Patients List Endpoint")
    try:
        response = requests.get(f"{API_BASE}/patients?limit=10", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log_success(f"Patients endpoint working - {len(data)} patients")
            
            # Check patient data structure
            if data:
                patient = data[0]
                required_fields = [
                    "patient_id", "triage_level", "chief_complaint",
                    "timestamp", "eta_display"
                ]
                missing = [f for f in required_fields if f not in patient]
                if missing:
                    log_error(f"Missing fields in patient data: {missing}")
                else:
                    log_success("All required patient fields present")
                    log_info(f"Sample patient ID: {patient.get('patient_id')}")
                    log_info(f"Triage level: {patient.get('triage_level')}")
            return True, data
        else:
            log_error(f"Patients endpoint failed with status {response.status_code}")
            return False, None
    except Exception as e:
        log_error(f"Patients endpoint error: {e}")
        return False, None


def test_hospitals_endpoint():
    """Test /api/patient/hospitals endpoint."""
    log_test("Hospitals Search Endpoint")
    try:
        # Nersingen coordinates
        params = {
            "lat": 48.3936,
            "lon": 10.1208,
            "country": "DE",
            "n": 5
        }
        response = requests.get(f"{API_BASE}/patient/hospitals", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_success(f"Hospitals endpoint working - found {len(data)} hospitals")
            
            if data:
                hospital = data[0]
                log_info(f"Nearest: {hospital.get('name')}")
                log_info(f"Distance: {hospital.get('distance_km')} km")
                log_info(f"ETA: {hospital.get('eta_minutes')} min")
                
                # Verify required fields
                required = ["name", "lat", "lon", "distance_km", "eta_minutes"]
                missing = [f for f in required if f not in hospital]
                if missing:
                    log_error(f"Missing hospital fields: {missing}")
                else:
                    log_success("All required hospital fields present")
            return True, data
        else:
            log_error(f"Hospitals endpoint failed with status {response.status_code}")
            return False, None
    except Exception as e:
        log_error(f"Hospitals endpoint error: {e}")
        return False, None


def test_submit_patient():
    """Test /api/patient/submit endpoint."""
    log_test("Submit Patient Endpoint")
    try:
        response = requests.post(
            f"{API_BASE}/patient/submit",
            json=TEST_PATIENT,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_success("Patient submission successful")
            log_info(f"Patient ID: {data.get('patient_id')}")
            
            # Wait a moment for DB write
            time.sleep(0.5)
            
            # Verify patient appears in queue
            verify_response = requests.get(f"{API_BASE}/patients", timeout=5)
            if verify_response.status_code == 200:
                patients = verify_response.json()
                submitted_patient = next(
                    (p for p in patients if p.get("patient_id") == data.get("patient_id")),
                    None
                )
                if submitted_patient:
                    log_success("Patient found in queue")
                    log_info(f"Triage: {submitted_patient.get('triage_level')}")
                    log_info(f"Status: {submitted_patient.get('status')}")
                else:
                    log_error("Patient not found in queue after submission")
            
            return True, data
        else:
            log_error(f"Submit failed with status {response.status_code}")
            log_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        log_error(f"Submit endpoint error: {e}")
        return False, None


def test_transcribe_endpoint():
    """Test /api/patient/transcribe endpoint."""
    log_test("Audio Transcription Endpoint")
    
    # Create a dummy audio file for testing
    test_audio = Path(__file__).parent / "test_audio.webm"
    if not test_audio.exists():
        log_info("Skipping transcription test - no test audio file")
        log_info("This endpoint requires actual audio data to test")
        return True, None
    
    try:
        with open(test_audio, "rb") as f:
            files = {"audio": ("test.webm", f, "audio/webm")}
            response = requests.post(
                f"{API_BASE}/patient/transcribe",
                files=files,
                timeout=30
            )
        
        if response.status_code == 200:
            data = response.json()
            log_success("Transcription endpoint working")
            log_info(f"Detected language: {data.get('language')}")
            log_info(f"Transcribed text: {data.get('text', '')[:50]}...")
            return True, data
        else:
            log_error(f"Transcription failed with status {response.status_code}")
            return False, None
    except Exception as e:
        log_error(f"Transcription endpoint error: {e}")
        return False, None


def test_questions_endpoint():
    """Test /api/patient/questions endpoint."""
    log_test("Questions Generation Endpoint")
    try:
        request_data = {
            "complaint": "I have a severe headache",
            "detected_language": "en-US",
            "demographics": {
                "age_range": "25-44",
                "sex": "F"
            }
        }
        
        response = requests.post(
            f"{API_BASE}/patient/questions",
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success("Questions endpoint working")
            log_info(f"Generated {len(data.get('questions', []))} questions")
            log_info(f"Complaint in English: {data.get('complaint_en')}")
            
            if data.get('questions'):
                log_info(f"First question: {data['questions'][0]}")
            
            return True, data
        else:
            log_error(f"Questions endpoint failed with status {response.status_code}")
            log_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        log_error(f"Questions endpoint error: {e}")
        return False, None


def test_assess_endpoint():
    """Test /api/patient/assess endpoint."""
    log_test("Assessment Endpoint")
    try:
        request_data = {
            "complaint": "I have severe chest pain",
            "complaint_en": "I have severe chest pain",
            "detected_language": "en-US",
            "questions": [
                "When did the pain start?",
                "Does it radiate anywhere?",
                "Are you experiencing shortness of breath?"
            ],
            "answers": [
                {"question": "When did the pain start?", "answer": "30 minutes ago"},
                {"question": "Does it radiate anywhere?", "answer": "Yes, to my left arm"},
                {"question": "Are you experiencing shortness of breath?", "answer": "Yes"}
            ],
            "demographics": {
                "age_range": "45-64",
                "sex": "M"
            },
            "has_photo": False,
            "photo_count": 0
        }
        
        response = requests.post(
            f"{API_BASE}/patient/assess",
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success("Assessment endpoint working")
            log_info(f"Triage level: {data.get('triage_level')}")
            log_info(f"Risk score: {data.get('risk_score')}/10")
            log_info(f"Time sensitivity: {data.get('time_sensitivity')}")
            
            # Verify required assessment fields
            required = [
                "triage_level", "chief_complaint", "assessment",
                "risk_score", "recommended_action"
            ]
            missing = [f for f in required if f not in data]
            if missing:
                log_error(f"Missing assessment fields: {missing}")
            else:
                log_success("All required assessment fields present")
            
            return True, data
        else:
            log_error(f"Assessment endpoint failed with status {response.status_code}")
            log_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        log_error(f"Assessment endpoint error: {e}")
        return False, None


def test_dashboard_integration():
    """Test full patient flow from submission to dashboard display."""
    log_test("Complete Dashboard Integration")
    
    # Step 1: Submit a test patient
    log_info("Step 1: Submitting test patient...")
    success, submit_data = test_submit_patient()
    if not success:
        log_error("Dashboard integration test failed at submission")
        return False
    
    patient_id = submit_data.get("patient_id")
    
    # Step 2: Verify patient appears in stats
    log_info("Step 2: Checking stats update...")
    time.sleep(0.5)
    success, stats = test_stats_endpoint()
    if not success or stats.get("incoming", 0) == 0:
        log_error("Patient not reflected in stats")
        return False
    
    # Step 3: Verify patient appears in patients list
    log_info("Step 3: Checking patient list...")
    success, patients = test_patients_endpoint()
    if not success:
        log_error("Could not fetch patients list")
        return False
    
    test_patient_found = any(p.get("patient_id") == patient_id for p in patients)
    if test_patient_found:
        log_success(f"Test patient {patient_id} found in dashboard queue")
    else:
        log_error(f"Test patient {patient_id} not found in queue")
        return False
    
    # Step 4: Verify patient data integrity
    log_info("Step 4: Verifying patient data integrity...")
    patient_data = next(p for p in patients if p.get("patient_id") == patient_id)
    
    checks = [
        ("Triage level", patient_data.get("triage_level") == "EMERGENCY"),
        ("Has complaint", bool(patient_data.get("chief_complaint"))),
        ("Has assessment", bool(patient_data.get("assessment"))),
        ("Has ETA", patient_data.get("eta_minutes") is not None),
        ("Has location", patient_data.get("location") is not None),
        ("Status is incoming", patient_data.get("status") == "incoming"),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        if passed:
            log_success(f"  {check_name}")
        else:
            log_error(f"  {check_name}")
            all_passed = False
    
    if all_passed:
        log_success("Dashboard integration test PASSED")
        return True
    else:
        log_error("Dashboard integration test FAILED - some checks did not pass")
        return False


def run_all_tests():
    """Run complete test suite."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}CodeZero Integration Test Suite{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{YELLOW}Target: {BASE_URL}{RESET}")
    print(f"{YELLOW}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    # Track results
    results = {}
    
    # Test 1: Server health
    results["Server Health"] = test_server_health()
    if not results["Server Health"]:
        print(f"\n{RED}Tests aborted - server not available{RESET}")
        return
    
    # Test 2: Stats
    success, _ = test_stats_endpoint()
    results["Stats Endpoint"] = success
    
    # Test 3: Patients
    success, _ = test_patients_endpoint()
    results["Patients Endpoint"] = success
    
    # Test 4: Hospitals
    success, _ = test_hospitals_endpoint()
    results["Hospitals Endpoint"] = success
    
    # Test 5: Questions
    success, _ = test_questions_endpoint()
    results["Questions Endpoint"] = success
    
    # Test 6: Assessment
    success, _ = test_assess_endpoint()
    results["Assessment Endpoint"] = success
    
    # Test 7: Transcription (optional)
    success, _ = test_transcribe_endpoint()
    results["Transcription Endpoint"] = success
    
    # Test 8: Complete integration
    results["Dashboard Integration"] = test_dashboard_integration()
    
    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {test_name:.<50} {status}")
    
    print(f"\n{YELLOW}Results: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"{GREEN}🎉 All tests passed!{RESET}")
    else:
        print(f"{RED}❌ Some tests failed{RESET}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)