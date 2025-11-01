import json
from pathlib import Path
from src.semantic_mapper import SemanticMapper

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_bundle.json"

def j(g): return g["nodes"]

def test_tachycardia_rule_triggers():
    g = SemanticMapper().load_bundle(DATA).graph.to_jsonable()
    assert "Finding/Tachycardia" in j(g)

def test_fever_rule_triggers_when_over_38():
    bundle = json.loads(Path(DATA).read_text())
    # force temp > 38 for the temperature obs
    for e in bundle["entry"]:
        r = e.get("resource", {})
        if r.get("resourceType") == "Observation":
            for c in r.get("code", {}).get("coding", []):
                if c.get("system") == "http://loinc.org" and c.get("code") == "8310-5":
                    r["valueQuantity"]["value"] = 38.6
    tmp = Path("tests/tmp_bundle.json")
    tmp.write_text(json.dumps(bundle))
    g = SemanticMapper().load_bundle(tmp).graph.to_jsonable()
    tmp.unlink(missing_ok=True)
    assert "Finding/Fever" in j(g)
