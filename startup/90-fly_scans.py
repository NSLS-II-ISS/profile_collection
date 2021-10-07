import inspect
import bluesky.plans as bp
import bluesky.plan_stubs as bps
from bluesky.plan_patterns import spiral_square_pattern
import os, sys
from bluesky.utils import FailedStatus







def fly_scan_with_apb(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
    '''
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata
    n_cycles : int (default = 1)
        Number of times to run the scan automatically
    delay : float (default = 0)
        Delay in seconds between scans
    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans

    '''
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []
    # if autofoil:
    # if True:
    #     current_element = getattr(hhm, f'traj{int(hhm.lut_number_rbv.value)}').elem.value
    #     try:
    #         yield from set_reference_foil(current_element)
    #     except:
    #         pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        yield from shutter.open_plan()
        uid = (yield from execute_trajectory_apb(name_n, comment=comment))
        uids.append(uid)
        yield from shutter.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))
    return uids

def fly_scan_over_spiral(name: str, comment: str, n_cycles: int = 1, delay: float = 0, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    motor_x = motor_dictionary['giantxy_x']['object']
    motor_y = motor_dictionary['giantxy_y']['object']

    x_center = motor_x.read()[motor_x.name]['value']
    y_center = motor_y.read()[motor_y.name]['value']

    cycler = spiral_square_pattern(motor_x, motor_y, x_center, y_center, 10, 10, 11, 11) #10*2+1, 10*2+1)

    pos_cache={motor_x:x_center, motor_y: y_center}

    for i in range(n_cycles):
        name_n = '{} {:04d}'.format(name, i+1)
        position = list(cycler)[i]
        yield from bps.move_per_step(position, pos_cache)
        yield from fly_scan(name=name_n, comment=comment, n_cycles = 1, delay = delay, **kwargs)

    yield from bps.mv(motor_x,x_center,motor_y,y_center)



def fly_scan_with_apb_trigger(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
    '''
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata
    n_cycles : int (default = 1)
        Number of times to run the scan automatically
    delay : float (default = 0)
        Delay in seconds between scans
    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans

    '''
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []
    if autofoil:
        current_element = getattr(hhm, f'traj{int(hhm.lut_number_rbv.value)}').elem.value
        try:
            yield from set_reference_foil(current_element)
        except:
            pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        yield from shutter.open_plan()
        uid = (yield from execute_trajectory_apb_trigger(name_n, comment=comment))
        uids.append(uid)
        yield from shutter.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))
    return uids




def fly_scan_with_xs3(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
    '''
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata
    n_cycles : int (default = 1)
        Number of times to run the scan automatically
    delay : float (default = 0)
        Delay in seconds between scans
    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans

    '''
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []
    # if autofoil:
    # if True:
    #     current_element = getattr(hhm, f'traj{int(hhm.lut_number_rbv.value)}').elem.value
    #     try:
    #         yield from set_reference_foil(current_element)
    #     except:
    #         pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        yield from shutter.open_plan()
        uid = (yield from execute_trajectory_xs(name_n, comment=comment))
        uids.append(uid)
        yield from shutter.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))
    return uids




def fly_scan_with_pil100k(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False,
                          use_sample_registry: bool = False, **kwargs):
    '''
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata
    n_cycles : int (default = 1)
        Number of times to run the scan automatically
    delay : float (default = 0)
        Delay in seconds between scans
    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans

    '''
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []
    if autofoil:
        current_element = getattr(hhm, f'traj{int(hhm.lut_number_rbv.value)}').elem.value
        try:
            yield from set_reference_foil(current_element)
        except:
            pass

    for indx in range(int(n_cycles)):
        if use_sample_registry:
            if sample_registry.position_list is not None:
                yield from sample_registry.goto_unexposed_point_plan()
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        yield from shutter.open_plan()
        uid = (yield from execute_trajectory_pil100k(name_n, comment=comment))
        uids.append(uid)
        yield from shutter.close_plan()
        print(f'Trajectory is complete {print_now()}')
        if use_sample_registry:
            if sample_registry.position_list is not None:
                sample_registry.set_current_point_exposed()

        yield from bps.sleep(float(delay))
    return uids




