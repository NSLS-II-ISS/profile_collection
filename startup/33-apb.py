
print(ttime.ctime() + ' >>>> ' + __file__)
import itertools
import os
import time as ttime
# import uuid
from collections import deque

import numpy as np
import paramiko
from ophyd import Component as Cpt, Device, EpicsSignal, Kind
from ophyd.sim import NullStatus
from ophyd.status import SubscriptionStatus
from bluesky.utils import new_uid


class AnalogPizzaBox(Device):

    polarity = 'neg'

    ch1 = Cpt(EpicsSignal, 'SA:Ch1:mV-I', kind=Kind.hinted)
    ch2 = Cpt(EpicsSignal, 'SA:Ch2:mV-I', kind=Kind.hinted)
    ch3 = Cpt(EpicsSignal, 'SA:Ch3:mV-I', kind=Kind.hinted)
    ch4 = Cpt(EpicsSignal, 'SA:Ch4:mV-I', kind=Kind.hinted)
    ch5 = Cpt(EpicsSignal, 'SA:Ch5:mV-I', kind=Kind.hinted)
    ch6 = Cpt(EpicsSignal, 'SA:Ch6:mV-I', kind=Kind.hinted)
    ch7 = Cpt(EpicsSignal, 'SA:Ch7:mV-I', kind=Kind.hinted)
    ch8 = Cpt(EpicsSignal, 'SA:Ch8:mV-I', kind=Kind.hinted)


    ch1_offset = Cpt(EpicsSignal, 'Ch1:User:Offset-SP', kind=Kind.config)
    ch2_offset = Cpt(EpicsSignal, 'Ch2:User:Offset-SP', kind=Kind.config)
    ch3_offset = Cpt(EpicsSignal, 'Ch3:User:Offset-SP', kind=Kind.config)
    ch4_offset = Cpt(EpicsSignal, 'Ch4:User:Offset-SP', kind=Kind.config)
    ch5_offset = Cpt(EpicsSignal, 'Ch5:User:Offset-SP', kind=Kind.config)
    ch6_offset = Cpt(EpicsSignal, 'Ch6:User:Offset-SP', kind=Kind.config)
    ch7_offset = Cpt(EpicsSignal, 'Ch7:User:Offset-SP', kind=Kind.config)
    ch8_offset = Cpt(EpicsSignal, 'Ch8:User:Offset-SP', kind=Kind.config)

    ch1_adc_gain = Cpt(EpicsSignal, 'ADC1:Gain-SP')
    ch2_adc_gain = Cpt(EpicsSignal, 'ADC2:Gain-SP')
    ch3_adc_gain = Cpt(EpicsSignal, 'ADC3:Gain-SP')
    ch4_adc_gain = Cpt(EpicsSignal, 'ADC4:Gain-SP')
    ch5_adc_gain = Cpt(EpicsSignal, 'ADC5:Gain-SP')
    ch6_adc_gain = Cpt(EpicsSignal, 'ADC6:Gain-SP')
    ch7_adc_gain = Cpt(EpicsSignal, 'ADC7:Gain-SP')
    ch8_adc_gain = Cpt(EpicsSignal, 'ADC8:Gain-SP')

    ch1_adc_offset = Cpt(EpicsSignal, 'ADC1:Offset-SP')
    ch2_adc_offset = Cpt(EpicsSignal, 'ADC2:Offset-SP')
    ch3_adc_offset = Cpt(EpicsSignal, 'ADC3:Offset-SP')
    ch4_adc_offset = Cpt(EpicsSignal, 'ADC4:Offset-SP')
    ch5_adc_offset = Cpt(EpicsSignal, 'ADC5:Offset-SP')
    ch6_adc_offset = Cpt(EpicsSignal, 'ADC6:Offset-SP')
    ch7_adc_offset = Cpt(EpicsSignal, 'ADC7:Offset-SP')
    ch8_adc_offset = Cpt(EpicsSignal, 'ADC8:Offset-SP')

    acquire = Cpt(EpicsSignal, 'FA:SoftTrig-SP', kind=Kind.omitted)
    acquiring = Cpt(EpicsSignal, 'FA:Busy-I', kind=Kind.omitted)

    data_rate = Cpt(EpicsSignal, 'FA:Rate-I')
    divide = Cpt(EpicsSignal, 'FA:Divide-SP')
    sample_len = Cpt(EpicsSignal, 'FA:Samples-SP')
    wf_len = Cpt(EpicsSignal, 'FA:Wfm:Length-SP')

    stream = Cpt(EpicsSignal,'FA:Stream-SP', kind=Kind.omitted)
    streaming = Cpt(EpicsSignal,'FA:Streaming-I', kind=Kind.omitted)
    acq_rate= Cpt(EpicsSignal,'FA:Rate-I', kind=Kind.omitted)
    stream_samples = Cpt(EpicsSignal, 'FA:Stream:Samples-SP')

    trig_source = Cpt(EpicsSignal, 'Machine:Clk-SP')

    filename_bin = Cpt(EpicsSignal, 'FA:Stream:Bin:File-SP')
    filebin_status = Cpt(EpicsSignal, 'FA:Stream:Bin:File:Status-I')
    filename_txt = Cpt(EpicsSignal, 'FA:Stream:Txt:File-SP')
    filetxt_status = Cpt(EpicsSignal, 'FA:Stream:Txt:File:Status-I')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._IP = '10.66.59.42'

    def read_exposure_time(self):
        pass

    def set_exposure_time(self, value):
        pass


