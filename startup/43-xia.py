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
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)



ge_detector = GeDetector('XF:08IDB-ES{GE-Det:1}', name='ge_detector')
XF:08IDB-ES{GE-Det:1}mca1.R0LO
XF:08IDB-ES{GE-Det:1}mca1.R0HI
XF:08IDB-ES{GE-Det:1}mca1.R0
XF:08IDB-ES{GE-Det:1}mca1.R0NM

XF:08IDB-ES{GE-Det:1}dxp1:PreampGain

XF:08IDB-ES{GE-Det:1}StartAll
'''