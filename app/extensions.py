from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman
from flask_wtf import CSRFProtect

db = SQLAlchemy()
# render_as_batch: SQLite can't ALTER TABLE in place, so Alembic needs batch mode to add
# columns there (harmless no-op on Postgres, which supports ALTER TABLE natively).
migrate = Migrate(render_as_batch=True)
socketio = SocketIO()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()
# In-memory storage is fine here: the deployed app is a single gunicorn worker
# (-k gevent -w 1, see railway.json/Procfile) — one process, one in-memory limiter state,
# no multi-worker fragmentation to worry about.
limiter = Limiter(key_func=get_remote_address)
talisman = Talisman()
