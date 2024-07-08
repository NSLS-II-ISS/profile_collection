print(ttime.ctime() + ' >>>> ' + __file__)


def vibration_diagnostics(time=1):
    cur_divide_value = apb_ave.divide.value
    cur_sample_len = apb_ave.sample_len.value
    cur_wf_len = apb_ave.wf_len.value

    yield from bps.abs_set(apb_ave.divide, 36, wait=True)
    yield from bps.abs_set(apb_ave.sample_len, time*1e4, wait=True)
    yield from bps.abs_set(apb_ave.wf_len, time*1e4, wait=True)

    uid = (yield from bp.count([apb_ave], int(time), md={"plan_name": "vibration_diagnostics"}))

    table = db[uid].table()

    data = np.zeros((int(time * 1e4), 9))
    # print(data.shape)
    data[:, 0] = table['apb_ave_time_wf'][1]

    for i in range(8):
        col_name = 'apb_ave_ch' + str(i + 1) + '_wf'
        data[:, i + 1] = table[col_name][1]

    yield from bps.abs_set(apb_ave.divide, cur_divide_value, wait=True)
    yield from bps.abs_set(apb_ave.sample_len, cur_sample_len, wait=True)
    yield from bps.abs_set(apb_ave.wf_len, cur_wf_len, wait=True)

    data_ft(data)


def single_bender_scan_bundle(bender_position=None, **kwargs):
    loading = int(bender.load_cell.get())
    if bender_position is None:
        bender_position = np.round(bender.pos.position, 2)
    name = f"Bender scan at {kwargs['element']}-{kwargs['edge']} edge - {loading} N - {bender_position} um"
    plan_kwargs = {**{'name' : name, 'comment' : 'Bender scan',
                      'metadata': {'sample_name': 'foil',
                                   'sample_uid': 'foil',
                                   'sample_condition': f'loading={loading}, position={bender_position}',
                                   'cm2_bender_loading': loading,
                                   'cm2_bender_position': bender_position,
                                   'scan_type': 'xas',
                                   'scan_name': f'{kwargs["element"]}-{kwargs["edge"]} bender scan'}},
                   **kwargs}
    plans = [{'plan_name' : 'fly_scan_plan',
              'plan_kwargs' : plan_kwargs}]
    return plans

from xas.energy_calibration import get_energy_offset

def foil_camera_validate_barcode_plan(element=None, error_message_func=None):
    foil_camera.validate_barcode(element, error_message_func=error_message_func)
    yield from bps.null()

def prepare_foil_scan(element, edge):
    plans = []
    plans.append({'plan_name': 'set_reference_foil', 'plan_kwargs': {'element': element}})
    plans.append({'plan_name': 'sleep', 'plan_kwargs': {'delay': 2}})
    plans.append({'plan_name': 'foil_camera_validate_barcode_plan',
                  'plan_kwargs': {'element': element},
                  'plan_gui_services': ['error_message_box']})
    trajectory_filename = scan_manager.standard_trajectory_filename(element, edge, short=True)
    plans.append({'plan_name': 'optimize_gains',
                  'plan_kwargs': {'trajectory_filename': trajectory_filename}})
    return plans, trajectory_filename


def bender_scan_plan_bundle(element, edge, error_message_func=None):
    # element, edge = foil_camera.read_current_foil_and_edge(error_message_func=error_message_func)
    # trajectory_filename = scan_manager.standard_trajectory_filename(element, edge)

    bender_current_position = bender.pos.user_readback.get()
    bender_positions = bender_current_position + np.arange(-15, 20, 5)

    plans, trajectory_filename = prepare_foil_scan(element, edge)

    for bender_position in bender_positions:
        plans.append({'plan_name' : 'move_motor_plan',
                      'plan_kwargs' : {'motor_attr' : bender.name,
                                       'based_on' : 'object_name',
                                       'position' : bender_position}})
        plans.append({'plan_name' : 'sleep',
                      'plan_kwargs': {'delay': 3}})
        plans.append({'plan_name' : 'single_bender_scan_bundle',
                      'plan_kwargs' : {'trajectory_filename' : trajectory_filename,
                                       'detectors' : [],
                                       'element' : element,
                                       'e0' : xraydb.xray_edge(element, edge).energy,
                                       'edge' : edge}})
    plans.append({'plan_name': 'move_motor_plan',
                  'plan_kwargs': {'motor_attr': bender.name,
                                  'based_on': 'object_name',
                                  'position': bender_current_position}})
    return plans


