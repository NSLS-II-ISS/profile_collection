print(ttime.ctime() + ' >>>> ' + __file__)
import bluesky as bs
import bluesky.plans as bp
import time as ttime
from subprocess import call
import os
from isstools.conversions import xray
import signal
from periodictable import elements

from ophyd.device import Kind
import time


def general_scan_plan(detectors, motor, rel_start, rel_stop, num, exposure_time):

    for detector in detectors:
        detector.set_exposure_time(exposure_time)

    plan = bp.relative_scan(detectors, motor, rel_start, rel_stop, num)
    
    if hasattr(detectors[0], 'kickoff'):
        plan = bpp.fly_during_wrapper(plan, detectors)
    yield from shutter.open_plan()
    yield from plan
    yield from shutter.close_plan()

def general_scan(detectors=[], motor=None, rel_start=None, rel_stop=None, num_steps=1, exposure_time=1, liveplot_kwargs={}):

    # sys.stdout = kwargs.pop('stdout', sys.stdout)
    #print(f'Dets {detectors}')
    #print(f'Motors {motor}')
    motor_device = get_motor_device(motor)
    detector_devices = get_detector_device_list(detectors, flying=False)
    # print('[General Scan] Starting scan...')
    print_to_gui('[General Scan] Starting scan...')
    yield from (general_scan_plan(detector_devices, motor_device, rel_start, rel_stop, int(num_steps), exposure_time))
    # print('[General Scan] Done!')
    print_to_gui('[General Scan] Done!')


def tuning_scan(motor=None, detector=None, scan_range=None, scan_step=None, n_tries = 3, liveplot_kwargs=None):
    # sys.stdout = kwargs.pop('stdout', sys.stdout)
    print_to_gui(f'Scanning motor {motor}', tag='Tune Beamline')

    if type(motor) == list:
        motor = get_motor_device(motor[0], based_on='object_name')
        motor2 = get_motor_device(motor[1], based_on='object_name')
    else:
        motor = get_motor_device(motor, based_on='object_name')
        motor2 = None
    detector_device_list = get_detector_device_list([detector], flying=False)
    detector_device = detector_device_list[0]

    channel = detector_device.hints['fields'][0]
    for jj in range(n_tries):
        motor_init_position = motor.read()[motor.name]['value']
        min_limit = motor_init_position - scan_range / 2
        max_limit = motor_init_position + scan_range / 2 + scan_step / 2
        scan_positions = np.arange(min_limit, max_limit, scan_step)
        if motor2:
            motor2_init_position = motor2.read()[motor2.name]['value']
            min_limit = motor2_init_position - scan_range / 2
            max_limit = motor2_init_position + scan_range / 2 + scan_step / 2
            scan_positions2 = np.arange(min_limit, max_limit, scan_step)
        scan_range = (scan_positions[-1] - scan_positions[0])
        min_threshold = scan_positions[0] + scan_range / 10
        max_threshold = scan_positions[-1] - scan_range / 10
        if motor2:
            plan = bp.list_scan([detector_device], motor, scan_positions.tolist(),
                                            motor2, scan_positions2.tolist())
        else:
            plan = bp.list_scan([detector_device], motor, scan_positions.tolist())
        if hasattr(detector_device, 'kickoff'):
            plan = bpp.fly_during_wrapper(plan, [detector_device])
        uid = (yield from plan)
        if uid:
            hdr = db[uid]
            if detector_device.polarity == 'pos':
                idx = getattr(hdr.table()[channel], 'idxmax')()
            elif detector_device.polarity == 'neg':
                idx = getattr(hdr.table()[channel], 'idxmin')()
            motor_pos = hdr.table()[motor.name][idx]
            print_to_gui(f'New motor position {motor_pos}')

            if motor_pos < min_threshold:
                yield from bps.mv(motor,min_limit)
                if jj+1 < n_tries:
                    print_to_gui(f' Starting {jj+2} try')
            elif max_threshold < motor_pos:
                print_to_gui('max')
                if jj+1 < n_tries:
                    print_to_gui(f' Starting {jj+2} try')
                yield from bps.mv(motor, max_limit)
            else:
                yield from bps.mv(motor, motor_pos)
                break

def ramp_motor_scan(motor=None, detector_channels=None, range=0,  sleep = 0.2, velocity = None, return_motor_to_initial_position=False, start_acquiring_plan=None):
    yield from bps.mvr(motor, -range / 2)
    yield from bps.sleep(sleep)
    if velocity is not None:
        old_motor_velocity = motor.velocity.get()
        yield from bps.mv(motor.velocity, velocity)
    @return_NullStatus_decorator
    def _move_plan():
        yield from bps.mvr(motor, range)
        yield from bps.sleep(sleep)
    ramp_plan = ramp_plan_with_multiple_monitors(_move_plan(), [motor] + detector_channels, bps.null)
    if start_acquiring_plan is not None:
        yield from start_acquiring_plan
    yield from ramp_plan
    if velocity is not None:
        yield from bps.mv(motor.velocity, old_motor_velocity)
    if return_motor_to_initial_position:
        yield from bps.mvr(motor, -range / 2)



