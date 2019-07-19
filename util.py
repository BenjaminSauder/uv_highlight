import bpy


def distance_line_point(start, end, point):
    line_vec = start - end
    point_vec = start - point    
    line_unitvec = line_vec.normalized()
    if line_vec.length == 0:
        return 0

    point_vec_scaled = point_vec * (1.0 / line_vec.length)

    t = line_unitvec.dot(point_vec_scaled)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    nearest = line_vec * t
    dist = (nearest - point_vec).length
    return dist
