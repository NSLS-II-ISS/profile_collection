print(ttime.ctime() + ' >>>> ' + __file__)
import pandas as pd


def print_message_plan(msg='', tag='', add_timestamp=False, ntabs=0):
    print_to_gui(msg, tag=tag, add_timestamp=add_timestamp, ntabs=ntabs)
    yield from bps.null()

def sleep_plan(delay : float = 1.0):
    yield from bps.sleep(float(delay))

def move_bpm_fm_plan(action = 'insert'):
    yield from bps.mv(bpm_fm, action)

def put_bpm_fm_to_continuous_mode():
    # if hasattr(detector, 'image_mode'):
    yield from bps.mv(getattr(bpm_fm, 'image_mode'), 2)
    yield from bps.mv(getattr(bpm_fm, 'acquire'), 1)

def set_bpm_es_exposure_time(value : float = 0.2):
    yield from bps.mv(bpm_es.exp_time, value)



def set_hhm_feedback_plan(state=0, update_center=False):
    if update_center:
        hhm_feedback.update_center()
        yield from sleep_plan(delay=0.5)
    yield from bps.mv(hhm.fb_status, state)

def move_motor_plan(motor_attr='', based_on='description', position=None):
    motor_device = get_motor_device(motor_attr, based_on=based_on)
    yield from bps.mv(motor_device, position, wait=True)

# def move_mono_energy(energy : float = -1):
#     yield from move_motor_plan(motor_attr=hhm.energy.name, based_on='object_name', position=energy)

def move_mono_pitch(value: float = 680):
    yield from set_hhm_feedback_plan(0)
    yield from move_motor_plan(motor_attr=hhm.pitch.name, based_on='object_name', position=value)
    yield from set_hhm_feedback_plan(1)






# current_energy = 6492.001
# energy = 6493
# energy_arr = np.linspace(current_energy, energy, int(np.abs(energy - current_energy)) + 2)[1:]
# for _energy in energy_arr:
#     print(_energy)


def _bpm_es_exposure(energy):
    for prepare_range in bl_prepare_energy_ranges:
        if (energy >= prepare_range['energy_start']) and (energy <= prepare_range['energy_end']):
            return prepare_range['ES BPM exposure']



def move_mono_energy_with_fb(energy : float=-1, step : float=1000, delay : float=0.2, beampos_tol : float =25):
    target_beam_y_pos = hhm_feedback.center
    current_energy = hhm.energy.position

    nsteps = int(np.ceil(np.abs((energy - current_energy) / step)) + 1)
    energy_list = np.linspace(current_energy, energy, nsteps).tolist()

    for each_step in energy_list:
        yield from bps.mv(bpm_es.exp_time, _bpm_es_exposure(each_step))
        yield from bps.mv(hhm.energy, each_step)
        while True:
            current_beam_y_pos, err_msg = hhm_feedback.find_beam_position()
            # print_to_gui(f'{current_beam_y_pos}, {target_beam_y_pos}', tag='DEBUG')
            if err_msg == '':
                if np.abs(current_beam_y_pos - target_beam_y_pos) > beampos_tol:
                    yield from bps.sleep(delay)
                else:
                    break
            else:
                break






def move_mono_energy(energy : float=-1, with_feedback : bool=True, step : float=1000, delay : float=0.2, beampos_tol : float=25):

    if not with_feedback:
        yield from bps.mv(hhm.energy, energy)

    yield from move_mono_energy_with_fb(energy=energy, step=step, delay=delay, beampos_tol=beampos_tol)


# 12-22-2022 Two-duck coding session

# def ramp_motor_scan(motor, range, detectors: list, sleep = 0.2, velocity = None):
#     if velocity is not None:
#         old_motor_velocity = motor.velocity.get()
#         yield from bps.mv(motor.velocity, velocity)
#     yield from bps.mvr(motor, -range / 2)
#     yield from bps.sleep(sleep)
#     @return_NullStatus_decorator
#     def _move_pitch_plan():
#         yield from bps.mvr(motor, range)
#         yield from bps.sleep(sleep)
#     ramp_plan = ramp_plan_with_multiple_monitors(_move_pitch_plan(), [motor] + detectors, bps.null)
#     yield from ramp_plan
#     if velocity is not None:
#         yield from bps.mv(motor.velocity, old_motor_velocity)








