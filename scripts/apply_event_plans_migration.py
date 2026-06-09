#!/usr/bin/env python3
"""Apply sql/022_event_plans.sql and user_tasks/calendar_events column extensions."""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.config import get_settings  # noqa: E402


def build_ssl() -> ssl.SSLContext | None:
    settings = get_settings()
    if not settings.db_ssl:
        return None
    ca = Path(settings.db_ssl_ca_path)
    if ca.exists():
        ctx = ssl.create_default_context(cafile=str(ca))
    else:
        ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def table_exists(conn: pymysql.Connection, table: str) -> bool:
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (settings.db_name, table),
        )
        return bool(cur.fetchone()[0])


def column_exists(conn: pymysql.Connection, table: str, column: str) -> bool:
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (settings.db_name, table, column),
        )
        return bool(cur.fetchone()[0])


def add_column(conn: pymysql.Connection, table: str, column: str, ddl: str) -> None:
    if column_exists(conn, table, column):
        print(f"  {table}.{column} already exists — skipped")
        return
    try:
        with conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        print(f"  Added {table}.{column}")
    except pymysql.err.OperationalError as exc:
        if exc.args and exc.args[0] == 1060:
            print(f"  {table}.{column} already exists — skipped")
            conn.rollback()
            return
        raise


def main() -> None:
    settings = get_settings()
    sql_path = ROOT / "sql" / "022_event_plans.sql"
    print(f"Connecting to {settings.db_host}:{settings.db_port}/{settings.db_name} ...")
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        ssl=build_ssl(),
        connect_timeout=15,
    )
    try:
        if not table_exists(conn, "planner_event_plans"):
            print("  Applying 022_event_plans.sql ...")
            script = sql_path.read_text(encoding="utf-8")
            statements = [s.strip() for s in script.split(";") if s.strip()]
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            conn.commit()
        else:
            print("  planner_event_plans already exists — skipped plans DDL")

        if not table_exists(conn, "planner_event_recurrence"):
            print("  Creating planner_event_recurrence ...")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE planner_event_recurrence (
                        id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        plan_id         BIGINT UNSIGNED NOT NULL,
                        day_of_week     TINYINT UNSIGNED NOT NULL,
                        starts_time     TIME            NOT NULL,
                        duration_min    SMALLINT UNSIGNED NOT NULL DEFAULT 60,
                        PRIMARY KEY (id),
                        KEY idx_recurrence_plan (plan_id),
                        CONSTRAINT fk_recurrence_plan
                            FOREIGN KEY (plan_id) REFERENCES planner_event_plans (id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            conn.commit()
        else:
            print("  planner_event_recurrence already exists — skipped")

        print("  Extending user_tasks ...")
        add_column(conn, "user_tasks", "event_plan_id", "event_plan_id BIGINT UNSIGNED NULL AFTER calendar_event_id")
        add_column(conn, "user_tasks", "slice_date", "slice_date DATE NULL AFTER event_plan_id")
        add_column(conn, "user_tasks", "base_target_percent", "base_target_percent DECIMAL(5,2) NULL")
        add_column(conn, "user_tasks", "carryover_percent", "carryover_percent DECIMAL(5,2) NOT NULL DEFAULT 0")
        add_column(conn, "user_tasks", "effective_target_percent", "effective_target_percent DECIMAL(5,2) NULL")
        add_column(conn, "user_tasks", "completed_portion_percent", "completed_portion_percent DECIMAL(5,2) NOT NULL DEFAULT 0")
        add_column(conn, "user_tasks", "days_behind", "days_behind TINYINT UNSIGNED NOT NULL DEFAULT 0")
        add_column(conn, "user_tasks", "was_skipped_forward", "was_skipped_forward TINYINT(1) NOT NULL DEFAULT 0")
        add_column(conn, "user_tasks", "weight_profile", "weight_profile ENUM('planner','scheduled') NOT NULL DEFAULT 'planner'")
        add_column(conn, "user_tasks", "occurrence_starts_at", "occurrence_starts_at DATETIME(3) NULL")
        add_column(conn, "user_tasks", "slice_closed", "slice_closed TINYINT(1) NOT NULL DEFAULT 0")

        print("  Extending calendar_events ...")
        add_column(conn, "calendar_events", "event_plan_id", "event_plan_id BIGINT UNSIGNED NULL")
        add_column(conn, "calendar_events", "is_recurring_instance", "is_recurring_instance TINYINT(1) NOT NULL DEFAULT 0")

        print("  Extending user_profiles ...")
        add_column(conn, "user_profiles", "timezone", "timezone VARCHAR(64) NULL DEFAULT 'Asia/Dhaka'")

        print("  Creating slice unique index ...")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE UNIQUE INDEX uq_user_tasks_plan_slice "
                    "ON user_tasks (user_id, event_plan_id, slice_date)"
                )
            print("  Added uq_user_tasks_plan_slice")
        except pymysql.err.OperationalError as exc:
            if exc.args and exc.args[0] in (1061, 1062):
                print("  uq_user_tasks_plan_slice already exists — skipped")
                conn.rollback()
            else:
                raise

        conn.commit()
        print("Event plans migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
