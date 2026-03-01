"""
SQLite database service for the World Situation Monitor.

Provides persistent storage for events, aircraft trails, vessel positions,
and alerts using async SQLite via aiosqlite. Designed to complement the
in-memory data store by enabling historical queries, trend analysis,
and trail rendering.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite

logger = logging.getLogger("wsm.database")

# Database path from environment, defaulting to wsm.db in the working directory
DATABASE_URL: str = os.getenv("DATABASE_URL", "./wsm.db")

# Module-level connection reference for reuse across calls
_db: Optional[aiosqlite.Connection] = None


async def _get_db() -> aiosqlite.Connection:
    """Get or create the database connection."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_URL)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA synchronous=NORMAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db() -> None:
    """Close the database connection. Call on application shutdown."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database connection closed.")


# ============================================================================
# Schema initialization
# ============================================================================

async def init_db() -> None:
    """
    Create all tables if they do not exist.

    Tables:
        events       - Conflicts, missiles, earthquakes, and other geo-events
        aircraft_tracks - Position history for aircraft trail rendering
        vessels      - Vessel position snapshots
        alerts       - System and intelligence alerts
    """
    db = await _get_db()

    await db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id          TEXT NOT NULL,
            layer       TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT '',
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            title       TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            severity    TEXT NOT NULL DEFAULT 'low',
            source      TEXT NOT NULL DEFAULT '',
            timestamp   TEXT NOT NULL,
            metadata    TEXT NOT NULL DEFAULT '{}',
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            PRIMARY KEY (id, layer)
        );

        CREATE INDEX IF NOT EXISTS idx_events_layer
            ON events (layer);

        CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON events (timestamp);

        CREATE INDEX IF NOT EXISTS idx_events_layer_timestamp
            ON events (layer, timestamp);

        CREATE TABLE IF NOT EXISTS aircraft_tracks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            icao24      TEXT NOT NULL,
            callsign    TEXT NOT NULL DEFAULT '',
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            altitude    REAL,
            velocity    REAL,
            heading     REAL,
            on_ground   INTEGER NOT NULL DEFAULT 0,
            origin_country TEXT NOT NULL DEFAULT '',
            squawk      TEXT,
            timestamp   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_aircraft_tracks_icao24
            ON aircraft_tracks (icao24);

        CREATE INDEX IF NOT EXISTS idx_aircraft_tracks_timestamp
            ON aircraft_tracks (timestamp);

        CREATE INDEX IF NOT EXISTS idx_aircraft_tracks_icao24_timestamp
            ON aircraft_tracks (icao24, timestamp DESC);

        CREATE TABLE IF NOT EXISTS vessels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi        TEXT NOT NULL,
            name        TEXT NOT NULL DEFAULT '',
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            speed       REAL,
            course      REAL,
            vessel_type TEXT NOT NULL DEFAULT '',
            flag        TEXT NOT NULL DEFAULT '',
            destination TEXT NOT NULL DEFAULT '',
            timestamp   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_vessels_mmsi
            ON vessels (mmsi);

        CREATE INDEX IF NOT EXISTS idx_vessels_timestamp
            ON vessels (timestamp);

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type  TEXT NOT NULL,
            severity    TEXT NOT NULL DEFAULT 'info',
            title       TEXT NOT NULL DEFAULT '',
            message     TEXT NOT NULL DEFAULT '',
            layer       TEXT NOT NULL DEFAULT '',
            lat         REAL,
            lon         REAL,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            metadata    TEXT NOT NULL DEFAULT '{}',
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_type
            ON alerts (alert_type);

        CREATE INDEX IF NOT EXISTS idx_alerts_severity
            ON alerts (severity);

        CREATE INDEX IF NOT EXISTS idx_alerts_created_at
            ON alerts (created_at);
    """)

    await db.commit()
    logger.info("Database initialized at %s", DATABASE_URL)


# ============================================================================
# Event storage and retrieval
# ============================================================================

