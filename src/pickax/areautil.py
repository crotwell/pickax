
class Point:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

def in_area(bounds, point):
    inside = 0
    for  i in range(len(bounds)):
        lonA = bounds[i].longitude - point.longitude
        latA = bounds[i].latitude - point.latitude
        lonB = bounds[(i + 1) % len(bounds)].longitude - point.longitude
        latB = bounds[(i + 1) % len(bounds)].latitude - point.latitude
        check = polygonPointCheck(lonA, latA, lonB, latB)
        if check == 4:
            return True

        inside += check
    return inside != 0

def polygonPointCheck( lonA,  latA, lonB, latB):
    if(latA * latB > 0):
        return 0;
    if((lonA * latB != lonB * latA) or (lonA * lonB > 0)):
        if(latA * latB < 0):
            if(latA > 0):
                if(latA * lonB >= lonA * latB):
                    return 0
                return -2
            if(lonA * latB >= latA * lonB):
                return 0
            return 2
        if(latB == 0):
            if(latA == 0):
                return 0
            elif(lonB > 0):
                return 0;
            elif(latA > 0):
                return -1
            return 1
        elif(lonA > 0):
            return 0;
        elif(latB > 0):
            return 1
        return -1
    return 4
