import itertools
import uuid
from collections import namedtuple, deque
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import time as ttime
import pandas as pd

from ophyd import (ProsilicaDetector, SingleTrigger, Component as Cpt, Device,
                   EpicsSignal, EpicsSignalRO, ImagePlugin, StatsPlugin, ROIPlugin,
                   DeviceStatus)
from ophyd import DeviceStatus, set_and_wait
from ophyd.status import SubscriptionStatus
from ophyd.sim import NullStatus

from nslsii.ad33 import StatsPluginV33

from databroker.assets.handlers_base import HandlerBase
print(__file__)


class BPM(SingleTrigger, ProsilicaDetector):
    image = Cpt(ImagePlugin, 'image1:')
    stats1 = Cpt(StatsPluginV33, 'Stats1:')
    stats2 = Cpt(StatsPluginV33, 'Stats2:')
    stats3 = Cpt(StatsPluginV33, 'Stats3:')
    stats4 = Cpt(StatsPluginV33, 'Stats4:')

    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    roi3 = Cpt(ROIPlugin, 'ROI3:')
    roi4 = Cpt(ROIPlugin, 'ROI4:')
    counts = Cpt(EpicsSignal, 'Pos:Counts')
    exp_time = Cpt(EpicsSignal, 'cam1:AcquireTime_RBV', write_pv='cam1:AcquireTime')
    image_mode = Cpt(EpicsSignal,'cam1:ImageMode')
    acquire = Cpt(EpicsSignal, 'cam1:Acquire')

    # Actuator
    insert = Cpt(EpicsSignal, 'Cmd:In-Cmd')
    inserted = Cpt(EpicsSignalRO, 'Sw:InLim-Sts')

    retract = Cpt(EpicsSignal, 'Cmd:Out-Cmd')
    retracted = Cpt(EpicsSignal, 'Sw:OutLim-Sts')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs['cam.image_mode'] = 'Single'
        self.polarity = 'pos'
        # self._inserting = None
        # self._retracting = None

    def set(self, command):
        def callback(value, old_value, **kwargs):
            if value == 1:
                return True
            return False

        if command.lower() == 'insert':
            status = SubscriptionStatus(self.inserted, callback)
            self.insert.set('Insert')
            return status

        if command.lower() == 'retract':
            status = SubscriptionStatus(self.retracted, callback)
            self.retract.set('Retract')
            return status

