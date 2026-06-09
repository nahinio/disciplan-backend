"""Raw SQL — project teams, invitations, tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one
from app.repositories import notification_repo


async def _is_active_member(
    conn: pymysql.Connection, team_id: int, user_id: int
) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM team_members
        WHERE team_id = %s AND user_id = %s AND left_at IS NULL
        """,
        (team_id, user_id),
    )
    return row is not None


async def list_pending_invitations(
    conn: pymysql.Connection, user_email: str
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ti.id AS invitation_id,
            ti.team_id,
            ti.invitee_email,
            ti.created_at,
            t.name AS team_name,
            c.code AS course_code,
            c.title AS course_title,
            s.section_label AS section,
            up.display_name AS leader_name,
            u.email AS leader_email
        FROM team_invitations ti
        INNER JOIN team_invitation_statuses tis ON tis.id = ti.status_id
        INNER JOIN teams t ON t.id = ti.team_id AND t.disbanded_at IS NULL
        INNER JOIN courses c ON c.id = t.course_id
        LEFT JOIN sections s ON s.id = t.section_id
        INNER JOIN team_members leader_tm ON leader_tm.team_id = t.id AND leader_tm.left_at IS NULL
        INNER JOIN team_member_roles leader_role ON leader_role.id = leader_tm.role_id
            AND leader_role.code = 'leader'
        INNER JOIN users u ON u.id = leader_tm.user_id
        INNER JOIN user_profiles up ON up.user_id = leader_tm.user_id
        WHERE tis.code = 'pending' AND LOWER(ti.invitee_email) = LOWER(%s)
        ORDER BY ti.created_at DESC
        """,
        (user_email,),
    )


async def is_faculty_assigned(conn: pymysql.Connection, team_id: int) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM teams
        WHERE id = %s AND assigned_by_faculty_user_id IS NOT NULL AND disbanded_at IS NULL
        """,
        (team_id,),
    )
    return row is not None


async def list_user_teams(
    conn: pymysql.Connection,
    user_id: int,
    *,
    faculty_assigned_only: bool = False,
) -> list[dict[str, Any]]:
    faculty_filter = (
        "AND t.assigned_by_faculty_user_id IS NOT NULL" if faculty_assigned_only else ""
    )
    return await fetch_all(
        conn,
        f"""
        SELECT
            t.id, t.name AS team_name, t.created_at,
            c.code AS course_code, c.title AS course_title,
            s.section_label AS section,
            up.display_name AS leader_name,
            u.email AS leader_email,
            (SELECT COUNT(*) FROM team_members tm
             WHERE tm.team_id = t.id AND tm.left_at IS NULL) AS member_count,
            EXISTS (
                SELECT 1 FROM user_pinned_teams upt
                WHERE upt.team_id = t.id AND upt.user_id = %s
            ) AS is_pinned
        FROM teams t
        INNER JOIN courses c ON c.id = t.course_id
        LEFT JOIN sections s ON s.id = t.section_id
        INNER JOIN team_members my_tm ON my_tm.team_id = t.id AND my_tm.user_id = %s AND my_tm.left_at IS NULL
        INNER JOIN team_members leader_tm ON leader_tm.team_id = t.id AND leader_tm.left_at IS NULL
        INNER JOIN team_member_roles leader_role ON leader_role.id = leader_tm.role_id AND leader_role.code = 'leader'
        INNER JOIN users u ON u.id = leader_tm.user_id
        INNER JOIN user_profiles up ON up.user_id = leader_tm.user_id
        WHERE t.disbanded_at IS NULL {faculty_filter}
        ORDER BY is_pinned DESC, t.created_at DESC
        """,
        (user_id, user_id),
    )


