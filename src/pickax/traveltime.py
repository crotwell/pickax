from obspy.geodetics import locations2degrees
from obspy.taup import TauPyModel

class TravelTimeCalc:
    def __init__(self, phase_list, model=None):
        self.model = model if model is not None else TauPyModel(model="ak135")
        self.phase_list = phase_list
        self.cache = None
    def calculate(self, sta, quake):
        if self.cache is None or self.cache['sta']!=sta or self.cache['quake']!=quake:
            # need to recalc
            cache = {
                "sta": sta,
                "quake": quake,
                "arrivals": []
            }
            origin = quake.preferred_origin()
            if origin is not None:
                dist_deg = locations2degrees(sta.latitude, sta.longitude, origin.latitude, origin.longitude)
                cache['arrivals'] = self.model.get_travel_times(source_depth_in_km=origin.depth/1000,
                                          distance_in_degree=dist_deg,
                                          phase_list=self.phase_list)
        return cache['arrivals']
