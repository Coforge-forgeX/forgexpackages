# neptune_to_neo4j_converter.py
"""
NeptuneToNeo4jConverter
-----------------------

Converts a LightRAG `aquery_data`-style payload (or similarly shaped dicts) into a
normalized list of **nodes** and **edges** compatible with a Neo4j-like visualization
schema requested by the caller.

Target schema
=============
Node (example):
{
    "id": "3205",
    "labels": ["$1 Million Per Claim Insurance Limit"],
    "properties": {
        "file_path": "Travel, Transportation & Hospitality/Airlines/Chapter 11_Speciality Coverages_updated_18.pdf",
        "entity_type": "data",
        "truncate": "",
        "description": "...",
        "created_at": 1767867298,
        "source_id": "chunk-b7e6cb65b...",
        "entity_id": "$1 Million Per Claim Insurance Limit"
    }
}

Edge (example):
{
    "id": "3534",
    "type": "DIRECTED",
    "source": "3205",
    "target": "3194",
    "properties": {
        "file_path": "Travel, Transportation & Hospitality/Airlines/Chapter 11_Speciality Coverages_updated_18.pdf",
        "truncate": "",
        "keywords": "...",
        "description": "...",
        "created_at": 1767867302,
        "weight": 2,
        "source_id": "chunk-b7e6cb65b..."
    }
}

Design constraints
==================
* Deterministic ID assignment for nodes and edges (stable across runs for stable inputs).
* Handle missing entities referenced only in relationships by synthesizing minimal nodes.
* Deduplicate nodes by their canonical label (entity_name) and deduplicate edges by a
  stable signature of endpoints + salient properties.
* Preserve raw values (including HTML entities like "&amp;") — do **not** unescape.
* Always include `truncate: ""` in `properties` of nodes and edges.
* Be defensive about input shape and missing fields; log at DEBUG level for traceability.

NOTE: This converter produces exactly the **final** node/edge structure expected by the tool.
The caller/tool should not mutate structure further.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Leave configuration to host app; attach NullHandler to avoid "No handler" warnings
    logger.addHandler(logging.NullHandler())


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

def _sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _stable_numeric_id(seed: Any, namespace: str, digits: int = 13) -> str:
    """Create a stable numeric id (as string) from an arbitrary JSON-serializable seed.

    * Uses SHA1 over a namespaced JSON dump of the seed.
    * Returns up to `digits` decimal digits (default 13, ~43 bits),
      good balance between compactness and collision resistance.
    * Collision handling is done by caller using a salt loop if needed.
    """
    dump = json.dumps({"ns": namespace, "seed": seed}, sort_keys=True, default=str)
    hx = _sha1_hex(dump)
    # Take first 16 hex chars (~64 bits), convert to int, then reduce to decimal string with `digits` length
    num = int(hx[:16], 16)
    mod = 10 ** digits
    return str(num % mod).zfill(digits)


def _merge_properties(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Conservative merge: keep existing values; only fill missing/empty keys from incoming.
    Avoids property explosion while still enriching sparse nodes when duplicates appear.
    """
    out = dict(base)
    for k, v in incoming.items():
        if k not in out or out[k] in (None, ""):
            out[k] = v
    return out


@dataclass
class ConverterConfig:
    default_edge_type: str = "DIRECTED"
    node_id_digits: int = 13
    edge_id_digits: int = 13
    include_null_properties: bool = False  # if False, drop None values from properties
    enable_dedup: bool = True


