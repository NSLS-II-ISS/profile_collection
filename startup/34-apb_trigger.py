print(ttime.ctime() + ' >>>> ' + __file__)

import datetime as dt
import itertools
import os
import time as ttime
import uuid
from collections import deque

import numpy as np
import pandas as pd
import paramiko

from ophyd.status import SubscriptionStatus

# from xas.trajectory import trajectory_manager


class AnalogPizzaBoxTrigger(Device):
    freq = Cpt(EpicsSignal,'Frequency-SP')
    duty_cycle = Cpt(EpicsSignal,'DutyCycle-SP')
    max_counts = Cpt(EpicsSignal,'MaxCount-SP')

    acquire = Cpt(EpicsSignal, 'Mode-SP')
    acquiring = Cpt(EpicsSignal, 'Status-I')
    filename = Cpt(EpicsSignal,'Filename-SP', string=True)
    filebin_status = Cpt(EpicsSignalRO,'File:Status-I')
    stream = Cpt(EpicsSignal,'Stream:Mode-SP')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._acquiring = None

        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None

    def prepare_to_fly(self, traj_duration):
        self.num_points = int(self.freq.get() * (traj_duration + 1))

    # Step-scan interface
    def stage(self):
        staged_list = super().stage()

        file_uid = new_uid()
        self.fn = f'{ROOT_PATH}/{RAW_PATH}/apb/{dt.datetime.strftime(dt.datetime.now(), "%Y/%m/%d")}/{file_uid}.bin'
        self.filename.set(self.fn).wait()
        # self.poke_streaming_destination()
        self._resource_uid = new_uid()
        resource = {'spec': 'APB_TRIGGER', #self.name.upper(),
                    'root': ROOT_PATH,  # from 00-startup.py (added by mrakitin for future generations :D)
                    'resource_path': self.fn,
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()
        self.max_counts.set(self.num_points).wait()
        # self.stream.set(1).wait()
        return staged_list

    def unstage(self):
        self._datum_counter = None
        # self.stream.set(0).wait()
        return super().unstage()

    def kickoff(self):
        # return self.acquire.set(2)
        return self.stream.set(1)

    def complete(self):
        # self.acquire.set(0).wait()
        self.stream.set(0).wait()
        self.acquire.set(0).wait()
        self._datum_ids = []
        datum_id = '{}/{}'.format(self._resource_uid, next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))
        self._datum_ids.append(datum_id)
        return NullStatus()


    def collect(self):
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect starting')
        now = ttime.time()
        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data}, 'time': now,
                   'filled': {key: False for key in data}}
            # print(f'yield data {ttime.ctime(ttime.time())}')
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect complete')

        # self.unstage()


    def describe_collect(self):
        return_dict = {self.name:
                           {f'{self.name}': {'source': self.name.upper(),
                                             'dtype': 'array',
                                             'shape': [-1, -1],
                                             'filename': f'{self.fn}',
                                             'external': 'FILESTORE:'}}}
        return return_dict


    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item


    # def calc_num_points(self):
    #     # tr = trajectory_manager(hhm)
    #     info = trajectory_manager.read_info(silent=True)
    #     lut = str(int(hhm.lut_number_rbv.get()))
    #     traj_duration = int(info[lut]['size']) / 16000
    #     acq_num_points = traj_duration * self.acq_rate.get() * 1000 * 1.3
    #     self.num_points = int(round(acq_num_points, ndigits=-3))

apb_trigger = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:1:", name="apb_trigger")
apb_trigger_xs = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:1:", name="apb_trigger_xs")
apb_trigger_pil100k = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:2:", name="apb_trigger_pil100k")
apb_trigger_pil100k2 = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:3:", name="apb_trigger_pil100k2")


# class APBTriggerFileHandler(HandlerBase):
#     "Read APB trigger *.bin files"
#     def __init__(self, fpath):
#         raw_data = np.fromfile(fpath, dtype=np.int32)
#         raw_data = raw_data.reshape((raw_data.size // 3, 3))
#         columns = ['timestamp', 'transition']
#         derived_data = np.zeros((raw_data.shape[0], 2))
#         derived_data[:, 0] = raw_data[:, 1] + raw_data[:, 2]  * 8.0051232 * 1e-9  # Unix timestamp with nanoseconds
#         derived_data[:, 1] = raw_data[:, 0]
#
#         self.df = pd.DataFrame(data=derived_data, columns=columns)
#         self.raw_data = raw_data
#
#     def __call__(self):
#         return self.df
#
#
#
#
# db.reg.register_handler('APB_TRIGGER',
#                         APBTriggerFileHandler, overwrite=True)