def obtain_hhm_calibration_plan(dE=25, is_final=False, propagate_calibration=False, plot_func=None, error_message_func=None, liveplot_kwargs=None):
    energy_nominal, energy_actual = get_energy_offset(-1, db, c_proc, dE=dE, plot_fun=plot_func)

    print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy shift is {energy_actual - energy_nominal:.2f} eV')
    hhm.calibrate(energy_nominal, energy_actual, error_message_func=error_message_func)

    if is_final:
        print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy shift is {energy_actual - energy_nominal:.2f} eV')
        if np.abs(energy_actual - energy_nominal) < 0.1:
            if propagate_calibration:
                scan_manager.update_local_scans_offset_in_vicinity_of_e(energy_actual)
            print_to_gui(f'{ttime.ctime()} [Energy calibration] Completed')
        else:
            print_to_gui(f'{ttime.ctime()} [Energy calibration] Energy calibration error is > 0.1 eV. Check Manually.')
    yield from bps.null()


def validate_foil_edge(element, edge):
    results = c_proc.search(Key('Sample_name') == f'{element} foil').search(Key('Edge') == edge)
    if len(results) == 0:
        raise Exception(f'Error: No {element} foil {edge}-edge was found in the database')

def calibrate_mono_energy_plan_bundle(element='', edge='', propagate_calibration=False, dE=25, plan_gui_services=None, question_message_func=None, ):
    # # check if current trajectory is good for this calibration
    # validate_element_edge_in_db_proc(element, edge, error_message_func=error_message_func)
    run_calibration = True
    run_simple_scan = False
    try:
        validate_foil_edge(element, edge)
    except Exception as e:
        e_message = str(e)
        print_to_gui(e_message)
        if question_message_func is not None:
            ret = question_message_func('Warning', f'{e_message}\n would you like to take a spectrum from this foil anyway to calibrate manually?'
                                             f'\n If the spectum is good, do not forget to add to the library!')
            run_calibration = False
            run_simple_scan = ret

    if run_calibration or run_simple_scan:
        plans, trajectory_filename = prepare_foil_scan(element, edge)


        name = f'{element} {edge}-edge foil energy calibration'
        scan_kwargs = {'name': name, 'comment': '',
                       'trajectory_filename': trajectory_filename,
                       'detectors': [],
                       'element': element, 'e0': xraydb.xray_edge(element, edge).energy, 'edge': edge,
                       'metadata': {'sample_name': 'foil', 'sample_uid': 'foil', 'sample_condition': 'calibration scan',
                                    'scan_type': 'xas', 'scan_name': f'{element}-{edge} calibration scan'}}


    if run_calibration:
        plans.append({'plan_name': 'fly_scan_plan',
                      'plan_kwargs': {**scan_kwargs}})
        plans.append({'plan_name': 'obtain_hhm_calibration_plan',
                      'plan_kwargs': {'dE' : dE, 'is_final' : False, 'liveplot_kwargs': {}},
                     'plan_gui_services': plan_gui_services})
        plans.append({'plan_name': 'fly_scan_plan',
                      'plan_kwargs': {**scan_kwargs}})
        plans.append({'plan_name': 'obtain_hhm_calibration_plan',
                      'plan_kwargs': {'dE' : dE, 'is_final' : True, 'propagate_calibration': propagate_calibration, 'liveplot_kwargs': {}},
                      'plan_gui_services': plan_gui_services})
    else:
        if run_simple_scan:
            plans.append({'plan_name': 'fly_scan_plan',
                          'plan_kwargs': {**scan_kwargs}})
    return plans


def check_hhm_roll_plan(threshold=0.05):
    read_back = hhm.roll.user_readback.get()
    # read_back = -336
    set_point = hhm.roll.user_setpoint.get()

    if abs(read_back - set_point) > threshold:
        print_to_gui("hhm roll drifted from the setpoint. Correcting.", tag='Beamline', add_timestamp=True)
        yield from bps.mv(hhm.roll, set_point, wait=True)


def check_ic_voltages(threshold=10):
    # energy = hhm.energy.position
    # energy_range = [e_range for e_range in bl_prepare_energy_ranges if
    #                 e_range['energy_end'] > energy >= e_range['energy_start']][0]
    # ic_setpoint = energy_range['IC_voltage']
    hv_setters = [wps1.hv302, wps1.hv303, wps1.hv305]
    hv_names = ['I0', 'It', 'Ir']
    for hv_setter, hv_name in zip(hv_setters, hv_names):
        # ic_readback = abs(hv_setter.get().read_pv)
        ic_on = hv_setter.switch_pv.get()

        if not ic_on:
            print_to_gui(f"{hv_name} ion chamber high voltage is OFF. Turning it ON.",
                         tag='Beamline', add_timestamp=True)
            yield from bps.mv(hv_setter, 1, switch=True)

        # if abs(ic_readback - ic_setpoint) < threshold:
        #     print_to_gui(f"{hv_name} ion chamber high voltage was set to safe value. Correcting to desired value.", tag='Beamline', add_timestamp=True)
        #     yield from bps.mv(hv_setter, ic_setpoint)

