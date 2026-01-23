import sqlite3
import datetime
import uuid
import json

# [span_2](start_span)Executive Override Protocol - Demo Artifact[span_2](end_span)
# [span_3](start_span)Operationalizing containment-grade motifs into protocol law[span_3](end_span)

class ExecutiveOverrideProtocol:
    def __init__(self, db_name='protocol_canon.db'):
        self.db_name = db_name
        self._initialize_database()

    def _initialize_database(self):
        [span_4](start_span)"""Implements the Database Schema from the Protocol Spec[span_4](end_span)"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS motifs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    motif_text TEXT NOT NULL,
                    canonized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    anchor_txid TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_motif_anchor ON motifs (anchor_txid)')
            conn.commit()

    def canonize_motif(self, motif_text):
        [span_5](start_span)"""Converts motifs into enforceable schema[span_5](end_span)"""
        anchor_txid = str(uuid.uuid4())
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO motifs (motif_text, anchor_txid)
                VALUES (?, ?)
            ''', (motif_text, anchor_txid))
            conn.commit()
            
        return {
            "status": "200",
            "description": "Motif canonized into protocol law",
            "anchor_txid": anchor_txid
        }

if __name__ == "__main__":
    protocol = ExecutiveOverrideProtocol()
    # [span_6](start_span)Symbolic motif submission[span_6](end_span)
    print(json.dumps(protocol.canonize_motif("executive override"), indent=4))