def fly_scan_rixs_w_pilatus(name: str, comment: str, n_cycles: int = 1, delay: float = 0,
                             energy_min: float = motor_emission.energy.limits[0],
                             energy_max: float = motor_emission.energy.limits[1],
                             energy_step: float = 0.5,
                             reference=True, **kwargs):
    # sys.stdout = kwargs.pop('stdout', sys.stdout)
    # energy_grid = kwargs.pop('energy_grid', [])
    # time_grid = kwargs.pop('time_grid', [])
    # element = kwargs.pop('element', [])
    # e0 = kwargs.pop('e0', [])
    # edge = kwargs.pop('edge', [])

    emission_energies = np.arange(energy_min,
                                  energy_max + energy_step,
                                  energy_step)

    filename_uid_bundle = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.uids"
    print(f'Uids will be stored under  {filename_uid_bundle}')

    for indx in range(int(n_cycles)):
        for emission_energy in emission_energies:
            print(f'Emission moving to {emission_energy} ')
            yield from bps.mv(motor_emission, emission_energy)
            name_n = '{} {:04d}'.format(f'{name} {np.round(emission_energy,3)} ', indx + 1)
            yield from shutter.open_plan()
            print('Starting HERFD Scan...')
            yield from fly_scan_with_pil100k(name_n, comment, n_cycles=1, delay=0, autofoil=False, **kwargs)
            uid_herfd = db[-1].start['uid']
            yield from shutter.close_plan()
            print('HERFD Scan complete...')
            yield from bps.sleep(float(delay))
            with open(filename_uid_bundle, "a") as text_file:
                text_file.write(f'{ttime.ctime()} {emission_energy} {uid_herfd}\n')











##############################################################
# LEGACY

def fly_scan_with_sdd(name: str, comment: str, n_cycles: int = 1, delay: float = 0, **kwargs):
    """
    Trajectory Scan XIA - Runs the monochromator along the trajectory that is previously loaded in the controller and get data from the XIA N times

    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata

    n_cycles : int (default = 1)
        Number of times to run the scan automatically

    delay : float (default = 0)
    delay : float (default = 0)
        Delay in seconds between scans


    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans


    See Also
    --------
    :func:`tscan`
    """
    sys.stdout = kwargs.pop('stdout', sys.stdout)

    uids = []
    for i in range(int(n_cycles)):
        if n_cycles == 1:
            name_n = name
        else:
            name_n = name + ' ' + str(i + 1)
        print('Current step: {} / {}'.format(i + 1, n_cycles))
        # RE(prep_traj_plan())
        # uid, = RE(execute_xia_trajectory(name_n, comment=comment))
        yield from prep_traj_plan()
        # uid = (yield from execute_trajectory(name_n))
        uid = (yield from execute_xia_trajectory(name_n, comment=comment))
        print(f'uid: {uid}')

        uids.append(uid)
        yield from bps.sleep(float(delay))
    print('Done!')
    return uids





def fly_scan_with_camera(name: str, comment: str, n_cycles: int = 1, delay: float = 0, **kwargs):
    """
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times

    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata

    n_cycles : int (default = 1)
        Number of times to run the scan automatically

    delay : float (default = 0)
        Delay in seconds between scans


    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans


    See Also
    --------
    :func:`tscanxia`
    """

    # uids = []
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    for indx in range(int(n_cycles)):
        if n_cycles == 1:
            name_n = name
        else:
            name_n = name + ' ' + str(indx + 1)
        print('Current step: {} / {}'.format(indx + 1, n_cycles))
        yield from prep_traj_plan()
        uid = (yield from execute_camera_trajectory(name_n, comment=comment))
        yield uid
        # uids.append(uid)
        yield from bps.sleep(float(delay))
    print('Done!')
    # return uids






#
# def fly_scan(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil:bool=True, **kwargs):
#     '''
#     Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
#     Parameters
#     ----------
#     name : str
#         Name of the scan - it will be stored in the metadata
#     n_cycles : int (default = 1)
#         Number of times to run the scan automatically
#     delay : float (default = 0)
#         Delay in seconds between scans
#     Returns
#     -------
#     uid : list(str)
#         Lists containing the unique ids of the scans
#
#     '''
#
#     sys.stdout = kwargs.pop('stdout', sys.stdout)
#     uids = []
#     if autofoil:
#         current_element = getattr(hhm, f'traj{int(hhm.lut_number_rbv.value)}').elem.value
#         try:
#             yield from set_reference_foil(current_element)
#         except:
#             pass
#
#     for indx in range(int(n_cycles)):
#         name_n = '{} {:04d}'.format(name, indx + 1)
#         yield from prep_traj_plan()
#         print(f'Trajectory prepared at {print_now()}')
#         uid = (yield from execute_trajectory(name_n, comment=comment))
#         uids.append(uid)
#
#         print(f'Trajectory excecuted {print_now()}')
#         yield from bps.sleep(float(delay))
#     #yield from prep_traj_plan()
#     # yield from pre_stage_the_mono()
#     return uids



#WIP tests of teh trigger