class CAMERA(SingleTrigger, ProsilicaDetector):
    image = Cpt(ImagePlugin, 'image1:')

    stats1 = Cpt(StatsPluginV33, 'Stats1:')
    stats2 = Cpt(StatsPluginV33, 'Stats2:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')

    exp_time = Cpt(EpicsSignal, 'cam1:AcquireTime_RBV', write_pv='cam1:AcquireTime')
    polarity = 'pos'
    tiff_filepath = Cpt(EpicsSignal, 'TIFF1:FilePath_RBV', write_pv='TIFF1:FilePath')
    tiff_filename = Cpt(EpicsSignal, 'TIFF1:FileName_RBV', write_pv='TIFF1:FileName')
    tiff_filenumber = Cpt(EpicsSignal, 'TIFF1:FileNumber_RBV', write_pv='TIFF1:FileNumber')
    tiff_filefmt = Cpt(EpicsSignal, 'TIFF1:FileTemplate_RBV', write_pv='TIFF1:FileTemplate')

    bar1 = Cpt(EpicsSignal, 'Bar1:BarcodeMessage1_RBV')
    bar2 = Cpt(EpicsSignal, 'Bar1:BarcodeMessage2_RBV')
    bar3 = Cpt(EpicsSignal, 'Bar1:BarcodeMessage3_RBV')
    bar4 = Cpt(EpicsSignal, 'Bar1:BarcodeMessage4_RBV')
    bar5 = Cpt(EpicsSignal, 'Bar1:BarcodeMessage5_RBV')

    bar1Corner1X = Cpt(EpicsSignal, 'Bar1:UpperLeftX_RBV')
    bar1Corner2X = Cpt(EpicsSignal, 'Bar1:UpperRightX_RBV')
    bar1Corner3X = Cpt(EpicsSignal, 'Bar1:LowerLeftX_RBV')
    bar1Corner4X = Cpt(EpicsSignal, 'Bar1:LowerRightX_RBV')
    bar1Corner1Y = Cpt(EpicsSignal, 'Bar1:UpperLeftY_RBV')
    bar1Corner2Y = Cpt(EpicsSignal, 'Bar1:UpperRightY_RBV')
    bar1Corner3Y = Cpt(EpicsSignal, 'Bar1:LowerLeftY_RBV')
    bar1Corner4Y = Cpt(EpicsSignal, 'Bar1:LowerRightY_RBV')

    bar2Corner1X = Cpt(EpicsSignal, 'Bar2:UpperLeftX_RBV')
    bar2Corner2X = Cpt(EpicsSignal, 'Bar2:UpperRightX_RBV')
    bar2Corner3X = Cpt(EpicsSignal, 'Bar2:LowerLeftX_RBV')
    bar2Corner4X = Cpt(EpicsSignal, 'Bar2:LowerRightX_RBV')
    bar2Corner1Y = Cpt(EpicsSignal, 'Bar2:UpperLeftY_RBV')
    bar2Corner2Y = Cpt(EpicsSignal, 'Bar2:UpperRightY_RBV')
    bar2Corner3Y = Cpt(EpicsSignal, 'Bar2:LowerLeftY_RBV')
    bar2Corner4Y = Cpt(EpicsSignal, 'Bar2:LowerRightY_RBV')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #self.stage_sigs.clear()  # default stage sigs do not apply

    def stage(self, acquire_time, image_mode, *args, **kwargs):
        self.stage_sigs['cam.acquire_time'] =  acquire_time
        self.stage_sigs['cam.image_mode'] = image_mode
        super().stage(*args, **kwargs)

    @property
    def barcode1(self):
        return str(self.bar1.get()[:-1], encoding='UTF-8')

    @property
    def barcode2(self):
        return str(self.bar2.get()[:-1], encoding='UTF-8')

    def validate_barcode(self, input):
            if input in (self.barcode1, self.barcode2):
                return True
            print_to_gui(f'String {input} not found in {self.name} barcodes')
            return False


bpm_fm = BPM('XF:08IDA-BI{BPM:FM}', name='bpm_fm')
bpm_cm = BPM('XF:08IDA-BI{BPM:CM}', name='bpm_cm')
bpm_bt1 = BPM('XF:08IDA-BI{BPM:1-BT}', name='bpm_bt1')
bpm_bt2 = BPM('XF:08IDA-BI{BPM:2-BT}', name='bpm_bt2')
bpm_es = BPM('XF:08IDB-BI{BPM:ES}', name='bpm_es')

camera_sp1 = BPM('XF:08IDB-BI{BPM:SP-1}', name='camera_sp1')
# camera_sp2 = CAMERA('XF:08IDB-BI{BPM:SP-2}', name='camera_sp2')
camera_sp2 = BPM('XF:08IDB-BI{BPM:SP-2}', name='camera_sp2')

#camera_sp3 = CAMERA('XF:08IDB-BI{BPM:SP-3}', name='camera_sp3')
camera_sp4 = CAMERA('XF:08IDB-BI{BPM:SP-4}', name='camera_sp4')
camera_sp5 = CAMERA('XF:08IDB-BI{BPM:SP-5}', name='camera_sp5')
camera_sp6 = CAMERA('XF:08IDB-BI{BPM:SP-6}', name='camera_sp6')

foil_camera = camera_sp5

#bpm_ms1 = CAMERA('XF:08IDB-BI{BPM:MS-1}', name='bpm_ms1')

for bpm in [bpm_fm, bpm_cm, bpm_bt1, bpm_bt2, bpm_es,]: #camera_sp1, camera_sp2, camera_sp3, camera_sp4]:

    bpm.read_attrs = ['stats1', 'stats2']
    bpm.image.read_attrs = ['array_data']
    bpm.stats1.read_attrs = ['total', 'centroid']
    bpm.stats2.read_attrs = ['total', 'centroid']

