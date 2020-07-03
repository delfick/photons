"""
A connector between a bunch of database connections in threads
and the asyncio event loop.

Usage is as follows:

    def some_action(db):
        # db is an instance of interactor.database.connection.DatabaseConnection
        entry = db.create_entry(...)
        db.add(entry)
    await db_queue.request(some_action)

By requesting the function you are putting it onto a queue that will be
picked up by another thread. That thread will then create a database session
that is passed into the function.

The `request` function returns a future that is eventually fulfilled by that
worker and that's how we get the result from the different thread back into the
event loop.
"""
from interactor.database.connection import DatabaseConnection

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from sqlalchemy.pool import StaticPool
import sqlalchemy
import logging
import sys

log = logging.getLogger("photosn_interactor.database.db_queue")


class DBQueue(hp.ThreadToAsyncQueue):
    """Connect asyncio to threaded database connections"""

    _merged_options_formattable = True

    def setup(self, database):
        self.database = database

    def create_args(self, thread_number, existing):
        """This is run when the queue starts and before every request"""
        if existing:
            return existing

        return (DatabaseConnection(self.database, poolclass=StaticPool),)

    def wrap_request(self, proc, args):
        """We create a new session for every database request"""

        def ret():
            tries = 0
            while True:
                (db,) = args

                # Clone our database with a new session
                database = db.new_session()

                # Do the work
                try:
                    res = proc(database)
                    database.commit()
                    return res

                except sqlalchemy.exc.OperationalError as error:
                    database.rollback()
                    log.error(
                        hp.lc(
                            "Failed to use database, will rollback and maybe try again", error=error
                        )
                    )
                    tries += 1

                    if tries > 1:
                        raise

                except sqlalchemy.exc.InvalidRequestError as error:
                    database.rollback()
                    log.error(hp.lc("Failed to perform database operation", error=error))
                    raise

                except PhotonsAppError as error:
                    database.rollback()
                    log.error(hp.lc("Failed to use database", error=error))
                    raise

                except:
                    database.rollback()
                    exc_info = sys.exc_info()
                    log.exception(
                        hp.lc("Unexpected failure when using database", error=exc_info[1])
                    )
                    raise

                finally:
                    database.close()

        return ret