async def get_team(conn: pymysql.Connection, team_id: int) -> dict[str, Any] | None:
    team = await fetch_one(
        conn,
        """
        SELECT
            t.id, t.name AS team_name, t.created_at,
            c.code AS course_code, c.title AS course_title,
            s.section_label AS section
        FROM teams t
        INNER JOIN courses c ON c.id = t.course_id
        LEFT JOIN sections s ON s.id = t.section_id
        WHERE t.id = %s AND t.disbanded_at IS NULL
        """,
        (team_id,),
    )
    if not team:
        return None

    team["members"] = await fetch_all(
        conn,
        """
        SELECT
            u.id AS user_id, u.email,
            up.display_name AS name,
            tmr.code AS role_code,
            tm.joined_at,
            CASE WHEN tm.left_at IS NULL THEN 'accepted' ELSE 'left' END AS status
        FROM team_members tm
        INNER JOIN users u ON u.id = tm.user_id
        LEFT JOIN user_profiles up ON up.user_id = tm.user_id
        INNER JOIN team_member_roles tmr ON tmr.id = tm.role_id
        WHERE tm.team_id = %s AND tm.left_at IS NULL
        ORDER BY tmr.code = 'leader' DESC, tm.joined_at
        """,
        (team_id,),
    )

    team["pending_invitations"] = await fetch_all(
        conn,
        """
        SELECT ti.id, ti.invitee_email, ti.created_at
        FROM team_invitations ti
        INNER JOIN team_invitation_statuses tis ON tis.id = ti.status_id
        WHERE ti.team_id = %s AND tis.code = 'pending'
        ORDER BY ti.created_at DESC
        """,
        (team_id,),
    )

    team["tasks"] = await list_tasks(conn, team_id)
    team["important_dates"] = await list_dates(conn, team_id)
    team["announcements"] = await list_announcements(conn, team_id)
    return team


async def create_team(
    conn: pymysql.Connection,
    *,
    course_id: int,
    section_id: int | None,
    name: str,
    creator_user_id: int,
) -> int:
    leader_role = await fetch_one(
        conn, "SELECT id FROM team_member_roles WHERE code = 'leader' LIMIT 1"
    )
    if not leader_role:
        raise ValueError("Missing team_member_roles lookup")

    team_id = await execute_returning_id(
        conn,
        """
        INSERT INTO teams (section_id, course_id, name, created_by_user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (section_id, course_id, name, creator_user_id),
    )
    await execute(
        conn,
        """
        INSERT INTO team_members (team_id, user_id, role_id)
        VALUES (%s, %s, %s)
        """,
        (team_id, creator_user_id, leader_role["id"]),
    )
    return team_id


async def invite_member(
    conn: pymysql.Connection,
    *,
    team_id: int,
    invitee_email: str,
    invited_by_user_id: int,
) -> int:
    pending = await fetch_one(
        conn, "SELECT id FROM team_invitation_statuses WHERE code = 'pending' LIMIT 1"
    )
    if not pending:
        raise ValueError("Missing invitation status lookup")

    inv_id = await execute_returning_id(
        conn,
        """
        INSERT INTO team_invitations (team_id, invitee_email, invited_by_user_id, status_id)
        VALUES (%s, %s, %s, %s)
        """,
        (team_id, invitee_email.lower(), invited_by_user_id, pending["id"]),
    )

    invitee = await fetch_one(conn, "SELECT id FROM users WHERE email = %s", (invitee_email.lower(),))
    if invitee:
        team = await fetch_one(
            conn, "SELECT name FROM teams WHERE id = %s", (team_id,)
        )
        await notification_repo.create_notification(
            conn,
            recipient_user_id=invitee["id"],
            type_code="team_invite",
            title=f"Team invitation: {team['name'] if team else 'Project team'}",
            body_preview=f"You were invited to join {team['name'] if team else 'a team'}",
            reference_type_code="team",
            reference_id=team_id,
            action_path=f"/teams/{team_id}?tab=chat",
        )
    return inv_id


async def respond_invitation(
    conn: pymysql.Connection,
    *,
    invitation_id: int,
    user_id: int,
    user_email: str,
    accept: bool,
) -> bool:
    inv = await fetch_one(
        conn,
        """
        SELECT ti.id, ti.team_id, tis.code AS status_code
        FROM team_invitations ti
        INNER JOIN team_invitation_statuses tis ON tis.id = ti.status_id
        WHERE ti.id = %s AND LOWER(ti.invitee_email) = LOWER(%s)
        """,
        (invitation_id, user_email),
    )
    if not inv or inv["status_code"] != "pending":
        return False

    status_code = "accepted" if accept else "declined"
    status = await fetch_one(
        conn, "SELECT id FROM team_invitation_statuses WHERE code = %s", (status_code,)
    )
    if not status:
        return False

    await execute(
        conn,
        """
        UPDATE team_invitations
        SET status_id = %s, responded_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (status["id"], invitation_id),
    )

    if accept:
        member_role = await fetch_one(
            conn, "SELECT id FROM team_member_roles WHERE code = 'member' LIMIT 1"
        )
        if member_role:
            await execute(
                conn,
                """
                INSERT INTO team_members (team_id, user_id, role_id)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE left_at = NULL, role_id = VALUES(role_id)
                """,
                (inv["team_id"], user_id, member_role["id"]),
            )
    return True