bpm_fm.read_attrs = ['stats1', 'stats2', 'stats3', 'stats4']
bpm_fm.stats1.read_attrs = ['total', 'centroid']
bpm_fm.stats2.read_attrs = ['total', 'centroid']
bpm_fm.stats3.read_attrs = ['total', 'centroid']
bpm_fm.stats4.read_attrs = ['total', 'centroid']

for camera in [ camera_sp1, camera_sp2, camera_sp4]:   #camera_sp3,
    bpm.read_attrs = ['stats1', 'stats2']
    bpm.image.read_attrs = ['array_data']
    #bpm.stats1.read_attrs = ['total', 'centroid']
    #bpm.stats2.read_attrs = ['total', 'centroid']



tc_mask2_4 = EpicsSignal('XF:08IDA-OP{Mir:2-CM}T:Msk2_4-I',
                         name='tc_mask2_4')
tc_mask2_3 = EpicsSignal('XF:08IDA-OP{Mir:2-CM}T:Msk2_3-I',
                         name='tc_mask2_3')


bpm_fm.stats1.kind = 'hinted'
bpm_fm.stats1.total.kind = 'hinted'


camera_sp1.stats1.kind = 'hinted'
camera_sp1.stats1.total.kind = 'hinted'

camera_sp1.stats2.kind = 'hinted'
camera_sp1.stats2.total.kind = 'hinted'

camera_sp2.stats1.kind = 'hinted'
camera_sp2.stats1.total.kind = 'hinted'

camera_sp2.stats2.kind = 'hinted'
camera_sp2.stats2.total.kind = 'hinted'


class Encoder(Device):
    """This class defines components but does not implement actual reading.

    See EncoderFS and EncoderParser"""
    pos_I = Cpt(EpicsSignal, '}Cnt:Pos-I')
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    pos_array = Cpt(EpicsSignal, '}Cnt:Pos_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    # The '$' in the PV allows us to write 40 chars instead of 20.
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    dev_name = Cpt(EpicsSignal, '}DevName')

    filter_dy = Cpt(EpicsSignal, '}Fltr:dY-SP')
    filter_dt = Cpt(EpicsSignal, '}Fltr:dT-SP')
    reset_counts = Cpt(EpicsSignal, '}Rst-Cmd')

    ignore_sel = Cpt(EpicsSignal, suffix='}Ignore-RB', write_pv='}Ignore-Sel')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        if self.connected:
            self.ignore_sel.put(1)
            # self.filter_dt.put(10000)


def make_filename(filename):
    '''
        Makes a rootpath, filepath pair
    '''
    # RAW_PATH is a global defined in 00-startup.py
    write_path_template = os.path.join('encpb','%Y/%m/%d')
    # path without the root
    filepath = os.path.join(datetime.now().strftime(write_path_template), filename)
    return filepath


class EncoderFS(Encoder):
    "Encoder Device, when read, returns references to data in filestore."
    chunk_size = 1024

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None
        self._datum_ids = None

    def stage(self, *args, **kwargs):
        "Set the filename and record it in a 'resource' document in the filestore database."
        super().stage(*args, **kwargs)

        print('Staging of {} starting'.format(self.name))

        filename = 'en_' + str(uuid.uuid4())[:8]

        # without the root, but with data path + date folders
        full_path = make_filename(filename)
        # with the root
        self._full_path = os.path.join(ROOT_PATH, RAW_PATH, full_path)  # stash for future reference

        # FIXME: Quick TEMPORARY fix for beamline disaster
        # we are writing the file to a temp directory in the ioc and
        # then moving it to the GPFS system.
        #
        ioc_file_root = '/home/softioc/tmp/'
        self._ioc_full_path = os.path.join(ioc_file_root, filename)
        self._filename = filename

        #self.filepath.put(self._full_path)   # commented out during disaster
        self.filepath.put(self._ioc_full_path)

        self._resource_uid = str(uuid.uuid4())
        resource = {'spec': 'PIZZABOX_ENC_FILE_TXT_PD',
                    'root': ROOT_PATH,
                    'resource_path': full_path,
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()

        print('Staging of {} complete'.format(self.name))

    def unstage(self):
        set_and_wait(self.ignore_sel, 1)
        self._datum_counter = None
        return super().unstage()

    def kickoff(self):
        print(f'Kickoff {self.name} is starting')
        self._ready_to_collect = True
        "Start writing data into the file."

        set_and_wait(self.ignore_sel, 0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        print(f'Kickoff {self.name} is complete')
        return NullStatus()

    def complete(self):
        print(f'Storing {self.name} in {self._full_path}')
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")

        # print(f'     !!!!! {datetime.now()} complete in {self.name} before stop writing')

        # Stop adding new data to the file.
        set_and_wait(self.ignore_sel, 1)

        # print(f'     !!!!! {datetime.now()} complete in {self.name} after stop writing')

        #while not os.path.isfile(self._full_path):
        #    ttime.sleep(.1)

        # FIXME: beam line disaster fix.
        # Let's move the file to the correct place
        workstation_file_root = '/mnt/xf08ida-ioc1/'
        workstation_full_path = os.path.join(workstation_file_root, self._filename)
        print('Moving file from {} to {}'.format(workstation_full_path, self._full_path))
        cp_stat = shutil.copy(workstation_full_path, self._full_path)

        # HACK: Make datum documents here so that they are available for collect_asset_docs
        # before collect() is called. May need changes to RE to do this properly. - Dan A.

        self._datum_ids = []

        datum_id = '{}/{}'.format(self._resource_uid,  next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))

        self._datum_ids.append(datum_id)

        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        # print(f'     !!!!! {datetime.now()} collect in {self.name}')
        print('Collect of {} starting'.format(self.name))
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        #ttime.sleep(1)  # wait for file to be written by pizza box

        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data}, 'time': now,
                   'filled': {key: False for key in data}}
        print('Collect of {} complete'.format(self.name))

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.get(),
                      'source': 'pizzabox-enc-file',
                      'external': 'FILESTORE:',
                      'shape': [-1, -1],
                      'dtype': 'array'}}}

    def collect_asset_docs(self):
        # print(f'\ncollecting asset docs for {self.name}\n')
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item


