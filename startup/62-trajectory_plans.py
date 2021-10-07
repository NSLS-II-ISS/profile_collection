def execute_trajectory(name, **metadata):
    ''' Execute a trajectory on the flyers given:
            flyers : list of flyers to fly on
        scans on 'mono1' by default
        ignore_shutter : bool, optional
            If True, ignore the shutter
            (suspenders on shutter and ring current will be installed if not)
        NOTE: Not added yet
            (need to update isstools)
        ex:
            execute_trajectory(**md)
    '''
    # flyers = [pb4.di, pba2.adc7, pba1.adc6, pb9.enc1, pba1.adc1, pba2.adc6, pba1.adc7]
    # flyers = [pba2.adc7, pba1.adc6, pb9.enc1, pba1.adc1, pba2.adc6, pba1.adc7]
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
            # print(f'Flyer is {flyer}')
            if hasattr(flyer, 'offset'):
                md['{} offset'.format(flyer.name)] = flyer.offset.get()
            if hasattr(flyer, 'amp'):
                md['{} gain'.format(flyer.name)] = flyer.amp.get_gain()[0]
        md.update(**metadata)
        yield from bps.open_run(md=md)
        # print(f'==== ret (open run): {ret}')

        # TODO Replace this with actual status object logic.
        yield from bps.clear_checkpoint()
        yield from shutter.open_plan()
        # yield from xia1.start_trigger()
        # this must be a float
        # yield from bps.abs_set(hhm.enable_loop, 0, wait=True)
        # this must be a string
        yield from bps.abs_set(hhm.start_trajectory, '1', wait=True)

        # this should be replaced by a status object
        def poll_the_traj_plan():
            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    break
                else:
                    yield from bps.sleep(.1)

            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    yield from bps.sleep(.05)
                else:
                    break

        yield from bpp.finalize_wrapper(poll_the_traj_plan(),
                                        bpp.pchain(shutter.close_plan(),
                                                   bps.abs_set(hhm.stop_trajectory,
                                                               '1', wait=True)))

        ret = yield from bps.close_run()
        # print(f'==== ret2 (close run): {ret2}')

        return ret

    def final_plan(flyers):
        yield from bps.abs_set(hhm.trajectory_running, 0, wait=True)
        # yield from xia1.stop_trigger()
        flyers = flyers[::-1]
        for flyer in flyers:
            yield from bps.unstage(flyer)
        yield from bps.unstage(hhm)

    for flyer in flyers:
        yield from bps.stage(flyer)

    yield from bps.stage(hhm)
    fly_plan = bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan(flyers)),
                                      flyers)
    # TODO : Add in when suspend_wrapper is avaialable
    # if not ignore_shutter:
    # this will use suspenders defined in 24-suspenders.py
    # fly_plan = bpp.suspend_wrapper(fly_plan, suspenders)

    return (yield from fly_plan)


