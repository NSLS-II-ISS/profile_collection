print(ttime.ctime() + ' >>>> ' + __file__)
'''
from ophyd.device import (
    Device,
    Component as Cpt,
    DynamicDeviceComponent as DDC,
    FormattedComponent as FC)
import bluesky.plans as bp
import bluesky.plan_stubs as bps
# bp.list_scan
import numpy as np
import itertools
import time as ttime
from collections import deque, OrderedDict
from itertools import product
import pandas as pd
import warnings

class XmapMCA(Device):
    val = Cpt(EpicsSignal, ".VAL", kind=Kind.hinted)
    R0low = Cpt(EpicsSignal, ".R0LO", kind=Kind.hinted)
    R0high = Cpt(EpicsSignal, ".R0HI", kind=Kind.hinted)
    R0 = Cpt(EpicsSignal, ".R0", kind=Kind.hinted)
    R0nm = Cpt(EpicsSignal, ".R0NM", kind=Kind.hinted)


def make_channels(channels):
    out_dict = OrderedDict()
    for channel in channels:  # [int]
        attr = f'mca{channel:1d}'
        out_dict[attr] = (XmapMCA, attr, dict())
        # attr = f"preamp{channel:1d}_gain"
        # out_dict[attr] = (EpicsSignal, f"dxp{channel:1d}.PreampGain", dict())
    return out_dict


#def make_dxps


class GeDetector(Device):
    channels = DDC(make_channels(range(1, 33)))
    start = Cpt(EpicsSignal,'EraseStart')
    stop_all = Cpt(EpicsSignal,'StopAll')
    acquiring = Cpt(EpicsSignal,'Acquiring')
    preset_mode =  Cpt(EpicsSignal,'PresetMode')
    real_time = Cpt(EpicsSignal,'PresetReal')
    collection_mode = Cpt(EpicsSignal,'CollectMode')
    acquisition_time=Cpt(EpicsSignal,'PresetReal')

    def trigger(self):
        return self.get_mca()

    def get_mca(self):
        def is_done(value, old_value, **kwargs):
            if old_value == 1 and value ==0:
                return True
            return False

        status = SubscriptionStatus(self.acquiring, run=False, callback=is_done)
        self.start.put(1)
        return status


ge_detector = GeDetector('XF:08IDB-ES{GE-Det:1}', name='ge_detector')
'''