
import time as ttime
import sys
import numpy as np
from xas.xray import energy2angle
from xas.energy_calibration import get_energy_offset
# from xas.image_analysis import determine_beam_position_from_fb_image


def _compute_hhmy_value(energy):
    # tabulation is done using data collected on 2021-09-12 and 2021-09-13
    # data is stored in two files:
    # /nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation.json
    # /nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation_high_energies.json
    energy_tab = np.array([ 4800,  5000,  6000,  7000,  8000,  9000, 10000, 11000, 12000, 13000, 15000, 17500, 20000, 22500, 25000, 27500, 30000])
    hhmy_tab = np.array([9.71275, 9.62515, 9.3645 , 9.202  , 9.09365, 9.03125, 8.99405, 8.9373 , 8.9378 , 8.86945, 8.8442 , 8.68795, 8.70085, 8.62675, 8.65015, 8.55135, 8.55645])

    def get_matrix_from_energy(energy_in, offset=0):
        theta_deg = energy2angle(energy_in)
        V = 1 / np.cos(np.deg2rad(theta_deg - offset))
        A = np.vstack((V, energy_in, np.ones(V.size))).T
        return A

    def fit_hhmy(offset=0):
        A = get_matrix_from_energy(energy_tab, offset=offset)
        c, _, _, _ = np.linalg.lstsq(A, hhmy_tab, rcond=-1)
        return c

    coefs = fit_hhmy()
    a = get_matrix_from_energy(np.array(energy))
    return a @ coefs



bl_prepare_energy_ranges = [
        {
            'energy_start': 4500,
            'energy_end': 6000,
            'He_flow': 5,
            'N2_flow': 1,
            'IC_voltage': 1000,
            'HHRM': 0,
            'CM1':0,
            'Filterbox': 1,
            'ES BPM exposure': 0.05
        },
        {
            'energy_start': 6000,
            'energy_end': 10000,
            'He_flow': 5,
            'N2_flow': 3,
            'IC_voltage': 1700,
            'HHRM': 0,
            'CM1':0,
            'Filterbox': -69,
            'ES BPM exposure': 0.1
        },
        {
            'energy_start': 10000,
            'energy_end': 13000,
            'He_flow': 5,
            'N2_flow': 5,
            'IC_voltage': 1700,
            'HHRM': 0, # IS THIS SUPPOSED TO BE 80?
            'CM1':0,
            'Filterbox': -139,
            'ES BPM exposure': 0.2
        },
        {
            'energy_start': 13000,
            'energy_end': 17000,
            'He_flow': 5,
            'N2_flow': 5,
            'IC_voltage': 1700,
            'HHRM': 80,
            'CM1': 40,
            'Filterbox': -139,
            'ES BPM exposure': 0.2
        },
        {
            'energy_start': 17000,
            'energy_end': 25000,
            'He_flow': 2,
            'N2_flow': 5,
            'IC_voltage': 1900,
            'HHRM': 80,
            'CM1': 40,
            'Filterbox': -209,
            'ES BPM exposure': 0.8

        },
        {
            'energy_start': 25000,
            'energy_end': 35000,
            'He_flow': 2,
            'N2_flow': 5,
            'IC_voltage': 1900,
            'HHRM': 80,
            'CM1': 40,
            'Filterbox': -209,
            'ES BPM exposure': 0.8

        },
    ]