async def store_events(layer: str, events: list[dict]) -> int:
    """
    Store a batch of geo-events for a given layer.

    Uses INSERT OR REPLACE so that re-ingesting the same event ID + layer
    combination updates the existing row rather than creating duplicates.

    Args:
        layer:  The layer name (e.g. 'conflicts', 'missiles', 'earthquakes').
        events: List of event dicts. Expected keys align with the GeoEvent
                or MissileEvent models.

    Returns:
        Number of events stored.
    """
    if not events:
        return 0

    db = await _get_db()
    rows = []
    for event in events:
        rows.append((
            str(event.get("id", "")),
            layer,
            str(event.get("type", "")),
            float(event.get("lat", event.get("launch_lat", 0.0))),
            float(event.get("lon", event.get("launch_lon", 0.0))),
            str(event.get("title", "")),
            str(event.get("description", "")),
            str(event.get("severity", event.get("status", "low"))),
            str(event.get("source", "")),
            _to_iso(event.get("timestamp")),
            json.dumps(event.get("metadata", {}), default=str),
        ))

    await db.executemany(
        """
        INSERT OR REPLACE INTO events
            (id, layer, type, lat, lon, title, description, severity, source, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    await db.commit()
    logger.debug("Stored %d events for layer '%s'", len(rows), layer)
    return len(rows)


async def get_events_since(layer: str, since: datetime) -> list[dict]:
    """
    Retrieve events for a layer that occurred after a given timestamp.

    Args:
        layer: The layer name to query.
        since: Only return events with timestamp >= this value.

    Returns:
        List of event dicts ordered by timestamp ascending.
    """
    db = await _get_db()
    since_iso = since.isoformat()

    cursor = await db.execute(
        """
        SELECT id, layer, type, lat, lon, title, description, severity,
               source, timestamp, metadata, created_at
        FROM events
        WHERE layer = ? AND timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (layer, since_iso),
    )
    rows = await cursor.fetchall()
    return [_row_to_event_dict(row) for row in rows]


async def get_historical_counts(layer: str, hours: int = 24) -> list[dict]:
    """
    Get hourly event counts for a layer over the past N hours.
    Useful for rendering trend charts on the frontend.

    Args:
        layer: The layer name to query.
        hours: Number of hours to look back (default 24).

    Returns:
        List of dicts with 'hour' (ISO string) and 'count' keys,
        ordered chronologically.
    """
    db = await _get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    cursor = await db.execute(
        """
        SELECT strftime('%Y-%m-%dT%H:00:00Z', timestamp) AS hour,
               COUNT(*) AS count
        FROM events
        WHERE layer = ? AND timestamp >= ?
        GROUP BY hour
        ORDER BY hour ASC
        """,
        (layer, cutoff),
    )
    rows = await cursor.fetchall()
    return [{"hour": row["hour"], "count": row["count"]} for row in rows]


# ============================================================================
# Aircraft trail storage and retrieval
# ============================================================================

async def store_aircraft_positions(positions: list[dict]) -> int:
    """
    Store a batch of aircraft position snapshots for trail history.

    Each call appends new rows, building up a time-series of positions
    that can be queried to draw flight trails on the map.

    Args:
        positions: List of aircraft dicts matching the Aircraft model fields.

    Returns:
        Number of positions stored.
    """
    if not positions:
        return 0

    db = await _get_db()
    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for pos in positions:
        lat = pos.get("lat")
        lon = pos.get("lon")
        # Skip positions without valid coordinates
        if lat is None or lon is None:
            continue
        rows.append((
            str(pos.get("icao24", "")),
            str(pos.get("callsign", "")).strip(),
            float(lat),
            float(lon),
            _to_float(pos.get("altitude") or pos.get("baro_altitude")),
            _to_float(pos.get("velocity")),
            _to_float(pos.get("heading")),
            1 if pos.get("on_ground") else 0,
            str(pos.get("origin_country", "")),
            pos.get("squawk"),
            now_iso,
        ))

    if not rows:
        return 0

    await db.executemany(
        """
        INSERT INTO aircraft_tracks
            (icao24, callsign, lat, lon, altitude, velocity, heading,
             on_ground, origin_country, squawk, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    await db.commit()
    logger.debug("Stored %d aircraft positions", len(rows))
    return len(rows)


async def get_aircraft_trails(icao24: str, limit: int = 50) -> list[dict]:
    """
    Get the most recent position history for a specific aircraft.

    Args:
        icao24: The ICAO 24-bit transponder address of the aircraft.
        limit:  Maximum number of trail points to return (default 50).

    Returns:
        List of position dicts ordered oldest-to-newest, suitable for
        drawing a polyline trail on the map.
    """
    db = await _get_db()
    cursor = await db.execute(
        """
        SELECT icao24, callsign, lat, lon, altitude, velocity, heading,
               on_ground, origin_country, squawk, timestamp
        FROM aircraft_tracks
        WHERE icao24 = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (icao24, limit),
    )
    rows = await cursor.fetchall()

    # Reverse so the result is oldest-first (natural trail order)
    return [_row_to_aircraft_dict(row) for row in reversed(rows)]


# ============================================================================
# Vessel storage and retrieval
# ============================================================================