def execute_camera_trajectory(name, **metadata):
    flyers = [pb4.di, pba2.adc7, pba1.adc6, pb9.enc1, pba1.adc1, pba1.adc7]

    def inner():
        curr_traj = getattr(hhm, 'traj{:.0f}'.format(hhm.lut_number_rbv.get()))

        ret = (yield from bps.read(bpm_ms1.tiff_filenumber))
        if ret is None:
            raise Exception("Cannot read bpm_ms1 settings")
        else:
            tiff_filenumber = ret[bpm_ms1.tiff_filenumber.name]['value']

        new_folder = '/GPFS/xf08id/bpm_cameras_images/{}-{}/'.format(name, tiff_filenumber)
        if not os.path.exists(new_folder):
            os.makedirs(new_folder)
            call(['setfacl', '-m', 'g:iss-staff:rwx', new_folder])
            call(['chmod', '777', new_folder])

        yield from bps.sleep(0.25)
        # yield from bps.abs_set(bpm_ms1.tiff_filepath, new_folder)
        bpm_ms1.tiff_filepath.put(new_folder)
        yield from bps.sleep(0.5)

        ret = (yield from bps.read(bpm_ms1.tiff_filepath))
        if ret is None:
            raise Exception("Cannot read bpm_ms1 settings")
        else:
            tiff_filepath = ret[bpm_ms1.tiff_filepath.name]['value']

        ret = (yield from bps.read(bpm_ms1.tiff_filename))
        if ret is None:
            raise Exception("Cannot read bpm_ms1 settings")
        else:
            tiff_filename = ret[bpm_ms1.tiff_filename.name]['value']

        ret = (yield from bps.read(bpm_ms1.tiff_filefmt))
        if ret is None:
            raise Exception("Cannot read bpm_ms1 settings")
        else:
            tiff_filefmt = ret[bpm_ms1.tiff_filefmt.name]['value']

        interp_fn = f"{ROOT_PATH}/{filepath}/{RE.md['year']}.{RE.md['cycle']}.{RE.md['PROPOSAL']}/{name}.txt"
        md = {'plan_args': {},
              'plan_name': 'execute_trajectory',
              'experiment': 'transmission',
              'name': name,
              'interp_filename': interp_fn,
              'images_dir': ''.join(chr(i) for i in tiff_filepath)[:-1],
              'images_name': ''.join(chr(i) for i in tiff_filename)[:-1],
              'images_name_fmt': ''.join(chr(i) for i in tiff_filefmt)[:-1],
              'first_image_number': tiff_filenumber,
              'angle_offset': str(hhm.angle_offset.get()),
              'trajectory_name': hhm.trajectory_name.get(),
              'element': curr_traj.elem.get(),
              'edge': curr_traj.edge.get(),
              'e0': curr_traj.e0.get()}
        for flyer in flyers:
            if hasattr(flyer, 'offset'):
                md['{} offset'.format(flyer.name)] = flyer.offset.get()

        md.update(**metadata)
        yield from bps.open_run(md=md)

        # TODO Replace this with actual status object logic.
        yield from bps.clear_checkpoint()
        yield from shutter.open_plan()
        yield from xia1.start_trigger()
        # this must be a float
        yield from bps.abs_set(hhm.enable_loop, 0, wait=True)
        # this must be a string
        yield from bps.abs_set(hhm.start_trajectory, '1', wait=True)

        # this should be replaced by a status object
        def poll_the_traj_plan():
            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    break
                else:
                    yield from bps.sleep(.1)

            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    yield from bps.sleep(.05)
                else:
                    break

        yield from bpp.finalize_wrapper(poll_the_traj_plan(),
                                        bpp.pchain(shutter.close_plan(),
                                                   bps.abs_set(hhm.stop_trajectory,
                                                               '1', wait=True)))

        yield from bps.close_run()

    def final_plan():
        yield from bps.abs_set(hhm.trajectory_running, 0, wait=True)
        yield from xia1.stop_trigger()
        for flyer in flyers:
            yield from bps.unstage(flyer)
        yield from bps.unstage(hhm)

    for flyer in flyers:
        yield from bps.stage(flyer)

    yield from bps.stage(hhm)

    return (yield from bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan()),
                                              flyers))


def execute_xia_trajectory(name, **metadata):
    # flyers = [pba2.adc7, pba1.adc6, pb9.enc1, pba1.adc1, pba2.adc6, pba1.adc7, pb4.di]
    flyers = [pba2.adc7, pba1.adc6, pba1.adc1, pba2.adc6, pba1.adc7, pb9.enc1, pb4.di]

    def inner():
        # Setting the name of the file
        xia1.netcdf_filename.put(name)
        next_file_number = xia1.netcdf_filenumber_rb.get()

        xia_rois = {}
        max_energy = xia1.mca_max_energy.get()
        for mca in xia1.mcas:
            if mca.kind & Kind.normal:
                for roi_number in range(12):
                    # if not (eval('xia1.{}.roi{}.low.get()'.format(mca, roi)) < 0 or eval('xia1.{}.roi{}.high.get()'.format(mca, roi)) < 0):
                    roi = getattr(mca, f'roi{roi_number}')
                    if not roi.low.get() < 0 or roi.high.get() < 0:
                        # xia_rois[eval('xia1.{}.roi{}.high.name'.format(mca, roi))] = eval('xia1.{}.roi{}.high.get()'.format(mca, roi)) * max_energy / 2048
                        # xia_rois[eval('xia1.{}.roi{}.low.name'.format(mca, roi))] = eval('xia1.{}.roi{}.low.get()'.format(mca, roi)) * max_energy / 2048
                        xia_rois[roi.high.name] = roi.high.get() * max_energy / 2048
                        xia_rois[roi.low.name] = roi.low.get() * max_energy / 2048

        interp_fn = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}.{RE.md['cycle']}.{RE.md['PROPOSAL']}/{name}.txt"
        curr_traj = getattr(hhm, 'traj{:.0f}'.format(hhm.lut_number_rbv.get()))
        try:
            full_element_name = getattr(elements, curr_traj.elem.get()).name.capitalize()
        except:
            full_element_name = curr_traj.elem.get()
        md = {'plan_args': {},
              'plan_name': 'execute_xia_trajectory',
              'experiment': 'fluorescence_sdd',
              'name': name,
              'interp_filename': interp_fn,
              'xia_max_energy': xia1.mca_max_energy.get(),
              'xia_filename': '{}_{:03}.nc'.format(name, next_file_number),
              'xia_rois': xia_rois,
              'angle_offset': str(hhm.angle_offset.get()),
              'trajectory_name': hhm.trajectory_name.get(),
              'element': curr_traj.elem.get(),
              'element_full': full_element_name,
              'edge': curr_traj.edge.get(),
              'e0': curr_traj.e0.get()}
        for flyer in flyers:
            if hasattr(flyer, 'offset'):
                md['{} offset'.format(flyer.name)] = flyer.offset.get()
        md.update(**metadata)
        yield from bps.open_run(md=md)

        # TODO Replace this with actual status object logic.
        yield from bps.clear_checkpoint()

        fname = ''.join(chr(i) for i in list(xia1.netcdf_filename_rb.get()))
        fname = fname[0:len(fname) - 1]
        while (fname != name):
            fname = ''.join(chr(i) for i in list(xia1.netcdf_filename_rb.get()))
            fname = name[0:len(fname) - 1]
            yield from bps.sleep(.05)

        yield from shutter.open_plan()
        yield from bps.sleep(.5)
        yield from xia1.start_mapping_scan()
        yield from bps.sleep(.5)

        # this must be a float
        yield from bps.abs_set(hhm.enable_loop, 0, wait=True)
        yield from bps.sleep(.5)
        # this must be a string
        yield from bps.abs_set(hhm.start_trajectory, "1", wait=True)
        yield from bps.sleep(.5)

        def poll_the_traj_plan():
            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    break
                else:
                    yield from bps.sleep(.1)

            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    yield from bps.sleep(.05)
                else:
                    break

        yield from bpp.finalize_wrapper(poll_the_traj_plan(),
                                        bpp.pchain(xia1.stop_scan(),
                                                   shutter.close_plan(),
                                                   bps.abs_set(hhm.stop_trajectory,
                                                               '1', wait=True)))

        ret =(yield from bps.close_run())
        return ret

    def final_plan():
        yield from bps.abs_set(hhm.trajectory_running, 0, wait=True)
        #        yield from xia1.stop_scan()
        while xia1.capt_start_stop.get():
            pass
        print('Stopped XIA')
        for flyer in flyers:
            yield from bps.unstage(flyer)
        yield from bps.unstage(hhm)

    for flyer in flyers:
        yield from bps.stage(flyer)

    yield from bps.stage(hhm)

    return (yield from bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan()), flyers))



 #
 #  fly_plan = bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan(flyers)),
 #                                      flyers)
 #    # TODO : Add in when suspend_wrapper is avaialable
 #    # if not ignore_shutter:
 #    # this will use suspenders defined in 24-suspenders.py
 #    # fly_plan = bpp.suspend_wrapper(fly_plan, suspenders)
 #
 #    return (yield from fly_plan)