def prepare_beamline_plan(energy: int = -1, energy_ranges=bl_prepare_energy_ranges, move_cm_mirror = False, stdout = sys.stdout):

    BPM_exposure_setter = bpm_es.exp_time
    He_flow_setter = gas_he.flow
    N2_flow_setter = gas_n2.flow
    high_voltage_setters = [wps1.hv302, wps1.hv303, wps1.hv305]
    safe_high_voltage = 580
    filter_box_setter = filterbox.y
    cm_setter = cm1.x
    hhrm_setter = hhrm.hor_translation
    settling_time = 120

    if type(energy) == str:
        energy = int(energy)

    energy_range = [e_range for e_range in energy_ranges if
                  e_range['energy_end'] > energy >= e_range['energy_start']][0]
    if not energy_range:
        print_to_gui('ERROR: Energy is outside of the beamline energy range',stdout=stdout)
        return


    current_filterbox_position = filterbox.y.read()[filterbox.y.name]['value']
    if (abs(energy_range['Filterbox'] - current_filterbox_position)) < 0.1:
        move_filter = False
    else:
        move_filter = True


    print_to_gui(f'[Prepare Beamline] Starting setting up the beamline to {energy} eV...',stdout=stdout)
    if move_cm_mirror == True:
        start_cm_position = cm_setter.position
        end_cm_position = energy_range['CM1']
        cm_motion_range = abs(end_cm_position-start_cm_position)
        moving_cm = cm_setter.set(end_cm_position)

    start_hhrm_position = hhrm_setter.position
    end_hhrm_position = energy_range['HHRM']
    hhrm_motion_range = abs(start_hhrm_position-end_hhrm_position)
    moving_hhrm = hhrm_setter.set(end_hhrm_position)

    print_to_gui('[Prepare Beamline] Setting high voltage supply to safe values...',stdout=stdout)

    hv_setter_values = []
    for high_voltage_setter in high_voltage_setters:
        hv_setter_values.append(high_voltage_setter)
        hv_setter_values.append(safe_high_voltage)
    yield from bps.mv(*hv_setter_values)
    print_to_gui('[Prepare Beamline] High voltage supply is set to safe values',stdout=stdout)


    start_time = ttime.time()
    print_to_gui('[Prepare Beamline] Setting ion chamber gas composition...', stdout=stdout)
    yield from bps.mv(
                        He_flow_setter,energy_range['He_flow'],
                        N2_flow_setter,energy_range['N2_flow'],
                      )
    print_to_gui('[Prepare Beamline] Ion chamber gas composition set',stdout=stdout)



    #close shutter before moving the filter


    if move_filter:
        print_to_gui('[Prepare Beamline] Closing frontend shutter before selecting filter', stdout=stdout)
        print('moving')
        # close shutter before moving the filter
        try:
            yield from bps.mv(shutter_fe_2b, 'Close')
        except FailedStatus:
            raise CannotActuateShutter(f'Error: Photon shutter failed to close.')

        yield from bps.mv(filter_box_setter,energy_range['Filterbox'])
        print_to_gui('[Prepare Beamline] Filter set',stdout=stdout)
        print_to_gui('[Prepare Beamline] Closing frontend shutter before selecting filter',stdout=stdout)

        try:
            yield from bps.mv(shutter_fe_2b, 'Open')
        except FailedStatus:
            print_to_gui(f'Error: Photon shutter failed to open.',stdout=stdout)

    print_to_gui('[Prepare Beamline] Moving vertical position of the second monochromator crystal', stdout=stdout)
    hhmy_position = _compute_hhmy_value(energy)
    yield from bps.mv(hhm.y_precise, hhmy_position)
    if np.abs(hhm.y_precise.user_readback.get() - hhmy_position)>0.05:
        yield from bps.mv(hhm.y_precise, hhmy_position)


    while ttime.time() < (start_time + settling_time):
        print_to_gui(f'[Prepare Beamline] {int(settling_time - (ttime.time()-start_time))} s left to settle the ion chamber gas flow',stdout=stdout)
        yield from bps.sleep(10)
    print_to_gui('[Prepare Beamline] Setting high voltage values',stdout=stdout)
    hv_setter_values = []
    for high_voltage_setter in high_voltage_setters:
        hv_setter_values.append(high_voltage_setter)
        hv_setter_values.append(energy_range['IC_voltage'])
    yield from bps.mv(*hv_setter_values)
    print_to_gui('[Prepare Beamline] High voltage values set',stdout=stdout)

    while not moving_hhrm.done:
        motion_so_far = hhrm_setter.position
        percent_complete = int(abs(motion_so_far - start_hhrm_position) / hhrm_motion_range * 100)
        print_to_gui(f'[Prepare Beamline] HHRM motion is {percent_complete} % complete',stdout=stdout)
        yield from bps.sleep(10)

    print_to_gui('[Prepare Beamline] High harmonics rejection mirror position set',stdout=stdout)

#
    if move_cm_mirror == True:
        while not moving_cm.done:
            motion_so_far = cm_setter.position
            percent_complete = int(abs(motion_so_far - start_cm_position) / cm_motion_range * 100)
            print_to_gui(f'[Prepare Beamline] CM1 motion is {percent_complete} % set',stdout=stdout)
            yield from bps.sleep(10)
        print_to_gui('[Prepare Beamline] CM1 mirror position set',stdout=stdout)

    print_to_gui('[Prepare Beamline] Moving to the target energy',stdout=stdout)
    yield from bps.mv(hhm.energy, energy)

    print_to_gui('[Prepare Beamline] Adjusting exposure on the monitor', stdout=stdout)
    yield from bps.mv(BPM_exposure_setter,energy_range['ES BPM exposure'])
    print_to_gui('[Prepare Beamline] Beamline preparation is complete',stdout=stdout)

    if np.abs(hhm.y_precise.user_readback.get() - hhmy_position) > 0.05:
        print_to_gui(f'Error: vertical position of the second monochromator crystal is not set. Set manually to {hhmy_position}',stdout=stdout)


