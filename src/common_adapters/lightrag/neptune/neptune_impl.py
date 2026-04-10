# lightrag_neptune/graph.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging

from lightrag.base import BaseGraphStorage
from lightrag.types import KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge
from lightrag.kg.shared_storage import get_data_init_lock
from lightrag.utils import logger

from .client import NeptuneGatewayClient  # your async HTTP client

READ_LOG = logging.getLogger(__name__)

_REQUIRED_EDGE_DEFAULTS = {
    "weight": 1.0,
    "source_id": None,
    "description": None,
    "keywords": None,
}

def _ensure_edge_defaults(props: Dict[str, Any]) -> Dict[str, Any]:
    print(f"[DEBUG] _ensure_edge_defaults input: {props}")
    try:
        out = dict(props or {})
        for k, default in _REQUIRED_EDGE_DEFAULTS.items():
            out.setdefault(k, default)
        # Normalize types
        if out.get("weight") is None:
            out["weight"] = 1.0
        try:
            out["weight"] = float(out["weight"])
        except Exception as e:
            print(f"[ERROR] _ensure_edge_defaults weight conversion error: {e}")
            out["weight"] = 1.0
        print(f"[DEBUG] _ensure_edge_defaults output: {out}")
        return out
    except Exception as e:
        print(f"[ERROR] _ensure_edge_defaults error: {e}")
        return {}

def _as_node_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expect either:
      - {"n": {"id": "...", "labels": [...], "properties": {...}}}
      - or {"id": "...", "labels": [...], "properties": {...}}
    Returns the inner normalized node dict.
    """
    print(f"[DEBUG] _as_node_dict input: {row}")
    try:
        n = row.get("n", row)
        props = n.get("properties", {})
        # Ensure "entity_id" exists (Neo4JStorage expects this in properties)
        if "entity_id" not in props:
            # Infer from "id" if provided
            eid = props.get("id") or n.get("id")
            if eid is not None:
                props["entity_id"] = eid
        # Ensure LightRAG-safe string props
        props.setdefault("source_id", "")
        props.setdefault("file_path", "")
        props.setdefault("description", props.get("description", ""))
        result = {"id": props.get("entity_id") or n.get("id"),
                  "labels": n.get("labels", []) or ["Entity"],
                  "properties": props}
        print(f"[DEBUG] _as_node_dict output: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] _as_node_dict error: {e}")
        return {}

def _as_edge_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expect either:
      - {"r": {"id":"...","type":"DIRECTED","source":"...","target":"...","properties":{...}}}
      - or the edge object itself as above.
    Returns the inner normalized edge dict.
    """
    print(f"[DEBUG] _as_edge_dict input: {row}")
    try:
        r = row.get("r", row)
        props = _ensure_edge_defaults(r.get("properties", {}))
        src   = r.get("source") or props.get("source_id")
        dst   = r.get("target") or props.get("target_id")
        result = {
            "id": r.get("id"),
            "type": r.get("type") or "DIRECTED",
            "source": src,
            "target": dst,
            "properties": props,
        }
        print(f"[DEBUG] _as_edge_dict output: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] _as_edge_dict error: {e}")
        return {}