async def store_vessel_positions(positions: list[dict]) -> int:
    """
    Store a batch of vessel position snapshots.

    Args:
        positions: List of vessel dicts matching the Vessel model fields.

    Returns:
        Number of positions stored.
    """
    if not positions:
        return 0

    db = await _get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []

    for pos in positions:
        rows.append((
            str(pos.get("mmsi", "")),
            str(pos.get("name", "")),
            float(pos.get("lat", 0.0)),
            float(pos.get("lon", 0.0)),
            _to_float(pos.get("speed")),
            _to_float(pos.get("course")),
            str(pos.get("vessel_type", "")),
            str(pos.get("flag", "")),
            str(pos.get("destination", "")),
            _to_iso(pos.get("last_update")) or now_iso,
        ))

    await db.executemany(
        """
        INSERT INTO vessels
            (mmsi, name, lat, lon, speed, course, vessel_type, flag, destination, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    await db.commit()
    logger.debug("Stored %d vessel positions", len(rows))
    return len(rows)


# ============================================================================
# Alert storage and retrieval
# ============================================================================

async def store_alert(
    alert_type: str,
    title: str,
    message: str,
    severity: str = "info",
    layer: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    metadata: Optional[dict] = None,
) -> int:
    """
    Store a single alert.

    Args:
        alert_type: Category of alert (e.g. 'escalation', 'threshold', 'anomaly').
        title:      Short alert title.
        message:    Full alert message.
        severity:   One of 'info', 'warning', 'critical'.
        layer:      Related data layer, if any.
        lat:        Latitude of the alert location, if applicable.
        lon:        Longitude of the alert location, if applicable.
        metadata:   Additional structured data.

    Returns:
        The row ID of the inserted alert.
    """
    db = await _get_db()
    cursor = await db.execute(
        """
        INSERT INTO alerts (alert_type, severity, title, message, layer, lat, lon, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert_type,
            severity,
            title,
            message,
            layer,
            lat,
            lon,
            json.dumps(metadata or {}, default=str),
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def get_recent_alerts(limit: int = 50, severity: Optional[str] = None) -> list[dict]:
    """
    Get recent alerts, optionally filtered by severity.

    Args:
        limit:    Maximum number of alerts to return.
        severity: Filter by severity level, or None for all.

    Returns:
        List of alert dicts ordered newest-first.
    """
    db = await _get_db()

    if severity:
        cursor = await db.execute(
            """
            SELECT id, alert_type, severity, title, message, layer,
                   lat, lon, acknowledged, metadata, created_at
            FROM alerts
            WHERE severity = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (severity, limit),
        )
    else:
        cursor = await db.execute(
            """
            SELECT id, alert_type, severity, title, message, layer,
                   lat, lon, acknowledged, metadata, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    rows = await cursor.fetchall()
    return [_row_to_alert_dict(row) for row in rows]


# ============================================================================
# Maintenance
# ============================================================================

async def cleanup_old_data(days: int = 7) -> dict[str, int]:
    """
    Remove data older than N days from all tables.

    Args:
        days: Number of days to retain. Data older than this is deleted.

    Returns:
        Dict mapping table names to the number of rows deleted.
    """
    db = await _get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    deleted = {}

    for table, col in [
        ("events", "timestamp"),
        ("aircraft_tracks", "timestamp"),
        ("vessels", "timestamp"),
        ("alerts", "created_at"),
    ]:
        cursor = await db.execute(
            f"DELETE FROM {table} WHERE {col} < ?",  # noqa: S608 - table names are hardcoded
            (cutoff,),
        )
        deleted[table] = cursor.rowcount

    await db.commit()

    total = sum(deleted.values())
    if total > 0:
        logger.info(
            "Cleaned up %d old rows (cutoff=%s): %s",
            total, cutoff, deleted,
        )
    return deleted


# ============================================================================
# Helper functions
# ============================================================================

def _to_iso(value) -> str:
    """Convert a value to an ISO 8601 timestamp string."""
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _to_float(value) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _row_to_event_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to an event dictionary."""
    d = dict(row)
    # Parse the metadata JSON back into a dict
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
    return d


def _row_to_aircraft_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to an aircraft position dictionary."""
    return {
        "icao24": row["icao24"],
        "callsign": row["callsign"],
        "lat": row["lat"],
        "lon": row["lon"],
        "altitude": row["altitude"],
        "velocity": row["velocity"],
        "heading": row["heading"],
        "on_ground": bool(row["on_ground"]),
        "origin_country": row["origin_country"],
        "squawk": row["squawk"],
        "timestamp": row["timestamp"],
    }


def _row_to_alert_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to an alert dictionary."""
    d = dict(row)
    d["acknowledged"] = bool(d.get("acknowledged", 0))
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
    return d
