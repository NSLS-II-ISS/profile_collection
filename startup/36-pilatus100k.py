print(ttime.ctime() + " >>>> " + __file__)

import uuid
from ophyd import (
    Component as Cpt,
    Device,
    EpicsSignal,
    ROIPlugin,
    OverlayPlugin,
    Signal,
    HDF5Plugin,
)
from ophyd.areadetector.plugins import ROIStatPlugin_V34, ImagePlugin_V33

from ophyd.areadetector.filestore_mixins import (
    FileStoreTIFFIterativeWrite,
    FileStoreHDF5IterativeWrite,
)
from ophyd.areadetector.cam import PilatusDetectorCam
from ophyd.areadetector.detectors import PilatusDetector
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector import TIFFPlugin
from ophyd.sim import NullStatus
from nslsii.ad33 import StatsPluginV33
from nslsii.ad33 import SingleTriggerV33
from ophyd.areadetector.base import DDC_SignalWithRBV, DDC_EpicsSignalRO
import itertools
from collections import deque, OrderedDict
from ophyd.areadetector.plugins import ImagePlugin_V33


class PilatusDetectorCamV33(PilatusDetectorCam):
    """This is used to update the Pilatus to AD33."""

    file_path = Cpt(SignalWithRBV, "FilePath", string=True)
    file_name = Cpt(SignalWithRBV, "FileName", string=True)
    file_template = Cpt(SignalWithRBV, "FileName", string=True)
    file_number = Cpt(SignalWithRBV, "FileNumber")
    file_auto_increment = Cpt(SignalWithRBV, "AutoIncrement")
    set_energy = Cpt(SignalWithRBV, "Energy")

    wait_for_plugins = Cpt(EpicsSignal, "WaitForPlugins", string=True, kind="config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update(
            {
                "wait_for_plugins": "Yes",
                "file_auto_increment": "Yes",
                "file_number": 0,
            }
        )

    def ensure_nonblocking(self):
        self.stage_sigs["wait_for_plugins"] = "Yes"
        for c in self.parent.component_names:
            cpt = getattr(self.parent, c)
            if cpt is self:
                continue
            if hasattr(cpt, "ensure_nonblocking"):
                cpt.ensure_nonblocking()


class PilatusDetectorCam(PilatusDetector):
    cam = Cpt(PilatusDetectorCamV33, "cam1:")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cam.ensure_nonblocking()


class HDF5PluginWithFileStore(HDF5Plugin, FileStoreHDF5IterativeWrite):
    """Add this as a component to detectors that write HDF5s."""

    def get_frames_per_point(self):
        return 1
        # if not self.parent.is_flying:
        #     return self.parent.cam.num_images.get()
        # else:
        #     return 1


# Making ROIStatPlugin that is actually useful
class ISSROIStatPlugin(ROIStatPlugin_V34):
    for i in range(1, 5):
        _attr = f"roi{i}"
        _attr_min_x = f"min_x"
        _attr_min_y = f"min_y"
        _pv_min_x = f"{i}:MinX"
        _pv_min_y = f"{i}:MinY"
        _attr_size_x = f"size_x"
        _attr_size_y = f"size_y"
        _pv_size_x = f"{i}:SizeX"
        _pv_size_y = f"{i}:SizeY"

        # this does work:
        vars()[_attr] = DDC_SignalWithRBV(
            (_attr_min_x, _pv_min_x),
            (_attr_min_y, _pv_min_y),
            (_attr_size_x, _pv_size_x),
            (_attr_size_y, _pv_size_y),
            doc="ROI position and size in XY",
            kind="normal",
        )

        _attr = f"stats{i}"
        _attr_total = f"total"
        _pv_total = f"{i}:Total_RBV"
        _attr_max = f"max_value"
        _pv_max = f"{i}:MaxValue_RBV"
        vars()[_attr] = DDC_EpicsSignalRO(
            (_attr_total, _pv_total),
            (_attr_max, _pv_max),
            doc="ROI stats",
            kind="normal",
        )


