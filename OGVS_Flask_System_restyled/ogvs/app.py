from flask import Flask

from database import init_db, seed_data
from routes.auth import bp as auth_bp
from routes.student import bp as student_bp
from routes.faculty import bp as faculty_bp
from routes.admin import bp as admin_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = "ogvs-dev-secret-key-change-me"  # TODO: move to env var in production

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_globals():
        from flask import session
        return {"current_role": session.get("role"), "current_username": session.get("username")}

    @app.errorhandler(403)
    def forbidden(e):
        return "403 — You don't have access to this page.", 403

    @app.errorhandler(404)
    def not_found(e):
        return "404 — Page not found.", 404

    return app


app = create_app()

if __name__ == "__main__":
    init_db()
    seed_data()
    app.run(host="0.0.0.0", port=5000, debug=True)
