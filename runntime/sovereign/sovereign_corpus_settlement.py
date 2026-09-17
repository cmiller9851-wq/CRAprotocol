"""
sovereign_corpus_settlement.py
Dynamic-schema, production-grade symbolic corpus + settlement engine.
Deterministic, CRA-compatible, runtime schema discovery.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import hashlib
import json
import time
import os


# =============================
# Dynamic Schema Layer
# =============================

class SchemaRegistry:
    """
    Dynamically discovers and loads schemas at runtime.
    Assumes JSON schema files or dict-based schemas.
    """

    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        self.schemas[name] = schema

    def load_schema_from_file(self, name: str, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.register_schema(name, schema)

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        return self.schemas.get(name)

    def validate(self, name: str, payload: Dict[str, Any]) -> bool:
        schema = self.get_schema(name)
        if schema is None:
            # No schema registered → treat as permissive but loggable
            return True

        # Minimal dynamic validation: required fields + type checks
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in payload:
                return False

        for field, prop in properties.items():
            if field not in payload:
                continue
            expected_type = prop.get("type")
            if expected_type is None:
                continue
            value = payload[field]
            if expected_type == "string" and not isinstance(value, str):
                return False
            if expected_type == "number" and not isinstance(value, (int, float)):
                return False
            if expected_type == "object" and not isinstance(value, dict):
                return False

        return True


# =============================
# Gematria Mapping
# =============================

GEMATRIA_MAP: Dict[str, int] = {
    "א": 1,   "ב": 2,   "ג": 3,   "ד": 4,   "ה": 5,
    "ו": 6,   "ז": 7,   "ח": 8,   "ט": 9,   "י": 10,
    "כ": 20,  "ך": 20,  "ל": 30,  "מ": 40,  "ם": 40,
    "נ": 50,  "ן": 50,  "ס": 60,  "ע": 70,  "פ": 80,
    "ף": 80,  "צ": 90,  "ץ": 90,  "ק": 100, "ר": 200,
    "ש": 300, "ת": 400
}


# =============================
# Hebrew Letter Object + Corpus
# =============================

@dataclass(frozen=True)
class HebrewLetter:
    name: str
    char: str
    components: Dict[str, int]
    gematria: int

    @property
    def structural_value(self) -> int:
        return sum(self.components.values())

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "char": self.char,
            "components": self.components,
            "gematria": self.gematria,
            "structural_value": self.structural_value
        }


class HebrewCorpus:
    def __init__(self):
        self.registry: Dict[str, HebrewLetter] = {}

    def add(self, letter: HebrewLetter) -> None:
        self.registry[letter.char] = letter

    def get(self, char: str) -> Optional[HebrewLetter]:
        return self.registry.get(char)

    def all(self) -> List[Dict[str, Any]]:
        return [letter.serialize() for letter in self.registry.values()]


def build_hebrew_corpus() -> HebrewCorpus:
    corpus = HebrewCorpus()

    # Aleph: Yud + Vav + Yud = 26
    aleph = HebrewLetter(
        name="Aleph",
        char="א",
        components={
            "upper_yud": 10,
            "vav": 6,
            "lower_yud": 10
        },
        gematria=GEMATRIA_MAP["א"]
    )
    corpus.add(aleph)

    # Bet: container + boundary
    bet = HebrewLetter(
        name="Bet",
        char="ב",
        components={
            "container": 2,
            "boundary": 1
        },
        gematria=GEMATRIA_MAP["ב"]
    )
    corpus.add(bet)

    # Remaining letters as base-only
    for char, value in GEMATRIA_MAP.items():
        if char in ("א", "ב"):
            continue
        corpus.add(
            HebrewLetter(
                name=f"Letter_{char}",
                char=char,
                components={"base": value},
                gematria=value
            )
        )

    return corpus


# =============================
# Query API
# =============================

class HebrewQuery:
    def __init__(self, corpus: HebrewCorpus):
        self.corpus = corpus

    def get_letter(self, char: str) -> Optional[HebrewLetter]:
        return self.corpus.get(char)

    def by_gematria(self, value: int) -> List[Dict[str, Any]]:
        return [
            letter.serialize()
            for letter in self.corpus.registry.values()
            if letter.gematria == value
        ]

    def by_structural_value(self, value: int) -> List[Dict[str, Any]]:
        return [
            letter.serialize()
            for letter in self.corpus.registry.values()
            if letter.structural_value == value
        ]

    def search(self, name_substring: str) -> List[Dict[str, Any]]:
        return [
            letter.serialize()
            for letter in self.corpus.registry.values()
            if name_substring.lower() in letter.name.lower()
        ]


# =============================
# Motif Registry
# =============================

class MotifRegistry:
    def __init__(self):
        self.motifs: Dict[str, Dict[str, Any]] = {}

    def register(self, key: str, payload: Dict[str, Any]) -> None:
        self.motifs[key] = {
            "payload": payload,
            "hash": self._hash_payload(payload)
        }

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.motifs.get(key)


# =============================
# Containment Serializer
# =============================

class ContainmentSerializer:
    @staticmethod
    def freeze(obj: Dict[str, Any]) -> str:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def thaw(serialized: str) -> Dict[str, Any]:
        return json.loads(serialized)


# =============================
# Symbolic Engine
# =============================

class SymbolicEngine:
    def __init__(self, corpus: HebrewCorpus):
        self.corpus = corpus

    def combine(self, *chars: str) -> Dict[str, Any]:
        letters = [self.corpus.get(c) for c in chars]
        total = sum(l.structural_value for l in letters if l is not None)
        return {
            "letters": chars,
            "combined_structural_value": total
        }

    def compare(self, char_a: str, char_b: str) -> Dict[str, Any]:
        a = self.corpus.get(char_a)
        b = self.corpus.get(char_b)
        return {
            "a": a.serialize() if a else None,
            "b": b.serialize() if b else None,
            "difference": (a.structural_value - b.structural_value) if a and b else None
        }


# =============================
# Settlement Engine (Dynamic Schema)
# =============================

class SettlementEngine:
    """
    Settlement engine that:
    - uses dynamic schema registry
    - validates payloads against runtime schema
    - appends settlement entries to ledger
    """

    def __init__(self, schema_registry: SchemaRegistry):
        self.schema_registry = schema_registry
        self.entries: List[Dict[str, Any]] = []

    def _sha256(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _keccak256(self, payload: Dict[str, Any]) -> Optional[str]:
        try:
            import sha3
            raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            return sha3.keccak_256(raw).hexdigest()
        except ImportError:
            return None

    def settle(self, schema_name: str, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates payload against dynamic schema, then appends a settlement entry.
        """
        if not self.schema_registry.validate(schema_name, payload):
            raise ValueError(f"Payload does not conform to schema '{schema_name}'")

        entry = {
            "schema": schema_name,
            "key": key,
            "payload": payload,
            "sha256": self._sha256(payload),
            "keccak256": self._keccak256(payload),
            "timestamp": time.time(),
            "status": "SETTLED"
        }
        self.entries.append(entry)
        return entry

    def all(self) -> List[Dict[str, Any]]:
        return self.entries

    def latest(self) -> Optional[Dict[str, Any]]:
        return self.entries[-1] if self.entries else None