apb = AnalogPizzaBox(prefix="XF:08IDB-CT{PBA:1}:", name="apb")
apb.wait_for_connection(timeout=10)


class AnalogPizzaBoxAverage(AnalogPizzaBox):

    ch1_mean = Cpt(EpicsSignal, 'FA:Ch1:Mean-I', kind=Kind.hinted)
    ch2_mean = Cpt(EpicsSignal, 'FA:Ch2:Mean-I', kind=Kind.hinted)
    ch3_mean = Cpt(EpicsSignal, 'FA:Ch3:Mean-I', kind=Kind.hinted)
    ch4_mean = Cpt(EpicsSignal, 'FA:Ch4:Mean-I', kind=Kind.hinted)
    ch5_mean = Cpt(EpicsSignal, 'FA:Ch5:Mean-I', kind=Kind.hinted)
    ch6_mean = Cpt(EpicsSignal, 'FA:Ch6:Mean-I', kind=Kind.hinted)
    ch7_mean = Cpt(EpicsSignal, 'FA:Ch7:Mean-I', kind=Kind.hinted)
    ch8_mean = Cpt(EpicsSignal, 'FA:Ch8:Mean-I', kind=Kind.hinted)

    time_wf = Cpt(EpicsSignal, 'FA:Time-Wfm', kind=Kind.hinted)
    ch1_wf = Cpt(EpicsSignal, 'FA:Ch1-Wfm', kind=Kind.hinted)
    ch2_wf = Cpt(EpicsSignal, 'FA:Ch2-Wfm', kind=Kind.hinted)
    ch3_wf = Cpt(EpicsSignal, 'FA:Ch3-Wfm', kind=Kind.hinted)
    ch4_wf = Cpt(EpicsSignal, 'FA:Ch4-Wfm', kind=Kind.hinted)
    ch5_wf = Cpt(EpicsSignal, 'FA:Ch5-Wfm', kind=Kind.hinted)
    ch6_wf = Cpt(EpicsSignal, 'FA:Ch6-Wfm', kind=Kind.hinted)
    ch7_wf = Cpt(EpicsSignal, 'FA:Ch7-Wfm', kind=Kind.hinted)
    ch8_wf = Cpt(EpicsSignal, 'FA:Ch8-Wfm', kind=Kind.hinted)

    saved_status = None
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._capturing = None
        self._ready_to_collect = False



    def trigger(self):
        # print_to_gui(f"Before {self.name} callback", add_timestamp=True)
        def callback(value, old_value, **kwargs):
            # print_to_gui(f"In {self.name} callback", add_timestamp=True)
            if self._capturing and int(round(old_value)) == 1 and int(round(value)) == 0:
                # print_to_gui(f"In {self.name} callback - DONE", add_timestamp=True)
                self._capturing = False
                return True
            else:
                self._capturing = True
                return False

        # print_to_gui(f"Before subscription to callback", add_timestamp=True)
        status = SubscriptionStatus(self.acquiring, callback, run=True)
        # print_to_gui(f"After subscription to callback", add_timestamp=True)

        st_acq = self.acquire.set(1)
        # print_to_gui(f"After acquire set", add_timestamp=True)

        return st_acq & status

    def save_current_status(self):
        self.saved_status = {}
        self.saved_status['divide'] = self.divide.get()
        self.saved_status['sample_len'] = self.sample_len.get()
        self.saved_status['wf_len'] = self.wf_len.get()

    def restore_to_saved_status(self):
        yield from bps.abs_set(self.divide, self.saved_status['divide'])
        yield from bps.abs_set(self.sample_len, self.saved_status['sample_len'])
        yield from bps.abs_set(self.wf_len, self.saved_status['wf_len'])

    def read_exposure_time(self):
        data_rate = self.data_rate.get()
        sample_len = apb_ave.sample_len.get()
        return np.round((data_rate * sample_len / 1000), 3)

    def set_exposure_time(self, new_exp_time):
        data_rate = self.data_rate.get()
        sample_len = 250 * (np.round(new_exp_time * data_rate * 1000 / 250))
        self.sample_len.set(sample_len).wait()
        self.wf_len.set(sample_len).wait()



