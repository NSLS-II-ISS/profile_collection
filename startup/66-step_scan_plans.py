


from ophyd import Staged
import bluesky.plan_stubs as bps
import bluesky.plans as bp


def adaq_pb_step_per_step_factory(energy_steps, time_steps):

    #scantime = sum(time_steps)
    #elapsed_time = 0

    energy_to_time_step = dict(zip(energy_steps, time_steps))

    def per_step_pb(detectors, motor, step, take_reading=None):
        #print(f' Energy {energy_step}')
        time_step=energy_to_time_step[step]

        for det in detectors:
            if det.name == 'apb_ave':
                samples = 250*(np.ceil(time_step*1005/250)) #hn I forget what that does... let's look into the new PB OPI
                yield from bps.abs_set(det.sample_len, samples, wait=True)
                yield from bps.abs_set(det.wf_len, samples, wait=True)
            elif det.name == 'pil100k':
                yield from bps.mv(det.cam.acquire_time, time_step)
            elif det.name == 'xs':
                yield from bps.mv(det.settings.acquire_time, time_step)

        yield from bps.mv(motor, step)
        devices = [*detectors, motor]
        # devices = [*detectors]
        # if close_shutter:
        start = ttime.time()
        yield from shutter.open_plan(printing=False)
        # for device in devices:
        #     start_trigger = ttime.time()
        #     yield from bps.trigger_and_read(devices=[device])
        #     print(f'{device.name} trigger took {ttime.time() - start_trigger}')
        # print(devices)
        # sdf
        yield from bps.trigger_and_read(devices=devices)
        yield from shutter.close_plan(printing=False)
        print(f'Total exposure time for this point is {ttime.time() - start} s')
        # if close_shutter:

    return per_step_pb

#OK so it seems that is the function that's we need



def step_scan_plan(name, comment, energy_steps, time_steps, detectors, element='', e0=0, edge=''):
    print(f'Edge in plan {edge}')
    fn = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.dat"
    fn = validate_file_exists(fn)


    try:
        full_element_name = getattr(elements, element).name.capitalize()
    except:
        full_element_name = element

    md = {'plan_args': {},
          'experiment': 'step_scan',
          'name': name,
          'comment': comment,
          'interp_filename': fn,
          'element': element,
          'element_full': full_element_name,
          'angle_offset': str(hhm.angle_offset.get()),
          'edge': edge,
          'e0': e0,
          }
    #yield from bp.list_scan(detectors=[adaq_pb_step], motor=hhm.energy, steps=energy_grid)
    yield from bps.abs_set(apb_ave.divide, 373, wait=True)

    for det in detectors:
        if det.name == 'xs':
            yield from bps.mv(det.total_points, len(energy_steps))
    yield from shutter.open_plan()
    yield from bp.list_scan( #this is the scan
        detectors,
        hhm.energy,
        list(energy_steps),
        per_step=adaq_pb_step_per_step_factory(energy_steps,time_steps), #and this function is colled at every step
        md=md
    )
    yield from shutter.close_plan()