class DigitalOutput(Device):
    """ DigitalOutput """
    enable = Cpt(EpicsSignal, '}Ena-Cmd')
    period_sp = Cpt(EpicsSignal, '}Period-SP')
    unit_sel = Cpt(EpicsSignal, '}Unit-Sel')
    dutycycle_sp = Cpt(EpicsSignal, '}DutyCycle-SP')
    default_pol = Cpt(EpicsSignal, '}Dflt-Sel')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        if self.connected:
            self.enable.put(0)


class DigitalInput(Device):
    """This class defines components but does not implement actual reading.

    See DigitalInputFS """
    data_I = Cpt(EpicsSignal, '}Raw:Data-I_')
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    # The '$' in the PV allows us to write 40 chars instead of 20.
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    dev_name = Cpt(EpicsSignal, '}DevName')

    # ignore_rb = Cpt(EpicsSignal, '}Ignore-RB')
    # ignore_sel = Cpt(EpicsSignal, '}Ignore-Sel')

    # Combined PVs into one components (to provide correct put-complete behavior).
    ignore_sel = Cpt(EpicsSignal, suffix='}Ignore-RB', write_pv='}Ignore-Sel')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        if self.connected:
            self.ignore_sel.put(1)



class DIFS(DigitalInput):
    "Encoder Device, when read, returns references to data in filestore."
    chunk_size = 1024

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."

        print('Staging of {} starting'.format(self.name))

        filename = 'di_' + str(uuid.uuid4())[:8]

        full_path = make_filename(filename)
        self._full_path = os.path.join(ROOT_PATH, full_path)

        # FIXME: Quick TEMPORARY fix for beamline disaster
        # we are writing the file to a temp directory in the ioc and
        # then moving it to the GPFS system.
        #
        ioc_file_root = '/home/softioc/tmp/'
        self._ioc_full_path = os.path.join(ioc_file_root, filename)
        self._filename = filename
        print(self._filename)
        # self.filepath.put(self._full_path)   # commented out during disaster
        self.filepath.put(self._ioc_full_path)

        self._resource_uid = str(uuid.uuid4())
        resource = {'spec': 'PIZZABOX_DI_FILE_TXT_PD',
                    'root': ROOT_PATH,
                    'resource_path': full_path,
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()

        super().stage()
        print('Staging of {} complete'.format(self.name))

    def unstage(self):
        set_and_wait(self.ignore_sel, 1)
        self._datum_counter = None
        return super().unstage()

    def kickoff(self):
        # print('kickoff', self.name)
        self._ready_to_collect = True
        "Start writing data into the file."

        set_and_wait(self.ignore_sel, 0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        return NullStatus()

    def complete(self):
        print('Storing', self.name, 'in', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        set_and_wait(self.ignore_sel, 1)
        #while not os.path.isfile(self._full_path):
        #    ttime.sleep(.1)

        # FIXME: beam line disaster fix.
        # Let's move the file to the correct place
        workstation_file_root = '/mnt/xf08ida-ioc1/'
        workstation_full_path = os.path.join(workstation_file_root, self._filename)
        print('Moving file from {} to {}'.format(workstation_full_path, self._full_path), end=' ... ')
        cp_stat = shutil.copy(workstation_full_path, self._full_path)
        print('done')
        # HACK: Make datum documents here so that they are available for collect_asset_docs
        # before collect() is called. May need changes to RE to do this properly. - Dan A.
        self._datum_ids = []

        datum_id = '{}/{}'.format(self._resource_uid,  next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))

        self._datum_ids.append(datum_id)
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        print('Collect of {} starting'.format(self.name))
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        #ttime.sleep(1)  # wait for file to be written by pizza box


        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data}, 'time': now,
                   'filled': {key: False for key in data}}

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.get(),
                      'source': 'pizzabox-di-file',
                      'external': 'FILESTORE:',
                      'shape': [1024, 5],
                      'dtype': 'array'}}}