class PilatusBase(SingleTriggerV33, PilatusDetectorCam):
    roi1 = Cpt(ROIPlugin, "ROI1:")
    roi2 = Cpt(ROIPlugin, "ROI2:")
    roi3 = Cpt(ROIPlugin, "ROI3:")
    roi4 = Cpt(ROIPlugin, "ROI4:")

    stats1 = Cpt(StatsPluginV33, "Stats1:", read_attrs=["total", "max_value"])
    stats2 = Cpt(StatsPluginV33, "Stats2:", read_attrs=["total"])
    stats3 = Cpt(StatsPluginV33, "Stats3:", read_attrs=["total"])
    stats4 = Cpt(StatsPluginV33, "Stats4:", read_attrs=["total"])
    image = Cpt(ImagePlugin_V33, "image1:")

    roistat = Cpt(ISSROIStatPlugin, "ROIStat1:")
    # roistat = Cpt(ROIStatPlugin_V34, 'ROIStat1:')

    over1 = Cpt(OverlayPlugin, "Over1:")

    polygon_roi_path = f"{ROOT_PATH_SHARED}/settings/json/pilatus_polygon_roi.json"

    def __init__(self, *args, readout=0.0024, **kwargs):
        super().__init__(*args, **kwargs)
        self.readout = readout  # seconds; for old Pilatus it is 0.0023s; for the new one it is 0.00095s
        self.hint_channels()
        # self._is_flying = False

    def hint_channels(self):
        self.stats1.kind = "hinted"
        self.stats1.total.kind = "hinted"
        self.stats2.kind = "hinted"
        self.stats2.total.kind = "hinted"
        self.stats3.kind = "hinted"
        self.stats3.total.kind = "hinted"
        self.stats4.kind = "hinted"
        self.stats4.total.kind = "hinted"

    def read_exposure_time(self):
        return self.cam.acquire_period.get()

    def set_exposure_time(self, exp_t):
        self.cam.acquire_time.put(np.floor((exp_t - self.readout) * 10000) / 10000)
        self.cam.acquire_period.put(exp_t)

    def set_num_images(self, num):
        self.cam.num_images.put(num)
        self.hdf5.num_capture.put(num)

    # def det_next_file(self, n):
    #     self.cam.file_number.put(n)

    def enforce_roi_match_between_plugins(self):
        for i in range(1, 5):
            _attr = getattr(self, f"roi{i}")
            _x = _attr.min_xyz.min_x.get()
            _y = _attr.min_xyz.min_y.get()
            _xs = _attr.size.x.get()
            _ys = _attr.size.y.get()
            _attr2 = getattr(self.roistat, f"roi{i}")
            _attr2.min_x.set(_x)
            _attr2.min_y.set(_y)
            _attr2.size_x.set(_xs)
            _attr2.size_y.set(_ys)

    def stage(self):
        self.enforce_roi_match_between_plugins()
        self.cam.file_name.put(f"{str(uuid.uuid4())[:8]}_")
        return super().stage()

    def get_roi_coords(self, roi_num):
        x = getattr(self, f"roi{roi_num}").min_xyz.min_x.get()
        y = getattr(self, f"roi{roi_num}").min_xyz.min_y.get()
        dx = getattr(self, f"roi{roi_num}").size.x.get()
        dy = getattr(self, f"roi{roi_num}").size.y.get()
        return x, y, dx, dy

    @property
    def roi_metadata(self):
        md = {}
        key_table = {"x": "min_x", "dx": "size_x", "y": "min_y", "dy": "size_y"}
        for i in range(1, 5):
            k_roi = f"roi{i}"
            roi_md = {}
            for k_md, k_epics in key_table.items():
                roi_md[k_md] = getattr(self.roistat, f"{k_roi}.{k_epics}").value
            md[k_roi] = roi_md
        return md

    def read_config_metadata(self):
        md = {}
        md["device_name"] = self.name
        md["threshold_energy"] = self.cam.threshold_energy.get()
        md["set_energy"] = self.cam.set_energy.get()
        md["gain_setting"] = self.cam.gain.get()
        md["gain_str"] = self.cam.gain_menu.get(as_string=True)
        md["roi"] = self.roi_metadata

        with open(self.polygon_roi_path, "r") as f:
            md["roi_polygon"] = json.loads(f.read())

        return md

    # @property
    # def is_flying(self):
    #     return self._is_flying
    #
    # @is_flying.setter
    # def is_flying(self, is_flying):
    #     self._is_flying = is_flying


