from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
# render_as_batch: SQLite can't ALTER TABLE in place, so Alembic needs batch mode to add
# columns there (harmless no-op on Postgres, which supports ALTER TABLE natively).
migrate = Migrate(render_as_batch=True)
socketio = SocketIO()
bcrypt = Bcrypt()
login_manager = LoginManager()
