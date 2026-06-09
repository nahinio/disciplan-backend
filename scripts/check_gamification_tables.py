#!/usr/bin/env python3
import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings  # noqa: E402

settings = get_settings()
ctx = None
if settings.db_ssl:
    ca = Path(settings.db_ssl_ca_path)
    ctx = ssl.create_default_context(cafile=str(ca)) if ca.exists() else ssl.create_default_context()

conn = pymysql.connect(
    host=settings.db_host,
    port=settings.db_port,
    user=settings.db_user,
    password=settings.db_password,
    database=settings.db_name,
    ssl=ctx,
    connect_timeout=15,
)
cur = conn.cursor()
for t in [
    "achievement_definitions",
    "user_achievement_progress",
    "user_streaks",
    "point_award_caps",
]:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (settings.db_name, t),
    )
    print(t, cur.fetchone()[0])
cur.execute("SELECT id, code FROM gamification_tiers ORDER BY id")
print("tiers:", cur.fetchall())
conn.close()