@dataclass
class NeptuneGraphStorage(BaseGraphStorage):
    """
    API-compatible storage with your Neo4JStorage:
    - same constructor signature
    - same method names and return types
    - builds KnowledgeGraph / Node / Edge objects
    """

    def __init__(self, namespace, global_config, embedding_func, workspace=None):
        print(f"[DEBUG] NeptuneGraphStorage.__init__ namespace={namespace}, workspace={workspace}")
        # Copy Neo4JStorage constructor semantics for workspace
        workspace = (workspace or "base") or "base"
        super().__init__(
            namespace=namespace,
            workspace=workspace,
            global_config=global_config,
            embedding_func=embedding_func,
        )
        self._client: Optional[NeptuneGatewayClient] = None

    def _get_workspace_label(self) -> str:
        # Keep the same concept so UI/logs remain consistent
        return self.workspace

    async def initialize(self):
        print(f"[DEBUG] NeptuneGraphStorage.initialize called")
        try:
            async with get_data_init_lock():
                base_url = self.global_config.get("addon_params", {}).get("NEPTUNE_GATEWAY_URL")
                api_key  = self.global_config.get("addon_params", {}).get("NEPTUNE_GATEWAY_KEY")
                print(f"[DEBUG] NeptuneGraphStorage.initialize base_url={base_url}, api_key={'***' if api_key else None}")
                if not base_url:
                    raise ValueError("NEPTUNE_GATEWAY_URL is required in addon_params")
                self._client = NeptuneGatewayClient(base_url, api_key=api_key)
        except Exception as e:
            print(f"[ERROR] NeptuneGraphStorage.initialize error: {e}")

    async def finalize(self):
        print(f"[DEBUG] NeptuneGraphStorage.finalize called")
        try:
            # HTTP client is lightweight; nothing persistent to close here
            self._client = None
        except Exception as e:
            print(f"[ERROR] NeptuneGraphStorage.finalize error: {e}")

    async def index_done_callback(self) -> None:
        # No file-based flush needed; Neptune is transactional
        return

    # ------------- Basic existence APIs -------------

    async def has_node(self, node_id: str) -> bool:
        print(f"[DEBUG] has_node({node_id})")
        try:
            res = await self._client.call("get_node", {"namespace": self.namespace, "node_id": node_id})
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] has_node({node_id}) result: {items}")
            return bool(items)
        except Exception as e:
            print(f"[ERROR] has_node({node_id}) error: {e}")
            return False

    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        print(f"[DEBUG] has_edge({source_node_id}, {target_node_id})")
        try:
            # Undirected presence check
            res = await self._client.call(
                "get_edge",
                {"namespace": self.namespace, "src_id": source_node_id, "dst_id": target_node_id},
            )
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] has_edge direct result: {items}")
            if items:
                return True
            # fallback: neighbors check
            res2 = await self._client.call(
                "get_node_edges",
                {"namespace": self.namespace, "node_id": source_node_id, "limit": 2000},
            )
            rows = res2.get("result", {}).get("results", [])
            print(f"[DEBUG] has_edge fallback rows: {rows}")
            for row in rows:
                src = row.get("src") or row.get("source")
                dst = row.get("dst") or row.get("target")
                if (src == source_node_id and dst == target_node_id) or (src == target_node_id and dst == source_node_id):
                    print(f"[DEBUG] has_edge found in fallback: src={src}, dst={dst}")
                    return True
            return False
        except Exception as e:
            print(f"[ERROR] has_edge({source_node_id}, {target_node_id}) error: {e}")
            return False

    # ------------- Node APIs -------------

    async def get_node(self, node_id: str) -> dict[str, str] | None:
        print(f"[DEBUG] get_node({node_id})")
        try:
            res = await self._client.call("get_node", {"namespace": self.namespace, "node_id": node_id})
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] get_node({node_id}) result: {items}")
            if not items:
                return None
            node = _as_node_dict(items[0])
            # Return only properties (Neo4JStorage returns node properties)
            print(f"[DEBUG] get_node({node_id}) node: {node}")
            return dict(node.get("properties", {}))
        except Exception as e:
            print(f"[ERROR] get_node({node_id}) error: {e}")
            return None

    async def get_nodes_batch(self, node_ids: list[str]) -> dict[str, dict]:
        print(f"[DEBUG] get_nodes_batch({node_ids})")
        out: dict[str, dict] = {}
        try:
            # Simple first pass; optimize with a batch endpoint later if needed.
            for nid in node_ids:
                out[nid] = await self.get_node(nid) or {}
            print(f"[DEBUG] get_nodes_batch output: {out}")
            return out
        except Exception as e:
            print(f"[ERROR] get_nodes_batch({node_ids}) error: {e}")
            return out

    async def node_degree(self, node_id: str) -> int:
        print(f"[DEBUG] node_degree({node_id})")
        try:
            res = await self._client.call("node_degree", {"namespace": self.namespace, "node_id": node_id})
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] node_degree({node_id}) result: {items}")
            if not items:
                return 0
            return int(items[0].get("degree") or items[0].get("deg") or 0)
        except Exception as e:
            print(f"[ERROR] node_degree({node_id}) error: {e}")
            return 0

    async def node_degrees_batch(self, node_ids: list[str]) -> dict[str, int]:
        print(f"[DEBUG] node_degrees_batch({node_ids})")
        degrees = {}
        try:
            for nid in node_ids:
                degrees[nid] = await self.node_degree(nid)
            print(f"[DEBUG] node_degrees_batch output: {degrees}")
            return degrees
        except Exception as e:
            print(f"[ERROR] node_degrees_batch({node_ids}) error: {e}")
            return degrees

    # ------------- Edge APIs -------------

    async def edge_degree(self, src_id: str, tgt_id: str) -> int:
        print(f"[DEBUG] edge_degree({src_id}, {tgt_id})")
        try:
            # Match Neo4JStorage semantics: sum of degrees
            result = (await self.node_degree(src_id)) + (await self.node_degree(tgt_id))
            print(f"[DEBUG] edge_degree({src_id}, {tgt_id}) result: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] edge_degree({src_id}, {tgt_id}) error: {e}")
            return 0

    async def edge_degrees_batch(self, edge_pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
        print(f"[DEBUG] edge_degrees_batch({edge_pairs})")
        try:
            # Sum-of-node-degrees per pair
            uniq = {nid for a, b in edge_pairs for nid in (a, b)}
            degs = await self.node_degrees_batch(list(uniq))
            result = {(a, b): degs.get(a, 0) + degs.get(b, 0) for a, b in edge_pairs}
            print(f"[DEBUG] edge_degrees_batch output: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] edge_degrees_batch({edge_pairs}) error: {e}")
            return {}

    async def get_edge(self, source_node_id: str, target_node_id: str) -> dict[str, str] | None:
        print(f"[DEBUG] get_edge({source_node_id}, {target_node_id})")
        try:
            res = await self._client.call(
                "get_edge",
                {"namespace": self.namespace, "src_id": source_node_id, "dst_id": target_node_id},
            )
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] get_edge({source_node_id}, {target_node_id}) result: {items}")
            if not items:
                return None
            edge = _as_edge_dict(items[0])
            print(f"[DEBUG] get_edge({source_node_id}, {target_node_id}) edge: {edge}")
            return _ensure_edge_defaults(edge.get("properties", {}))
        except Exception as e:
            print(f"[ERROR] get_edge({source_node_id}, {target_node_id}) error: {e}")
            return None

    async def get_edges_batch(self, pairs: list[dict[str, str]]) -> dict[tuple[str, str], dict]:
        print(f"[DEBUG] get_edges_batch({pairs})")
        out: dict[tuple[str, str], dict] = {}
        try:
            for p in pairs:
                src, tgt = p["src"], p["tgt"]
                out[(src, tgt)] = await self.get_edge(src, tgt) or _ensure_edge_defaults({})
            print(f"[DEBUG] get_edges_batch output: {out}")
            return out
        except Exception as e:
            print(f"[ERROR] get_edges_batch({pairs}) error: {e}")
            return out

    async def get_node_edges(self, source_node_id: str) -> list[tuple[str, str]] | None:
        print(f"[DEBUG] get_node_edges({source_node_id})")
        try:
            res = await self._client.call(
                "get_node_edges",
                {"namespace": self.namespace, "node_id": source_node_id, "limit": 2000},
            )
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] get_node_edges({source_node_id}) result: {items}")
            pairs: list[tuple[str, str]] = []
            for row in items:
                src = row.get("src") or row.get("source")
                dst = row.get("dst") or row.get("target")
                if src and dst:
                    pairs.append((src, dst))
            print(f"[DEBUG] get_node_edges({source_node_id}) pairs: {pairs}")
            return pairs
        except Exception as e:
            print(f"[ERROR] get_node_edges({source_node_id}) error: {e}")
            return None

    async def get_nodes_edges_batch(self, node_ids: list[str]) -> dict[str, list[tuple[str, str]]]:
        print(f"[DEBUG] get_nodes_edges_batch({node_ids})")
        out: dict[str, list[tuple[str, str]]] = {}
        try:
            for nid in node_ids:
                out[nid] = await self.get_node_edges(nid) or []
            print(f"[DEBUG] get_nodes_edges_batch output: {out}")
            return out
        except Exception as e:
            print(f"[ERROR] get_nodes_edges_batch({node_ids}) error: {e}")
            return out

    # ------------- Mutations -------------

    async def upsert_node(self, node_id: str, node_data: dict[str, str]) -> None:
        print(f"[DEBUG] upsert_node({node_id}, {node_data})")
        try:
            # Neo4JStorage requires node_data to contain 'entity_id'
            if "entity_id" not in node_data:
                raise ValueError("Neptune: node_data must contain 'entity_id'")
            entity_type = node_data.get("entity_type") or "Concept"
            labels = ["Entity", entity_type]  # workspace label is encoded by namespace in gateway

            props = {**node_data}
            # Ensure string props LightRAG expects
            for k in ("source_id", "file_path", "description"):
                v = props.get(k)
                if v is None:
                    props[k] = "" if k != "description" else (props.get("description") or "")

            print(f"[DEBUG] upsert_node props: {props}")
            await self._client.call(
                "upsert_node",
                {
                    "namespace": self.namespace,
                    "node": {"id": node_id, "labels": labels, "properties": props},
                },
            )
        except Exception as e:
            print(f"[ERROR] upsert_node({node_id}) error: {e}")

    async def upsert_edge(self, source_node_id: str, target_node_id: str, edge_data: dict[str, str]) -> None:
        print(f"[DEBUG] upsert_edge({source_node_id}, {target_node_id}, {edge_data})")
        try:
            props = _ensure_edge_defaults(edge_data or {})
            # Standardize on DIRECTED for parity with Neo4JStorage
            print(f"[DEBUG] upsert_edge props: {props}")
            await self._client.call(
                "upsert_edge",
                {
                    "namespace": self.namespace,
                    "edge": {
                        "id": props.get("id") or f"{source_node_id}__{target_node_id}__DIRECTED",
                        "src": source_node_id,
                        "dst": target_node_id,
                        "type": "DIRECTED",
                        "properties": {
                            **props,
                            "source_id": source_node_id,
                            "target_id": target_node_id,
                        },
                    },
                },
            )
        except Exception as e:
            print(f"[ERROR] upsert_edge({source_node_id}, {target_node_id}) error: {e}")

    async def delete_node(self, node_id: str) -> None:
        print(f"[DEBUG] delete_node({node_id})")
        try:
            await self._client.call("delete_node", {"namespace": self.namespace, "node_id": node_id})
        except Exception as e:
            print(f"[ERROR] delete_node({node_id}) error: {e}")

    async def remove_nodes(self, nodes: list[str]):
        print(f"[DEBUG] remove_nodes({nodes})")
        try:
            # Keep same behavior (iterative) for now
            for nid in nodes:
                await self.delete_node(nid)
        except Exception as e:
            print(f"[ERROR] remove_nodes({nodes}) error: {e}")

    async def remove_edges(self, edges: list[tuple[str, str]]):
        print(f"[DEBUG] remove_edges({edges})")
        try:
            await self._client.call("remove_edges", {"namespace": self.namespace, "pairs": edges})
        except Exception as e:
            print(f"[ERROR] remove_edges({edges}) error: {e}")

    # ------------- Bulk reads -------------

    async def get_all_nodes(self) -> list[dict]:
        print(f"[DEBUG] get_all_nodes()")
        try:
            res = await self._client.call("get_all_nodes", {"namespace": self.namespace, "limit": 10000})
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] get_all_nodes result: {items}")
            out = []
            for row in items:
                n = _as_node_dict(row.get("n", row))
                props = dict(n["properties"])
                props["id"] = props.get("entity_id") or n["id"]
                out.append(props)
            print(f"[DEBUG] get_all_nodes output: {out}")
            return out
        except Exception as e:
            print(f"[ERROR] get_all_nodes error: {e}")
            return []

    async def get_all_edges(self) -> list[dict]:
        print(f"[DEBUG] get_all_edges()")
        try:
            res = await self._client.call("get_all_edges", {"namespace": self.namespace, "limit": 20000})
            items = res.get("result", {}).get("results", [])
            print(f"[DEBUG] get_all_edges result: {items}")
            out = []
            for row in items:
                e = _as_edge_dict(row)
                props = dict(e["properties"])
                props["source"] = e["source"]
                props["target"] = e["target"]
                out.append(props)
            print(f"[DEBUG] get_all_edges output: {out}")
            return out
        except Exception as e:
            print(f"[ERROR] get_all_edges error: {e}")
            return []

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        print(f"[DEBUG] get_popular_labels(limit={limit})")
        try:
            res = await self._client.call("get_popular_labels", {"namespace": self.namespace, "top_k": limit})
            labels = res.get("result", {}).get("labels", [])
            print(f"[DEBUG] get_popular_labels output: {labels}")
            return labels
        except Exception as e:
            print(f"[ERROR] get_popular_labels error: {e}")
            return []

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        print(f"[DEBUG] search_labels(query={query}, limit={limit})")
        try:
            q = (query or "").strip()
            if not q:
                return []
            res = await self._client.call("search_labels", {"namespace": self.namespace, "prefix": q, "limit": limit})
            labels = res.get("result", {}).get("labels", [])
            print(f"[DEBUG] search_labels output: {labels}")
            return labels
        except Exception as e:
            print(f"[ERROR] search_labels error: {e}")
            return []

    # ------------- Knowledge graph -------------

    async def get_knowledge_graph(
        self,
        node_label: str,
        max_depth: int = 3,
        max_nodes: int | None = None,
    ) -> KnowledgeGraph:
        print(f"[DEBUG] get_knowledge_graph(node_label={node_label}, max_depth={max_depth}, max_nodes={max_nodes})")
        try:
            # Resolve max_nodes just like Neo4JStorage
            if max_nodes is None:
                max_nodes = self.global_config.get("max_graph_nodes", 1000)
            else:
                max_nodes = min(max_nodes, self.global_config.get("max_graph_nodes", 1000))

            # Call gateway
            res = await self._client.call(
                "get_knowledge_graph",
                {
                    "namespace": self.namespace,
                    "seed_ids": [] if node_label == "*" else [node_label],
                    "limit": int(max_nodes),
                    "depth": int(max_depth),
                },
            )
            payload = res.get("result", {})
            nodes_raw = payload.get("nodes") or payload.get("entities") or []
            edges_raw = payload.get("edges") or payload.get("relations") or []

            print(f"[DEBUG] get_knowledge_graph nodes_raw: {nodes_raw}")
            print(f"[DEBUG] get_knowledge_graph edges_raw: {edges_raw}")

            kg = KnowledgeGraph()
            seen_nodes: set[str] = set()
            seen_edges: set[str] = set()

            # Nodes
            for nrow in nodes_raw:
                node = _as_node_dict(nrow)
                nid = str(node["properties"].get("entity_id") or node["id"])
                if nid in seen_nodes:
                    continue
                kg.nodes.append(
                    KnowledgeGraphNode(
                        id=nid,
                        labels=[nid],  # match Neo4JStorage behavior (labels as [entity_id])
                        properties=dict(node["properties"]),
                    )
                )
                seen_nodes.add(nid)

            # Edges
            for erow in edges_raw:
                edge = _as_edge_dict(erow)
                if not (edge["source"] and edge["target"]):
                    continue
                eid = edge.get("id") or f"{edge['source']}__{edge['target']}__{edge['type']}"
                if eid in seen_edges:
                    continue
                kg.edges.append(
                    KnowledgeGraphEdge(
                        id=str(eid),
                        type=edge["type"] or "DIRECTED",
                        source=str(edge["source"]),
                        target=str(edge["target"]),
                        properties=dict(edge["properties"]),
                    )
                )
                seen_edges.add(eid)

            # We don’t know true total node count here, so is_truncated is conservative:
            kg.is_truncated = len(kg.nodes) >= max_nodes
            print(f"[DEBUG] get_knowledge_graph output: nodes={len(kg.nodes)}, edges={len(kg.edges)}, is_truncated={kg.is_truncated}")
            return kg
        except Exception as e:
            print(f"[ERROR] get_knowledge_graph error: {e}")
            return KnowledgeGraph()

    
    async def get_all_labels(self) -> list[str]:
        print(f"[DEBUG] get_all_labels()")
        try:
            res = await self._client.call(
                "get_all_labels",
                {"namespace": self._ns()},
            )
            labels = res.get("result", {}).get("labels", [])
            # Ensure list[str], de-dup + stable order (if gateway already sorted, this is a no-op)
            result = list(dict.fromkeys([str(l) for l in labels if l is not None]))
            print(f"[DEBUG] get_all_labels output: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] get_all_labels error: {e}")
            return []


    # ------------- Lifecycle -------------

    async def drop(self) -> dict[str, str]:
        print(f"[DEBUG] drop() called")
        try:
            await self._client.call("drop_graph", {"namespace": self.namespace})
            msg = {"status": "success", "message": f"workspace '{self._get_workspace_label()}' data dropped"}
            print(f"[DEBUG] drop() success: {msg}")
            return msg
        except Exception as e:
            msg = {"status": "error", "message": str(e)}
            print(f"[DEBUG] drop() error: {msg}")
            return msg