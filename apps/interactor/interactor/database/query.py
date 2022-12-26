import logging

from sqlalchemy.future import select

log = logging.getLogger("interactor.database.connection")


class Query:
    """
    Object to abstract getting stuff from the database
    """

    def __init__(self, session, Base):
        self.Base = Base
        self.session = session

    ########################
    ###   GETTERS
    ########################

    def __getattr__(self, key):
        """
        Custom getattr to get

        get_<ModelName>
            Finds first model with provided keyword attributes

        get_<ModelName>s
            Finds all model with provided keyword attributes

        get_one_<ModelName>
            Find the only model with provided keyword attributes

        create_<ModelName>
            Create this model

        get_or_create_<ModelName>
            Finds first model with provided keyword attributes or creates one.
        """
        # Return private or existing things
        if key.startswith("_") or key in self.__dict__:
            return object.__getattribute__(self, key)

        # Dynamically determine which get method to use
        if key.startswith("get_") or key.startswith("create_"):
            if key.startswith("create_"):
                name = key[7:]
                action = "create_model"
            elif key.startswith("get_one_"):
                name = key[7:]
                action = "get_one_model"
            elif key.startswith("get_or_create_"):
                name = key[14:]
                action = "get_or_create_model"
            else:
                name = key[4:]
                if name.endswith("s"):
                    name = name[:-1]
                    action = "get_models"
                else:
                    action = "get_model"

            model_name = self.clean_name(name)
            if model_name.lower() not in self.Base.metadata.tables:
                raise AttributeError("No such table as %s" % model_name)

            def getter(**attrs):
                """Returned method that calls the desired action with the correct model"""
                for mapper in self.Base.registry.mappers:
                    if mapper.class_.__name__ == model_name:
                        model = mapper.class_
                        return object.__getattribute__(self, action)(model, attrs)
                raise AttributeError(model_name)

            return getter

        # Let getattribute raise errors
        return object.__getattribute__(self, key)

    async def all(self, model, *filters, change=None):
        query = select(model).where(*filters)
        if change is not None:
            query = change(query)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_model(self, model, attrs):
        filters = self.make_filters(model, attrs) if type(attrs) is dict else attrs
        result = await self.session.execute(select(model).where(*filters))
        return result.scalars().one_or_none()

    async def get_models(self, model, attrs):
        filters = self.make_filters(model, attrs) if type(attrs) is dict else attrs
        result = await self.session.execute(select(model).where(*filters))
        return result.scalars().all()

    async def get_one_model(self, model, attrs, **kwargs):
        filters = self.make_filters(model, attrs) if type(attrs) is dict else attrs
        result = await self.session.execute(select(model).where(*filters))
        return result.scalars().one()

    async def get_or_create_model(self, model, attrs, **kwargs):
        found = await self.get_model(model, attrs, **kwargs)
        if not found:
            made = await self.create_model(model, attrs)
            return made, True
        else:
            return found, False

    async def create_model(self, model, attrs):
        return model(**attrs)

    ########################
    ###   UTILITY
    ########################

    def clean_name(self, name):
        return "".join(part.capitalize() for part in name.split("_"))

    def make_filters(self, model, attrs):
        filters = []
        for key, val in attrs.items():
            filters.append(getattr(model, key) == val)
        return filters
