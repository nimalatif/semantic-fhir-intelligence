# src/population_graph.py
"""
Build a Collective Intelligence Graph from many per-patient FHIR Bundles.

Pipeline:
1) For each bundle in data/bundles/, use SemanticMapper to produce a per-patient graph.
2) Extract "concepts" we care about (default: derived Findings + key LOINC-coded Observations).
3) For each patient, compute co-occurrence pairs among that patient's concepts.
4) Aggregate across all patients: edge weight = number of patients where both concepts co-occurred.
5) Export:
   - out/meta_graph.json  (nodes, edges with weight)
   - out/cooccurrence.csv (source, target, weight)
   - out/meta_graph.png   (optional, if networkx/matplotlib installed)
"""

from __future__ import annotations
from pathlib import Path
import json
from collections import defaultdict
from typing import Dict, Set, Tuple, List

from src.semantic_mapper import SemanticMapper  # reuse your mapper

BUNDLES_DIR = Path("data/bundles")
OUT_DIR = Path("out")

# Which node types to include as "concepts" in population graph
INCLUDE_NODE_TYPES = {"Finding", "Code"}  # Finding/*, and Code/system|code

def concepts_from_graph(graph_dict: Dict) -> Set[str]:
    """
    Return a set of concept IDs for a single patient graph.
    Concepts we include:
      - Any node with type "Finding" (e.g., Finding/Fever)
      - Any node with type "Code"    (e.g., Code/http://loinc.org|8867-4)
    """
    concepts: Set[str] = set()
    for nid, node in graph_dict["nodes"].items():
        ntype = node.get("type")
        if ntype in INCLUDE_NODE_TYPES:
            concepts.add(nid)
    return concepts

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Gather per-patient concept sets
    per_patient_concepts: List[Set[str]] = []
    bundle_files = sorted(BUNDLES_DIR.glob("*.json"))
    if not bundle_files:
        raise SystemExit("No bundles found in data/bundles/. Run: python -m src.synth_data")

    for fp in bundle_files:
        mapper = SemanticMapper().load_bundle(fp)
        g = mapper.graph.to_jsonable()
        C = concepts_from_graph(g)
        if C:
            per_patient_concepts.append(C)

    # 2) Aggregate co-occurrences across patients
    #    For each patient set C, add 1 to every unordered pair in C
    pair_weight: Dict[Tuple[str, str], int] = defaultdict(int)
    node_counts: Dict[str, int] = defaultdict(int)

    for C in per_patient_concepts:
        # count singletons too (for node degree / normalization if desired)
        for c in C:
            node_counts[c] += 1

        # all unordered pairs
        items = sorted(C)
        for i in range(len(items)):
            for j in range(i+1, len(items)):
                a, b = items[i], items[j]
                pair_weight[(a, b)] += 1

    # 3) Build meta-graph JSON
    nodes_json = {
        nid: {
            "id": nid,
            "type": "Concept",
            "props": {"support": node_counts.get(nid, 0)},
        }
        for nid in node_counts
    }
    edges_json = [
        {"src": a, "dst": b, "rel": "CO_OCCURS_WITH", "weight": w}
        for (a, b), w in sorted(pair_weight.items(), key=lambda x: -x[1])
        if w > 0
    ]
    meta = {"nodes": nodes_json, "edges": edges_json}

    # 4) Write outputs
    (OUT_DIR / "meta_graph.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Also as CSV for quick viz (Gephi, etc.)
    with (OUT_DIR / "cooccurrence.csv").open("w", encoding="utf-8") as f:
        f.write("source,target,weight\n")
        for e in edges_json:
            f.write(f"{e['src']},{e['dst']},{e['weight']}\n")

    print(f"✅ Wrote out/meta_graph.json with {len(nodes_json)} nodes and {len(edges_json)} edges.")
    print("✅ Wrote out/cooccurrence.csv")

    # 5) Optional quick plot (if you have networkx/matplotlib)
    try:
        import networkx as nx  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        G = nx.Graph()
        for nid, nd in nodes_json.items():
            G.add_node(nid, support=nd["props"]["support"])
        for e in edges_json:
            G.add_edge(e["src"], e["dst"], weight=e["weight"])

        # scale node size by support; edge width by weight
        sizes = [50 + 15*G.nodes[n]["support"] for n in G.nodes]
        widths = [0.5 + 0.2*d["weight"] for _,_,d in G.edges(data=True)]

        plt.figure(figsize=(10, 8))
        pos = nx.spring_layout(G, seed=42)
        nx.draw(G, pos, with_labels=False, node_size=sizes, width=widths)
        # Draw top labels (optional): only for high-support nodes to keep clean
        for n, (x, y) in pos.items():
            if G.nodes[n]["support"] >= 10:
                plt.text(x, y, n.split("/")[-1][:20], fontsize=8, ha="center", va="center")

        plt.tight_layout()
        plt.savefig(OUT_DIR / "meta_graph.png", dpi=180)
        plt.close()
        print("🖼  Wrote out/meta_graph.png (requires networkx/matplotlib)")
    except Exception:
        print("Tip: pip install networkx matplotlib for a quick PNG plot.")

if __name__ == "__main__":
    main()