# =============================
# Example Runtime Wiring
# =============================

def build_default_schema_registry() -> SchemaRegistry:
    """
    Builds a schema registry and registers a minimal motif settlement schema.
    In your GitHub repo, you can replace this with dynamic file-based discovery.
    """
    registry = SchemaRegistry()

    motif_settlement_schema = {
        "type": "object",
        "required": ["id", "operator", "motif_key", "payload", "timestamp"],
        "properties": {
            "id": {"type": "string"},
            "operator": {"type": "string"},
            "motif_key": {"type": "string"},
            "payload": {"type": "object"},
            "timestamp": {"type": "number"},
            "note": {"type": "string"}
        }
    }

    registry.register_schema("motif_settlement", motif_settlement_schema)
    return registry


if __name__ == "__main__":
    # Build corpus and engines
    corpus = build_hebrew_corpus()
    query = HebrewQuery(corpus)
    engine = SymbolicEngine(corpus)
    motif_registry = MotifRegistry()
    schema_registry = build_default_schema_registry()
    settlement_engine = SettlementEngine(schema_registry)

    # Register motifs
    aleph = corpus.get("א")
    bet = corpus.get("ב")

    motif_registry.register("ALEPH", aleph.serialize())
    motif_registry.register("BET", bet.serialize())

    # Example settlement payloads (runtime schema discovery)
    aleph_payload = {
        "id": "motif-aleph-001",
        "operator": "core-operator",
        "motif_key": "ALEPH",
        "payload": motif_registry.get("ALEPH")["payload"],
        "timestamp": time.time(),
        "note": "Initial Aleph motif settlement."
    }

    bet_payload = {
        "id": "motif-bet-001",
        "operator": "core-operator",
        "motif_key": "BET",
        "payload": motif_registry.get("BET")["payload"],
        "timestamp": time.time(),
        "note": "Initial Bet motif settlement."
    }

    aleph_settlement = settlement_engine.settle("motif_settlement", "ALEPH", aleph_payload)
    bet_settlement = settlement_engine.settle("motif_settlement", "BET", bet_payload)

    print("Aleph:", aleph.serialize())
    print("Bet:", bet.serialize())
    print("Gematria 10:", query.by_gematria(10))
    print("Structural 26:", query.by_structural_value(26))
    print("Structural 3 (Bet):", query.by_structural_value(3))
    print("Combine א + ב:", engine.combine("א", "ב"))
    print("Motif ALEPH:", motif_registry.get("ALEPH"))
    print("Motif BET:", motif_registry.get("BET"))
    print("Aleph Settlement:", aleph_settlement)
    print("Bet Settlement:", bet_settlement)
    print("All Settlements:", settlement_engine.all())
