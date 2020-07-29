# from ophyd.areadetector import (AreaDetector, PixiradDetectorCam, ImagePlugin,
#                                 TIFFPlugin, StatsPlugin, HDF5Plugin,
#                                 ProcessPlugin, ROIPlugin, TransformPlugin,
#                                 OverlayPlugin)
# from ophyd.areadetector.plugins import PluginBase
# from ophyd.areadetector.cam import AreaDetectorCam
# from ophyd.device import BlueskyInterface
# from ophyd.areadetector.trigger_mixins import SingleTrigger
# from ophyd.areadetector.filestore_mixins import (FileStoreIterativeWrite,
#                                                  FileStoreHDF5IterativeWrite,
#                                                  FileStoreTIFFSquashing,
#                                                  FileStoreTIFF)
# from ophyd import Signal, EpicsSignal, EpicsSignalRO
# from ophyd.status import SubscriptionStatus
# from ophyd.sim import NullStatus  # TODO: remove after complete/collect are defined
# from ophyd import Component as Cpt, set_and_wait
#
# from pathlib import PurePath
# from nslsii.detectors.xspress3 import (XspressTrigger, Xspress3Detector,
#                                          Xspress3Channel, Xspress3FileStore, logger)
#
# #from isstools.trajectory.trajectory import trajectory_manager
#
# import bluesky.plans as bp
# import bluesky.plan_stubs as bps
#
# import numpy as np
# import itertools
# import time as ttime
# from collections import deque, OrderedDict
#
#
# class Xspress3FileStoreFlyable(Xspress3FileStore):
#     def warmup(self):
#         """
#         A convenience method for 'priming' the plugin.
#         The plugin has to 'see' one acquisition before it is ready to capture.
#         This sets the array size, etc.
#         NOTE : this comes from:
#             https://github.com/NSLS-II/ophyd/blob/master/ophyd/areadetector/plugins.py
#         We had to replace "cam" with "settings" here.
#         Also modified the stage sigs.
#         """
#         print("warming up the hdf5 plugin...")
#         set_and_wait(self.enable, 1)
#         sigs = OrderedDict([(self.parent.settings.array_callbacks, 1),
#                             (self.parent.settings.trigger_mode, 'Internal'),
#                             # just in case the acquisition time is set very long...
#                             (self.parent.settings.acquire_time, 1),
#                             # (self.capture, 1),
#                             (self.parent.settings.acquire, 1)])
#
#         original_vals = {sig: sig.get() for sig in sigs}
#
#         # Remove the hdf5.capture item here to avoid an error as it should reset back to 0 itself
#         # del original_vals[self.capture]
#
#         for sig, val in sigs.items():
#             ttime.sleep(0.1)  # abundance of caution
#             set_and_wait(sig, val)
#
#         ttime.sleep(2)  # wait for acquisition
#
#         for sig, val in reversed(list(original_vals.items())):
#             ttime.sleep(0.1)
#             set_and_wait(sig, val)
#         print("done")
#
#     def unstage(self):
#         """A custom unstage method is needed to avoid these messages:
#
#         Still capturing data .... waiting.
#         Still capturing data .... waiting.
#         Still capturing data .... waiting.
#         Still capturing data .... giving up.
#         """
#         return super().unstage()
#
#
# dpb_sec = pb2.di.sec_array
# dpb_nsec = pb2.di.nsec_array
#
#
# class ISSXspress3Detector(XspressTrigger, Xspress3Detector):
#     roi_data = Cpt(PluginBase, 'ROIDATA:')
#     channel1 = Cpt(Xspress3Channel, 'C1_', channel_num=1, read_attrs=['rois'])
#     channel2 = Cpt(Xspress3Channel, 'C2_', channel_num=2, read_attrs=['rois'])
#     channel3 = Cpt(Xspress3Channel, 'C3_', channel_num=3, read_attrs=['rois'])
#     channel4 = Cpt(Xspress3Channel, 'C4_', channel_num=4, read_attrs=['rois'])
#     # create_dir = Cpt(EpicsSignal, 'HDF5:FileCreateDir')
#
#     hdf5 = Cpt(Xspress3FileStoreFlyable, 'HDF5:',
#                read_path_template='/nsls2/xf08id/data/x3test/',
#                root='/nsls2/xf08id/data/',
#                write_path_template='/nsls2/xf08id/data/x3test/',
#                )
#
#     def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
#                  **kwargs):
#         if configuration_attrs is None:
#             configuration_attrs = ['external_trig', 'total_points',
#                                    'spectra_per_point', 'settings',
#                                    'rewindable']
#         if read_attrs is None:
#             read_attrs = ['channel1', 'channel2', 'channel3', 'channel4', 'hdf5']
#         super().__init__(prefix, configuration_attrs=configuration_attrs,
#                          read_attrs=read_attrs, **kwargs)
#         self.set_channels_for_hdf5()
#         # self.create_dir.put(-3)
#
#         self._asset_docs_cache = deque()
#         self._datum_counter = None
#
#     def stop(self):
#         ret = super().stop()
#         self.hdf5.stop()
#         return ret
#
#     def stage(self):
#         if self.spectra_per_point.get() != 1:
#             raise NotImplementedError(
#                 "multi spectra per point not supported yet")
#         ret = super().stage()
#         self._datum_counter = itertools.count()
#         return ret
#
#     def unstage(self):
#         self.settings.trigger_mode.put(0)  # 'Software'
#         super().unstage()
#         self._datum_counter = None
#
#     def complete(self, *args, **kwargs):
#         for resource in self.hdf5._asset_docs_cache:
#             self._asset_docs_cache.append(('resource', resource[1]))
#
#         self._datum_ids = []
#
#         num_frames = xs.hdf5.num_captured.get()
#
#         for frame_num in range(num_frames):
#             datum_id = '{}/{}'.format(self.hdf5._resource_uid, next(self._datum_counter))
#             datum = {'resource': self.hdf5._resource_uid,
#                      'datum_kwargs': {'frame': frame_num},
#                      'datum_id': datum_id}
#             self._asset_docs_cache.append(('datum', datum))
#             self._datum_ids.append(datum_id)
#
#         return NullStatus()
#
#     def collect(self):
#         # TODO: try to separate it from the xspress3 class
#         collected_frames = self.settings.array_counter.get()
#         dpb_sec_values = np.array(dpb_sec.get(), dtype='float128')[:collected_frames * 2: 2]
#         dpb_nsec_values = np.array(dpb_nsec.get(), dtype='float128')[:collected_frames * 2: 2]
#
#         di_timestamps = dpb_sec_values + dpb_nsec_values * 1e-9
#
#         assert len(di_timestamps) == len(self._datum_ids), \
#             (f'The length of "di_timestamps" ({len(di_timestamps)}) '
#              f'does not match the length of "self._datum_ids" ({len(self._datum_ids)})')
#
#         for datum_id, ts in zip(self._datum_ids, di_timestamps):
#             data = {self.name: datum_id}
#             # TODO: fix the lost precision as pymongo complained about np.float128.
#             ts = float(ts)
#             yield {'data': data,
#                    'timestamps': {key: ts for key in data},
#                    'time': ts,  # TODO: use the proper timestams from the mono start and stop times
#                    'filled': {key: False for key in data}}
#
#     def collect_asset_docs(self):
#         items = list(self._asset_docs_cache)
#         self._asset_docs_cache.clear()
#         for item in items:
#             yield item
#
#     def set_channels_for_hdf5(self, channels=(1, 2, 3, 4)):
#         """
#         Configure which channels' data should be saved in the resulted hdf5 file.
#
#         Parameters
#         ----------
#         channels: tuple, optional
#             the channels to save the data for
#         """
#         # The number of channel
#         for n in channels:
#             getattr(self, f'channel{n}').rois.read_attrs = ['roi{:02}'.format(j) for j in [1, 2, 3, 4]]
#         self.hdf5.num_extra_dims.put(0)
#         self.settings.num_channels.put(len(channels))
#
#     # Currently only using four channels. Uncomment these to enable more
#     # channels:
#     # channel5 = C(Xspress3Channel, 'C5_', channel_num=5)
#     # channel6 = C(Xspress3Channel, 'C6_', channel_num=6)
#     # channel7 = C(Xspress3Channel, 'C7_', channel_num=7)
#     # channel8 = C(Xspress3Channel, 'C8_', channel_num=8)
#
#
# xs = ISSXspress3Detector('XF:08IDB-ES{Xsp:1}:', name='xs')
# xs.channel2.vis_enabled.put(1)
# xs.channel3.vis_enabled.put(1)
#
# # This is necessary for when the ioc restarts
# # we have to trigger one image for the hdf5 plugin to work correctly
# # else, we get file writing errors
# xs.hdf5.warmup()
#
# # Hints:
# for n in [1, 2]:
#     getattr(xs, f'channel{n}').rois.roi01.value.kind = 'hinted'
#
# xs.settings.configuration_attrs = ['acquire_period',
# 			           'acquire_time',
# 			           'gain',
# 			           'image_mode',
# 			           'manufacturer',
# 			           'model',
# 			           'num_exposures',
# 			           'num_images',
# 			           'temperature',
# 			           'temperature_actual',
# 			           'trigger_mode',
# 			           'config_path',
# 			           'config_save_path',
# 			           'invert_f0',
# 			           'invert_veto',
# 			           'xsp_name',
# 			           'num_channels',
# 			           'num_frames_config',
# 			           'run_flags',
#                                    'trigger_signal']
#
# for n, d in xs.channels.items():
#     roi_names = ['roi{:02}'.format(j) for j in [1, 2, 3, 4]]
#     d.rois.read_attrs = roi_names
#     d.rois.configuration_attrs = roi_names
#     for roi_n in roi_names:
#         getattr(d.rois, roi_n).value_sum.kind = 'omitted'
#
#
# class XSFlyer:
#     def __init__(self, *, pb, di, motor_ts, pb_triggers, xs_dets, an_dets, motor):
#         """
#         The flyer based on a single encoder pizza-box and multiple xspress3 devices running a mono.
#
#         Parameters
#         ----------
#         pb : an encoder pizza-box orchestrating the experiment (triggering and timestamping the xspress3)
#         di : a digital input to timestamp trigger pulses
#         motor_ts : an encoder pizza-box for timestamping the motor (mono)
#         pb_triggers : list
#             a list of names of the trigger signals (e.g., 'do1') from the pizza-box digital outputs.
#             It's possible to configure up to 4 triggers per pizza-box, triggering a corresponding xspress3 detector each.
#         xs_dets : list
#             a list of ophyd devices for the xspress3 detectors (up to 4 xspress3 detectors per 1 pizza-box)
#         an_dets : list
#             a list of analog detectors to be triggered
#         motor : a monochromator motor
#         """
#         self.name = f'{pb.name}-{"-".join([xs_det.name for xs_det in xs_dets])}-{"-".join([an_det.name for an_det in an_dets])}-{motor.name}-{self.__class__.__name__}'
#         self.pb = pb
#         self.di = di
#         self.motor_ts = motor_ts
#         self.pb_triggers = pb_triggers
#         self.xs_dets = xs_dets
#         self.an_dets = an_dets
#         self.motor = motor
#
#         # self.parent = None
#         self.num_points = {}
#         self._motor_status = None
#
#     def __repr__(self):
#         return f"""\
#     Flyer '{self.name}' with the following config:
#
#         - encoder pizza-box  : {self.pb.name}
#         - pizza-box triggers : {', '.join([x for x in self.pb_triggers])}
#         - xspress3 detectors : {', '.join([x.name for x in self.xs_dets])}
#         - analog detectors   : {', '.join([x.name for x in self.an_dets])}
#         - motor              : {self.motor.name}
# """
#
#     def kickoff(self, *args, **kwargs):
#         # Set all required signals in xspress3
#         self._calc_num_points()
#         for xs_det in self.xs_dets:
#             xs_det.hdf5.file_write_mode.put('Stream')
#
#             # Prepare the soft signals for hxntools.detectors.xspress3.Xspress3FileStore#stage
#             xs_det.external_trig.put(True)
#             xs_det.total_points.put(self.num_points[xs_det.name])
#             # TODO: sort out how many spectra per point we should have
#             xs_det.spectra_per_point.put(1)
#             xs_det.stage()
#
#             # These parameters are dynamically set for the case of
#             # the external triggering mode in the stage() method (see above).
#             # xs_det.settings.num_images.put(self.num_points[xs_det.name])
#             # xs_det.hdf5.num_capture.put(self.num_points[xs_det.name])
#
#         for xs_det in self.xs_dets:
#             # These parameters are dynamically set for the case of
#             # the external triggering mode in the stage() method (see above).
#
#             # "Acquisition Controls and Status" (top left pane) -->
#             # "Trigger" selection button 'TTL Veto Only (3)'
#             # xs_det.settings.trigger_mode.put('TTL Veto Only')
#             # "File Saving" (left bottom pane) --> "Start File Saving" button
#             # xs_det.hdf5.capture.put(1)
#
#             # "Acquisition Controls and Status" (top left pane) --> "Start" button
#             xs_det.settings.acquire.put(1)
#
#         # analog pizza-boxes:
#         for an_det in self.an_dets:
#             an_det.stage()
#             an_det.kickoff()
#
#         # Parameters of the encoder pizza-boxes:
#         # (J8B channel for pb2)
#         self.pb.stage()
#         self.pb.kickoff()
#         self.motor_ts.stage()
#         self.motor_ts.kickoff()
#         self.di.stage()
#         self.di.kickoff()
#         for pb_trigger in self.pb_triggers:
#             getattr(self.pb.parent, pb_trigger).enable.put(1)
#
#         self._motor_status = self.motor.set('start')
#
#         return NullStatus()
#
#     def complete(self):
#         def callback_motor():
#             # Parameters of the encoder pizza-boxes:
#             # (J8B channel for pb2)
#             for pb_trigger in self.pb_triggers:
#                 getattr(self.pb.parent, pb_trigger).enable.put(0)
#
#             for an_det in self.an_dets:
#                 an_det.complete()
#             self.pb.complete()
#             self.motor_ts.complete()
#             self.di.complete()
#
#             for xs_det in self.xs_dets:
#                 # "Acquisition Controls and Status" (top left pane) -->
#                 # "Trigger" selection button 'Internal'
#                 xs_det.settings.trigger_mode.put('Internal')
#                 # "Acquisition Controls and Status" (top left pane) --> "Stop" button
#                 xs_det.settings.acquire.put(0)
#                 # TODO: check what happens when the number of collected frames is the same as expected.
#                 # There is a chance the stop saving button is pressed twice.
#                 xs_det.hdf5.capture.put(0)  # this is to save the file is the number of collected frames is less than expected
#                 xs_det.complete()
#
#         self._motor_status.add_callback(callback_motor)
#
#         return self._motor_status
#
#     def describe_collect(self):
#         """
#         In [3]: hdr.stream_names
#         Out[3]:
#         ['pba1_adc5',
#          'pba1_adc8',
#          'pba1_adc7',
#          'pba1_adc4',
#          'xs',
#          'pb2_enc1',
#          'pba1_adc3',
#          'pba1_adc6']
#
#         In [4]: hdr.table(stream_name='pba1_adc5')
#         Out[4]:
#                                          time                             pba1_adc5
#         seq_num
#         1       2019-11-27 15:08:43.058514118  b0d95db8-f2c4-49ab-a918-014e02775b3a
#
#         In [5]: hdr.table(stream_name='pba1_adc5', fill=True)
#         Out[5]:
#                                          time                                          pba1_adc5
#         seq_num
#         1       2019-11-27 15:08:43.058514118            timestamp       adc
#         0      1.574885e...
#
#         In [6]: hdr.table(stream_name='pb1_enc1', fill=True)
#         Out[6]:
#         Empty DataFrame
#         Columns: []
#         Index: []
#
#         In [7]: hdr.table(stream_name='pb2_enc1', fill=True)
#         Out[7]:
#         Empty DataFrame
#         Columns: []
#         Index: []
#
#         In [8]: hdr.table(stream_name='xs', fill=True)
#         Out[8]:
#         Empty DataFrame
#         Columns: []
#         Index: []
#         """
#         return_dict = {}
#
#         # xspress3 detectors:
#         for xs_det in self.xs_dets:
#             return_dict[xs_det.name] = {f'{xs_det.name}': {'source': 'xspress3',
#                                                            'dtype': 'array',
#                                                            'shape': [xs_det.settings.num_images.get(),
#                                                                      xs_det.hdf5.array_size.height.get(),
#                                                                      xs_det.hdf5.array_size.width.get()],
#                                                            'external': 'FILESTORE:'}}
#         # analog pizza-boxes:
#         for an_det in self.an_dets:
#             return_dict[an_det.name] = an_det.describe_collect()[an_det.name]
#
#         # encoder pizza-box:
#         return_dict[self.pb.name] = self.pb.describe_collect()[self.pb.name]
#         return_dict[self.motor_ts.name] = self.motor_ts.describe_collect()[self.motor_ts.name]
#         return_dict[self.di.name] = self.di.describe_collect()[self.di.name]
#
#         return return_dict
#
#     def collect_asset_docs(self):
#         for xs_det in self.xs_dets:
#             yield from xs_det.collect_asset_docs()
#         # for an_det in self.an_dets:
#         #     yield from an_det.collect_asset_docs()
#         # yield from self.pb.collect_asset_docs()
#
#     def collect(self):
#         for xs_det in self.xs_dets:
#             xs_det.unstage()
#         for an_det in self.an_dets:
#             an_det.unstage()
#         self.pb.unstage()
#         self.motor_ts.unstage()
#         self.di.unstage()
#
#         def collect_all():
#             yield from self.pb.collect()
#             yield from self.motor_ts.collect()
#             yield from self.di.collect()
#             for an_det in self.an_dets:
#                 yield from an_det.collect()
#             for xs_det in self.xs_dets:
#                 yield from xs_det.collect()
#
#         return collect_all()
#
# #    def _calc_num_points(self):
# #        """
# #        Calculate a number of points for the xspress3 detectors.
# #
# #        "Acquisition Controls and Status" (top left pane) --> "Number Of Frames" field
# #        """
# #        tr = trajectory_manager(self.motor)
# #        info = tr.read_info(silent=True)
# #        lut = str(int(self.motor.lut_number_rbv.get()))
# #        traj_duration = int(info[lut]['size']) / 16_000
# #        for pb_trigger, xs_det in zip(self.pb_triggers, self.xs_dets):
# #            units = getattr(self.pb.parent, pb_trigger).unit_sel.get(as_string=True)
# #            if units == 'us':
# #                 multip = 1e-6  # micro-seconds
# #            elif units == 'ms':
# #                 multip = 1e-3  # milli-seconds
# #            else:
# #                raise RuntimeError(f'The units "{units}" are not supported yet.')
# #            acq_num_points = traj_duration / (getattr(self.pb.parent, pb_trigger).period_sp.get() * multip) * 1.3
# #            self.num_points[xs_det.name] = int(round(acq_num_points, ndigits=0))
#
#
# #xsflyer_pb2 = XSFlyer(pb=pb2.enc1,
# #                      di=pb2.di,
# #                      motor_ts=pb1.enc1,
# #                      pb_triggers=['do1'],
# #                      xs_dets=[xs],
# #                      an_dets=[pba1.adc3, pba1.adc4, pba1.adc5, pba1.adc6, pba1.adc7, pba1.adc8],
# #                      motor=mono1)
#
#
# def xs_plan():
#     yield from bps.mv(xsflyer_pb2.motor, 'prepare')
#     yield from bp.fly([xsflyer_pb2])
