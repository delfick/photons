from delfick_project.norms import sb
from interactor.database.base import Base
from interactor.database.models.scene_spec import make_spec
from sqlalchemy import Boolean, Column, Integer, String, Text


class Scene(Base):
    uuid = Column(String(64), nullable=True, index=True)
    matcher = Column(Text(), nullable=False)
    power = Column(Boolean(), nullable=True)
    color = Column(Text(), nullable=True)
    zones = Column(Text(), nullable=True)
    chain = Column(Text(), nullable=True)
    duration = Column(Integer(), nullable=True)

    __repr_columns__ = ("uuid", "matcher")

    def as_object(self):
        dct = {
            "uuid": self.uuid,
            "matcher": self.matcher,
            "power": self.power,
            "color": self.color,
            "zones": self.zones,
            "chain": self.chain,
            "duration": self.duration,
        }
        return self.Spec(storing=False).empty_normalise(**dct)

    def as_dict(self, ignore=None):
        return {
            k: v
            for k, v in self.as_object().as_dict().items()
            if v is not None and k not in (ignore or ())
        }

    @classmethod
    def Spec(kls, storing=True):
        return make_spec(storing=storing)

    @classmethod
    def DelayedSpec(kls, storing=True):
        spec = kls.Spec(storing=storing)

        class delayed(sb.Spec):
            def normalise_filled(self, meta, val):
                val = sb.dictionary_spec().normalise(meta, val)

                def normalise(uuid):
                    if "uuid" in val:
                        del val["uuid"]
                    return spec.normalise(meta, {"uuid": uuid, **val})

                return normalise

        return delayed()
