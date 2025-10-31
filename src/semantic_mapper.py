# src/semantic_mapper.py
"""
Minimal FHIR → semantic graph mapper.

- Reads a FHIR Bundle (JSON)
- Extracts core resources (Patient, Observation, Encounter, Condition, MedicationStatement)
- Builds a simple knowledge graph in memory (nodes + edges)
- Emits:
    * graph dict  (portable JSON-serializable object)
    * derived facts (very simple rules, e.g., fever if temperature > 38C)

No external deps required. If `networkx` is available, you can export to a DiGraph.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

# ----------------------------
# Data structures
# ----------------------------

@dataclass
class Node:
    id: str            # e.g., "Patient/example"
    type: str          # e.g., "Patient", "Observation"
    props: Dict[str, Any]

@dataclass
class Edge:
    src: str           # node id
    dst: str           # node id
    rel: str           # relationship label, e.g., "HAS_SUBJECT", "HAS_CODE"

@dataclass
class Graph:
    nodes: Dict[str, Node]
    edges: List[Edge]

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
        }

    # Optional export if user has networkx installed
    def to_networkx(self):
        try:
            import networkx as nx  # type: ignore
        except Exception as e:
            raise RuntimeError("Install networkx to use to_networkx(): pip install networkx") from e
        G = nx.DiGraph()
        for nid, n in self.nodes.items():
            G.add_node(nid, **n.props, type=n.type)
        for e in self.edges:
            G.add_edge(e.src, e.dst, rel=e.rel)
        return G

# ----------------------------
# Mapper
# ----------------------------

class SemanticMapper:
    def __init__(self):
        self.graph = Graph(nodes={}, edges=[])

    # Utility
    def _add_node(self, rid: str, rtype: str, props: Dict[str, Any]) -> None:
        if rid not in self.graph.nodes:
            self.graph.nodes[rid] = Node(id=rid, type=rtype, props=props)
        else:
            # merge props non-destructively
            self.graph.nodes[rid].props.update({k: v for k, v in props.items() if v is not None})

    def _add_edge(self, src: str, dst: str, rel: str) -> None:
        self.graph.edges.append(Edge(src=src, dst=dst, rel=rel))

    # ------------------------
    # Main entry
    # ------------------------
    def load_bundle(self, path: str | Path) -> "SemanticMapper":
        bundle = json.loads(Path(path).read_text(encoding="utf-8"))
        if bundle.get("resourceType") != "Bundle":
            raise ValueError("Input must be a FHIR Bundle JSON.")
        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            self._ingest_resource(res)
        # After ingest, derive simple facts
        self._derive_simple_facts()
        return self

    # ------------------------
    # Resource handlers
    # ------------------------
    def _ingest_resource(self, r: Dict[str, Any]) -> None:
        rtype = r.get("resourceType")
        rid = f"{rtype}/{r.get('id','unknown')}"
        if rtype == "Patient":
            self._add_patient(rid, r)
        elif rtype == "Observation":
            self._add_observation(rid, r)
        elif rtype == "Encounter":
            self._add_encounter(rid, r)
        elif rtype == "Condition":
            self._add_condition(rid, r)
        elif rtype == "MedicationStatement":
            self._add_medication_statement(rid, r)
        else:
            # store unknowns for transparency
            self._add_node(rid, rtype or "Unknown", {"raw": r})

    def _add_patient(self, rid: str, r: Dict[str, Any]) -> None:
        name = None
        if r.get("name"):
            nm = r["name"][0]
            family = nm.get("family", "")
            given = " ".join(nm.get("given", []))
            name = (given + " " + family).strip()
        props = {
            "gender": r.get("gender"),
            "birthDate": r.get("birthDate"),
            "name": name,
        }
        self._add_node(rid, "Patient", props)

    def _add_observation(self, rid: str, r: Dict[str, Any]) -> None:
        code = self._code_text(r.get("code"))
        value = self._value_text(r)
        self._add_node(rid, "Observation", {"code": code, "value": value, "status": r.get("status")})

        subj_ref = self._ref(r.get("subject"))
        if subj_ref:
            self._add_edge(rid, subj_ref, "HAS_SUBJECT")

        # coding edge(s)
        for c in (r.get("code", {}).get("coding", []) or []):
            system = c.get("system")
            code_val = c.get("code")
            if system and code_val:
                code_node_id = f"Code/{system}|{code_val}"
                self._add_node(code_node_id, "Code", {"system": system, "code": code_val, "display": c.get("display")})
                self._add_edge(rid, code_node_id, "HAS_CODE")

    def _add_encounter(self, rid: str, r: Dict[str, Any]) -> None:
        self._add_node(rid, "Encounter", {"status": r.get("status"), "class": r.get("class", {}).get("code")})
        subj_ref = self._ref(r.get("subject"))
        if subj_ref:
            self._add_edge(rid, subj_ref, "HAS_SUBJECT")

    def _add_condition(self, rid: str, r: Dict[str, Any]) -> None:
        code = self._code_text(r.get("code"))
        self._add_node(rid, "Condition", {"code": code, "clinicalStatus": r.get("clinicalStatus", {}).get("text")})
        subj_ref = self._ref(r.get("subject"))
        if subj_ref:
            self._add_edge(rid, subj_ref, "HAS_SUBJECT")

    def _add_medication_statement(self, rid: str, r: Dict[str, Any]) -> None:
        med = self._code_text(r.get("medicationCodeableConcept"))
        self._add_node(rid, "MedicationStatement", {"medication": med, "status": r.get("status")})
        subj_ref = self._ref(r.get("subject"))
        if subj_ref:
            self._add_edge(rid, subj_ref, "HAS_SUBJECT")

    # ------------------------
    # Helpers
    # ------------------------
    def _code_text(self, code_obj: Optional[Dict[str, Any]]) -> Optional[str]:
        if not code_obj:
            return None
        if "text" in code_obj:
            return code_obj["text"]
        codings = code_obj.get("coding", [])
        if codings:
            c = codings[0]
            disp = c.get("display")
            return disp or f"{c.get('system','')}|{c.get('code','')}".strip("|")
        return None

    def _value_text(self, obs: Dict[str, Any]) -> Optional[str]:
        if "valueQuantity" in obs:
            v = obs["valueQuantity"]
            return f"{v.get('value')} {v.get('unit')}".strip()
        if "valueString" in obs:
            return obs["valueString"]
        if "valueCodeableConcept" in obs:
            return self._code_text(obs["valueCodeableConcept"])
        return None

    def _ref(self, maybe_ref: Any) -> Optional[str]:
        if isinstance(maybe_ref, dict) and "reference" in maybe_ref:
            return maybe_ref["reference"]
        return None

    # ------------------------
    # Simple derived facts (toy rules)
    # ------------------------
    def _derive_simple_facts(self) -> None:
        """
        Example rule:
        - If there's an Observation with LOINC 8310-5 (Body temperature) and value > 38 C,
          assert a node 'Finding/Fever' and connect patient -> fever.
        """
        # find all temperature observations
        temps = []
        for e in self.graph.edges:
            if e.rel == "HAS_CODE":
                code_node = self.graph.nodes.get(e.dst)
                if code_node and code_node.props.get("system") == "http://loinc.org" and code_node.props.get("code") == "8310-5":
                    obs = self.graph.nodes.get(e.src)
                    if obs and obs.type == "Observation":
                        temps.append(obs)

        for obs in temps:
            # parse numeric temperature if possible
            val = obs.props.get("value")  # e.g., "37.5 Celsius"
            try:
                number = float(str(val).split()[0])
            except Exception:
                number = None

            if number is not None and number > 38.0:
                fever_id = "Finding/Fever"
                self._add_node(fever_id, "Finding", {"label": "Fever"})
                # connect fever to the patient subject of this observation
                # find subject edge from obs
                subj: Optional[str] = None
                for e in self.graph.edges:
                    if e.src == obs.id and e.rel == "HAS_SUBJECT":
                        subj = e.dst
                        break
                if subj:
                    self._add_edge(subj, fever_id, "HAS_FINDING")

# ----------------------------
# Convenience CLI
# ----------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Map a FHIR Bundle to a semantic graph")
    ap.add_argument("bundle", help="Path to FHIR Bundle JSON")
    ap.add_argument("-o", "--out", default="graph.json", help="Output JSON path")
    args = ap.parse_args()

    mapper = SemanticMapper().load_bundle(args.bundle)
    out = mapper.graph.to_jsonable()
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"✅ Wrote {args.out} with {len(out['nodes'])} nodes and {len(out['edges'])} edges.")

if __name__ == "__main__":
    main()
