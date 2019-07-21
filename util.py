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


def point_in_polygon(point, polygon):
    x, y = point[0], point[1]

    vert_count = len(polygon)
    inside = False
    j = vert_count - 1

    for i in range(vert_count):

        xi = polygon[i][0]
        yi = polygon[i][1]
        xj = polygon[j][0]
        yj = polygon[j][1]

        intersect = (((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi))
        if (intersect):
            inside = not inside

        j = i
        
    return inside