class PizzaBoxFS(Device):
    ts_sec = Cpt(EpicsSignal, '}T:sec-I')
    #internal_ts_sel = Cpt(EpicsSignal, '}T:Internal-Sel')

    enc1 = Cpt(EncoderFS, ':1')
    enc2 = Cpt(EncoderFS, ':2')
    enc3 = Cpt(EncoderFS, ':3')
    enc4 = Cpt(EncoderFS, ':4')
    di = Cpt(DIFS, ':DI')
    do0 = Cpt(DigitalOutput, '-DO:0')
    do1 = Cpt(DigitalOutput, '-DO:1')
    do2 = Cpt(DigitalOutput, '-DO:2')
    do3 = Cpt(DigitalOutput, '-DO:3')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written

    def kickoff(self):
        "Call encoder.kickoff() for every encoder."
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            status = getattr(self, attr_name).kickoff()
            print("Eli's test", self.attr_name)
        # it's fine to just return one of the status objects
        return status

    def collect(self):
        "Call encoder.collect() for every encoder."
        # Stop writing data to the file in all encoders.
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            set_and_wait(getattr(self, attr_name).ignore_sel, 1)
        # Now collect the data accumulated by all encoders.
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            yield from getattr(self, attr_name).collect()

    # def trigger(self, *args, **kwargs):
    #     start_trigger = ttime.time()
    #     status = super().trigger(*args, **kwargs)
    #     print(f'{self.name} took {ttime.time() - start_trigger} to trigger')
    #     return status



pb1 = PizzaBoxFS('XF:08IDA-CT{Enc01', name = 'pb1')
pb2 = PizzaBoxFS('XF:08IDA-CT{Enc02', name = 'pb2')
pb4 = PizzaBoxFS('XF:08IDA-CT{Enc04', name = 'pb4') #PB inside hutch B (for now)
pb5 = PizzaBoxFS('XF:08IDA-CT{Enc05', name = 'pb5')
pb6 = PizzaBoxFS('XF:08IDA-CT{Enc06', name = 'pb6')
pb7 = PizzaBoxFS('XF:08IDA-CT{Enc07', name = 'pb7')
pb9 = PizzaBoxFS('XF:08IDA-CT{Enc09', name = 'pb9')
pb9.enc1.pulses_per_deg = 360000
pb9.enc1.wait_for_connection(timeout=10)

