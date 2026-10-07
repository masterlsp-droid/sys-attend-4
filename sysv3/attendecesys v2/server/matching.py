import struct
import math

def euclidean_distance(a, b):
    a_floats = struct.unpack(f"{len(a)//4}f", a) if isinstance(a, (bytes, bytearray)) else a
    b_floats = struct.unpack(f"{len(b)//4}f", b) if isinstance(b, (bytes, bytearray)) else b
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a_floats, b_floats)))
