print(ttime.ctime() + ' >>>> ' + __file__)

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
from ophyd import DeviceStatus
from ophyd.status import SubscriptionStatus
from ophyd.sim import NullStatus

from nslsii.ad33 import StatsPluginV33

from databroker.assets.handlers_base import HandlerBase



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
    # filepath = Cpt(EpicsSignal, '}ID:File')
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
    # RAW_FILEPATH is a global defined in 00-startup.py
    write_path_template = os.path.join(RAW_PATH, 'encpb','%Y/%m/%d')
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

    @property
    def enc_rate(self):
        enc_rate_in_points = self.filter_dt.get()
        return (1 / (enc_rate_in_points * 10 * 1e-9) / 1e3)


    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."
        staged_list = super().stage()

        # print('Staging of {} starting'.format(self.name))

        filename = 'en_' + str(uuid.uuid4())[:8]

        # without the root, but with data path + date folders
        full_path = make_filename(filename)
        # with the root
        self._full_path = os.path.join(ROOT_PATH, full_path)  # stash for future reference
        #print_to_gui(f' filepath {self._full_path}')

        # FIXME: Quick TEMPORARY fix for beamline disaster
        # we are writing the file to a temp directory in the ioc and
        # then moving it to the GPFS system.
        #
        ioc_file_root = '/home/softioc/tmp/'
        self._ioc_full_path = os.path.join(ioc_file_root, filename)
        self._filename = filename

        #self.filepath.put(self._full_path)   # commented out during disaster
        # self.filepath.put(self._ioc_full_path)
        self.filepath.set(self._ioc_full_path)

        self._resource_uid = str(uuid.uuid4())
        resource = {'spec': 'PIZZABOX_ENC_FILE_TXT_PD',
                    'root': ROOT_PATH,
                    'resource_path': full_path,
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()

        # print('Staging of {} complete'.format(self.name))
        return staged_list

    def unstage(self):
        self._datum_counter = None
        return super().unstage()

    def kickoff(self):
        return self.ignore_sel.set(0)


    def complete(self):
        print_to_gui(f'{ttime.ctime()} >>> {self.name} complete starting...')
        self.ignore_sel.set(1).wait()

        # print(f'     !!!!! {datetime.now()} complete in {self.name} after stop writing')

        #while not os.path.isfile(self._full_path):
        #    ttime.sleep(.1)

        # FIXME: beam line disaster fix.
        # Let's move the file to the correct place
        workstation_file_root = '/mnt/xf08ida-ioc1/'
        workstation_full_path = os.path.join(workstation_file_root, self._filename)
        # print('Moving file from {} to {}'.format(workstation_full_path, self._full_path))
        print_to_gui(f'{ttime.ctime()} Moving file from {workstation_full_path} to {self._full_path}')

        print_to_gui(f'Here')
        cp_stat = shutil.copy(workstation_full_path, self._full_path)
        print_to_gui(f'Copy done')
        # HACK: Make datum documents here so that they are available for collect_asset_docs
        # before collect() is called. May need changes to RE to do this properly. - Dan A.

        self._datum_ids = []

        datum_id = '{}/{}'.format(self._resource_uid,  next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))

        self._datum_ids.append(datum_id)
        print_to_gui(f'{ttime.ctime()} >>> {self.name} complete complete')
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        # print(f'     !!!!! {datetime.now()} collect in {self.name}')
        # print('Collect of {} starting'.format(self.name))
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect starting...')

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        #ttime.sleep(1)  # wait for file to be written by pizza box

        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data},
                   'time': now,
                   'filled': {key: False for key in data}}
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect done')
        # print(f'{ttime.ctime()} >>> {self.name} collect complete')

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        return_dict = {self.name:
                           {self.name: {'source': 'pizzabox-enc-file',
                                        'dtype': 'array',
                                        'shape': [-1, -1],
                                        'filename': self._full_path,
                                        # 'devname': self.dev_name.get(),
                                        'external': 'FILESTORE:'}}}
        return return_dict

    def collect_asset_docs(self):
        # print(f'\ncollecting asset docs for {self.name}\n')
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item




class PizzaBoxFS(Device):
    ts_sec = Cpt(EpicsSignal, '}T:sec-I')
    #internal_ts_sel = Cpt(EpicsSignal, '}T:Internal-Sel')

    enc1 = Cpt(EncoderFS, ':1')
    enc2 = Cpt(EncoderFS, ':2')
    enc3 = Cpt(EncoderFS, ':3')
    enc4 = Cpt(EncoderFS, ':4')
    # di = Cpt(DIFS, ':DI')
    # do0 = Cpt(DigitalOutput, '-DO:0')
    # do1 = Cpt(DigitalOutput, '-DO:1')
    # do2 = Cpt(DigitalOutput, '-DO:2')
    # do3 = Cpt(DigitalOutput, '-DO:3')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written


# pb1 = PizzaBoxFS('XF:08IDA-CT{Enc01', name = 'pb1')
# pb2 = PizzaBoxFS('XF:08IDA-CT{Enc02', name = 'pb2')
# pb4 = PizzaBoxFS('XF:08IDA-CT{Enc04', name = 'pb4') #PB inside hutch B (for now)
# pb5 = PizzaBoxFS('XF:08IDA-CT{Enc05', name = 'pb5')
# pb6 = PizzaBoxFS('XF:08IDA-CT{Enc06', name = 'pb6')
# pb7 = PizzaBoxFS('XF:08IDA-CT{Enc07', name = 'pb7')
pb9 = PizzaBoxFS('XF:08IDA-CT{Enc09', name ='pb9')
hhm_encoder = pb9.enc1
hhm_encoder.pulses_per_deg = 360000
pb9.wait_for_connection(timeout=10)

# class PizzaBoxEncHandlerTxtPD(HandlerBase):
#     "Read PizzaBox text files using info from filestore."
#     def __init__(self, fpath):
#         self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'encoder', 'index', 'state'], sep=' ')
#
#     def __call__(self):
#         return self.df

# from xas.handlers import PizzaBoxEncHandlerTxtPD
#
# db.reg.register_handler('PIZZABOX_ENC_FILE_TXT_PD',
#                         PizzaBoxEncHandlerTxtPD, overwrite=True)
