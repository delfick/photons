import logging

from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base, declared_attr

log = logging.getLogger("interactor.database.connection")


class Base:
    # Metadata gets set by Sqlalchemy
    metadata = None

    # __repr_columns__ must be set by subclasses of Base
    __repr_columns__ = None

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True)

    def __repr__(self):
        title = self.__tablename__
        cols = dict((key, getattr(self, key)) for key in self.__repr_columns__)
        columns = ", ".join("%s:%s" % (key, value) for key, value in cols.items())
        return "<%s (%s)>" % (title, columns)


Base = declarative_base(cls=Base)