def execute_loop_trajectory(name, **metadata):
    flyers = [pba1.adc6, pba1.adc1, pba2.adc6, pba1.adc7, pb9.enc1]

    # flyers = [pba1.adc6, pb9.enc1, pba1.adc1, pba1.adc7]
    def inner():
        md = {'plan_args': {}, 'plan_name': 'execute_loop_trajectory', 'experiment': 'transmission', 'name': name,
              pba1.adc1.name + ' offset': pba1.adc1.offset.get(), pba1.adc6.name + ' offset': pba1.adc6.offset.get(),
              pba2.adc6.name + ' offset': pba2.adc6.offset.get(), pba1.adc7.name + ' offset': pba1.adc7.offset.get(),
              'trajectory_name': hhm.trajectory_name.get()}
        md.update(**metadata)
        yield from bps.open_run(md=md)

        # TODO Replace this with actual status object logic.
        yield from shutter.open_plan()
        yield from bps.abs_set(hhm.enable_loop, 1, wait=True)  # hhm.enable_loop.put("1")
        yield from bps.abs_set(hhm.start_trajectory, "1", wait=True)  # NOT SURE IF THIS LINE SHOULD BE HERE

        def poll_the_traj_plan():
            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                if ret is None:
                    break
                is_running = ret['hhm_trajectory_running']['value']

                if is_running:
                    break
                else:
                    yield from bps.sleep(.1)

            while True:
                ret = (yield from bps.read(hhm.trajectory_running))
                retloop = (yield from bps.read(hhm.enable_loop_rbv))
                if ret is None or retloop is None:
                    break
                loop_is_running = retloop['hhm_enable_loop_rbv']['value']

                if loop_is_running:
                    yield from bps.sleep(.05)
                else:
                    break

        yield from bpp.finalize_wrapper(poll_the_traj_plan(),
                                        bpp.pchain(shutter.close_plan(),
                                                   bps.abs_set(hhm.stop_trajectory,
                                                               '1', wait=True),
                                                   bps.abs_set(hhm.enable_loop,
                                                               0, wait=True)))

        yield from bps.close_run()

    def final_plan():
        yield from bps.abs_set(hhm.trajectory_running, 0, wait=True)

        for flyer in flyers:
            yield from bps.unstage(flyer)
        yield from bps.unstage(hhm)

    for flyer in flyers:
        yield from bps.stage(flyer)

    yield from bps.stage(hhm)

    return (yield from bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan()),
                                              flyers))