class Adc(Device):
    file_size = Cpt(EpicsSignal, '}FileSize')
    reset = Cpt(EpicsSignal, '}Rst-Cmd')
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    #pos_array = Cpt(EpicsSignal, '}Cnt:Pos_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    sample_rate = Cpt(EpicsSignal,'}F:Sample-I_', write_pv='}F:Sample-SP')
    enable_averaging = Cpt(EpicsSignal, '}Avrg-Sts', write_pv='}Avrg-Sel')
    averaging_points = Cpt(EpicsSignal, '}Avrg-SP')
    averaging_points_rbv = Cpt(EpicsSignal, '}GP-ADC:Reg0-RB_')
    volt_array = Cpt(EpicsSignal, '}V-I')
    volt = Cpt(EpicsSignal, '}E-I')
    offset = Cpt(EpicsSignal, '}Offset')
    dev_name = Cpt(EpicsSignal, '}DevName')
    dev_saturation = Cpt(EpicsSignal, '}DevSat')
    polarity = 'neg'
    buffer_level =  Cpt(EpicsSignalRO, '}Buf:Rel-I')

    enable_sel = Cpt(EpicsSignal, '}Ena-Sel')
    enable_rb = Cpt(EpicsSignal, '}Ena-Sts')

    def timeout_handler(self, signum, frame):
        print("{}.connected timeout".format(self.name))
        raise Exception("end of time")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False

        #signal.signal(signal.SIGALRM, self.timeout_handler)
        #signal.setitimer(signal.ITIMER_REAL, 2)
        #try:
        #    while(self.connected == False):
        #        pass
        if self.connected:
            #self.enable_sel.put(1)
            #self.sample_rate.put(350)
            self.enable_averaging.put(1)
            if self.averaging_points.get() == 0:
                self.averaging_points.put("1024")
        #except Exception as exc:
        #    pass
        #signal.alarm(0)


class AdcFS(Adc):
    "Adc Device, when read, returns references to data in filestore."
    chunk_size = 1024
    write_path_template = os.path.join(ROOT_PATH, RAW_PATH, '/%Y/%m/%d')

    def __init__(self, *args, **kwargs):
        self.file_move_executor = ThreadPoolExecutor(max_workers=2)
        super().__init__(*args, **kwargs)
        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."
        if self.connected:
            print( 'Staging of {} starting'.format(self.name))

            filename = 'an_' + str(uuid.uuid4())[:8]
            full_path = make_filename(filename)
            self._full_path = os.path.join(ROOT_PATH, full_path)

            # FIXME: Quick TEMPORARY fix for beamline disaster
            # we are writing the file to a temp directory in the ioc and
            # then moving it to the GPFS system.
            #
            ioc_file_root = '/home/softioc/tmp/'
            self._ioc_full_path = os.path.join(ioc_file_root, filename)
            self._filename = filename

            print("Temp IOC filename:" + self._ioc_full_path)

            #self.filepath.put(self._full_path)   # commented out during disaster
            self.filepath.put(self._ioc_full_path)

            self._resource_uid = str(uuid.uuid4())
            resource = {'spec': 'PIZZABOX_AN_FILE_TXT_PD',
                        'root': ROOT_PATH,
                        'resource_path': full_path,
                        'resource_kwargs': {},
                        'path_semantics': os.name,
                        'uid': self._resource_uid}
            self._asset_docs_cache.append(('resource', resource))
            self._datum_counter = itertools.count()

            print('Staging of {} complete'.format(self.name))
            super().stage()

    def unstage(self):
        if(self.connected):
            set_and_wait(self.enable_sel, 1)
            self._datum_counter = None
            return super().unstage()

    def kickoff(self):
        print('kickoff', self.name)
        self._ready_to_collect = True

        "Start writing data into the file."
        # set_and_wait(self.enable_sel, 0)
        st = self.enable_sel.set(0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        # return NullStatus()
        return st

    def complete(self):
        print('Storing', self.name, 'in', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        set_and_wait(self.enable_sel, 1)
        workstation_file_root = '/mnt/xf08idb-ioc1/'
        workstation_full_path = os.path.join(workstation_file_root, self._filename)
        while not os.path.isfile(workstation_full_path):
            ttime.sleep(.1)

        # FIXME: beam line disaster fix.
        # Let's move the file to the correct place

        print('Moving file from {} to {}'.format(workstation_full_path, self._full_path))
        stat = shutil.copy(workstation_full_path, self._full_path)

        # HACK: Make datum documents here so that they are available for collect_asset_docs
        # before collect() is called. May need changes to RE to do this properly. - Dan A.
        self._datum_ids = []
        datum_id = '{}/{}'.format(self._resource_uid,  next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))

        self._datum_ids.append(datum_id)
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        print('Collect of {} starting'.format(self.name))
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()

        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data}, 'time': now,
                   'filled': {key: False for key in data}}

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.get(),
                      'source': 'pizzabox-adc-file',
                      'external': 'FILESTORE:',
                      'shape': [5,],
                      'dtype': 'array'}}}


