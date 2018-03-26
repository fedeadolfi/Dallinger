"""Create a connection to the database."""

from contextlib import contextmanager
from functools import wraps
import logging
import os
import sys

from psycopg2.extensions import TransactionRollbackError
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError


logger = logging.getLogger('dallinger.db')

db_url_default = "postgresql://dallinger:dallinger@localhost/dallinger"
db_url = os.environ.get("DATABASE_URL", db_url_default)
engine = create_engine(db_url, pool_size=1000)
session = scoped_session(sessionmaker(autocommit=False,
                                      autoflush=True,
                                      bind=engine))

Base = declarative_base()
Base.query = session.query_property()


db_user_warning = """
*********************************************************
*********************************************************


Dallinger now requires a database user named "dallinger".

Run:

    createuser -P dallinger --createdb

Consult the developer guide for more information.


*********************************************************
*********************************************************

"""


@contextmanager
def sessions_scope(local_session, commit=False):
    """Provide a transactional scope around a series of operations."""
    try:
        yield local_session
        if commit:
            local_session.commit()
            logger.debug('DB session auto-committed as requested')
    except Exception as e:
        # We log the exception before re-raising it, in case the rollback also
        # fails
        logger.exception('Exception during scoped worker transaction, '
                         'rolling back.')
        # This rollback is potentially redundant with the remove call below,
        # depending on how the scoped session is configured, but we'll be
        # explicit here.
        local_session.rollback()
        raise e
    finally:
        local_session.remove()
        logger.debug('Session complete, db session closed')


def scoped_session_decorator(func):
    """Manage contexts and add debugging to db sessions."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with sessions_scope(session):
            # The session used in func comes from the funcs globals, but
            # it will be a proxied thread local var from the session
            # registry, and will therefore be identical to the one returned
            # by the context manager above.
            logger.debug('Running worker %s in scoped DB session',
                         func.__name__)
            return func(*args, **kwargs)
    return wrapper


def init_db(drop_all=False, bind=engine):
    """Initialize the database, optionally dropping existing tables."""
    try:
        if drop_all:
            Base.metadata.drop_all(bind=bind)
        Base.metadata.create_all(bind=bind)
    except OperationalError as err:
        msg = 'password authentication failed for user "dallinger"'
        if msg in err.message:
            sys.stderr.write(db_user_warning)
        raise

    return session


def serialized(func):
    """Run a function within a db transaction using SERIALIZABLE isolation.

    With this isolation level, committing will fail if this transaction
    read data that was since modified by another transaction. So we need
    to handle that case and retry the transaction.
    """

    @wraps(func)
    def wrapper(*args, **kw):
        attempts = 100
        while attempts > 0:
            try:
                session.connection(
                    execution_options={'isolation_level': 'SERIALIZABLE'})
                with sessions_scope(session, commit=True):
                    return func(*args, **kw)
            except OperationalError as exc:
                if isinstance(exc.orig, TransactionRollbackError):
                    if attempts > 0:
                        attempts -= 1
                    else:
                        raise Exception(
                            'Could not commit serialized transaction '
                            'after 100 attempts.')
                else:
                    raise
    return wrapper


# Reset outbox when session begins
@event.listens_for(Session, 'after_begin')
def after_begin(session, transaction, connection):
    logger.debug(
            'Clearing message queue due to begin: {}'.format(session.info))
    session.info['outbox'] = []


# Reset outbox after rollback
@event.listens_for(Session, 'after_soft_rollback')
def after_soft_rollback(session, previous_transaction):
    logger.debug(
            'Clearing message queue due to rollback: {}'.format(session.info))
        
    session.info['outbox'] = []


def queue_message(channel, message):
    logger.debug(
            'Enqueueing message to {}: {}'.format(channel, message))
    if 'outbox' not in session.info:
        session.info['outbox'] = []
    session.info['outbox'].append((channel, message))


# Publish messages to redis after commit
@event.listens_for(Session, 'after_commit')
def after_commit(session):
    from dallinger.heroku.worker import conn as redis

    for channel, message in session.info.get('outbox', ()):
        logger.debug(
            'Publishing message to {}: {}'.format(channel, message))
        redis.publish(channel, message)
