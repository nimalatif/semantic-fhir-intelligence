# src/synth_data.py
"""
Generate synthetic FHIR Bundle files (one per patient) into data/bundles/.
Keeps it small and deterministic: each patient may have temperature, heart rate,
and optional SpO2. We vary values to create co-occurring patterns like
(Fever, Tachycardia), (No fever, Normal HR), etc.
"""

from __future__ import annotations
from pathlib import Path
import json, random

OUT_DIR = Path("data/bundles")
random.seed(1234)

def make_patient_bundle(pid: int) -> dict:
    """
    Produce a tiny FHIR Bundle with:
      - Patient
      - Observation: Body temperature (LOINC 8310-5)
      - Observation: Heart rate (LOINC 8867-4)
      - Optional Observation: SpO2 (LOINC 59408-5-ish, we’ll treat it as saturation)
    Some patients will have fever (>38.0 C), some tachycardia (>100 bpm),
    some low SpO2 (<92).
    """
    # Choose a simple phenotype
    # weights tilt toward “mildly sick” to create co-occurrences
    phenotype = random.choices(
        population=[
            "normal",
            "fever_only",
            "tachy_only",
            "fever_tachy",
            "low_spo2",
            "fever_tachy_low_spo2",
        ],
        weights=[2, 2, 2, 4, 1, 2],
        k=1,
    )[0]

    temp = 37.0
    hr   = 80
    spo2 = 97

    if phenotype in ("fever_only", "fever_tachy", "fever_tachy_low_spo2"):
        temp = round(random.uniform(38.2, 39.4), 1)
    if phenotype in ("tachy_only", "fever_tachy", "fever_tachy_low_spo2"):
        hr = random.randint(105, 125)
    if phenotype in ("low_spo2", "fever_tachy_low_spo2"):
        spo2 = random.randint(86, 91)

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": f"p{pid}",
                    "gender": random.choice(["male", "female"]),
                    "birthDate": f"{random.randint(1960, 1995)}-01-01",
                    "name": [{"family": "Doe", "given": [f"Pat{pid}"]}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"obs_temp_{pid}",
                    "status": "final",
                    "code": {
                        "text": "Body temperature",
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8310-5",
                            "display": "Body temperature"
                        }]
                    },
                    "subject": {"reference": f"Patient/p{pid}"},
                    "valueQuantity": {"value": temp, "unit": "Celsius"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"obs_hr_{pid}",
                    "status": "final",
                    "code": {
                        "text": "Heart rate",
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8867-4",
                            "display": "Heart rate"
                        }]
                    },
                    "subject": {"reference": f"Patient/p{pid}"},
                    "valueQuantity": {"value": hr, "unit": "beats/minute"},
                }
            },
        ]
    }

    # Optional SpO2
    if random.random() < 0.5 or phenotype in ("low_spo2", "fever_tachy_low_spo2"):
        bundle["entry"].append({
            "resource": {
                "resourceType": "Observation",
                "id": f"obs_spo2_{pid}",
                "status": "final",
                "code": {
                    "text": "Oxygen saturation",
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "59408-5",
                        "display": "Oxygen saturation in Arterial blood by Pulse oximetry"
                    }]
                },
                "subject": {"reference": f"Patient/p{pid}"},
                "valueQuantity": {"value": spo2, "unit": "%"},
            }
        })

    return bundle

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n = 60  # number of synthetic patients to generate
    for i in range(n):
        b = make_patient_bundle(i)
        fp = OUT_DIR / f"bundle_{i:03d}.json"
        fp.write_text(json.dumps(b, indent=2), encoding="utf-8")
    print(f"✅ Wrote {n} synthetic bundles to {OUT_DIR}/")

if __name__ == "__main__":
    main()