# def quick_pitch_scan(pitch_range=0.5, pitch_speed=0.2):
#     yield from bps.mvr(hhm.pitch, -pitch_range / 2, wait=True)
#     @return_NullStatus_decorator
#     def _move_pitch_plan():
#         yield from bps.mvr(hhm.pitch, pitch_range, wait=True)
#
#     yield from bps.mv(hhm.pitch.velocity, pitch_speed)
#     ramp_plan = ramp_plan_with_multiple_monitors(_move_pitch_plan(), [hhm.pitch, apb_ave.ch1], bps.null)
#     yield from ramp_plan
#     yield from bps.mv(hhm.pitch.velocity, 60)
#
#
# def quick_pitch_optimization(pitch_range=0.5, pitch_speed=0.2, n_tries=3):
#     yield from set_hhm_feedback_plan(0)
#     current_pitch_value = hhm.pitch.position
#
#     for i in range(n_tries):
#
#         print_to_gui(f'Starting attempt #{i + 1}', tag='Pitch Scan')
#
#         yield from quick_pitch_scan(pitch_range=pitch_range, pitch_speed=pitch_speed)
#
#         new_pitch_pos = find_optimum_pitch_pos(db, -1)
#         print_to_gui(f'New pitch position: {new_pitch_pos}', tag='Pitch Scan')
#         yield from bps.mv(hhm.pitch, new_pitch_pos, wait=True)
#
#         min_threshold = current_pitch_value - pitch_range / 2 + pitch_range / 10
#         max_threshold = current_pitch_value + pitch_range / 2 - pitch_range / 10
#
#         if (new_pitch_pos > min_threshold) and (new_pitch_pos < max_threshold):
#             break
#         else:
#             if (i+1) > n_tries:
#                 print_to_gui(f'Exceeded number of attempts. Adjust pitch manually.', tag='Pitch Scan')
#
#     yield from set_hhm_feedback_plan(1, update_center=True)
# def plot_monitor_scan(db, uid):
#     hdr = db[uid]
#     # df = {}
#     plt.figure()
#     for stream_name in hdr.stream_names:
#         t = hdr.table(stream_name=stream_name)
#         column_name = stream_name.replace('_monitor', '')
#         plt.plot(t.time, t[column_name])


def process_monitor_scan(db, uid, det_for_time_base=None):
    hdr = db[uid]
    df = {}
    if det_for_time_base is not None:
        for stream_name in hdr.stream_names:
            if stream_name.startswith(det_for_time_base):
                print(f'time base will be determined based on {stream_name}')
                t = hdr.table(stream_name=stream_name)
                df['time'] = t['time'].astype(dtype=int).values * 1e-9
                break

    for stream_name in hdr.stream_names:
        t = hdr.table(stream_name=stream_name)
        this_time = t['time'].astype(dtype=int).values * 1e-9
        if not 'time' in df.keys():
            df['time'] = this_time

        column_name = stream_name.replace('_monitor', '')
        this_data = t[column_name].values
        df[column_name] = np.interp(df['time'], this_time, this_data)

    return pd.DataFrame(df)

def find_optimum_motor_pos(db, uid, motor='hhm_pitch', channel='apb_ch1', polarity='neg', plot_func=None):
    df = process_monitor_scan(db, uid)
    if polarity == 'neg':
        idx = df[channel].idxmin()
    elif polarity == 'pos':
        idx = df[channel].idxmax()
    else:
        raise ValueError

    optimum_value = df[motor][idx]

    if plot_func is not None:
        plot_func(df[motor].values, df[channel].values, optimum_value,
                  positions_axis_label=motor, values_axis_label=channel)

    return optimum_value


# plt.figure(1, clear=True)
# plt.plot(df['hhm_pitch'], df['apb_ave_ch1'])

# def bla():
#     yield
#     return 'c'
#
# def bla2():
#     bb = bla()
#     st = (yield from bb)
#     print('NOW', st)
#
# gg = bla2()
# hh = list(gg)