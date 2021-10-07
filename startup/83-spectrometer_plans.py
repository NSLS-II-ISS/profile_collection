def elastic_scan_plan(DE=5, dE=0.1):
    npt = np.round(DE/dE + 1)
    name = 'elastic spectrometer scan'
    plan = bp.relative_scan([pil100k, apb_ave], hhm.energy, -DE/2, DE/2, npt, md={'plan_name': 'elastic_scan ' + motor.name, 'name' : name})
    yield from plan


def johann_calibration_scan_plan(energies, DE=5, dE=0.1):
    for energy in energies:
        yield from bps.mv(hhm.energy, energy)
        # yield from move_emission_energy_plan(energy)
        yield from bps.mv(motor_emission, energy)
        yield from elastic_scan_plan(DE=DE, dE=dE)



def plot_radiation_damage_scan_data(db, uid):
    t = db[uid].table()
    plt.figure()
    plt.plot(t['time'], t['pil100k_stats1_total']/np.abs(t['apb_ave_ch1_mean']))


def n_pil100k_exposures_plan(n):
    yield from shutter.open_plan()
    yield from bp.count([pil100k, apb_ave], n)
    yield from shutter.close_plan()



def johann_emission_scan_plan(name, comment, energy_steps, time_steps, detectors, element='', e0=0, line=''):
    print(f'Line in plan {line}')
    fn = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.dat"
    fn = validate_file_exists(fn)

    try:
        full_element_name = getattr(elements, element).name.capitalize()
    except:
        full_element_name = element

    md = {'plan_args': {},
          'experiment': 'step_scan_emission',
          'name': name,
          'comment': comment,
          'interp_filename': fn,
          'element': element,
          'element_full': full_element_name,
          'line': line,
          'e0': e0,
          }
    #yield from bp.list_scan(detectors=[adaq_pb_step], motor=hhm.energy, steps=energy_grid)
    yield from bps.abs_set(apb_ave.divide, 373, wait=True)

    # for det in detectors:
    #     if det.name == 'xs':
    #         yield from bps.mv(det.total_points, len(energy_steps))

    yield from bp.list_scan( #this is the scan
        detectors,
        motor_emission, list(energy_steps),
        per_step=adaq_pb_step_per_step_factory(energy_steps, time_steps), #and this function is colled at every step
        md=md
    )





