print(ttime.ctime() + ' >>>> ' + __file__)

from ophyd.areadetector import (AreaDetector, PixiradDetectorCam, ImagePlugin,
                                TIFFPlugin, StatsPlugin, HDF5Plugin,
                                ProcessPlugin, ROIPlugin, TransformPlugin,
                                OverlayPlugin)
from ophyd.areadetector.plugins import PluginBase
from ophyd.areadetector.cam import AreaDetectorCam
from ophyd.device import BlueskyInterface
from ophyd.areadetector.trigger_mixins import SingleTrigger
from ophyd.areadetector.filestore_mixins import (FileStoreIterativeWrite,
                                                 FileStoreHDF5IterativeWrite,
                                                 FileStoreTIFFSquashing,
                                                 FileStoreTIFF)
from ophyd import Signal, EpicsSignal, EpicsSignalRO
from ophyd.status import SubscriptionStatus
from ophyd.sim import NullStatus  # TODO: remove after complete/collect are defined
from ophyd import Component as Cpt
from ophyd.status import SubscriptionStatus, DeviceStatus

from pathlib import PurePath
from nslsii.detectors.xspress3 import (XspressTrigger, Xspress3Detector,
                                       Xspress3Channel, Xspress3FileStore, Xspress3ROI, logger)

#from isstools.trajectory.trajectory import trajectory_manager

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
'''
class GeDetector(Device):
    mca1 = Cpt(EpicsSignal, f'mca1.VAL')
    mca2 = Cpt(EpicsSignal, f'mca2.VAL')
    mca3 = Cpt(EpicsSignal, f'mca3.VAL')
    mca4 = Cpt(EpicsSignal, f'mca4.VAL')
    mca5 = Cpt(EpicsSignal, f'mca5.VAL')
    mca6 = Cpt(EpicsSignal, f'mca6.VAL')
    mca7 = Cpt(EpicsSignal, f'mca7.VAL')
    mca8 = Cpt(EpicsSignal, f'mca8.VAL')
    mca9 = Cpt(EpicsSignal, f'mca9.VAL')
    mca10 = Cpt(EpicsSignal, f'mca10.VAL')
    mca11 = Cpt(EpicsSignal, f'mca11.VAL')
    mca12 = Cpt(EpicsSignal, f'mca12.VAL')
    mca13 = Cpt(EpicsSignal, f'mca13.VAL')
    mca14 = Cpt(EpicsSignal, f'mca13.VAL')
    
    mca15 = Cpt(EpicsSignal, f'mca15.VAL')
    mca16 = Cpt(EpicsSignal, f'mca16.VAL')
    mca17 = Cpt(EpicsSignal, f'mca17.VAL')
    mca18 = Cpt(EpicsSignal, f'mca18.VAL')
    mca19 = Cpt(EpicsSignal, f'mca19.VAL')
    mca20 = Cpt(EpicsSignal, f'mca20.VAL')
    mca21 = Cpt(EpicsSignal, f'mca21.VAL')
    mca22 = Cpt(EpicsSignal, f'mca22.VAL')
    mca23 = Cpt(EpicsSignal, f'mca23.VAL')
    mca24 = Cpt(EpicsSignal, f'mca24.VAL')
    mca25 = Cpt(EpicsSignal, f'mca25.VAL')
    mca26 = Cpt(EpicsSignal, f'mca26.VAL')
    mca27 = Cpt(EpicsSignal, f'mca27.VAL')
    mca28 = Cpt(EpicsSignal, f'mca28.VAL')
    mca29 = Cpt(EpicsSignal, f'mca29.VAL')
    mca30 = Cpt(EpicsSignal, f'mca30.VAL')
    mca31 = Cpt(EpicsSignal, f'mca31.VAL')
    mca32 = Cpt(EpicsSignal, f'mca32.VAL')
    
    
    preamp_gain1 = Cpt(EpicsSignal, 'dxp1:PreampGain')
    preamp_gain2 = Cpt(EpicsSignal, 'dxp2:PreampGain')
    preamp_gain3 = Cpt(EpicsSignal, 'dxp3:PreampGain')
    preamp_gain4 = Cpt(EpicsSignal, 'dxp4:PreampGain')
    preamp_gain5 = Cpt(EpicsSignal, 'dxp5:PreampGain')
    preamp_gain6 = Cpt(EpicsSignal, 'dxp6:PreampGain')
    preamp_gain7 = Cpt(EpicsSignal, 'dxp7:PreampGain')
    
    
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)



ge_detector = GeDetector('XF:08IDB-ES{GE-Det:1}', name='ge_detector')

peak_max = 585
device = ge_detector.preamp_gain2
coeff=peak_max*2/1150

current_gain = device.get()
device.set(current_gain/coeff)


class GeDetector(Device):
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)

for i in range(32):
    setattr(GeDetector, f'mca{i+1}', Cpt(EpicsSignal, f'mca{i+1}.VAL'))
    setattr(GeDetector, f'preamp_gain{i+1}',Cpt(EpicsSignal, f'dxp{i+1}:PreampGain'))
ge_detector = GeDetector('XF:08IDB-ES{GE-Det:1}', name='ge_detector')





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