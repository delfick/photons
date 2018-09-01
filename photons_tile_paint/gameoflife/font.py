from photons_tile_paint.font.base import Character

characters = []

def character(pattern):
    char = Character(pattern)
    characters.append(char)
    return char

Blinker = character("""
        ###
    """)

Block = character("""
        ##
        ##
    """)

Tub = character("""
        _#_
        #_#
        _#_
    """)

Boat = character("""
        ##_
        #_#
        _#_
    """)

Glider = character("""
        ###
        #__
        _#_
    """)

Ship = character("""
        ##_
        #_#
        _##
    """)

BeeHive = character("""
        _##_
        #__#
        _##_
    """)

Barge = character("""
        _#__
        #_#_
        _#_#
        __#_
    """)

Toad = character("""
        ###_
        _###
    """)

Beacon = character("""
        ##__
        #___
        ___#
        __##
    """)

LongBoat = character("""
        ##__
        #_#_
        _#_#
        __#_
    """)

Loaf = character("""
        _##_
        #__#
        #_#_
        _#__
    """)

Pond = character("""
        _##_
        #__#
        #__#
        _##_
    """)

Mango = character("""
        _##__
        #__#_
        _#__#
        __##_
    """)

LongBarge = character("""
        _#___
        #_#__
        _#_#_
        __#_#
        ___#_
    """)

HalfFleet = character("""
        ##____
        #_#___
        _##___
        ___##_
        ___#_#
        ____##
    """)

HalfBakery = character("""
        _##____
        #__#___
        _#_#___
        __#_##_
        ___#__#
        ____#_#
        _____#_
    """)
