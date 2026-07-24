import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # app/__init__.py deliberately turns PRAGMA foreign_keys ON for every SQLite
            # connection (so local dev/tests catch real FK violations production's Postgres
            # would also catch) — but that same engine is reused here, and SQLite's only way to
            # ALTER a table (what batch_alter_table does under the hood: create a new table,
            # copy rows, drop the old one, rename) requires FK enforcement to be off for that
            # swap, or the DROP TABLE step fails with "FOREIGN KEY constraint failed" on any
            # table something else references (confirmed live: batch_alter_table('users', ...)
            # in b7d4e0f21a6c). Safe to leave off for the rest of this process — `flask db
            # upgrade` is a short-lived CLI invocation, not the long-running app, so there's
            # nothing else on this connection for it to affect.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            # SQLAlchemy 2.x auto-begins a transaction on a Connection's first execute() — left
            # open, it silently absorbs Alembic's own context.begin_transaction()/commit below
            # into itself (Alembic detects the already-active transaction and defers commit
            # responsibility to whoever started it), so every migration below "succeeds" with no
            # error and advances the logged revision, but nothing actually reaches disk.
            # Confirmed live: exit code 0, clean log output, alembic_version unchanged, columns
            # still missing. Committing this one PRAGMA statement immediately closes that
            # transaction out, so Alembic's own begin_transaction() starts a fresh one it fully
            # owns and will actually commit.
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
