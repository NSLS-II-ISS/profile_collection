
def execute_constant_energy(name, duration,**metadata):

    flyers = [pba2.adc7, pba1.adc6, pba1.adc1, pba2.adc6, pba1.adc7, pb9.enc1]
    def inner():
        interp_fn = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.raw"
        interp_fn = validate_file_exists(interp_fn)
        print(f'Filepath  {interp_fn}')
        curr_traj = getattr(hhm, 'traj{:.0f}'.format(hhm.lut_number_rbv.get()))
        try:
            full_element_name = getattr(elements, curr_traj.elem.get()).name.capitalize()
        except:
            full_element_name = curr_traj.elem.get()
        md = {'plan_args': {},
              'plan_name': 'execute_trajectory',
              'experiment': 'fly_energy_scan',
              'name': name,
              'interp_filename': interp_fn,
              'angle_offset': str(hhm.angle_offset.get()),
              'trajectory_name': hhm.trajectory_name.get(),
              'element': curr_traj.elem.get(),
              'element_full': full_element_name,
              'edge': curr_traj.edge.get(),
              'e0': curr_traj.e0.get(),
              'pulses_per_degree': hhm.pulses_per_deg,
}
        for flyer in flyers:
            #print(f'Flyer is {flyer}')
            if hasattr(flyer, 'offset'):
                md['{} offset'.format(flyer.name)] = flyer.offset.get()
            if hasattr(flyer, 'amp'):
                md['{} gain'.format(flyer.name)]= flyer.amp.get_gain()[0]
        md.update(**metadata)
        yield from bps.open_run(md=md)
        #print(f'==== ret (open run): {ret}')

        # TODO Replace this with actual status object logic.
        yield from bps.clear_checkpoint()

        yield from shutter.open_plan()
        yield from bps.sleep(duration)
        yield from shutter.close_plan()


        ret = yield from bps.close_run()


        return ret


    def final_plan(flyers):
        yield from bps.abs_set(hhm.trajectory_running, 0, wait=True)
        #yield from xia1.stop_trigger()
        flyers = flyers[::-1]
        for flyer in flyers:
            yield from bps.unstage(flyer)
        yield from bps.unstage(hhm)


    for flyer in flyers:
        yield from bps.stage(flyer)

    yield from bps.stage(hhm)
    fly_plan = bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan(flyers)),
                                      flyers)
    return (yield from fly_plan)