class NeptuneToNeo4jConverter:
    """Convert LightRAG `aquery_data` payload (or compatible dict) into target nodes/edges.

    Public API:
        converter = NeptuneToNeo4jConverter()
        result = converter.transform(resp)  # returns {"nodes": [...], "edges": [...]} matching target schema
    """

    def __init__(self, config: Optional[ConverterConfig] = None, logger_: Optional[logging.Logger] = None) -> None:
        self.cfg = config or ConverterConfig()
        self.log = logger_ or logger
        self._node_id_map: Dict[str, str] = {}  # canonical label -> numeric id
        self._reverse_node_ids: Dict[str, str] = {}  # id -> canonical label
        self._edge_signatures: set[str] = set()

    # -------------------------- Public API -------------------------- #
    def transform(self, payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Convert input payload into canonical `nodes` and `edges` lists.

        Accepts either whole `resp` from LightRAG or `resp['data']`.
        """
        self.log.debug("Starting transform. Top-level keys: %s", list(payload.keys())[:10])

        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and ("entities" in data or "relationships" in data):
            entities = data.get("entities") or []
            relationships = data.get("relationships") or []
        else:
            # Fallback: the payload itself may be the data block
            entities = payload.get("entities") or []
            relationships = payload.get("relationships") or []

        self.log.debug(
            "Parsed input: entities=%d, relationships=%d",
            len(entities) if isinstance(entities, list) else -1,
            len(relationships) if isinstance(relationships, list) else -1,
        )

        if not isinstance(entities, list):
            self.log.warning("`entities` is not a list; got type=%s. Coercing to empty list.", type(entities).__name__)
            entities = []
        if not isinstance(relationships, list):
            self.log.warning("`relationships` is not a list; got type=%s. Coercing to empty list.", type(relationships).__name__)
            relationships = []

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # 1) Build nodes from entities
        for ent in entities:
            node = self._entity_to_node(ent)
            if node is None:
                continue
            # Dedup by canonical label
            canonical_label = node["labels"][0]
            existing = next((n for n in nodes if n["labels"][0] == canonical_label), None)
            if existing is None:
                nodes.append(node)
            else:
                # conservative merge of properties
                merged_props = _merge_properties(existing.get("properties", {}), node.get("properties", {}))
                existing["properties"] = merged_props
                self.log.debug("Merged duplicate entity into node label='%s'", canonical_label)

        # 2) Ensure nodes exist for relationship endpoints that may be missing in entities
        referenced_labels = self._collect_relationship_labels(relationships)
        for lbl in referenced_labels:
            if not any(n["labels"][0] == lbl for n in nodes):
                synth_node = self._synthesize_node(lbl)
                nodes.append(synth_node)
                self.log.debug("Synthesized node for relationship-only label='%s'", lbl)

        # 3) Build edges
        for rel in relationships:
            edge = self._relationship_to_edge(rel)
            if edge is None:
                continue

            sig = self._edge_signature(edge)
            if self.cfg.enable_dedup and sig in self._edge_signatures:
                self.log.debug("Skipped duplicate edge sig=%s", sig)
                continue
            self._edge_signatures.add(sig)
            edges.append(edge)

        self.log.debug("Transform completed: nodes=%d, edges=%d", len(nodes), len(edges))
        return {"nodes": nodes, "edges": edges}

    # -------------------------- Internals -------------------------- #
    def _canonical_node_label(self, entity: Dict[str, Any]) -> Optional[str]:
        name = entity.get("entity_name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        # Try alternates if provided
        for key in ("label", "name", "id"):
            v = entity.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _get_or_assign_node_id(self, canonical_label: str) -> str:
        if canonical_label in self._node_id_map:
            return self._node_id_map[canonical_label]

        # Deterministic ID based on canonical label; resolve collisions if any
        base_id = _stable_numeric_id(canonical_label, namespace="node", digits=self.cfg.node_id_digits)
        node_id = base_id
        salt_idx = 0
        while node_id in self._reverse_node_ids and self._reverse_node_ids[node_id] != canonical_label:
            salt_idx += 1
            node_id = _stable_numeric_id(f"{canonical_label}::{salt_idx}", namespace="node", digits=self.cfg.node_id_digits)
            if salt_idx > 50:
                # Extremely unlikely; fallback to stronger seed
                node_id = _stable_numeric_id({"lbl": canonical_label, "salt": salt_idx}, namespace="node", digits=self.cfg.node_id_digits)
                break

        self._node_id_map[canonical_label] = node_id
        self._reverse_node_ids[node_id] = canonical_label
        return node_id

    def _clean_properties(self, props: Dict[str, Any]) -> Dict[str, Any]:
        if self.cfg.include_null_properties:
            props.setdefault("truncate", "")
            return props
        cleaned = {}
        for k, v in props.items():
            if v is not None:
                cleaned[k] = v
        cleaned.setdefault("truncate", "")
        return cleaned

    def _entity_to_node(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(entity, dict):
            self.log.debug("Skipping non-dict entity: %r", entity)
            return None

        canonical_label = self._canonical_node_label(entity)
        if not canonical_label:
            self.log.debug("Entity lacks a canonical label: %r", entity)
            return None

        node_id = self._get_or_assign_node_id(canonical_label)

        # Build properties
        props: Dict[str, Any] = {}
        # Pass through commonly used fields if present
        for key in ("file_path", "entity_type", "description", "created_at", "source_id"):
            if key in entity:
                props[key] = entity[key]

        # Ensure these are set
        props.setdefault("entity_type", entity.get("entity_type"))
        props.setdefault("entity_id", canonical_label)

        node = {
            "id": node_id,
            "labels": [canonical_label],
            "properties": self._clean_properties(props),
        }
        self.log.debug("Created node id=%s label=%s", node_id, canonical_label)
        return node

    def _synthesize_node(self, label: str) -> Dict[str, Any]:
        node_id = self._get_or_assign_node_id(label)
        props = {
            "entity_type": "unknown",
            "entity_id": label,
        }
        node = {
            "id": node_id,
            "labels": [label],
            "properties": self._clean_properties(props),
        }
        return node

    def _collect_relationship_labels(self, relationships: Iterable[Dict[str, Any]]) -> List[str]:
        labels: set[str] = set()
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            src = rel.get("src_id") or rel.get("source") or rel.get("source_id")
            tgt = rel.get("tgt_id") or rel.get("target") or rel.get("target_id")
            if isinstance(src, str) and src.strip():
                labels.add(src.strip())
            if isinstance(tgt, str) and tgt.strip():
                labels.add(tgt.strip())
        return sorted(labels)

    def _relationship_to_edge(self, rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(rel, dict):
            self.log.debug("Skipping non-dict relationship: %r", rel)
            return None

        src_label = rel.get("src_id") or rel.get("source") or rel.get("source_id")
        tgt_label = rel.get("tgt_id") or rel.get("target") or rel.get("target_id")

        if not isinstance(src_label, str) or not src_label.strip():
            self.log.debug("Relationship missing/invalid source: %r", rel)
            return None
        if not isinstance(tgt_label, str) or not tgt_label.strip():
            self.log.debug("Relationship missing/invalid target: %r", rel)
            return None

        src_label = src_label.strip()
        tgt_label = tgt_label.strip()

        # Ensure node IDs exist for endpoints
        src_id = self._get_or_assign_node_id(src_label)
        tgt_id = self._get_or_assign_node_id(tgt_label)

        # Edge ID based on endpoints + salient properties for stability
        salient = {
            "src": src_label,
            "tgt": tgt_label,
            "desc": rel.get("description") or "",
            "kw": rel.get("keywords") or "",
            "fp": rel.get("file_path") or "",
            "ts": rel.get("created_at") or "",
        }
        edge_id = _stable_numeric_id(salient, namespace="edge", digits=self.cfg.edge_id_digits)

        # Properties: carry over selected relationship attributes
        props: Dict[str, Any] = {}
        for key in ("file_path", "keywords", "description", "created_at", "weight", "source_id"):
            if key in rel:
                props[key] = rel[key]

        edge = {
            "id": edge_id,
            "type": self.cfg.default_edge_type,
            "source": src_id,
            "target": tgt_id,
            "properties": self._clean_properties(props),
        }
        self.log.debug(
            "Created edge id=%s %s->%s type=%s", edge_id, src_label, tgt_label, self.cfg.default_edge_type
        )
        return edge

    def _edge_signature(self, edge: Dict[str, Any]) -> str:
        """Create a compact edge signature for deduplication.
        Combines endpoints and a few properties to avoid near-duplicate duplicates.
        """
        sig_seed = {
            "s": edge.get("source"),
            "t": edge.get("target"),
            "ty": edge.get("type"),
        }
        props = edge.get("properties", {}) or {}
        # Only the most salient textual props influence duplicate detection
        for k in ("description", "keywords", "file_path"):
            if k in props and props[k] is not None:
                sig_seed[k] = props[k]
        return _sha1_hex(json.dumps(sig_seed, sort_keys=True, default=str))


# -------------------------- Convenience function -------------------------- #

def convert(payload: Dict[str, Any], config: Optional[ConverterConfig] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Functional wrapper for one-off usage."""
    conv = NeptuneToNeo4jConverter(config=config)
    return conv.transform(payload)


# ------------------------------- Self-test -------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sample = {
        "data": {
            "entities": [
                {
                    "entity_name": "Reserve ELITT",
                    "entity_type": "concept",
                    "description": "Reserve ELITT is a system ...",
                    "source_id": "chunk-abc",
                    "file_path": "Travel, Transportation & Hospitality/Airlines/RESERVE ELITT - c.pdf",
                    "created_at": 1772101860,
                },
                {
                    "entity_name": "Reserve Block",
                    "entity_type": "concept",
                    "description": "Reserve Block is a scheduling unit ...",
                    "source_id": "chunk-def",
                    "file_path": "Travel, Transportation & Hospitality/Airlines/RESERVE ELITT - c.pdf",
                    "created_at": 1772098163,
                },
            ],
            "relationships": [
                {
                    "src_id": "Reserve Block",
                    "tgt_id": "Reserve ELITT",
                    "description": "Reserve ELITT facilitates the trading ...",
                    "keywords": "inventory management,trading",
                    "weight": 1.0,
                    "source_id": "Reserve Block",
                    "file_path": "Travel, Transportation & Hospitality/Airlines/RESERVE ELITT - c.pdf",
                    "created_at": 1772101775,
                },
                {  # references a non-entity; will synthesize node
                    "src_id": "Crew Member",
                    "tgt_id": "Reserve Block",
                    "description": "Crew Member is responsible for picking up, dropping, and trading Reserve Blocks.",
                    "keywords": "assignment,drop,pick up,trade",
                    "weight": 1.0,
                    "source_id": "Crew Member",
                    "file_path": "Travel, Transportation & Hospitality/Airlines/RESERVE ELITT - c.pdf",
                    "created_at": 1772101902,
                },
            ],
        }
    }
    out = convert(sample)
    print(json.dumps(out, indent=2))
