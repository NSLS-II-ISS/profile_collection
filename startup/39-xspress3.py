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
from ophyd import Component as Cpt, set_and_wait
from ophyd.status import SubscriptionStatus, DeviceStatus

from pathlib import PurePath
from nslsii.detectors.xspress3 import (XspressTrigger, Xspress3Detector,
                                       Xspress3Channel, Xspress3FileStore, Xspress3ROI, logger)

#from isstools.trajectory.trajectory import trajectory_manager

import bluesky.plans as bp
import bluesky.plan_stubs as bps

import numpy as np
import itertools
import time as ttime
from collections import deque, OrderedDict
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
        print("warming up the hdf5 plugin...")
        set_and_wait(self.enable, 1)
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
            set_and_wait(sig, val)

        ttime.sleep(2)  # wait for acquisition

        for sig, val in reversed(list(original_vals.items())):
            ttime.sleep(0.1)
            set_and_wait(sig, val)
        print("done")

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
dpb_sec = pb4.di.sec_array
dpb_sec_nelm = EpicsSignalRO(f'{dpb_sec.pvname}.NELM', name='dpb_sec_nelm')

dpb_nsec = pb4.di.nsec_array
dpb_nsec_nelm = EpicsSignalRO(f'{dpb_nsec.pvname}.NELM', name='dpb_nsec_nelm')

from event_model import compose_datum_page, schema_validators, DocumentNames, schemas

# resource, datum_ids, datum_kwarg_list)
def compose_bulk_datum(*, resource_uid, counter, datum_kwargs, validate=True):
    # print_message_now(datum_kwargs)
    # any_column, *_ = datum_kwargs
    # print_message_now(any_column)
    N = len(datum_kwargs)
    # print_message_now(N)
    doc = {'resource': resource_uid,
           'datum_ids': ['{}/{}'.format(resource_uid, next(counter)) for _ in range(N)],
           'datum_kwarg_list': datum_kwargs}
    # if validate:
    #     schema_validators[DocumentNames.bulk_datum].validate(doc)
    return doc



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
               read_path_template='/nsls2/xf08id/data/xspress3/%Y/%m/%d/',
               root='/nsls2/xf08id/data/',
               write_path_template='/nsls2/xf08id/data/xspress3/%Y/%m/%d/',
               )


    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):
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

        self._asset_docs_cache = deque()
        self._datum_counter = None

        self.channel1.rois.roi01.configuration_attrs.append('bin_low')

    # Step-scan interface methods.
    def stage(self):
        if self.spectra_per_point.get() != 1:
            raise NotImplementedError(
                "multi spectra per point not supported yet")

        ret = super().stage()
        self._datum_counter = itertools.count()
        return ret

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

    def unstage(self):
        self.settings.trigger_mode.put(1)  # 'Software'
        super().unstage()
        self._datum_counter = None

    def stop(self):
        ret = super().stop()
        self.hdf5.stop()
        return ret

    # Fly-able interface methods.
    # def kickoff(self):
    #     # TODO: implement the kickoff method for the flying mode once the hardware is ready.
    #     raise NotImplementedError()

    def complete(self, *args, **kwargs):
        for resource in self.hdf5._asset_docs_cache:
            self._asset_docs_cache.append(('resource', resource[1]))

        self._datum_ids = []

        num_frames = self.hdf5.num_captured.get()

        # print(f'\n!!! num_frames: {num_frames}\n')
        resource_uid = self.hdf5._resource_uid

        # [{'frame' : i} for i in np.arange(num_frames)]
        datum_kwargs = [{'frame': i} for i in range(num_frames)]
        # datum_kwargs = np.arange(num_frames).tolist()
        print_message_now('Composing datum page')
        doc = compose_bulk_datum(resource_uid=resource_uid,
                                 counter=self._datum_counter,
                                 datum_kwargs=datum_kwargs)
        print_message_now('DONE Composing datum page')
        print_message_now(doc)
        self._asset_docs_cache.append(('bulk_datum', doc))
        _datum_id_counter = itertools.count()
        for frame_num in range(num_frames):
            datum_id = '{}/{}'.format(resource_uid, next(_datum_id_counter))
            #     datum = {'resource': _resource,
            #              'datum_kwargs': {'frame': frame_num},
            #              'datum_id': datum_id}
            #     self._asset_docs_cache.append(('datum', datum))
            self._datum_ids.append(datum_id)

        return NullStatus()

    def collect(self):
        # TODO: try to separate it from the xspress3 class
        collected_frames = self.settings.array_counter.get()

        # This is a hack around the issue with .NORD (number of elements to #
        # read) that does not match .NELM (number of elements to that the array
        # will hold)
        dpb_sec_nelm_count = int(dpb_sec_nelm.get())
        dpb_nsec_nelm_count = int(dpb_nsec_nelm.get())
        dpb_sec_values = np.array(dpb_sec.get(count=dpb_sec_nelm_count),
                                  dtype='float128')[:collected_frames * 2: 2]
        dpb_nsec_values = np.array(dpb_nsec.get(count=dpb_nsec_nelm_count),
                                   dtype='float128')[:collected_frames * 2: 2]

        di_timestamps = dpb_sec_values + dpb_nsec_values * 1e-9

        len_di_timestamps = len(di_timestamps)
        len_datum_ids = len(self._datum_ids)

        if len_di_timestamps != len_datum_ids:
            warnings.warn(f'The length of "di_timestamps" ({len_di_timestamps}) '
                          f'does not match the length of "self._datum_ids" ({len_datum_ids})')

        # num_frames = min(len_di_timestamps, len_datum_ids)
        num_frames = len_datum_ids
        for frame_num in range(num_frames):

            datum_id = self._datum_ids[frame_num]
            print(f'{ttime.time()} >>> xs3 collect ', frame_num, datum_id)

            # ts = di_timestamps[frame_num]
            ts = di_timestamps

            data = {self.name: datum_id}
            # TODO: fix the lost precision as pymongo complained about np.float128.
            ts = float(ts)

            # print(f'data: {data}\nlen_di_timestamps: {len_di_timestamps}\nlen_datum_ids: {len_di_timestamps}')

            yield {'data': data,
                   'timestamps': {key: ts for key in data},
                   'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
                   'filled': {key: False for key in data}}

    # The collect_asset_docs(...) method was removed as it exists on the hdf5 component and should be used there.

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

    # Currently only using four channels. Uncomment these to enable more
    # channels:
    # channel5 = C(Xspress3Channel, 'C5_', channel_num=5)
    # channel6 = C(Xspress3Channel, 'C6_', channel_num=6)
    # channel7 = C(Xspress3Channel, 'C7_', channel_num=7)
    # channel8 = C(Xspress3Channel, 'C8_', channel_num=8)

