import copy


def step_scan(name: str, comment: str, n_cycles: int = 1, delay: float = 0, energy_down: bool = True, use_sample_registry: bool = False, autofoil=True, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    energy_grid = kwargs.pop('energy_grid', [])
    time_grid = kwargs.pop('time_grid', [])
    element = kwargs.pop('element', [])
    e0 = kwargs.pop('e0', [])
    edge = kwargs.pop('edge', [])

    if energy_down:
        energy_grid = energy_grid[::-1]
        time_grid = time_grid[::-1]

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from shutter.open_plan()
        yield from step_scan_plan(name_n, comment, energy_grid, time_grid, [apb_ave], element=element, e0=e0, edge=edge)
        yield from shutter.close_plan()
        yield from bps.sleep(float(delay))
        if use_sample_registry:
            if sample_registry.position_list is not None:
                sample_registry.set_current_point_exposed()
                yield from sample_registry.goto_next_point_plan()
                sample_registry.dump_data()


def step_scan_w_pilatus(name: str, comment: str, n_cycles: int = 1, delay: float = 0, energy_down: bool = True, use_sample_registry: bool = False, reference=True, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    energy_grid = kwargs.pop('energy_grid', [])
    time_grid = kwargs.pop('time_grid', [])
    element = kwargs.pop('element', [])
    e0 = kwargs.pop('e0', [])
    edge = kwargs.pop('edge', [])

    if energy_down:
        energy_grid = energy_grid[::-1]
        time_grid = time_grid[::-1]

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from shutter.open_plan()
        yield from step_scan_plan(name_n, comment, energy_grid, time_grid, [apb_ave, pil100k, hhm.enc.pos_I], element=element, e0=e0, edge=edge )
        yield from shutter.close_plan()
        yield from bps.sleep(float(delay))
        if use_sample_registry:
            if sample_registry.position_list is not None:
                sample_registry.set_current_point_exposed()
                yield from sample_registry.goto_next_point_plan()
                sample_registry.dump_data()


def vonhamos_calibration_scan_plan(name: str, comment: str, n_cycles: int = 1, e_min : int = 4902, e_max : int = 4977, e_step : int = 5, exp_time : float= 10.0, **kwargs):
    energy_grid = np.arange(e_min, e_max + e_step, e_step)
    time_grid = np.ones(energy_grid.size) * exp_time
    kwargs['energy_grid'] = [int(i) for i in energy_grid]
    kwargs['time_grid'] = [int(i) for i in time_grid]

    if 'n_cycles' in kwargs:
        n_cycles = kwargs['n_cycles']
        kwargs.pop('n_cycles', [])

    yield from step_scan_w_pilatus(name, comment, n_cycles=n_cycles, energy_down=True, use_sample_registry=False, reference=False, **kwargs)




def step_scan_w_xs(name: str, comment: str, n_cycles: int = 1, delay: float = 0, energy_down: bool = True, use_sample_registry: bool = False, autofoil=True, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    energy_grid = kwargs.pop('energy_grid', [])
    time_grid = kwargs.pop('time_grid', [])
    element = kwargs.pop('element', [])
    e0 = kwargs.pop('e0', [])
    edge = kwargs.pop('edge', [])

    if energy_down:
        energy_grid = energy_grid[::-1]
        time_grid = time_grid[::-1]

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from shutter.open_plan()
        yield from step_scan_plan(name_n, comment, energy_grid, time_grid, [apb_ave, xs, hhm.enc.pos_I], element=element, e0=e0, edge=edge )
        yield from shutter.close_plan()
        yield from bps.sleep(float(delay))
        if use_sample_registry:
            if sample_registry.position_list is not None:
                sample_registry.set_current_point_exposed()
                yield from sample_registry.goto_next_point_plan()
                sample_registry.dump_data()




def step_scan_emission_w_pilatus(name: str, comment: str, n_cycles: int = 1, delay: float = 0, use_sample_registry: bool = False,
                                 energy_bkg_lo: float = motor_emission.limits[0][0]-10,
                                 energy_min: float = motor_emission.limits[0][0],
                                 energy_max: float = motor_emission.limits[0][1],
                                 energy_bkg_hi: float = motor_emission.limits[0][1]+10,
                                 energy_step_coarse: float = 1.0,
                                 energy_step: float = 0.5,
                                 exposure_time: float = 1.0,
                                 **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    # emission_energies = kwargs.pop('emission_energies', [])
    # time_grid = kwargs.pop('time_grid', [])
    emission_energies_lo = np.arange(energy_bkg_lo,
                                     energy_min,
                                     energy_step_coarse)
    emission_energies_roi = np.arange(energy_min,
                                  energy_max + energy_step,
                                  energy_step)
    emission_energies_hi = np.arange(energy_max + energy_step_coarse,
                                     energy_bkg_hi,
                                     energy_step_coarse)
    emission_energies = np.hstack((emission_energies_lo, emission_energies_roi, emission_energies_hi))
    time_grid = np.ones(emission_energies.size) * exposure_time
    element = kwargs.pop('element', [])
    e0 = kwargs.pop('e0', [])
    line = kwargs.pop('line', [])

    if use_sample_registry:
        if sample_registry.position_list is not None:
            yield from sample_registry.goto_unexposed_point_plan()

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        # move the spectrometer to the first position before opening the shutter
        yield from bps.mv(motor_emission, emission_energies[0])
        yield from shutter.open_plan()
        yield from johann_emission_scan_plan(name_n, comment, emission_energies, time_grid, [apb_ave, pil100k, motor_emission],
                                             element=element, e0=e0, line=line )
        yield from shutter.close_plan()
        yield from bps.sleep(float(delay))
        if use_sample_registry:
            if sample_registry.position_list is not None:
                sample_registry.set_current_point_exposed()
                yield from sample_registry.goto_next_point_plan()
                # sample_registry.dump_data()


def step_scan_rixs_w_pilatus(name: str, comment: str, n_cycles: int = 1, delay: float = 0, energy_down: bool = True,
                             energy_min: float = motor_emission.energy.limits[0],
                             energy_max: float = motor_emission.energy.limits[1],
                             energy_step: float = 0.5,
                             use_sample_registry: bool = True,
                             energy_out_norm: float = 7649,
                             energy_in_norm: float = 8000,
                             resume_file: str = '',
                             reference=True, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    energy_grid = kwargs.pop('energy_grid', [])
    time_grid = kwargs.pop('time_grid', [])
    element = kwargs.pop('element', [])
    e0 = kwargs.pop('e0', [])
    edge = kwargs.pop('edge', [])

    if energy_down:
        energy_grid = energy_grid[::-1]
        time_grid = time_grid[::-1]

    emission_energies = np.arange(energy_min,
                                  energy_max + energy_step,
                                  energy_step)

    if use_sample_registry:
        if sample_registry.position_list is not None:
            yield from sample_registry.goto_unexposed_point_plan()

    for indx in range(int(n_cycles)):

        if resume_file:
            _name = copy.copy(resume_file)
            resume_file = ''
            resume_flag = True
        else:
            _name = f'{name} {indx + 1}'
            resume_flag = False

        filename_uid_bundle = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{_name}.uids"
        print(f'Uids will be stored in  {filename_uid_bundle}')
        rixs_logger = RIXSLogger(filename_uid_bundle, resume_flag=resume_flag)

        for emission_energy in emission_energies:
            if rixs_logger.energy_was_measured(emission_energy):
                print(f'Emission energy {emission_energy} eV was already measured in this scan')
                continue

            print(f'Emission moving to {emission_energy} ')
            yield from bps.mv(motor_emission, emission_energy)
            name_n = '{} {:04d}'.format(f'{name} {emission_energy} ', indx + 1)
            yield from shutter.open_plan()
            print('Starting HERFD Scan...')
            yield from step_scan_plan(name_n, comment, energy_grid, time_grid, [apb_ave, pil100k, hhm.enc.pos_I], element=element, e0=e0, edge=edge )
            uid_herfd = db[-1].start['uid']
            yield from shutter.close_plan()
            print('HERFD Scan complete...')
            # with open(filename_uid_bundle, "a") as text_file:
            #     text_file.write(f'{ttime.ctime()} {emission_energy} {uid_herfd}\n')

            if use_sample_registry:
                if sample_registry.position_list is not None:
                    sample_registry.set_current_point_exposed()
                    _pos = sample_registry.get_nom_and_act_positions()
                    rixs_logger.write_uid_herfd(uid_herfd, emission_energy)
                    rixs_logger.write_herfd_pos(uid_herfd, *_pos)

                    sample_registry.record_herfd_uid_for_current_point(uid_herfd)
                    sample_registry.dump_data()
                    yield from sample_registry.goto_next_point_plan()
            else:
                rixs_logger.write_uid_herfd(uid_herfd, emission_energy)



        if use_sample_registry:
            if sample_registry.position_list is not None:
                print('collecting normalization data')
                print('moving mono/emission energies')
                yield from bps.mv(motor_emission, energy_out_norm)
                yield from bps.mv(hhm.energy, energy_in_norm)
                herfd_uid_list = sample_registry.get_list_of_herfd_positions()
                for _herfd_uid in herfd_uid_list:
                    if _herfd_uid in rixs_logger.herfd_list:
                        if not rixs_logger.point_was_normalized(_herfd_uid):
                            yield from sample_registry.goto_index_plan(herfd_index)
                            yield from pil_count()
                            uid_norm = db[-1].start['uid']
                            _pos = sample_registry.get_nom_and_act_positions()
                            rixs_logger.write_uid_norm(_herfd_uid, uid_norm, energy_in_norm, energy_out_norm, *_pos)
                            # sample_registry[herfd_index].pop('uid')

        yield from bps.sleep(float(delay))












