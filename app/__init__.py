from flask import Flask, render_template

from .config import Config
from .extensions import bcrypt, db, login_manager, migrate, socketio
from .blueprints.auth import auth_bp
from .blueprints.missions import missions_bp
from .blueprints.scoring import scoring_bp
from .blueprints.cipher import cipher_bp
from .blueprints.leaderboard import leaderboard_bp
from .blueprints.mod import mod_bp
from .blueprints.booth import booth_bp
from .blueprints.security import security_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    bcrypt.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(missions_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(cipher_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(mod_bp)
    app.register_blueprint(booth_bp)
    app.register_blueprint(security_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User

        return User.query.get(int(user_id))

    @app.route("/")
    def home():
        return render_template("index.html")

    with app.app_context():
        db.create_all()

    return app