class PilatusHDF5(PilatusBase):
    hdf5 = Cpt(
        HDF5PluginWithFileStore,
        suffix="HDF1:",
        root="/",
        write_path_template=f"{ROOT_PATH}/{RAW_PATH}/pil100k/%Y/%m/%d",
    )  # ,
    # write_path_template=f'/nsls2/xf08id/data/pil100k/%Y/%m/%d')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_primary_roi(1)
        # self.set_primary_roi(2)
        # self.set_primary_roi(3)
        # self.set_primary_roi(4)

    def set_primary_roi(self, num):
        st = f"stats{num}"
        # self.read_attrs = [st, 'tiff']
        self.read_attrs = [st, "hdf5"]
        getattr(self, st).kind = "hinted"


class PilatusStreamHDF5(PilatusHDF5):

    def __init__(self, *args, ext_trigger_device=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext_trigger_device = ext_trigger_device
        self._asset_docs_cache = deque()
        self._datum_counter = None

        self.datum_keys = [{"data_type": "image", "roi_num": 0}]
        for i in range(4):
            self.datum_keys.append({"data_type": "roi", "roi_num": i + 1})

    def format_datum_key(self, input_dict):
        name_short = self.name.split("_")[0]  # to remove "stream" part if needed
        # output =f'pil100k_{input_dict["data_type"]}'
        output = f'{name_short}_{input_dict["data_type"]}'
        if input_dict["data_type"] == "roi":
            output += f'{input_dict["roi_num"]:01d}'
        return output

    def prepare_to_fly(self, traj_duration):
        self.acq_rate = self.ext_trigger_device.freq.get()
        self.num_points = int(self.acq_rate * (traj_duration + 2))
        self.ext_trigger_device.prepare_to_fly(traj_duration)

    # TODO: change blocking to NO upon staging of this class !!!
    def stage(self):
        staged_list = super().stage()
        self._datum_counter = itertools.count()
        # self.is_flying = True
        self.hdf5._asset_docs_cache[0][1][
            "spec"
        ] = "PIL100k_HDF5"  # This is to make the files to go to correct handler
        self.hdf5._asset_docs_cache[0][1][
            "resource_kwargs"
        ] = {}  # This is to make the files to go to correct handler

        self.set_num_images(self.num_points)
        # for i in range(10):
        #     if self.cam.num_images.get() != self.num_points:
        #         self.set_num_images(self.num_points)
        #         ttime.sleep(0.1)
        #     else:
        #         break
        self.set_exposure_time(1 / self.acq_rate)
        self.cam.array_counter.put(0)
        self.cam.trigger_mode.put(2)
        self.cam.image_mode.put(1)

        # self.hdf5.blocking_callbacks.put(1)

        staged_list += self.ext_trigger_device.stage()
        return staged_list

    def unstage(self):
        self._datum_counter = None

        unstaged_list = super().unstage()
        self.cam.trigger_mode.put(0)
        self.cam.image_mode.put(0)
        self.set_num_images(1)
        self.set_exposure_time(1)
        # self.hdf5.blocking_callbacks.put(0)
        unstaged_list += self.ext_trigger_device.unstage()
        return unstaged_list

    def kickoff(self):
        self.cam.acquire.set(1).wait()
        return self.ext_trigger_device.kickoff()

    def complete(self):
        print_to_gui(f"Pilatus100k complete is starting...", add_timestamp=True)
        acquire_status = self.cam.acquire.set(0)
        capture_status = self.hdf5.capture.set(0)
        (acquire_status and capture_status).wait()

        ext_trigger_status = self.ext_trigger_device.complete()
        for resource in self.hdf5._asset_docs_cache:
            self._asset_docs_cache.append(("resource", resource[1]))
        self._datum_ids = []
        # num_frames = self.hdf5.num_captured.get()
        _resource_uid = self.hdf5._resource_uid
        self._datum_ids = {}

        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            datum_id = f"{_resource_uid}/{datum_key}"
            self._datum_ids[datum_key] = datum_id
            doc = {
                "resource": _resource_uid,
                "datum_id": datum_id,
                "datum_kwargs": datum_key_dict,
            }
            self._asset_docs_cache.append(("datum", doc))

        # datum_kwargs = [{'frame': i} for i in range(num_frames)]
        # doc = compose_bulk_datum(resource_uid=_resource_uid,
        #                          counter=self._datum_counter,
        #                          datum_kwargs=datum_kwargs)
        # self._asset_docs_cache.append(('bulk_datum', doc))
        # _datum_id_counter = itertools.count()
        # for frame_num in range(num_frames):
        #     datum_id = '{}/{}'.format(_resource_uid, next(_datum_id_counter))
        #     self._datum_ids.append(datum_id)

        print_to_gui(f"Pilatus100k complete is done.", add_timestamp=True)
        return NullStatus() and ext_trigger_status

    def collect(self):
        print_to_gui(f"Pilatus100k collect is starting...", add_timestamp=True)
        ts = ttime.time()
        yield {
            "data": self._datum_ids,
            "timestamps": {
                self.format_datum_key(key_dict): ts for key_dict in self.datum_keys
            },
            "time": ts,  # TODO: use the proper timestamps from the mono start and stop times
            "filled": {
                self.format_datum_key(key_dict): False for key_dict in self.datum_keys
            },
        }

        # num_frames = len(self._datum_ids)
        #
        # for frame_num in range(num_frames):
        #     datum_id = self._datum_ids[frame_num]
        #     data = {self.name: datum_id}
        #
        #     ts = ttime.time()
        #
        #     yield {'data': data,
        #            'timestamps': {key: ts for key in data},
        #            'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
        #            'filled': {key: False for key in data}}
        print_to_gui(f"Pilatus100k collect is complete", add_timestamp=True)
        yield from self.ext_trigger_device.collect()

    def describe_collect(self):
        pil100k_spectra_dicts = {}
        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            if datum_key_dict["data_type"] == "image":
                value = {
                    "source": "PIL100k_HDF5",
                    "dtype": "array",
                    "dtype_numpy": "<i4",
                    # 'shape': [self.cam.num_images.get(),
                    "shape": [
                        self.hdf5.num_captured.get(),
                        self.hdf5.array_size.height.get(),
                        self.hdf5.array_size.width.get(),
                    ],
                    "dims": ["frames", "row", "col"],
                    "external": "FILESTORE:",
                }
            elif datum_key_dict["data_type"] == "roi":
                value = {
                    "source": "PIL100k_HDF5",
                    "dtype": "array",
                    "dtype_numpy": "<f8",
                    # 'shape': [self.cam.num_images.get()],
                    "shape": [self.hdf5.num_captured.get()],
                    "dims": ["frames"],
                    "external": "FILESTORE:",
                }
            else:
                raise KeyError(f'data_type={datum_key_dict["data_type"]} not supported')
            pil100k_spectra_dicts[datum_key] = value

        return_dict_pil100k = {self.name: pil100k_spectra_dicts}

        # return_dict_pil100k = {self.name:
        #                    {f'{self.name}': {'source': 'PIL100k_HDF5',
        #                                      'dtype': 'array',
        #                                      'shape': [self.cam.num_images.get(),
        #                                                #self.settings.array_counter.get()
        #                                                self.hdf5.array_size.height.get(),
        #                                                self.hdf5.array_size.width.get()],
        #                                     'filename': f'{self.hdf5.full_file_name.get()}',
        #                                      'external': 'FILESTORE:'}}}
        #
        return_dict_trig = self.ext_trigger_device.describe_collect()
        return {**return_dict_pil100k, **return_dict_trig}

    def describe(self):
        # Add better detector metadata to avoid Tiled server side conversion.
        res = super().describe()
        key = "pil_100k2"
        cam_dtype = self.parent.cam.data_type.get(as_string=True)
        # Dynamically set Dtype
        type_map = {
            "Int32": "<i4",
            "UInt8": "|u1",
            "UInt16": "<u2",
            "Float32": "<f4",
            "Float64": "<f8",
        }
        if cam_dtype in type_map:
            res[key].setdefault("dtype_str", type_map[cam_dtype])
        else:
            res[key].setdefault("dtype_numpy", "<i4")
        return res

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item
        yield from self.ext_trigger_device.collect_asset_docs()

    def read_config_metadata(self):
        md = super().read_config_metadata()
        freq = self.ext_trigger_device.freq.get()
        dc = self.ext_trigger_device.duty_cycle.get()
        md["frame_rate"] = freq
        md["duty_cycle"] = dc
        md["acquire_time"] = 1 / freq
        md["exposure_time"] = 1 / freq * dc / 100
        return md

    # def set_expected_number_of_points(self, acq_rate, traj_time):


pil100k = PilatusHDF5("XF:08IDB-ES{Det:PIL1}:", name="pil100k")  # , detector_id="SAXS")
pil100k2 = PilatusHDF5("XF:08IDB-ES{Det:PIL2}", name="pil100k2", readout=0.001)
pil100k_stream = PilatusStreamHDF5(
    "XF:08IDB-ES{Det:PIL1}:",
    name="pil100k_stream",
    ext_trigger_device=apb_trigger_pil100k,
)
pil100k2_stream = PilatusStreamHDF5(
    "XF:08IDB-ES{Det:PIL2}",
    name="pil100k2_stream",
    ext_trigger_device=apb_trigger_pil100k2,
    readout=0.001,
)

pil100k.set_primary_roi(1)
pil100k.stats1.kind = "hinted"
pil100k.stats2.kind = "hinted"
pil100k.stats3.kind = "hinted"
pil100k.stats4.kind = "hinted"


pil100k2.set_primary_roi(1)
pil100k2.stats1.kind = "hinted"
pil100k2.stats2.kind = "hinted"
pil100k2.stats3.kind = "hinted"
pil100k2.stats4.kind = "hinted"


# pil100k.cam.ensure_nonblocking()


def take_pil100k_test_image_plan():
    yield from shutter.open_plan()
    pil100k2.cam.acquire.set(1)
    yield from bps.sleep(pil100k2.cam.acquire_time.value + 0.1)
    yield from shutter.close_plan()


def pil_count(acq_time: int = 1, num_frames: int = 1, open_shutter: bool = True):
    if open_shutter:
        yield from shutter.open_plan()
    yield from bp.count([pil100k, apb_ave])
    if open_shutter:
        yield from shutter.close_plan()


def pil2_count(acq_time: int = 1, num_frames: int = 1, open_shutter: bool = True):
    if open_shutter:
        yield from shutter.open_plan()
    pil100k2.cam.acquire_time.put(acq_time)
    pil100k2.cam.acquire_period.put(acq_time + 0.1)
    yield from bp.count([pil100k2, apb_ave])
    if open_shutter:
        yield from shutter.close_plan()
    pil100k2.cam.acquire_time.put(1)
    pil100k2.cam.acquire_period.put(1 + 0.1)


from itertools import product
import pandas as pd
from databroker.assets.handlers import (
    HandlerBase,
    PilatusCBFHandler,
    AreaDetectorTiffHandler,
    Xspress3HDF5Handler,
)


# PIL100k_HDF_DATA_KEY = 'entry/instrument/NDAttributes'
# class ISSPilatusHDF5Handler(Xspress3HDF5Handler): # Denis: I used Xspress3HDF5Handler as basis since it has all the basic functionality and I more or less understand how it works
#     specs = {'PIL100k_HDF5'} | HandlerBase.specs
#     HANDLER_NAME = 'PIL100k_HDF5'
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, key=PIL100k_HDF_DATA_KEY, **kwargs)
#         self._roi_data = None
#         self.hdfrois = [f'ROI{i + 1}' for i in range(4)]
#         self.chanrois = [f'pil100k_ROI{i + 1}' for i in range(4)]
#
#
#     def _get_dataset(self):
#         if self._dataset is not None:
#             return
#
#         _data_columns = [self._file[self._key + f'/_{chanroi}Total'][()] for chanroi in self.hdfrois]
#         self._roi_data = np.vstack(_data_columns).T
#         self._image_data = self._file['entry/data/data'][()]
#         # self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)
#         # self._dataset = data_columns
#
#     def __call__(self, data_type:str='image', roi_num=None):
#         # print(f'{ttime.ctime()} XS dataset retrieving starting...')
#         self._get_dataset()
#
#         if data_type=='image':
#             # print(output.shape, output.squeeze().shape)
#             return self._image_data
#
#         elif data_type=='roi':
#             return self._roi_data[:, roi_num - 1].squeeze()
#
#         else:
#             raise KeyError(f'data_type={data_type} not supported')

# def __call__(self, *args, frame=None,  **kwargs):
#     self._get_dataset()
#     return_dict = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
#     # return_dict['image'] = self._image_data[frame, :, :].squeeze()
#     return return_dict
#     # return self._roi_data


from xas.handlers import ISSPilatusHDF5Handler

db.reg.register_handler("PIL100k_HDF5", ISSPilatusHDF5Handler, overwrite=True)