apb_ave = AnalogPizzaBoxAverage(prefix="XF:08IDB-CT{PBA:1}:", name="apb_ave")
apb_ave.wait_for_connection(timeout=10)


# def cb_print(value, **kwargs):
#     print_to_gui(f"{kwargs['obj'].name:30s}: In cb_print: {kwargs['old_value'] = } -> {value = }", add_timestamp=True)
#
#
# apb_ave.acquiring.subscribe(cb_print)
# apb_ave.acquire.subscribe(cb_print)


class AnalogPizzaBoxStream(AnalogPizzaBoxAverage):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._acquiring = None
        # self.ssh = paramiko.SSHClient()

        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None
        self.num_points = None

    def stage(self):
        file_uid = new_uid()
        # self.calc_num_points(traj_duration)
        self.stream_samples.put(self.num_points)
        #self.filename_target = f'{ROOT_PATH}/data/apb/{dt.datetime.strftime(dt.datetime.now(), "%Y/%m/%d")}/{file_uid}'
        # Note: temporary static file name in GPFS, due to the limitation of 40 symbols in the filename field.
        #self.filename = f'{ROOT_PATH}/data/apb/{file_uid[:8]}'
        self.filename = f'{ROOT_PATH}/{RAW_PATH}/apb/{dt.datetime.strftime(dt.datetime.now(), "%Y/%m/%d")}/{file_uid}'
        self.filename_bin.put(f'{self.filename}.bin')
        self.filename_txt.put(f'{self.filename}.txt')

        self._resource_uid = new_uid()
        resource = {'spec': 'APB',
                    'root': ROOT_PATH,  # from 00-startup.py (added by mrakitin for future generations :D)
                    'resource_path': f'{self.filename}.bin',
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()

        status = self.trig_source.set(1)
        status.wait()
        return super().stage()

    def kickoff(self):
        return self.stream.set(1)

    def trigger(self):
        def callback(value, old_value, **kwargs):
            # print(f'{ttime.time()} {old_value} ---> {value}')
            if self._acquiring and int(round(old_value)) == 1 and int(round(value)) == 0:
                self._acquiring = False
                return True
            else:
                self._acquiring = True
                return False

        status = SubscriptionStatus(self.acquiring, callback)
        self.acquire.set(1)
        return status

    def unstage(self, *args, **kwargs):
        self._datum_counter = None
        return super().unstage(*args, **kwargs)
        # self.stream.set(0)

    # # Fly-able interface

    # Not sure if we need it here or in FlyerAPB (see 63-...)
    def complete(self, *args, **kwargs):
        # print(f'{ttime.ctime()} >>> {self.name} complete: begin')
        print_to_gui(f'{self.name} complete starting', add_timestamp=True)
        def callback_saving(value, old_value, **kwargs):
            # if int(round(old_value)) == 1 and int(round(value)) == 0:
            if int(round(old_value)) == 0 and int(round(value)) == 1:
                print_to_gui('APB FILEWRITING DONE', add_timestamp=True)
                return True
            else:
                return False
        filebin_st = SubscriptionStatus(self.filebin_status, callback_saving)
        filetxt_st = SubscriptionStatus(self.filetxt_status, callback_saving)
        self.stream.set(0).wait()
        # filebin_st.wait()
        # print_debug(f'filebin_st={filebin_st} filetxt_st={filetxt_st}')
        self._datum_ids = []
        datum_id = '{}/{}'.format(self._resource_uid, next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))
        # print(f'{ttime.ctime()} >>> {self.name} complete: done')
        self._datum_ids.append(datum_id)
        print_to_gui(f'{self.name} complete done', add_timestamp=True)
        return filebin_st & filetxt_st

    def collect(self): # Copied from 30-detectors.py (class EncoderFS)
        # print(f'{ttime.ctime()} >>> {self.name} collect starting')
        print_to_gui(f'{self.name} collect starting', add_timestamp=True)
        now = ttime.time()
        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data},
                   'time': now,
                   'filled': {key: False for key in data}}
        print_to_gui(f'{self.name} collect done', add_timestamp=True)
        # print(f'{ttime.ctime()} >>> {self.name} collect complete')

    def describe_collect(self):
        return_dict = {self.name:
                            {self.name: {'source': 'APB',
                                         'dtype': 'array',
                                         'shape': [-1, -1],
                                         'filename_bin': f'{self.filename}.bin',
                                         'filename_txt': f'{self.filename}.txt',
                                         'external': 'FILESTORE:'}}}
        return return_dict

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def prepare_to_fly(self, traj_duration):
        # traj_duration = get_traj_duration()
        # acq_num_points = traj_duration * self.acq_rate.get() * 1000 * 1.3
        acq_num_points = (traj_duration + 8) * self.acq_rate.get() * 1000
        self.num_points = int(round(acq_num_points, ndigits=-3))


    # def set_stream_points(self):
    #     trajectory_manager.current_trajectory_duration


