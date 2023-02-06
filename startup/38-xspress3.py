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


class Xspress3FileStoreFlyable(Xspress3FileStore):
    def warmup(self):
        """
        A convenience method for 'priming' the plugin.
        The plugin has to 'see' one acquisition before it is ready to capture.
        This sets the array size, etc.
        NOTE : this comes from:
            https://github.com/NSLS-II/ophyd/blob/master/ophyd/areadetector/plugins.py
        We had to replace "cam" with "settings" here.
        Also modified the stage sigs.
        """
        print_to_gui("warming up the hdf5 plugin...")
        self.enable.set(1).wait()
        sigs = OrderedDict([(self.parent.settings.array_callbacks, 1),
                            (self.parent.settings.trigger_mode, 'Internal'),
                            # just in case the acquisition time is set very long...
                            (self.parent.settings.acquire_time, 1),
                            # (self.capture, 1),
                            (self.parent.settings.acquire, 1)])

        original_vals = {sig: sig.get() for sig in sigs}

        # Remove the hdf5.capture item here to avoid an error as it should reset back to 0 itself
        # del original_vals[self.capture]

        for sig, val in sigs.items():
            ttime.sleep(0.1)  # abundance of caution
            sig.set(val).wait()

        ttime.sleep(2)  # wait for acquisition

        for sig, val in reversed(list(original_vals.items())):
            ttime.sleep(0.1)
            sig.set(val).wait()
        print_to_gui("done")

    # def unstage(self):
    #   """A custom unstage method is needed to avoid these messages:
    #
    #   Still capturing data .... waiting.
    #   Still capturing data .... waiting.
    #   Still capturing data .... waiting.
    #   Still capturing data .... giving up.
    #   """
    #   return super().unstage()


# NELM specifies the number of elements that the array will hold NORD is Number
# of Elements Read (at QAS, as of March 25, 2020, .NELM was set to 50000 for
# the PVs below, but .NORD was always returning 1024 elements)
# dpb_sec = pb4.di.sec_array
# dpb_sec_nelm = EpicsSignalRO(f'{dpb_sec.pvname}.NELM', name='dpb_sec_nelm')
#
# dpb_nsec = pb4.di.nsec_array
# dpb_nsec_nelm = EpicsSignalRO(f'{dpb_nsec.pvname}.NELM', name='dpb_nsec_nelm')

from event_model import compose_datum_page, schema_validators, DocumentNames, schemas

# resource, datum_ids, datum_kwarg_list)


_xs_calibration_data = {'Cu' : {'true': 8039, 'ch1': 8160, 'ch2': 7980, 'ch3': 8120, 'ch4': 7880},
                        'Pd': {'true': 21124, 'ch1': 21430, 'ch2': 20990, 'ch3': 21340, 'ch4': 20730}}
def _convert_xs_energy_nom2act(energy, ch_index):
    ch = f'ch{ch_index}'
    ks = [0, (_xs_calibration_data['Cu'][ch] / _xs_calibration_data['Cu']['true']), (_xs_calibration_data['Pd'][ch] / _xs_calibration_data['Pd']['true'])]
    es = [0, _xs_calibration_data['Cu']['true'], _xs_calibration_data['Pd']['true']]
    k = np.interp(energy, es, ks)
    return energy * k

def _compute_window_for_xs_roi_energy(energy):
    es = [_xs_calibration_data['Cu']['true'], _xs_calibration_data['Pd']['true']]
    ws = [500, 1000]
    w = np.interp(energy, es, ws)
    return w
# _convert_xs_energy_nom2act(8039, 1)

