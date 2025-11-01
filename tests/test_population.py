# tests/test_population.py
from src.semantic_mapper import SemanticMapper
from src.population_graph import concepts_from_graph

def test_concepts_extraction_from_single_bundle(tmp_path):
    # Minimal single-bundle with fever + tachycardia scenario
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType":"Patient","id":"p1","name":[{"family":"Doe","given":["A"]}]}},
            {"resource": {
                "resourceType":"Observation","id":"o1","status":"final",
                "code":{"text":"Body temperature","coding":[{"system":"http://loinc.org","code":"8310-5"}]},
                "subject":{"reference":"Patient/p1"},
                "valueQuantity":{"value":38.6,"unit":"Celsius"}
            }},
            {"resource": {
                "resourceType":"Observation","id":"o2","status":"final",
                "code":{"text":"Heart rate","coding":[{"system":"http://loinc.org","code":"8867-4"}]},
                "subject":{"reference":"Patient/p1"},
                "valueQuantity":{"value":112,"unit":"beats/minute"}
            }},
        ]
    }
    p = tmp_path / "b.json"
    p.write_text(__import__("json").dumps(bundle))

    g = SemanticMapper().load_bundle(p).graph.to_jsonable()
    C = concepts_from_graph(g)

    # Expect derived Finding/Fever and Finding/Tachycardia, plus Code nodes
    assert any(c.startswith("Finding/") for c in C)
    assert "Finding/Fever" in C
    assert "Finding/Tachycardia" in C
    assert any(c.startswith("Code/http://loinc.org|") for c in C)