xs = ISSXspress3Detector('XF:08IDB-ES{Xsp:1}:', name='xs')


def initialize_Xspress3(xs, hdf5_warmup=True):
    # TODO: do not put on startup or do it conditionally, if on beamline.
    xs.channel2.vis_enabled.put(1)
    xs.channel3.vis_enabled.put(1)
    xs.channel4.vis_enabled.put(1)
    xs.total_points.put(1)

    # This is necessary for when the ioc restarts
    # we have to trigger one image for the hdf5 plugin to work correctly
    # else, we get file writing errors
    if hdf5_warmup:
        xs.hdf5.warmup()

    # Hints:
    for n in [1, 2]:
        getattr(xs, f'channel{n}').rois.roi01.value.kind = 'hinted'

    xs.settings.configuration_attrs = ['acquire_period',
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

    for n, d in xs.channels.items():
        roi_names = ['roi{:02}'.format(j) for j in [1, 2, 3, 4]]
        d.rois.read_attrs = roi_names
        d.rois.configuration_attrs = roi_names
        for roi_n in roi_names:
            getattr(d.rois, roi_n).value_sum.kind = 'omitted'

initialize_Xspress3(xs)


def xs_count(acq_time:float = 1, num_frames:int =1):

    yield from bps.mv(xs.settings.erase, 0)
    yield from bp.count([xs], acq_time)


def calibrate_xs_plan():
    # detectors = [xs]
    energies = np.arange(10000, 26000, 1000)
    for energy in energies:
        if energy < 12000:
            yield from set_attenuator('200')
        else:
            yield from set_attenuator('1000')
        yield from bps.mv(hhm.energy, energy)
        yield from bps.sleep(1)
        yield from bp.list_scan([xs], hhm.energy, [int(energy)])

        # yield from bps.mv(hhm.energy, energy)
        # yield from bps.sleep(1)
        # yield from bp.count([xs])

def calibrate_xs_plan_vs_int():
    # detectors = [xs]
    energy = 24350
    yield from bps.mv(hhm.energy, energy)
    atts = ['200', '400', '600', '1000', '2000', '4000']
    for att in atts:
        yield from set_attenuator(att)
        yield from bps.sleep(1)
        yield from bp.list_scan([xs, apb_ave], hhm.energy, [int(energy)])








class ISSXspress3DetectorStream(ISSXspress3Detector):

    def stage(self, acq_rate, traj_time, *args, **kwargs):
        self.hdf5.file_write_mode.put(2) # put it to Stream |||| IS ALREADY STREAMING
        self.external_trig.put(True)
        self.set_expected_number_of_points(acq_rate, traj_time)
        self.spectra_per_point.put(1)
        self.settings.trigger_mode.put(3) # put the trigger mode to TTL in

        super().stage(*args, **kwargs)
        # note, hdf5 is already capturing at this point
        self.settings.acquire.put(1) # start recording data

    def set_expected_number_of_points(self, acq_rate, traj_time):
        self._num_points = int(acq_rate * (traj_time + 1) )
        self.total_points.put(self._num_points)


    def describe_collect(self):
        return_dict = {self.name:
                           {f'{self.name}': {'source': 'XS',
                                             'dtype': 'array',
                                             'shape': [self.settings.num_images.get(),
                                                       #self.settings.array_counter.get()
                                                       self.hdf5.array_size.height.get(),
                                                       self.hdf5.array_size.width.get()],
                                            'filename': f'{self.hdf5.full_file_name.get()}',
                                             'external': 'FILESTORE:'}}}
        return return_dict

    def collect(self):
        print(f'{ttime.ctime()} Xspress3 collect is starting...')


        num_frames = len(self._datum_ids)

        for frame_num in range(num_frames):
            datum_id = self._datum_ids[frame_num]
            data = {self.name: datum_id}

            ts = ttime.time()

            yield {'data': data,
                   'timestamps': {key: ts for key in data},
                   'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
                   'filled': {key: False for key in data}}

        print(f'{ttime.ctime()} Xspress3 collect is complete')

    def collect_asset_docs(self):
        # print(f'                {ttime.ctime()} converting to list start')
        items = list(self._asset_docs_cache)
        # print(f'                {ttime.ctime()} converting to list end. len(items)={len(items)}')
        self._asset_docs_cache.clear()
        for i, item in enumerate(items):
            # print(f'                {ttime.ctime()} yielding item {i}')
            yield item


    def unstage(self, *args, **kwargs):
        super().unstage(*args, **kwargs)
        self.settings.trigger_mode.put(1)
        self.total_points.put(1)


xs_stream = ISSXspress3DetectorStream('XF:08IDB-ES{Xsp:1}:', name='xs_stream')
initialize_Xspress3(xs_stream, hdf5_warmup=True)

from itertools import product
import pandas as pd
from databroker.assets.handlers import HandlerBase, Xspress3HDF5Handler

class ISSXspress3HDF5Handler(Xspress3HDF5Handler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._roi_data = None
        self._num_channels = None

    def _get_dataset(self): # readpout of the following stuff should be done only once, this is why I redefined _get_dataset method - Denis Leshchev Feb 9, 2021
        # dealing with parent
        super()._get_dataset()

        # finding number of channels
        if self._num_channels is not None:
            return
        print(f'{ttime.ctime()} Determining number of channels...')
        shape = self.dataset.shape
        if len(shape) != 3:
            raise RuntimeError(f'The ndim of the dataset is not 3, but {len(shape)}')
        self._num_channels = shape[1]

        if self._roi_data is not None:
            return
        print(f'{ttime.ctime()} reading ROI data...')
        self.chanrois = [f'CHAN{c}ROI{r}' for c, r in product([1, 2, 3, 4], [1, 2, 3, 4])]
        _data_columns = [self._file['/entry/instrument/detector/NDAttributes'][chanroi][()] for chanroi in
                         self.chanrois]
        data_columns = np.vstack(_data_columns).T
        self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)


    def __call__(self, *args, frame=None, **kwargs):
        # print(f'{ttime.ctime()} XS dataset retrieving starting...')
        self._get_dataset()
        return_dict = {f'ch_{i+1}' : self._dataset[frame, i, :] for i in range(self._num_channels)}
        return_dict_rois = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
        return {**return_dict, **return_dict_rois}
        # print(f'{ttime.ctime()} XS dataset retrieving complete')


# heavy-weight file handler
db.reg.register_handler(ISSXspress3HDF5Handler.HANDLER_NAME,
                        ISSXspress3HDF5Handler, overwrite=True)




class ISSXspress3HDF5Handler_light(Xspress3HDF5Handler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._roi_data = None
        self._num_channels = None

    def _get_dataset(self): # readpout of the following stuff should be done only once, this is why I redefined _get_dataset method - Denis Leshchev Feb 9, 2021
        # dealing with parent
        # super()._get_dataset()

        # finding number of channels
        # if self._num_channels is not None:
        #     return
        # print('determening number of channels')
        # shape = self.dataset.shape
        # if len(shape) != 3:
        #     raise RuntimeError(f'The ndim of the dataset is not 3, but {len(shape)}')
        # self._num_channels = shape[1]

        if self._roi_data is not None:
            return
        print('reading ROI data')
        self.chanrois = [f'CHAN{c}ROI{r}' for c, r in product([1, 2, 3, 4], [1, 2, 3, 4])]
        _data_columns = [self._file['/entry/instrument/detector/NDAttributes'][chanroi][()] for chanroi in
                         self.chanrois]
        data_columns = np.vstack(_data_columns).T
        self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)

    def __call__(self, *args, frame=None, **kwargs):
            self._get_dataset()
            # return_dict = {f'ch_{i+1}' : self._dataset[frame, i, :] for i in range(self._num_channels)}
            return_dict_rois = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
            # return {**return_dict, **return_dict_rois}
            return return_dict_rois


# db.reg.register_handler(ISSXspress3HDF5Handler_light.HANDLER_NAME,
#                         ISSXspress3HDF5Handler_light, overwrite=True)