class ISSXspress3Detector(XspressTrigger, Xspress3Detector):
    roi_data = Cpt(PluginBase, 'ROIDATA:')
    channel1 = Cpt(Xspress3Channel, 'C1_', channel_num=1, read_attrs=['rois'])
    channel2 = Cpt(Xspress3Channel, 'C2_', channel_num=2, read_attrs=['rois'])
    channel3 = Cpt(Xspress3Channel, 'C3_', channel_num=3, read_attrs=['rois'])
    channel4 = Cpt(Xspress3Channel, 'C4_', channel_num=4, read_attrs=['rois'])
    # create_dir = Cpt(EpicsSignal, 'HDF5:FileCreateDir')

    mca1_sum = Cpt(EpicsSignal, 'ARRSUM1:ArrayData')
    mca2_sum = Cpt(EpicsSignal, 'ARRSUM2:ArrayData')
    mca3_sum = Cpt(EpicsSignal, 'ARRSUM3:ArrayData')
    mca4_sum = Cpt(EpicsSignal, 'ARRSUM4:ArrayData')

    mca1 = Cpt(EpicsSignal, 'ARR1:ArrayData')
    mca2 = Cpt(EpicsSignal, 'ARR2:ArrayData')
    mca3 = Cpt(EpicsSignal, 'ARR3:ArrayData')
    mca4 = Cpt(EpicsSignal, 'ARR4:ArrayData')

    hdf5 = Cpt(Xspress3FileStoreFlyable, 'HDF5:',
               read_path_template=f'{ROOT_PATH}/{RAW_PATH}/xspress3/%Y/%m/%d/',
               root=f'{ROOT_PATH}/{RAW_PATH}/',
               write_path_template=f'{ROOT_PATH}/{RAW_PATH}/xspress3/%Y/%m/%d/',
               )


    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None, **kwargs):
        if configuration_attrs is None:
            configuration_attrs = ['external_trig', 'total_points',
                                   'spectra_per_point', 'settings',
                                   'rewindable']
        if read_attrs is None:
            read_attrs = ['channel1', 'channel2', 'channel3', 'channel4', 'hdf5', 'settings.acquire_time']
        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)
        self.set_channels_for_hdf5()
        # self.create_dir.put(-3)
        self.spectra_per_point.put(1)
        self.channel1.rois.roi01.configuration_attrs.append('bin_low')

        self._asset_docs_cache = deque()
        # self._datum_counter = None
        self.warmup()

    # Step-scan interface methods.
    # def stage(self):
    #     staged_list = super().stage()
    #
    #     return staged_list

    # def unstage(self):
    #
    #     return super().unstage()

    def trigger(self):

        self._status = DeviceStatus(self)
        self.settings.erase.put(1)
        # self.settings.erase.put(1)    # this was
        self._acquisition_signal.put(1, wait=False)
        trigger_time = ttime.time()

        for sn in self.read_attrs:
            if sn.startswith('channel') and '.' not in sn:
                ch = getattr(self, sn)
                self.dispatch(ch.name, trigger_time)

        self._abs_trigger_count += 1
        return self._status

    def set_exposure_time(self, new_exp_time):
        self.settings.acquire_time.set(new_exp_time).wait()

    def read_exposure_time(self):
        return self.settings.acquire_time.get()

    def test_exposure(self, acq_time=1, num_images=1):
        _old_acquire_time = self.settings.acquire_time.value
        _old_num_images = self.settings.num_images.value
        # self.settings.acquire_time.set(acq_time).wait()
        self.set_exposure_time(acq_time)
        self.settings.num_images.set(num_images).wait()
        self.settings.erase.put(1)
        self._acquisition_signal.put(1, wait=True)
        # self.settings.acquire_time.set(_old_acquire_time).wait()
        self.set_exposure_time(_old_acquire_time)
        self.settings.num_images.set(_old_num_images).wait()

    def set_channels_for_hdf5(self, channels=(1, 2, 3, 4)):
        """
        Configure which channels' data should be saved in the resulted hdf5 file.
        Parameters
        ----------
        channels: tuple, optional
            the channels to save the data for
        """
        # The number of channel
        for n in channels:
            getattr(self, f'channel{n}').rois.read_attrs = ['roi{:02}'.format(j) for j in [1, 2, 3, 4]]
        self.hdf5.num_extra_dims.put(0)
        self.settings.num_channels.put(len(channels))

    def warmup(self, hdf5_warmup=False):
        self.channel1.vis_enabled.put(1)
        self.channel2.vis_enabled.put(1)
        self.channel3.vis_enabled.put(1)
        self.channel4.vis_enabled.put(1)
        self.total_points.put(1)
        if hdf5_warmup:
            self.hdf5.warmup()

        # Hints:
        for n in range(1, 5):
            getattr(self, f'channel{n}').rois.roi01.value.kind = 'hinted'

        self.settings.configuration_attrs = ['acquire_period',
                                           'acquire_time',
                                           'gain',
                                           'image_mode',
                                           'manufacturer',
                                           'model',
                                           'num_exposures',
                                           'num_images',
                                           'temperature',
                                           'temperature_actual',
                                           'trigger_mode',
                                           'config_path',
                                           'config_save_path',
                                           'invert_f0',
                                           'invert_veto',
                                           'xsp_name',
                                           'num_channels',
                                           'num_frames_config',
                                           'run_flags',
                                           'trigger_signal']

        for key, channel in self.channels.items():
            roi_names = ['roi{:02}'.format(j) for j in [1, 2, 3, 4]]
            channel.rois.read_attrs = roi_names
            channel.rois.configuration_attrs = roi_names
            for roi_n in roi_names:
                getattr(channel.rois, roi_n).value_sum.kind = 'omitted'

    def set_limits_for_roi(self, energy_nom, roi, window='auto'):

        for ch_index, channel in self.channels.items():
            if window == 'auto':
                w = _compute_window_for_xs_roi_energy(energy_nom)
            else:
                w = int(window)
            energy = _convert_xs_energy_nom2act(energy_nom, ch_index)
            ev_low_new = int(energy - w / 2)
            ev_high_new = int(energy + w / 2)

            roi_obj = getattr(channel.rois, roi)
            if ev_high_new < roi_obj.ev_low.get():
                roi_obj.ev_low.put(ev_low_new)
                roi_obj.ev_high.put(ev_high_new)
            else:
                roi_obj.ev_high.put(ev_high_new)
                roi_obj.ev_low.put(ev_low_new)

    def ensure_roi4_covering_total_mca(self, emin=600, emax=40960):
        for ch_index, channel in self.channels.items():
            channel.rois.roi04.ev_high.put(emax)
            channel.rois.roi04.ev_low.put(emin)