def calibrate_energy_plan(element, edge, dE=25, plot_fun=None):
    # # check if current trajectory is good for this calibration
    yield from set_reference_foil(element)
    yield from bps.sleep(1)
    success = foil_camera.validate_barcode(element)
    if not success: return
    success = trajectory_manager.validate_element(element, edge)
    if not success: return
    name = f'{element} {edge} foil scan'
    yield from fly_scan_with_apb(name, '')
    energy_nominal, energy_actual = get_energy_offset(-1, db, db_proc, dE=dE, plot_fun=plot_fun)
    print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy shift is {energy_actual-energy_nominal:.2f} eV')
    success = hhm.calibrate(energy_nominal, energy_actual)
    if not success: return
    trajectory_manager.reinit()
    yield from fly_scan_with_apb(name, '')
    energy_nominal, energy_actual = get_energy_offset(-1, db, db_proc, dE=dE, plot_fun=plot_fun)
    print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy shift is {energy_actual - energy_nominal:.2f} eV')
    if np.abs(energy_actual - energy_nominal) < 0.1:
        print_to_gui(f'{ttime.ctime()} [Energy calibration] Completed')
    else:
        print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy calibration error is > 0.1 eV. Check Manually.')


def optimize_beamline_plan(energy: int = -1,  tune_elements=tune_elements, stdout = sys.stdout, force_prepare = False, enable_fb_in_the_end=True):
    old_energy = hhm.energy.read()['hhm_energy']['value']
    if force_prepare or ((np.abs((energy-old_energy)/old_energy)> 0.1) or (np.sign(old_energy-13000)) != (np.sign(energy-13000))):
        yield from shutter.close_plan()
        yield from prepare_beamline_plan(energy, move_cm_mirror = True, stdout = sys.stdout)
        yield from tune_beamline_plan(tune_elements=tune_elements, stdout=sys.stdout, enable_fb_in_the_end=enable_fb_in_the_end)
    else:
        print_to_gui(f'Beamline is already prepared for {energy} eV', stdout=stdout)
        yield from bps.mv(hhm.energy, energy)


def tabulate_hhmy_position_plan(stdout=sys.stdout):
    _energies = [13000, 15000, 17500, 20000, 22500, 25000, 27500, 30000]  # np.arange(5000, 11000, 1000)
    data_df = pd.DataFrame(columns=['energy', 'hhmy', 'hhrmy', 'uid'])

    for energy in _energies:
        # enable_fb_in_the_end = energy>13000

        yield from optimize_beamline_plan(energy, tune_elements=tune_elements_ext, force_prepare=True, enable_fb_in_the_end=False)
        uid = db[-3].start['uid']
        data_df = data_df.append({'energy' : energy,
                                  'hhmy' : hhm.y.user_readback.get(),
                                  'hhrmy' : hhrm.y.user_readback.get(),
                                  'uid' : uid},
                                   ignore_index=True)
        data_df.to_json(f'{ROOT_PATH_SHARED}/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation_high_energies.json')





# def adjust_filter_plan(energy: int = -1, energy_ranges=bl_prepare_energy_ranges, plan_description='HHM_Y tabulating'):
#     filter_box_setter = filterbox.y
#     current_filterbox_position = filterbox.y.read()[filterbox.y.name]['value']
#
#     energy_range = [e_range for e_range in energy_ranges if
#                     e_range['energy_end'] > energy >= e_range['energy_start']][0]
#     if not energy_range:
#         print_to_gui('ERROR: Energy is outside of the beamline energy range', stdout=stdout)
#         return
#
#     if (abs(energy_range['Filterbox'] - current_filterbox_position)) < 0.1:
#         move_filter = False
#     else:
#         move_filter = True
#
#     if move_filter:
#         print_to_gui(f'[{plan_description}] Closing frontend shutter before selecting filter', stdout=stdout)
#         print('moving')
#         # close shutter before moving the filter
#         try:
#             yield from bps.mv(shutter_fe_2b, 'Close')
#         except FailedStatus:
#             raise CannotActuateShutter(f'Error: Photon shutter failed to close.')
#
#         yield from bps.mv(filter_box_setter,energy_range['Filterbox'])
#         print_to_gui(f'[{plan_description}] Filter set',stdout=stdout)
#         print_to_gui(f'[{plan_description}] Closing frontend shutter before selecting filter',stdout=stdout)
#
#         try:
#             yield from bps.mv(shutter_fe_2b, 'Open')
#         except FailedStatus:
#             print_to_gui(f'Error: Photon shutter failed to open.',stdout=stdout)