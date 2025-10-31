# Semantic FHIR Intelligence

**Goal:** Turn raw FHIR Bundles into a simple **semantic graph** (nodes + edges) and derive **clinical findings** with transparent, rule-based logic. Great for decision-support prototypes, interoperability demos, and explainable health AI.

---

## Why this matters (business + tech)

Healthcare data is exchanged as *facts* (e.g., “Temp=38.6 °C”, “LOINC 8310-5”). What’s missing is the **meaning** (e.g., “this implies Fever”, “HR=112 → Tachycardia”).  
This project adds a small but powerful semantic layer:

- **From data to meaning:** FHIR → graph → derived “Findings”
- **Explainable:** each finding is backed by explicit rules and traceable edges
- **Composable:** add rules for your domain (sepsis screen, anticoagulation warnings, etc.)

---

## Repo structure

```
semantic-fhir-intelligence/
├─ data/
│  └─ sample_bundle.json          # example FHIR Bundle (Patient + Observations)
├─ src/
│  ├─ __init__.py
│  └─ semantic_mapper.py          # FHIR → graph + toy rules (Fever, Tachycardia)
├─ tests/
│  └─ test_rules.py               # pytest: verifies rules fire correctly
├─ notebooks/
│  └─ 01_fhir_exploration.ipynb   # (optional) analysis/viz playground
├─ graph.json                     # sample output (generated)
├─ pytest.ini                     # adds project root to PYTHONPATH for tests
└─ README.md
```

---

## Quickstart

### 1️⃣ Run the mapper (CLI)

```bash
python -m src.semantic_mapper data/sample_bundle.json -o graph.json
```

**Output:** `graph.json` with:
- Nodes: `Patient`, `Observation`, `Code`, derived `Finding/*`
- Edges: `HAS_SUBJECT`, `HAS_CODE`, `HAS_FINDING`

---

### 2️⃣ Current toy rules

- **Fever** if **LOINC 8310-5** (Body temperature) **> 38.0 °C**
- **Tachycardia** if **LOINC 8867-4** (Heart rate) **> 100 bpm**

> Try editing `data/sample_bundle.json` to temp `38.6` or HR `112` and re-run.

---

### 3️⃣ Run tests

```bash
pytest -q
```

---

## Example output

```json
{
  "nodes": {
    "Patient/example": { "...": "..." },
    "Observation/obs1": { "type": "Observation", "props": { "code": "Body temperature", "value": "38.5 Celsius" } },
    "Code/http://loinc.org|8310-5": { "type": "Code", "props": { "system": "http://loinc.org", "code": "8310-5" } },
    "Finding/Fever": { "type": "Finding", "props": { "label": "Fever" } }
  },
  "edges": [
    { "src": "Observation/obs1", "dst": "Patient/example", "rel": "HAS_SUBJECT" },
    { "src": "Observation/obs1", "dst": "Code/http://loinc.org|8310-5", "rel": "HAS_CODE" },
    { "src": "Patient/example", "dst": "Finding/Fever", "rel": "HAS_FINDING" }
  ]
}
```

---

## Architecture (Mermaid)

```mermaid
flowchart LR
  A[ FHIR Bundle JSON ] --> B[Ingest & Normalize]
  B --> C[Graph Builder\nNodes: Patient, Observation, Code\nEdges: HAS_SUBJECT, HAS_CODE]
  C --> D[Rule Engine]
  D -->|Temp > 38C (8310-5)| F[Finding/Fever]
  D -->|HR > 100 bpm (8867-4)| G[Finding/Tachycardia]
  C --> H[Graph JSON Export]
  F --> H
  G --> H
```

---

## How to extend (add your own clinical logic)

1. Add new observations/conditions to the **Bundle** (`data/sample_bundle.json`).
2. Implement a rule in `src/semantic_mapper.py`:
   - Add a helper like `_rule_hypoxia_spo2_under_92()`
   - Look up the right LOINC/SNOMED code(s)
   - Parse numeric value, compare to threshold
   - Create a node like `"Finding/Hypoxia"` and connect `Patient → HAS_FINDING`
3. Register the rule in `_derive_simple_facts()`.

> Keep rules simple and explicit; PR reviewers love transparency.

---

## Dev notes

- **Zero external deps** required. Optional:  
  ```bash
  pip install networkx matplotlib
  ```
  Then in a notebook you can call:
  ```python
  from src.semantic_mapper import SemanticMapper
  G = SemanticMapper().load_bundle("data/sample_bundle.json").graph.to_networkx()
  ```

- **Testing:** `pytest -q`  
- **Style:** keep rules small, deterministic, and unit-tested.

---

## Roadmap

- [ ] More vitals rules (BP categories, RR > 20, SpO₂ < 92%)  
- [ ] Medication → Indication/Response links (Condition ↔ MedicationStatement)  
- [ ] SNOMED CT findings mapping (human-readable labels)  
- [ ] JSON-LD / RDF export (optional)  
- [ ] Simple UI to render the graph and findings

---

## Data & privacy

Use only **synthetic** or **de-identified** data.  
Do **not** commit PHI or PII.

---

## License

MIT (or your choice). Add a `LICENSE` file if you plan to open source.