# def compose_bulk_datum_xs(*, resource_uid, counter, datum_kwargs, validate=True):
#     # print_message_now(datum_kwargs)
#     # any_column, *_ = datum_kwargs
#     # print_message_now(any_column)
#     N = len(datum_kwargs)
#     # print_message_now(N)
#     doc = {'resource': resource_uid,
#            'datum_ids': ['{}/{}'.format(resource_uid, next(counter)) for _ in range(N)],
#            'datum_kwarg_list': datum_kwargs}
#     # if validate:
#     #     schema_validators[DocumentNames.bulk_datum].validate(doc)
#     return doc

class ISSXspress3DetectorStream(ISSXspress3Detector):

    def __init__(self, *args, ext_trigger_device=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext_trigger_device = ext_trigger_device
        self._datum_counter = None
        self._infer_datum_keys()

    def _infer_datum_keys(self):
        self.datum_keys = []
        for i in range(self.hdf5.array_size.height.get()):
            # self.datum_keys.append({"name": f"{self.name}",
            #                         "channel": i + 1,
            #                         "type": "spectrum"})
            # self.datum_keys.append({"name": f"{self.name}",
            #                         "channel": i + 1,
            #                         "type": "roi"})
            self.datum_keys.append({"data_type": "spectrum",
                                    "channel": i + 1,
                                    "roi_num" : 0})

            channel = getattr(self, f"channel{i+1}")
            for roi_num in range(1, channel.rois.num_rois.get() + 1):
                if getattr(channel.rois, f"roi{roi_num:02d}").enable.get() == 1:
                    self.datum_keys.append({"data_type": "roi",
                                            "channel": i + 1,
                                            "roi_num": roi_num})

            # self.datum_keys.append(f'{self.name}_ch{i + 1:02d}_roi')

    def format_datum_key(self, input_dict):
        # return f'{input_dict["name"]}_ch{input_dict["channel"]:02d}_{input_dict["type"]}'
        output =f'xs_ch{input_dict["channel"]:02d}_{input_dict["data_type"]}'
        if input_dict["data_type"] == 'roi':
            output += f'{input_dict["roi_num"]:02d}'
        return output

    def prepare_to_fly(self, traj_duration):
        acq_rate = self.ext_trigger_device.freq.get()
        self.num_points = int(acq_rate * (traj_duration + 1))
        self.ext_trigger_device.prepare_to_fly(traj_duration)

    def stage(self):
        self._infer_datum_keys()
        self._datum_counter = itertools.count()
        self.total_points.put(self.num_points)
        self.hdf5.file_write_mode.put(2)
        self.external_trig.put(True)
        self.settings.trigger_mode.put(3)
        staged_list = super().stage()
        staged_list += self.ext_trigger_device.stage()
        return staged_list

    def unstage(self):
        unstaged_list = super().unstage()
        self._datum_counter = None
        self.hdf5.file_write_mode.put(0)
        self.external_trig.put(False)
        self.settings.trigger_mode.put(1)
        self.total_points.put(1)
        unstaged_list += self.ext_trigger_device.unstage()
        return unstaged_list


    def kickoff(self):
        self.settings.acquire.set(1).wait()
        return self.ext_trigger_device.kickoff()

    def complete(self):
        print_to_gui(f'Xspress3 complete is starting...', add_timestamp=True)

        acquire_status = self.settings.acquire.set(0)
        capture_status = self.hdf5.capture.set(0)
        (acquire_status and capture_status).wait()


        ext_trigger_status = self.ext_trigger_device.complete()
        for resource in self.hdf5._asset_docs_cache:
            self._asset_docs_cache.append(('resource', resource[1]))

        _resource_uid = self.hdf5._resource_uid
        self._datum_ids = {}

        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            datum_id = f'{_resource_uid}/{datum_key}'
            self._datum_ids[datum_key] = datum_id
            doc = {'resource': _resource_uid,
                    'datum_id': datum_id,
                    'datum_kwargs': datum_key_dict}
            self._asset_docs_cache.append(('datum', doc))

        print_to_gui(f'Xspress3 complete is done.', add_timestamp=True)
        return NullStatus() and ext_trigger_status

    def collect(self):
        print_to_gui(f'Xspress3 collect is starting...', add_timestamp=True)
        ts = ttime.time()
        yield {'data': self._datum_ids,
               'timestamps': {self.format_datum_key(key_dict): ts for key_dict in self.datum_keys},
               'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
               'filled': {self.format_datum_key(key_dict): False for key_dict in self.datum_keys}}
        print_to_gui(f'Xspress3 collect is done.', add_timestamp=True)
        yield from self.ext_trigger_device.collect()

    def describe_collect(self):
        xs3_spectra_dicts = {}
        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            if datum_key_dict['data_type'] == 'spectrum':
                value = {'source': 'XS',
                         'dtype': 'array',
                         'shape': [self.settings.num_images.get(),
                                   self.hdf5.array_size.width.get()],
                         'dims': ['frames', 'row'],
                         'external': 'FILESTORE:'}
            elif datum_key_dict['data_type'] == 'roi':
                value = {'source': 'XS',
                         'dtype': 'array',
                         'shape': [self.settings.num_images.get()],
                         'dims': ['frames'],
                         'external': 'FILESTORE:'}
            else:
                raise KeyError(f'data_type={datum_key_dict["data_type"]} not supported')
            xs3_spectra_dicts[datum_key] = value

        return_dict_xs = {self.name : xs3_spectra_dicts}

        return_dict_trig = self.ext_trigger_device.describe_collect()
        return {**return_dict_xs, **return_dict_trig}

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        # print_to_gui(f"items = {items}", tag='XS DEBUG')
        self._asset_docs_cache.clear()
        for item in items:
            yield item
        yield from self.ext_trigger_device.collect_asset_docs()


xs = ISSXspress3Detector('XF:08IDB-ES{Xsp:1}:', name='xs')
xs_stream = ISSXspress3DetectorStream('XF:08IDB-ES{Xsp:1}:', name='xs_stream', ext_trigger_device=apb_trigger_xs)


#
# class ISSXspress3HDF5Handler(Xspress3HDF5Handler):
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._roi_data = None
#         # self._num_channels = None
#
#     def _get_dataset(self):
#         super()._get_dataset()
#
#         if self._roi_data is not None:
#             return
#         print(f'{ttime.ctime()} Determining number of channels...')
#         shape = self.dataset.shape
#         if len(shape) != 3:
#             raise RuntimeError(f'The ndim of the dataset is not 3, but {len(shape)}')
#         _num_channels = shape[1]
#
#         self._roi_data = {}
#         all_keys = self._file['/entry/instrument/detector/NDAttributes'].keys()
#         for chan in range(1, _num_channels + 1):
#             base = f'CHAN{chan}ROI'
#             keys = [k for k in all_keys if k.startswith(base) and not k.endswith('LM')]
#             for key in keys:
#                 roi_num = int(key.replace(base, ''))
#                 self._roi_data[(chan, roi_num)] = self._file['/entry/instrument/detector/NDAttributes'][key][()]
#
#     def __call__(self, data_type:str='spectrum', channel:int=1, roi_num:int=1):
#         # print(f'{ttime.ctime()} XS dataset retrieving starting...')
#         self._get_dataset()
#
#         if data_type=='spectrum':
#             # output = self._dataset[:, channel - 1, :]
#             # print(output.shape, output.squeeze().shape)
#             return self._dataset[:, channel - 1, :].squeeze()
#
#         elif data_type=='roi':
#             return self._roi_data[(channel, roi_num)].squeeze()
#
#         else:
#             raise KeyError(f'data_type={data_type} not supported')



from xas.handlers import ISSXspress3HDF5Handler
# heavy-weight file handler
db.reg.register_handler(ISSXspress3HDF5Handler.HANDLER_NAME,
                        ISSXspress3HDF5Handler, overwrite=True)



def xs_count(acq_time:float = 1, num_frames:int =1):

    yield from bps.mv(xs.settings.erase, 0)
    yield from bp.count([xs], acq_time)