def quick_tuning_scan(motor=None, detector=None, channel=None, scan_range=None, velocity=None, n_tries = 3, plot_func=None, liveplot_kwargs=None):
    motor_device = get_motor_device(motor, based_on='object_name')
    detector_device = get_detector_device_list([detector], flying=False)[0]
    detector_channel = get_detector_channel(detector, channel)

    print_to_gui(f'Quick scanning motor {motor}', tag='Tune Beamline')
    for jj in range(n_tries):
        motor_init_position = motor_device.position
        min_limit = motor_init_position - scan_range / 2
        max_limit = motor_init_position + scan_range / 2
        min_threshold = min_limit + scan_range / 10
        max_threshold = max_limit - scan_range / 10
        plan = ramp_motor_scan(motor_device, [detector_channel], scan_range, velocity=velocity )
        (yield from plan)
        # hdr = db[-1]
        motor_pos = find_optimum_motor_pos(db, -1, motor=motor_device.name, channel=detector_channel.name, polarity=detector_device.polarity, plot_func=plot_func)
        if motor_pos < min_threshold:
            yield from bps.mv(motor_device, min_limit)
            print_to_gui('Optimal position is below the minimum in range')
            if jj+1 < n_tries:
                print_to_gui(f' Starting {jj+2} try')
        elif max_threshold < motor_pos:
            print_to_gui('Optimal position is above the maximum in range')
            if jj+1 < n_tries:
                print_to_gui(f' Starting {jj+2} try')
            yield from bps.mv(motor_device, max_limit)
        else:
            print_to_gui(f'The {motor} position was optimized: position={motor_pos:.3f}')
            yield from bps.mv(motor_device, motor_pos)
            break



def prepare_detectors_for_exposure_plan(detectors, n_exposures=1):
    for det in detectors:
        if det.name == 'apb_ave':
            yield from bps.abs_set(apb_ave.divide, 373, wait=True)
        if det.name == 'xs':
            yield from bps.mv(det.total_points, n_exposures)
        # if det.name == 'pil100k':
        #     yield from bps.mv(det.total_points, n_exposures)


def set_detector_exposure_time_plan(detectors, exposure_time):
    for det in detectors:
        if det.name == 'apb_ave':
            # samples = 250*(np.ceil(exposure_time*1005/250)) #hn I forget what that does... let's look into the new PB OPI
            samples = np.round(exposure_time * 1005, -1)  # Denis: attempt to improve this?
            yield from bps.abs_set(det.sample_len, samples, wait=True)
            yield from bps.abs_set(det.wf_len, samples, wait=True)
        elif det.name == 'pil100k':
            yield from bps.mv(det.cam.acquire_time, exposure_time)
        elif det.name == 'xs':
            yield from bps.mv(det.settings.acquire_time, exposure_time)


def get_n_exposures_plan_md(name, comment, energy, detectors_dict, n_exposures, dwell_time, metadata):
        fn = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['proposal']}/{name}.dat"
        fn = validate_file_exists(fn)

        md_general = get_general_md()
        md_detectors = get_detector_md(detectors_dict)
        md_scan = {'experiment': 'collect_n_exposures',
                   'interp_filename': fn,
                   'name': name,
                   'comment': comment,
                   'hhm_energy' : energy,
                   'detectors': md_detectors,
                   'n_exposures' : n_exposures,
                   'dwell_time' : dwell_time,
                   'plot_hint': '$5/$1'}

        return {**md_general, **md_scan, **metadata}


def general_n_exposures(detectors, n_exposures, dwell_time, md):
    yield from prepare_detectors_for_exposure_plan(detectors, n_exposures=n_exposures)
    yield from set_detector_exposure_time_plan(detectors, dwell_time)
    yield from shutter.open_plan()
    yield from bp.count(detectors, n_exposures, md=md)
    yield from shutter.close_plan()


def collect_n_exposures_plan(name : str = '', comment : str = '',
                             n_exposures : int = 1, dwell_time : float = 1.0,
                             mono_energy : float = 7112,
                             detectors : list = [], mono_angle_offset=None, metadata={}):

    if mono_angle_offset is not None: hhm.set_new_angle_offset(mono_angle_offset)
    default_detectors = [apb_ave, hhm_encoder]
    aux_detectors = get_detector_device_list(detectors, flying=False)
    all_detectors = default_detectors + aux_detectors
    detectors_dict = {k: {'device': v} for k, v in zip(detectors, aux_detectors)}
    md = get_n_exposures_plan_md(name, comment, mono_energy, detectors_dict, n_exposures, dwell_time, metadata)

    yield from bps.mv(hhm.energy, mono_energy)
    yield from general_n_exposures(all_detectors, n_exposures, dwell_time, md)







