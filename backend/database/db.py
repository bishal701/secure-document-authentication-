import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.config import DB_PATH

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Documents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        document_id TEXT PRIMARY KEY,
        issuer_id TEXT NOT NULL,
        document_hash TEXT NOT NULL,
        watermark_hash TEXT NOT NULL,
        template_id TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ISSUED'
    );
    """)

    # Signatures Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signatures (
        signature_id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        key_id TEXT NOT NULL,
        signature TEXT NOT NULL,
        algorithm TEXT NOT NULL DEFAULT 'Ed25519',
        timestamp TEXT NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents (document_id)
    );
    """)

    # Trust Registry Table (Component B)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trust_registry (
        issuer_id TEXT PRIMARY KEY,
        domain TEXT NOT NULL UNIQUE,
        public_key TEXT NOT NULL,
        key_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, REVOKED, EXPIRED
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT
    );
    """)

    # Verification Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_logs (
        verification_id TEXT PRIMARY KEY,
        document_id TEXT,
        qr_status TEXT,
        signature_status TEXT,
        watermark_status TEXT,
        watermark_score REAL,
        copy_status TEXT,
        copy_score REAL,
        domain_status TEXT,
        ai_status TEXT,
        ai_score REAL,
        final_status TEXT,
        diagnostic_notes TEXT,
        timestamp TEXT NOT NULL
    );
    """)

    # Experiments & Ablation Logs Table (Roadmap Sections 7 & 16)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS experiments (
        experiment_id TEXT PRIMARY KEY,
        document_id TEXT,
        printer TEXT,
        paper TEXT,
        template TEXT,
        script TEXT,
        attack_type TEXT,
        rotation REAL,
        lighting TEXT,
        device TEXT,
        qr_success INTEGER,
        watermark_score REAL,
        copy_score REAL,
        signature_valid INTEGER,
        domain_valid INTEGER,
        ai_score REAL,
        final_result TEXT,
        verification_time REAL,
        timestamp TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)
