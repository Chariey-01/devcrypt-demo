from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from .extensions import login_manager


def wants_json(req):
    # A plain browser page navigation always advertises text/html prominently in Accept; this
    # app's own fetch() calls never set an explicit Accept header, so they fall back to the
    # browser's bare "*/*" default — that asymmetry is what tells the two apart here, since
    # neither login_required nor roles_required has any other signal to go on.
    return "text/html" not in req.accept_mimetypes


def register_error_handlers(app):
    @login_manager.unauthorized_handler
    def _unauthorized():
        # Reached whenever @login_required's current_user.is_authenticated check fails — no
        # session at all, an expired one, or (per User.is_authenticated's dependency on
        # is_active) a deactivated staff account. Never a genuine authorization failure (that's
        # the 403 handler below) and never caused by a temporary outage — the request reached a
        # live server just fine, it's specifically "please sign in again."
        message = "Your session has expired. Please sign in again."
        if wants_json(request):
            return jsonify({"error": message}), 401
        flash(message, "error")
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def _forbidden(_error):
        # Reached only from roles_required's explicit role check — a real, logged-in session
        # that simply doesn't have permission for this page (wrong staff role, or a team trying
        # a staff-only route). Not a session/outage problem, so redirecting to login would just
        # loop; a plain explanation is more honest than Werkzeug's stock Forbidden page.
        message = "You don't have permission to access that page with your current account."
        if wants_json(request):
            return jsonify({"error": message}), 403
        return render_template("errors/403.html", message=message), 403

    @app.errorhandler(CSRFError)
    def _csrf_error(_error):
        # A stale/missing token — most commonly a tab left open across a full server
        # redeploy, which rotates SECRET_KEY-derived signing state. Same wants_json split as
        # every other handler here rather than Flask-WTF's default plain-text 400 body.
        message = "Your form session expired — please refresh the page and try again."
        if wants_json(request):
            return jsonify({"error": message}), 400
        flash(message, "error")
        resp = redirect(request.referrer or url_for("home"))
        resp.status_code = 400
        return resp

    @app.errorhandler(429)
    def _rate_limited(_error):
        message = "Too many attempts — please wait a moment before trying again."
        if wants_json(request):
            return jsonify({"error": message}), 429
        flash(message, "error")
        resp = redirect(request.referrer or url_for("home"))
        resp.status_code = 429
        return resp