apb_stream = AnalogPizzaBoxStream(prefix="XF:08IDB-CT{PBA:1}:", name="apb_stream")
apb_stream.wait_for_connection(timeout=10)
_ = apb_stream.read()
_ = apb_stream.streaming.read()

apb.ch1.polarity = 'neg'
apb.ch2.polarity = 'neg'
apb.ch3.polarity = 'neg'
apb.ch4.polarity = 'neg'
apb.ch1.amp = i0_amp
apb.ch2.amp = it_amp
apb.ch3.amp = ir_amp
apb.ch4.amp = iff_amp
apb.ch5.amp = None
apb.ch6.amp = None
apb.ch7.amp = None
apb.ch8.amp = None

# apb.amp_ch1 = i0_amp
# apb.amp_ch2 = it_amp
# apb.amp_ch3 = ir_amp
# apb.amp_ch4 = iff_amp
# apb.amp_ch5 = None
# apb.amp_ch6 = None
# apb.amp_ch7 = None
# apb.amp_ch8 = None

apb_ave.ch1.polarity = 'neg'
apb_ave.ch2.polarity = 'neg'
apb_ave.ch3.polarity = 'neg'
apb_ave.ch4.polarity = 'neg'
apb_ave.ch1.amp = i0_amp
apb_ave.ch2.amp = it_amp
apb_ave.ch3.amp = ir_amp
apb_ave.ch4.amp = iff_amp
apb_ave.ch5.amp = None
apb_ave.ch6.amp = None
apb_ave.ch7.amp = None
apb_ave.ch8.amp = None

# apb.amp_ch5 = None
# apb.amp_ch6 = None
# apb.amp_ch7 = None
# apb.amp_ch8 = None








# class APBBinFileHandler(HandlerBase):
#     "Read electrometer *.bin files"
#     def __init__(self, fpath):
#         # It's a text config file, which we don't store in the resources yet, parsing for now
#         fpath_txt = f'{os.path.splitext(fpath)[0]}.txt'
#
#         with open(fpath_txt, 'r') as fp:
#             content = fp.readlines()
#             content = [x.strip() for x in content]
#
#         _ = int(content[0].split(':')[1])
#         Gains = [int(x) for x in content[1].split(':')[1].split(',')]
#         Offsets = [int(x) for x in content[2].split(':')[1].split(',')]
#         FAdiv = float(content[3].split(':')[1])
#         FArate = float(content[4].split(':')[1])
#         trigger_timestamp = float(content[5].split(':')[1].strip().replace(',', '.'))
#
#         raw_data = np.fromfile(fpath, dtype=np.int32)
#
#         columns = ['timestamp', 'i0', 'it', 'ir', 'iff', 'aux1', 'aux2', 'aux3', 'aux4']
#         num_columns = len(columns) + 1  # TODO: figure out why 1
#         raw_data = raw_data.reshape((raw_data.size // num_columns, num_columns))
#
#         derived_data = np.zeros((raw_data.shape[0], raw_data.shape[1] - 1))
#         derived_data[:, 0] = raw_data[:, -2] + raw_data[:, -1]  * 8.0051232 * 1e-9  # Unix timestamp with nanoseconds
#         for i in range(num_columns - 2):
#             derived_data[:, i+1] = raw_data[:, i] #((raw_data[:, i] ) - Offsets[i]) / Gains[i]
#
#         self.df = pd.DataFrame(data=derived_data, columns=columns)
#         self.raw_data = raw_data
#
#     def __call__(self):
#         #print(f'Returning {self.df}')
#         return self.df

#resetting APB to default data rate
_st = apb_stream.divide.set(375)


# from xas.handlers import APBBinFileHandler
#
# db.reg.register_handler('APB',
#                         APBBinFileHandler, overwrite=True)