async def leave_team(conn: pymysql.Connection, team_id: int, user_id: int) -> bool:
    count = await execute(
        conn,
        """
        UPDATE team_members SET left_at = UTC_TIMESTAMP(3)
        WHERE team_id = %s AND user_id = %s AND left_at IS NULL
        """,
        (team_id, user_id),
    )
    return count > 0


async def disband_team(conn: pymysql.Connection, team_id: int) -> None:
    await execute(
        conn,
        "UPDATE teams SET disbanded_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (team_id,),
    )


async def list_tasks(conn: pymysql.Connection, team_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            tt.id, tt.title, tt.description, tt.due_at, tt.is_completed,
            tp.code AS priority_code,
            u.email AS assignee_email,
            up.display_name AS assignee_name
        FROM team_tasks tt
        INNER JOIN task_priorities tp ON tp.id = tt.priority_id
        LEFT JOIN users u ON u.id = tt.assignee_user_id
        LEFT JOIN user_profiles up ON up.user_id = tt.assignee_user_id
        WHERE tt.team_id = %s
        ORDER BY tt.is_completed ASC, tt.due_at ASC, tt.id DESC
        """,
        (team_id,),
    )


async def create_task(
    conn: pymysql.Connection,
    *,
    team_id: int,
    creator_user_id: int,
    title: str,
    description: str | None,
    assignee_user_id: int | None,
    priority_code: str,
    due_at: datetime | None,
) -> int:
    priority = await fetch_one(
        conn, "SELECT id FROM task_priorities WHERE code = %s", (priority_code,)
    )
    if not priority:
        raise ValueError(f"Unknown priority: {priority_code}")
    return await execute_returning_id(
        conn,
        """
        INSERT INTO team_tasks (
            team_id, title, description, assignee_user_id,
            priority_id, due_at, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (team_id, title, description, assignee_user_id, priority["id"], due_at, creator_user_id),
    )


async def toggle_task(conn: pymysql.Connection, team_id: int, task_id: int, completed: bool) -> bool:
    count = await execute(
        conn,
        """
        UPDATE team_tasks
        SET is_completed = %s,
            completed_at = CASE WHEN %s = 1 THEN UTC_TIMESTAMP(3) ELSE NULL END
        WHERE id = %s AND team_id = %s
        """,
        (int(completed), int(completed), task_id, team_id),
    )
    return count > 0


async def list_dates(conn: pymysql.Connection, team_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT id, label AS title, occurs_at AS date, created_at
        FROM team_important_dates
        WHERE team_id = %s
        ORDER BY occurs_at ASC
        """,
        (team_id,),
    )


async def create_date(
    conn: pymysql.Connection,
    *,
    team_id: int,
    creator_user_id: int,
    label: str,
    occurs_at: datetime,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO team_important_dates (team_id, label, occurs_at, created_by_user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (team_id, label, occurs_at, creator_user_id),
    )


async def list_announcements(conn: pymysql.Connection, team_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ta.id, ta.title, ta.body AS content, ta.created_at,
            up.display_name AS author_name
        FROM team_announcements ta
        INNER JOIN user_profiles up ON up.user_id = ta.author_user_id
        WHERE ta.team_id = %s
        ORDER BY ta.created_at DESC
        """,
        (team_id,),
    )


async def create_announcement(
    conn: pymysql.Connection,
    *,
    team_id: int,
    author_user_id: int,
    title: str,
    body: str,
) -> int:
    ann_id = await execute_returning_id(
        conn,
        """
        INSERT INTO team_announcements (team_id, author_user_id, title, body)
        VALUES (%s, %s, %s, %s)
        """,
        (team_id, author_user_id, title, body),
    )

    team = await fetch_one(conn, "SELECT name FROM teams WHERE id = %s", (team_id,))
    team_name = team["name"] if team else "your team"
    await execute(
        conn,
        """
        INSERT INTO notifications (
            recipient_user_id, type_id, title, body_preview,
            reference_type_id, reference_id, action_path
        )
        SELECT
            tm.user_id,
            (SELECT id FROM notification_types WHERE code = 'new_announcement' LIMIT 1),
            %s,
            LEFT(%s, 300),
            (SELECT id FROM reference_entity_types WHERE code = 'team' LIMIT 1),
            %s,
            CONCAT('/teams/', %s, '?tab=announcements')
        FROM team_members tm
        WHERE tm.team_id = %s
          AND tm.left_at IS NULL
          AND tm.user_id <> %s
        """,
        (
            f"Team announcement: {team_name}",
            body or title,
            team_id,
            team_id,
            team_id,
            author_user_id,
        ),
    )
    return ann_id


async def pin_team(conn: pymysql.Connection, user_id: int, team_id: int) -> None:
    await execute(
        conn,
        """
        INSERT IGNORE INTO user_pinned_teams (user_id, team_id)
        VALUES (%s, %s)
        """,
        (user_id, team_id),
    )


async def unpin_team(conn: pymysql.Connection, user_id: int, team_id: int) -> None:
    await execute(
        conn,
        "DELETE FROM user_pinned_teams WHERE user_id = %s AND team_id = %s",
        (user_id, team_id),
    )


async def user_is_leader(conn: pymysql.Connection, team_id: int, user_id: int) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM team_members tm
        INNER JOIN team_member_roles tmr ON tmr.id = tm.role_id
        WHERE tm.team_id = %s AND tm.user_id = %s AND tm.left_at IS NULL AND tmr.code = 'leader'
        """,
        (team_id, user_id),
    )
    return row is not None


async def list_section_teams(conn: pymysql.Connection, section_id: int) -> list[dict[str, Any]]:
    teams = await fetch_all(
        conn,
        """
        SELECT
            t.id, t.name AS team_name, t.created_at,
            c.code AS course_code, c.title AS course_title,
            s.section_label AS section,
            leader_up.display_name AS leader_name,
            leader_u.email AS leader_email,
            (SELECT COUNT(*) FROM team_members tm
             WHERE tm.team_id = t.id AND tm.left_at IS NULL) AS member_count
        FROM teams t
        INNER JOIN courses c ON c.id = t.course_id
        LEFT JOIN sections s ON s.id = t.section_id
        INNER JOIN team_members leader_tm ON leader_tm.team_id = t.id AND leader_tm.left_at IS NULL
        INNER JOIN team_member_roles leader_role ON leader_role.id = leader_tm.role_id AND leader_role.code = 'leader'
        INNER JOIN users leader_u ON leader_u.id = leader_tm.user_id
        INNER JOIN user_profiles leader_up ON leader_up.user_id = leader_tm.user_id
        WHERE t.section_id = %s AND t.disbanded_at IS NULL
        ORDER BY t.created_at DESC
        """,
        (section_id,),
    )
    for team in teams:
        team["members"] = await fetch_all(
            conn,
            """
            SELECT
                u.email,
                up.display_name AS name,
                tmr.code AS role_code,
                tm.joined_at
            FROM team_members tm
            INNER JOIN users u ON u.id = tm.user_id
            LEFT JOIN user_profiles up ON up.user_id = tm.user_id
            INNER JOIN team_member_roles tmr ON tmr.id = tm.role_id
            WHERE tm.team_id = %s AND tm.left_at IS NULL
            ORDER BY tmr.code = 'leader' DESC, up.display_name
            """,
            (team["id"],),
        )
    return teams


async def faculty_assign_team(
    conn: pymysql.Connection,
    *,
    course_id: int,
    section_id: int,
    name: str,
    faculty_user_id: int,
    leader_user_id: int,
    member_user_ids: list[int],
) -> int:
    leader_role = await fetch_one(
        conn, "SELECT id FROM team_member_roles WHERE code = 'leader' LIMIT 1"
    )
    member_role = await fetch_one(
        conn, "SELECT id FROM team_member_roles WHERE code = 'member' LIMIT 1"
    )
    if not leader_role or not member_role:
        raise ValueError("Missing team member roles")

    team_id = await execute_returning_id(
        conn,
        """
        INSERT INTO teams (
            section_id, course_id, name,
            created_by_user_id, leader_user_id, assigned_by_faculty_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (section_id, course_id, name, faculty_user_id, leader_user_id, faculty_user_id),
    )

    all_ids = list({leader_user_id, *member_user_ids})
    for uid in all_ids:
        role_id = leader_role["id"] if uid == leader_user_id else member_role["id"]
        await execute(
            conn,
            "INSERT INTO team_members (team_id, user_id, role_id) VALUES (%s, %s, %s)",
            (team_id, uid, role_id),
        )
        team = await fetch_one(conn, "SELECT name FROM teams WHERE id = %s", (team_id,))
        await notification_repo.create_notification(
            conn,
            recipient_user_id=uid,
            type_code="team_invite",
            title=f"Assigned to team: {team['name'] if team else name}",
            body_preview=f"You were added to project team {name}",
            reference_type_code="team",
            reference_id=team_id,
            action_path=f"/teams/{team_id}?tab=chat",
        )
    return team_id


async def update_team(
    conn: pymysql.Connection,
    team_id: int,
    *,
    name: str | None = None,
    leader_user_id: int | None = None,
    add_member_user_ids: list[int] | None = None,
    remove_member_user_ids: list[int] | None = None,
) -> bool:
    team = await fetch_one(
        conn, "SELECT id FROM teams WHERE id = %s AND disbanded_at IS NULL", (team_id,)
    )
    if not team:
        return False

    if name is not None:
        await execute(conn, "UPDATE teams SET name = %s WHERE id = %s", (name, team_id))
    if leader_user_id is not None:
        leader_role = await fetch_one(
            conn, "SELECT id FROM team_member_roles WHERE code = 'leader' LIMIT 1"
        )
        member_role = await fetch_one(
            conn, "SELECT id FROM team_member_roles WHERE code = 'member' LIMIT 1"
        )
        if leader_role and member_role:
            await execute(
                conn,
                """
                UPDATE team_members SET role_id = %s
                WHERE team_id = %s AND left_at IS NULL AND role_id = %s
                """,
                (member_role["id"], team_id, leader_role["id"]),
            )
            await execute(
                conn,
                """
                UPDATE team_members SET role_id = %s
                WHERE team_id = %s AND user_id = %s AND left_at IS NULL
                """,
                (leader_role["id"], team_id, leader_user_id),
            )
            await execute(
                conn,
                "UPDATE teams SET leader_user_id = %s WHERE id = %s",
                (leader_user_id, team_id),
            )

    member_role = await fetch_one(
        conn, "SELECT id FROM team_member_roles WHERE code = 'member' LIMIT 1"
    )
    if add_member_user_ids and member_role:
        for uid in add_member_user_ids:
            await execute(
                conn,
                """
                INSERT INTO team_members (team_id, user_id, role_id)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE left_at = NULL, role_id = VALUES(role_id)
                """,
                (team_id, uid, member_role["id"]),
            )

    if remove_member_user_ids:
        for uid in remove_member_user_ids:
            await execute(
                conn,
                """
                UPDATE team_members SET left_at = UTC_TIMESTAMP(3)
                WHERE team_id = %s AND user_id = %s AND left_at IS NULL
                """,
                (team_id, uid),
            )
    return True


async def list_team_member_ids(conn: pymysql.Connection, team_id: int) -> list[int]:
    rows = await fetch_all(
        conn,
        """
        SELECT user_id FROM team_members
        WHERE team_id = %s AND left_at IS NULL
        """,
        (team_id,),
    )
    return [r["user_id"] for r in rows]
