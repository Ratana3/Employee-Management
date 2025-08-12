    
from datetime import datetime, timedelta
from email.message import EmailMessage
import logging
import os
import smtplib
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf


@admin_bp.route('/verification', methods=['GET'])
def verification():
    return render_template('Admin/Verifications.html')

#Route for account verification (Start)

# ---- ROUTES CRUD ----

@admin_bp.route("/manage/routes", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["list_routes"])
def list_routes(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT r.id, r.route_name, r.description
            FROM routes r
            ORDER BY r.route_name
        """)
        routes = [{"route_id": r[0], "route_name": r[1], "description": r[2]} for r in cur.fetchall()]
        # fetch actions for all routes
        for route in routes:
            cur.execute("""
                SELECT a.id, a.action_name, a.description
                FROM route_actions ra
                JOIN actions a ON ra.action_id = a.id
                WHERE ra.route_id = %s
                ORDER BY a.action_name
            """, (route["route_id"],))
            route["actions"] = [
                {"action_id": a[0], "action_name": a[1], "description": a[2]} for a in cur.fetchall()
            ]
        # Audit: log successful route listing
        log_audit(admin_id, role, "list_routes", f"Listed all routes and actions")
        return jsonify({"routes": routes})
    except Exception as e:
        # Incident: log error fetching route list
        log_incident(admin_id, role, f"Failed to list routes: {str(e)}", severity="Medium")
        return jsonify({"error": "Failed to fetch routes"}), 500
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route("/manage/routes", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["create_route"])
def create_route(admin_id, role, role_id):
    data = request.json
    route_name = data.get("route_name")
    description = data.get("description")
    if not route_name:
        return jsonify({"error": "Missing route_name"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO routes (route_name, description) VALUES (%s, %s) RETURNING id", (route_name, description))
        route_id = cur.fetchone()[0]
        conn.commit()
        # Audit: log successful route creation
        log_audit(admin_id, role, "create_route", f"Created route '{route_name}' (id={route_id})")
        return jsonify({"route_id": route_id}), 201
    except Exception as e:
        conn.rollback()
        # Incident: log error creating route
        log_incident(admin_id, role, f"Failed to create route '{route_name}': {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route("/manage/routes/<int:route_id>", methods=["PUT"])
@token_required_with_roles_and_2fa(required_actions=["update_route"])
def update_route(admin_id, role, role_id, route_id):
    data = request.json
    route_name = data.get("route_name")
    description = data.get("description")
    if not route_name:
        return jsonify({"error": "Missing route_name"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE routes SET route_name = %s, description = %s WHERE id = %s RETURNING id", (route_name, description, route_id))
        updated = cur.fetchone()
        conn.commit()
        if updated:
            # Audit: log successful route update
            log_audit(admin_id, role, "update_route", f"Updated route id={route_id} to name='{route_name}'")
            return jsonify({"message": "Route updated"})
        else:
            # Incident: route not found
            log_incident(admin_id, role, f"Tried to update non-existent route id={route_id}", severity="Low")
            return jsonify({"error": "Route not found"}), 404
    except Exception as e:
        conn.rollback()
        # Incident: log error updating route
        log_incident(admin_id, role, f"Failed to update route id={route_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route("/manage/routes/<int:route_id>", methods=["DELETE"])
@token_required_with_roles_and_2fa(required_actions=["delete_route"])
def delete_route(admin_id, role, role_id, route_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM routes WHERE id = %s RETURNING id", (route_id,))
        deleted = cur.fetchone()
        conn.commit()
        if deleted:
            # Audit: log successful route deletion
            log_audit(admin_id, role, "delete_route", f"Deleted route id={route_id}")
            return jsonify({"message": "Route deleted"})
        else:
            # Incident: route not found
            log_incident(admin_id, role, f"Tried to delete non-existent route id={route_id}", severity="Low")
            return jsonify({"error": "Route not found"}), 404
    except Exception as e:
        conn.rollback()
        # Incident: log error deleting route
        log_incident(admin_id, role, f"Failed to delete route id={route_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

# ---- ACTIONS CRUD ----

@csrf.exempt
@admin_bp.route("/manage/routes/<int:route_id>/actions", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["create_action"])
def create_action(admin_id, role, role_id, route_id):
    data = request.json
    action_name = data.get("action_name")
    description = data.get("description")
    if not action_name:
        return jsonify({"error": "Missing action_name"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # create action if not exists, then link to route
        cur.execute("INSERT INTO actions (action_name, description) VALUES (%s, %s) ON CONFLICT (action_name) DO UPDATE SET description=EXCLUDED.description RETURNING id", (action_name, description))
        action_id = cur.fetchone()[0]
        cur.execute("INSERT INTO route_actions (route_id, action_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (route_id, action_id))
        conn.commit()
        # Audit: log successful action creation/linking
        log_audit(admin_id, role, "create_action", f"Created/linked action '{action_name}' (id={action_id}) to route id={route_id}")
        return jsonify({"action_id": action_id}), 201
    except Exception as e:
        conn.rollback()
        # Incident: log error creating action
        log_incident(admin_id, role, f"Failed to create/link action '{action_name}' to route id={route_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route("/manage/routes/<int:route_id>/actions/<int:action_id>", methods=["PUT"])
@token_required_with_roles_and_2fa(required_actions=["update_action"])
def update_action(admin_id, role, role_id, route_id, action_id):
    data = request.json
    action_name = data.get("action_name")
    description = data.get("description")
    if not action_name:
        return jsonify({"error": "Missing action_name"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE actions SET action_name = %s, description = %s WHERE id = %s RETURNING id", (action_name, description, action_id))
        updated = cur.fetchone()
        conn.commit()
        if updated:
            # Audit: log successful action update
            log_audit(admin_id, role, "update_action", f"Updated action id={action_id} to name='{action_name}' on route id={route_id}")
            return jsonify({"message": "Action updated"})
        else:
            # Incident: action not found
            log_incident(admin_id, role, f"Tried to update non-existent action id={action_id} on route id={route_id}", severity="Low")
            return jsonify({"error": "Action not found"}), 404
    except Exception as e:
        conn.rollback()
        # Incident: log error updating action
        log_incident(admin_id, role, f"Failed to update action id={action_id} on route id={route_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route("/manage/routes/<int:route_id>/actions/<int:action_id>", methods=["DELETE"])
@token_required_with_roles_and_2fa(required_actions=["delete_action"])
def delete_action(admin_id, role, role_id, route_id, action_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM route_actions WHERE route_id = %s AND action_id = %s", (route_id, action_id))
        cur.execute("DELETE FROM actions WHERE id = %s RETURNING id", (action_id,))
        deleted = cur.fetchone()
        conn.commit()
        if deleted:
            # Audit: log successful action deletion
            log_audit(admin_id, role, "delete_action", f"Deleted action id={action_id} from route id={route_id}")
            return jsonify({"message": "Action deleted"})
        else:
            # Incident: action not found
            log_incident(admin_id, role, f"Tried to delete non-existent action id={action_id} from route id={route_id}", severity="Low")
            return jsonify({"error": "Action not found"}), 404
    except Exception as e:
        conn.rollback()
        # Incident: log error deleting action
        log_incident(admin_id, role, f"Failed to delete action id={action_id} from route id={route_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

# --- ROUTE: Get all routes and their actions (with description) ---
@admin_bp.route("/routes", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["get_all_routes_and_actions"])
def get_all_routes_and_actions(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT r.id, r.route_name, r.description, a.id, a.action_name, a.description
            FROM routes r
            LEFT JOIN route_actions ra ON r.id = ra.route_id
            LEFT JOIN actions a ON ra.action_id = a.id
            ORDER BY r.route_name, a.action_name
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Organize as [{route_id, route_name, description, actions: [{action_id, action_name, description}, ...]}, ...]
        routes_dict = {}
        for route_id, route_name, route_desc, action_id, action_name, action_desc in rows:
            if route_id not in routes_dict:
                routes_dict[route_id] = {
                    "route_id": route_id,
                    "route_name": route_name,
                    "description": route_desc,
                    "actions": []
                }
            if action_id:
                routes_dict[route_id]["actions"].append({
                    "action_id": action_id,
                    "action_name": action_name,
                    "description": action_desc
                })
        routes = list(routes_dict.values())
        # Audit: log successful fetch of all routes/actions
        log_audit(admin_id, role, "get_all_routes_and_actions", "Fetched all routes and their actions")
        return jsonify({"routes": routes})
    except Exception as e:
        # Incident: log error fetching all routes/actions
        log_incident(admin_id, role, f"Failed to fetch all routes and actions: {str(e)}", severity="Medium")
        return jsonify({"error": "Failed to fetch routes and actions"}), 500

# --- ROUTE: Get actions for a specific route (with description) ---
@admin_bp.route("/route-actions/<string:route_name>", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["get_actions_for_route"])
def get_actions_for_route(admin_id, role, role_id, route_name):
    """
    Returns the list of actions (with id, name, and description) available for a specific route/page.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Get route id and description
        cur.execute("SELECT id, description FROM routes WHERE route_name = %s", (route_name,))
        route_row = cur.fetchone()
        if not route_row:
            cur.close()
            conn.close()
            # Incident: route not found
            log_incident(admin_id, role, f"Tried to fetch actions for non-existent route '{route_name}'", severity="Low")
            return jsonify({"error": f"Route '{route_name}' not found."}), 404
        route_id, route_desc = route_row

        # Get actions for this route
        cur.execute("""
            SELECT a.id, a.action_name, a.description
            FROM route_actions ra
            JOIN actions a ON ra.action_id = a.id
            WHERE ra.route_id = %s
            ORDER BY a.action_name
        """, (route_id,))
        actions = [
            {"action_id": row[0], "action_name": row[1], "description": row[2]}
            for row in cur.fetchall()
        ]
        cur.close()
        conn.close()
        # Audit: log successful fetch of actions for a route
        log_audit(admin_id, role, "get_actions_for_route", f"Fetched actions for route '{route_name}' (id={route_id})")
        return jsonify({
            "route_id": route_id,
            "route_name": route_name,
            "route_description": route_desc,
            "actions": actions
        })
    except Exception as e:
        # Incident: log error fetching actions for route
        log_incident(admin_id, role, f"Error fetching actions for route '{route_name}': {str(e)}", severity="Medium")
        logging.error(f"Error fetching actions for route {route_name}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
       
# --- ROUTE: Get admin permissions for a route or all routes ---
@admin_bp.route("/get-admin-permissions/<int:target_admin_id>", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["get_admin_permissions"])
def get_admin_permissions(admin_id, role, role_id, target_admin_id):
    route = request.args.get("route")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if route == "ALL":
            # Return all routes with granted actions, including descriptions
            cur.execute("""
                SELECT r.id, r.route_name, r.description, a.id, a.action_name, a.description
                FROM admin_route_actions ara
                JOIN routes r ON ara.route_id = r.id
                JOIN actions a ON ara.action_id = a.id
                WHERE ara.admin_id = %s
                ORDER BY r.route_name, a.action_name
            """, (target_admin_id,))
            rows = cur.fetchall()
            # Group by route
            route_dict = {}
            for route_id, route_name, route_desc, action_id, action_name, action_desc in rows:
                if route_id not in route_dict:
                    route_dict[route_id] = {
                        "route_id": route_id,
                        "route_name": route_name,
                        "description": route_desc,
                        "granted_actions": []
                    }
                route_dict[route_id]["granted_actions"].append({
                    "action_id": action_id,
                    "action_name": action_name,
                    "description": action_desc
                })
            routes = list(route_dict.values())
            # Audit: log successful fetch of all permissions for admin
            log_audit(admin_id, role, "get_admin_permissions", f"Fetched ALL permissions for admin_id={target_admin_id}")
            return jsonify({"routes": routes})

        elif not route:
            return jsonify({"error": "Missing route parameter"}), 400
        else:
            # Look up route_id and route description
            cur.execute("SELECT id, description FROM routes WHERE route_name = %s", (route,))
            route_row = cur.fetchone()
            if not route_row:
                # Incident: route not found
                log_incident(admin_id, role, f"Tried to fetch permissions for non-existent route '{route}'", severity="Low")
                return jsonify({"error": f"Route '{route}' not found."}), 400
            route_id, route_desc = route_row
            # Get all possible actions for the route (with description)
            cur.execute("""
                SELECT a.id, a.action_name, a.description
                FROM route_actions ra
                JOIN actions a ON ra.action_id = a.id
                WHERE ra.route_id = %s
            """, (route_id,))
            all_actions = {row[0]: {"action_name": row[1], "description": row[2]} for row in cur.fetchall()}
            # Get granted actions for this admin on this route (with description)
            cur.execute("""
                SELECT a.id, a.action_name, a.description
                FROM admin_route_actions ara
                JOIN actions a ON ara.action_id = a.id
                WHERE ara.admin_id = %s AND ara.route_id = %s
            """, (target_admin_id, route_id))
            granted_actions = {row[0]: {"action_name": row[1], "description": row[2]} for row in cur.fetchall()}

            # Available actions are those in all_actions not in granted_actions
            available_actions = [
                {
                    "action_id": aid,
                    "action_name": ainfo["action_name"],
                    "description": ainfo["description"],
                }
                for aid, ainfo in all_actions.items() if aid not in granted_actions
            ]
            granted_actions_list = [
                {
                    "action_id": aid,
                    "action_name": ainfo["action_name"],
                    "description": ainfo["description"],
                }
                for aid, ainfo in granted_actions.items()
            ]
            # Audit: log successful fetch of specific route permissions for admin
            log_audit(admin_id, role, "get_admin_permissions", f"Fetched permissions for admin_id={target_admin_id} on route='{route}'")
            return jsonify({
                "route_id": route_id,
                "route": route,
                "description": route_desc,
                "available_actions": sorted(available_actions, key=lambda x: x["action_name"]),
                "granted_actions": sorted(granted_actions_list, key=lambda x: x["action_name"]),
            })
    except Exception as e:
        # Incident: log error fetching admin permissions
        log_incident(admin_id, role, f"Error fetching permissions for admin_id={target_admin_id} (route={route}): {str(e)}", severity="Medium")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cur.close()
        conn.close()

# --- ROUTE: Get admins (for table and search) ---
@admin_bp.route("/get-admins", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["get_admins"])
def get_admins(admin_id, role, role_id):
    search = request.args.get("search", "").strip().lower()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT admin_id, first_name, last_name, email, r.role_name
            FROM admins a
            JOIN roles r ON a.role_id = r.role_id
            WHERE LOWER(first_name) LIKE %s
               OR LOWER(last_name) LIKE %s
               OR LOWER(email) LIKE %s
            ORDER BY first_name, last_name
        """
        wildcard = f"%{search}%"
        cur.execute(query, (wildcard, wildcard, wildcard))
        admins = [
            {
                "admin_id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "email": row[3],
                "role": row[4],
            }
            for row in cur.fetchall()
        ]
        # Audit: log successful admin search/fetch
        log_audit(admin_id, role, "get_admins", f"Fetched admins with search='{search}'")
        return jsonify({"admins": admins})
    except Exception as e:
        # Incident: log error fetching admins
        log_incident(admin_id, role, f"Error fetching admins (search='{search}'): {str(e)}", severity="Medium")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cur.close()
        conn.close()

# --- ROUTE: Grant access (actions) to a specific admin ---
@csrf.exempt
@admin_bp.route("/grant_access", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=['grant_access'])
def grant_access(current_admin_id, role, role_id):
    logging.debug(f"Grant Access called by admin_id={current_admin_id}, role={role}, role_id={role_id}")

    data = request.get_json()
    logging.debug(f"Received data payload: {data}")

    target_admin_id = data.get("admin_id")
    permissions = data.get("permissions", [])  # [{"route_id": ..., "actions": [action_id, ...]}, ...]
    logging.debug(f"Target admin_id: {target_admin_id}, Permissions: {permissions}")

    if not target_admin_id or not permissions:
        logging.warning("Missing admin_id or permissions in request.")
        return jsonify({"error": "Missing admin_id or permissions"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Grant each selected permission (route_id + action_id)
        for perm in permissions:
            route_id = perm.get("route_id")
            actions = perm.get("actions", [])
            logging.debug(f"Granting permissions for route_id={route_id} with actions={actions}")

            for action_id in actions:
                logging.debug(f"Inserting (admin_id={target_admin_id}, route_id={route_id}, action_id={action_id})")
                cur.execute(
                    """
                    INSERT INTO admin_route_actions (admin_id, route_id, action_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (admin_id, route_id, action_id) DO UPDATE SET action_id = EXCLUDED.action_id
                    """,
                    (target_admin_id, route_id, action_id)
                )

        conn.commit()
        logging.info(f"Successfully granted access to admin_id={target_admin_id} with permissions={permissions}")

        # Audit: log successful access grant
        log_audit(current_admin_id, role, "grant_access", f"Granted access to admin_id={target_admin_id} with permissions={permissions}")
        return jsonify({"message": "Access granted successfully"})
    except Exception as e:
        conn.rollback()
        import traceback
        tb = traceback.format_exc()
        logging.error(f"Error granting access to admin_id={target_admin_id}: {e}\nTraceback:\n{tb}")

        # Incident: log error granting access
        log_incident(current_admin_id, role, f"Error granting access to admin_id={target_admin_id}: {str(e)}", severity="High")
        print(tb)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- ROUTE: Remove access (actions) from a specific admin ---
@csrf.exempt
@admin_bp.route("/remove-access", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["remove_access"])
def remove_access(current_admin_id, role, role_id):
    data = request.get_json()
    target_admin_id = data.get("admin_id")
    route_id = data.get("route_id")
    actions = data.get("actions", [])
    if not target_admin_id or not route_id or not actions:
        return jsonify({"error": "Missing admin_id, route_id, or actions"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        logging.debug(f"Removing actions {actions} from admin_id={target_admin_id} on route_id={route_id}")
        # Remove only the specified actions
        cur.executemany(
            "DELETE FROM admin_route_actions WHERE admin_id = %s AND route_id = %s AND action_id = %s",
            [(target_admin_id, route_id, action_id) for action_id in actions]
        )
        conn.commit()

        # Check if there are any granted actions left for this admin on this route
        cur.execute(
            "SELECT COUNT(*) FROM admin_route_actions WHERE admin_id = %s AND route_id = %s",
            (target_admin_id, route_id)
        )
        remaining_count = cur.fetchone()[0]

        # Audit: log successful permission removal
        log_audit(current_admin_id, role, "remove_access", f"Removed actions {actions} on route_id={route_id} from admin_id={target_admin_id}")

        return jsonify({
            "message": "Access removed successfully",
            "no_actions_left": remaining_count == 0,
        })
    except Exception as e:
        conn.rollback()
        import traceback
        tb = traceback.format_exc()
        logging.error(f"Error removing actions for admin_id={target_admin_id}: {e}\nTraceback:\n{tb}")
        # Incident: log error during access removal
        log_incident(current_admin_id, role, f"Error removing actions {actions} on route_id={route_id} from admin_id={target_admin_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
#Route for deleting the registration
logging.basicConfig(level=logging.DEBUG)

@admin_bp.route("/delete-registration", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["delete_admin"])
def delete_admin(current_admin_id, current_role, current_role_id):
    data = request.json
    target_admin_id = data.get("admin_id")

    logging.debug(f"Received delete request data: {data}")
    logging.debug(f"Parsed target_admin_id (to delete): {target_admin_id}")
    logging.debug(f"Request made by current_admin_id: {current_admin_id}")

    if not target_admin_id:
        logging.warning("Admin ID missing in request.")
        return jsonify({"error": True, "message": "Admin ID is required"}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Nullify as admin team lead in teams
        logging.info(f"[DELETE_ADMIN] Setting team_lead_admin_id = NULL in teams where team_lead_admin_id = {target_admin_id}")
        cur.execute("UPDATE teams SET team_lead_admin_id = NULL WHERE team_lead_admin_id = %s", (target_admin_id,))
        conn.commit()

        # Delete related two_factor_verifications by admin_id
        logging.debug(f"Attempting to delete two_factor_verifications for admin_id {target_admin_id}")
        cur.execute("DELETE FROM two_factor_verifications WHERE admin_id = %s", (target_admin_id,))
        logging.debug("Successfully deleted from two_factor_verifications.")
        conn.commit()

        # Delete from team_members by admin_id
        logging.info(f"[DELETE_ADMIN] Deleting from team_members where admin_id = {target_admin_id}")
        cur.execute("DELETE FROM team_members WHERE admin_id = %s", (target_admin_id,))
        conn.commit()

        # Get admin's email before deleting admin record
        cur.execute("SELECT email FROM admins WHERE admin_id = %s", (target_admin_id,))
        admin_email_row = cur.fetchone()
        admin_email = admin_email_row[0] if admin_email_row else None

        # If admin is also an employee, do the full delete_employee cascade
        employee_id = None
        if admin_email:
            cur.execute("SELECT employee_id FROM employees WHERE email = %s", (admin_email,))
            emp_row = cur.fetchone()
            employee_id = emp_row[0] if emp_row else None

        if employee_id:
            # Nullify as employee team lead in teams
            logging.info(f"[DELETE_ADMIN] Setting team_lead_employee_id = NULL in teams where team_lead_employee_id = {employee_id}")
            cur.execute("UPDATE teams SET team_lead_employee_id = NULL WHERE team_lead_employee_id = %s", (employee_id,))
            conn.commit()

            # Delete from employee_breaks
            logging.info(f"[DELETE_ADMIN] Deleting from employee_breaks where employee_id = {employee_id}")
            cur.execute("DELETE FROM employee_breaks WHERE employee_id = %s", (employee_id,))
            conn.commit()

            # Delete from attendance_logs
            logging.info(f"[DELETE_ADMIN] Deleting from attendance_logs where employee_id = {employee_id}")
            cur.execute("DELETE FROM attendance_logs WHERE employee_id = %s", (employee_id,))
            conn.commit()
            
            # Handle goals and their dependencies
            cur.execute("SELECT goal_id FROM goals WHERE employee_id = %s", (employee_id,))
            goal_ids = [row[0] for row in cur.fetchall()]
            for goal_id in goal_ids:
                logging.info(f"[DELETE_ADMIN] Deleting from goal_action_plans where goal_id = {goal_id}")
                cur.execute("DELETE FROM goal_action_plans WHERE goal_id = %s", (goal_id,))
                conn.commit()
                logging.info(f"[DELETE_ADMIN] Deleting from goal_evaluations where goal_id = {goal_id}")
                cur.execute("DELETE FROM goal_evaluations WHERE goal_id = %s", (goal_id,))
                conn.commit()

            # Delete from other tables referencing employee_id
            child_tables = [
                "badge_assignments",
                "bonuses_incentives",
                "expense_claims",
                "goal_progress",
                "goal_progress_notes",
                "goal_progress_percentage",
                "survey_responses",
                "savings_plans",
                "two_factor_verifications",
                "assessment_answers",
                "survey_assignments",
                "ticket_responses",
            ]
            for table in child_tables:
                logging.info(f"[DELETE_ADMIN] Deleting from {table} where employee_id = {employee_id}")
                cur.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee_id,))
                conn.commit()

            # Delete from goals
            logging.info(f"[DELETE_ADMIN] Deleting from goals where employee_id = {employee_id}")
            cur.execute("DELETE FROM goals WHERE employee_id = %s", (employee_id,))
            conn.commit()

            # Delete from other related tables (by employee_id)
            related_tables = [
                "team_members", "payroll", "tax_records", "feedback_requests", 
                "alerts", "meetings", "announcements", "bank_details"
            ]
            for table in related_tables:
                logging.info(f"[DELETE_ADMIN] Deleting from {table} where employee_id = {employee_id}")
                cur.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee_id,))
                conn.commit()

            # Finally, delete from employees table
            logging.info("[DELETE_ADMIN] Deleting from employees table.")
            cur.execute("DELETE FROM employees WHERE employee_id = %s;", (employee_id,))
            conn.commit()
            logging.info(f"[DELETE_ADMIN] Deleted employee from employees table with ID {employee_id}.")
        else:
            logging.warning(f"Admin with ID {target_admin_id} not found in employees table; skipping employees delete.")

        # Delete from admins table
        logging.debug(f"Attempting to delete admin with admin_id {target_admin_id}")
        cur.execute("DELETE FROM admins WHERE admin_id = %s", (target_admin_id,))
        logging.debug("Successfully deleted from admins.")
        conn.commit()

        logging.info(f"Admin with ID {target_admin_id} deleted successfully by {current_admin_id}.")

        # Audit: log successful admin deletion
        log_audit(current_admin_id, current_role, "delete_admin", f"Deleted admin with ID {target_admin_id}")

        return jsonify({"message": "Admin registration deleted successfully"}), 200

    except psycopg2.errors.ForeignKeyViolation as fk_error:
        if conn:
            conn.rollback()
        logging.error(f"Foreign key violation while deleting admin {target_admin_id}: {fk_error}")
        log_incident(current_admin_id, current_role, f"ForeignKeyViolation while deleting admin {target_admin_id}: {fk_error}", severity="Medium")
        return jsonify({
            "error": True,
            "message": "Cannot delete admin because it is referenced in other tables (e.g., badge_assignments, expense_claims, etc)."
        }), 400

    except Exception as e:
        if conn:
            conn.rollback()
        logging.exception(f"Unexpected error while deleting admin {target_admin_id}")
        log_incident(current_admin_id, current_role, f"Unexpected error while deleting admin {target_admin_id}: {str(e)}", severity="High")
        return jsonify({
            "error": True,
            "message": f"An unexpected error occurred: {str(e)}"
        }), 500

    finally:
        if cur:
            try:
                cur.close()
                logging.debug("[DELETE_ADMIN] Cursor closed.")
            except Exception as ex:
                logging.warning(f"[DELETE_ADMIN] Failed to close cursor: {str(ex)}")
        if conn:
            try:
                conn.close()
                logging.debug("[DELETE_ADMIN] Database connection closed.")
            except Exception as ex:
                logging.warning(f"[DELETE_ADMIN] Failed to close DB connection: {str(ex)}")
                                            
# ✅ Route to Fetch Pending Admin Registrations (with assigned permissions from admin_route_permissions)
@admin_bp.route("/pending-registrations", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["get_pending_registrations"])
def get_pending_registrations(admin_id, role, role_id):
    try:
        logging.debug("Fetching pending admin registrations...")

        conn = get_db_connection()
        cur = conn.cursor()

        # Get all admins with role name lookup
        cur.execute(
            """
            SELECT a.admin_id, a.first_name, a.last_name, a.email, 
                   r.role_name, a.is_verified 
            FROM admins a
            LEFT JOIN roles r ON a.role_id = r.role_id
            """
        )
        all_admins = cur.fetchall()
        logging.debug(f"Fetched {len(all_admins)} admins.")

        admin_list = []
        for admin in all_admins:
            admin_id = admin[0]
            logging.debug(f"Processing admin ID: {admin_id}")

            # Fetch distinct route names assigned to this admin via admin_route_actions
            cur.execute(
                """
                SELECT DISTINCT routes.route_name
                FROM admin_route_actions ara
                JOIN routes ON ara.route_id = routes.id
                WHERE ara.admin_id = %s
                """,
                (admin_id,),
            )
            assigned_permissions = [row[0] for row in cur.fetchall()]
            logging.debug(f"Admin ID {admin_id} permissions: {assigned_permissions}")

            admin_list.append({
                "admin_id": admin_id,
                "first_name": admin[1],
                "last_name": admin[2],
                "email": admin[3],
                "role": admin[4],
                "is_verified": admin[5],
                "permissions": assigned_permissions,  # Always a list, even if empty
            })

        cur.close()
        conn.close()
        logging.debug("Successfully fetched admin registrations.")

        # Audit: log successful pending registration fetch
        log_audit(admin_id, role, "get_pending_registrations", "Fetched all pending admin registrations and permissions")

        return jsonify({"pending_admins": admin_list})

    except Exception as e:
        logging.error(f"Error fetching admin registrations: {e}", exc_info=True)
        # Incident: log error fetching pending registrations
        log_incident(admin_id, role, f"Error fetching pending admin registrations: {str(e)}", severity="Medium")
        return jsonify({"error": "Internal server error"}), 500
     
# --- Verify Admin Route ---
@admin_bp.route("/verify", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["verify_admin"])
def verify_admin(current_admin_id, current_role, current_role_id):
    data = request.json
    target_admin_id = data.get("admin_id")

    if not target_admin_id:
        return jsonify({"message": "Admin ID is missing!"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        logging.info(f"Admin ID to verify: {target_admin_id}")
        logging.info(f"Verified by Super Admin ID: {current_admin_id}")

        # --- Get verified admin's email ---
        cur.execute("SELECT email FROM admins WHERE admin_id = %s", (target_admin_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            logging.error(f"No email found for target admin {target_admin_id}")
            return jsonify({"message": "Target admin not found or missing email"}), 404
        target_email = row[0]

        # --- Perform verification ---
        cur.execute(
            """
            UPDATE admins
            SET is_verified = %s
            WHERE admin_id = %s
            """,
            (True, target_admin_id),
        )

        conn.commit()
        logging.info(f"Successfully verified admin {target_admin_id} by {current_admin_id}")

        # Audit: log successful admin verification
        log_audit(current_admin_id, current_role, "verify_admin", f"Verified admin {target_admin_id}")

        # --- Send verification email using EMAIL_USER as sender ---
        try:
            sender_email = os.environ.get("EMAIL_USER")
            sender_password = os.environ.get("EMAIL_PASSWORD")
            smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.environ.get("SMTP_PORT", 587))

            if not (sender_email and sender_password):
                logging.error("EMAIL_USER or EMAIL_PASSWORD not set in environment variables.")
            else:
                msg = EmailMessage()
                msg["Subject"] = "Your admin account has been verified"
                msg["From"] = sender_email
                msg["To"] = target_email
                msg.set_content("Congratulations! Your admin account has been successfully verified.")

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.send_message(msg)
                logging.info(f"Verification email sent to {target_email} from {sender_email}")

        except Exception as email_error:
            logging.error(f"Failed to send verification email: {email_error}", exc_info=True)
            # Continue even if email fails

        return jsonify({"message": "Admin verification updated successfully!"})

    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        logging.error(f"Error: {str(e)}")
        # Incident: log error during verification
        log_incident(current_admin_id, current_role, f"Error verifying admin {target_admin_id}: {str(e)}", severity="High")
        return jsonify({"message": f"Error: {str(e)}"}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# --- Reject Admin Route ---
@admin_bp.route("/reject", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["reject_admin"])
def reject_admin(current_admin_id, current_role, current_role_id):
    data = request.json
    target_admin_id = data.get("admin_id")
    title = data.get("title")
    message = data.get("message")

    logging.debug(f"Received rejection request: {data}")
    logging.debug(f"Rejection performed by admin {current_admin_id}")

    if not target_admin_id or not title or not message:
        logging.warning("Missing admin_id, title, or message in request.")
        return jsonify({"error": "Admin ID, title, and message are required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- Get rejected admin's email ---
        cur.execute("SELECT email FROM admins WHERE admin_id = %s", (target_admin_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            logging.error(f"No email found for target admin {target_admin_id}")
            return jsonify({"error": "Target admin not found or missing email"}), 404
        target_email = row[0]

        # Determine who is assigning the alert
        assigned_by_super_admin = current_admin_id if current_role == "super_admin" else None
        assigned_by_admin = current_admin_id if current_role != "super_admin" else None

        # Store rejection reason in alerts table
        cur.execute(
            """
            INSERT INTO alerts (
                title, message, created_at, 
                assigned_by_admin, assigned_by_super_admin
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, message, datetime.now(), assigned_by_admin, assigned_by_super_admin),
        )
        logging.debug(f"Rejection alert created for admin ID {target_admin_id}.")

        # Update the 'is_verified' column to false for the rejected admin
        cur.execute(
            """
            UPDATE admins
            SET is_verified = %s
            WHERE admin_id = %s
            """,
            (False, target_admin_id),
        )
        logging.debug(f"Admin ID {target_admin_id} verification status set to false.")

        # Remove all permissions associated with this admin in the admin_permissions table
        cur.execute(
            """
            DELETE FROM admin_route_actions
            WHERE admin_id = %s
            """,
            (target_admin_id,),
        )
        logging.debug(f"All permissions removed for admin ID {target_admin_id}.")

        conn.commit()
        cur.close()
        conn.close()

        # Audit: log successful admin rejection
        log_audit(current_admin_id, current_role, "reject_admin", f"Rejected admin {target_admin_id} with title '{title}'")

        # --- Send rejection email using EMAIL_USER as sender ---
        try:
            sender_email = os.environ.get("EMAIL_USER")
            sender_password = os.environ.get("EMAIL_PASSWORD")
            smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.environ.get("SMTP_PORT", 587))

            if not (sender_email and sender_password):
                logging.error("EMAIL_USER or EMAIL_PASSWORD not set in environment variables.")
            else:
                msg = EmailMessage()
                msg["Subject"] = title
                msg["From"] = sender_email
                msg["To"] = target_email
                msg.set_content(message)

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.send_message(msg)
                logging.info(f"Rejection email sent to {target_email} from {sender_email}")

        except Exception as email_error:
            logging.error(f"Failed to send rejection email: {email_error}", exc_info=True)
            # Continue even if email fails

        return jsonify({"message": "Admin rejected, alert created, permissions removed, and notification sent"}), 200

    except Exception as e:
        logging.error(f"Error rejecting admin: {e}", exc_info=True)
        # Incident: log error during rejection
        log_incident(current_admin_id, current_role, f"Error rejecting admin {target_admin_id}: {str(e)}", severity="High")
        return jsonify({"error": "Server error"}), 500
    
@admin_bp.route("/review-requests", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["review_requests"])
def review_requests(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    # Join to admins and super_admins for info
    cur.execute("""
        SELECT ar.id, 
               COALESCE(a.email, sa.email) as email,
               CASE WHEN ar.admin_id IS NOT NULL THEN 'admin' ELSE 'super_admin' END as role,
               r.route_name, act.action_name, ar.status, ar.requested_at,COALESCE(a.first_name, sa.last_name) as name
        FROM admin_access_requests ar
        LEFT JOIN admins a ON ar.admin_id = a.admin_id
        LEFT JOIN super_admins sa ON ar.super_admin_id = sa.super_admin_id
        JOIN routes r ON ar.route_id = r.id
        JOIN actions act ON ar.action_id = act.id
        WHERE ar.status = 'pending'
        ORDER BY ar.requested_at ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    requests = [
        {
            "id": row[0],
            "email": row[1],
            "role": row[2],
            "route_name": row[3],
            "action_name": row[4],
            "status": row[5],
            "requested_at": row[6].isoformat() if row[6] else None,
            "name": row[7]
        }
        for row in rows
    ]
    return jsonify({"requests": requests})

@csrf.exempt
@admin_bp.route("/review-requests/action", methods=["POST"])
@token_required_with_roles_and_2fa(required_actions=["review_requests_action"])
def review_requests_action(admin_id, role, role_id):
    data = request.get_json()
    req_id = data.get("request_id")
    action = data.get("action")  # "approve" or "reject"
    if not req_id or action not in ["approve", "reject"]:
        return jsonify({"error": "Invalid input."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch details of the request
        cur.execute("""
            SELECT admin_id, route_id, action_id FROM admin_access_requests
            WHERE id = %s AND status = 'pending'
        """, (req_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Request not found or already handled."}), 404

        target_admin_id, route_id, action_id = row

        if action == "approve":
            # 1. Update status to approved
            cur.execute("""
                UPDATE admin_access_requests
                SET status = 'approved'
                WHERE id = %s AND status = 'pending'
            """, (req_id,))
            # 2. Insert into admin_route_actions (grant permission)
            cur.execute("""
                INSERT INTO admin_route_actions (admin_id, route_id, action_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (admin_id, route_id, action_id) DO UPDATE SET action_id = EXCLUDED.action_id
            """, (target_admin_id, route_id, action_id))
        elif action == "reject":
            # Only update status to rejected
            cur.execute("""
                UPDATE admin_access_requests
                SET status = 'rejected'
                WHERE id = %s AND status = 'pending'
            """, (req_id,))

        conn.commit()
        return jsonify({"message": f"Request {action}d."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
#Route for account verification (End)