class PizzaBoxAnalogFS(Device):
    #internal_ts_sel = Cpt(EpicsSignal, 'Gen}T:Internal-Sel')

    adc1 = Cpt(AdcFS, 'ADC:1')
    adc6 = Cpt(AdcFS, 'ADC:6')
    adc7 = Cpt(AdcFS, 'ADC:7')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written
        # self.stage_sigs[self.internal_ts_sel] = 1

    def kickoff(self):
        "Call encoder.kickoff() for every encoder."
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            status = getattr(self, attr_name).kickoff()
        # it's fine to just return one of the status objects
        return status

    def collect(self):
        "Call adc.collect() for every encoder."
        # Stop writing data to the file in all encoders.
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            set_and_wait(getattr(self, attr_name).enable_sel, 0)
        # Now collect the data accumulated by all encoders.
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            yield from getattr(self, attr_name).collect()

pba1 = PizzaBoxAnalogFS('XF:08IDB-CT{GP1-', name = 'pba1')

pba2 = PizzaBoxAnalogFS('XF:08IDB-CT{GP-', name = 'pba2')

for jj in [1, 6, 7]:
    getattr(pba1, f'adc{jj}').volt.kind = 'hinted'
    getattr(pba2, f'adc{jj}').volt.kind = 'hinted'
    getattr(pba1, f'adc{jj}').kind = 'hinted'
    getattr(pba2, f'adc{jj}').kind = 'hinted'


class PizzaBoxEncHandlerTxt(HandlerBase):
    encoder_row = namedtuple('encoder_row',
                             ['ts_s', 'ts_ns', 'encoder', 'index', 'state'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.encoder_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxDIHandlerTxt(HandlerBase):
    di_row = namedtuple('di_row', ['ts_s', 'ts_ns', 'encoder', 'index', 'di'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.di_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxAnHandlerTxt(HandlerBase):
    encoder_row = namedtuple('encoder_row', ['ts_s', 'ts_ns', 'index', 'adc'])
    "Read PizzaBox text files using info from filestore."

    bases = (10, 10, 10, 16)
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):

        cs = self.chunk_size
        return [self.encoder_row(*(int(v, base=b) for v, b in zip(ln.split(), self.bases)))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]



db.reg.register_handler('PIZZABOX_AN_FILE_TXT',
                        PizzaBoxAnHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_ENC_FILE_TXT',
                        PizzaBoxEncHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_DI_FILE_TXT',
                        PizzaBoxDIHandlerTxt, overwrite=True)


# New handlers to support reading files into a Pandas dataframe
class PizzaBoxAnHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'index', 'adc'], sep=' ')

    def __call__(self):
        return self.df

class PizzaBoxDIHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'encoder', 'index', 'di'], sep=' ')

    def __call__(self):
        return self.df

class PizzaBoxEncHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'encoder', 'index', 'state'], sep=' ')

    def __call__(self):
        return self.df


db.reg.register_handler('PIZZABOX_AN_FILE_TXT_PD',
                        PizzaBoxAnHandlerTxtPD, overwrite=True)
db.reg.register_handler('PIZZABOX_DI_FILE_TXT_PD',
                        PizzaBoxDIHandlerTxtPD, overwrite=True)
db.reg.register_handler('PIZZABOX_ENC_FILE_TXT_PD',
                        PizzaBoxEncHandlerTxtPD, overwrite=True)
