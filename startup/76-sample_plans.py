from xas.image_analysis import analyze_spiral_scan


def optimize_sample_plan(*args, **kwargs):
    # sys.stdout = kwargs.pop('stdout', sys.stdout)
    sample_x_nominal = kwargs['sample_x']
    sample_y_nominal = kwargs['sample_y']
    edge_energy = kwargs['energy']
    sample_name = kwargs['name']
    # print('moving giantxy to the nominal position')
    # yield from bps.mv(giantxy.x, sample_x_nominal) # move to nominal position
    # yield from bps.mv(giantxy.y, sample_y_nominal) # move to nominal position
    # print('adjusting gains')
    # yield from adjust_ic_gains(**kwargs)
    # yield from bps.sleep(0.2)
    # print('measuring offsets')
    # yield from get_offsets(*args, **kwargs)
    # yield from bps.sleep(0.2)
    # print('moving energy above the edge')
    # yield from bps.mv(hhm.energy, edge_energy + 100)  # move energy above the edge
    # # prelim spiral scan:
    # spiral_plan = general_spiral_scan([apb_ave],
    #                                   motor1=giantxy.x, motor2=giantxy.y,
    #                                   motor1_range=15, motor2_range=15,
    #                                   motor1_nsteps=15, motor2_nsteps=15,
    #                                   time_step=0.1)
    # print('performing spiral scan to find optimal position on the sample')
    # uid = (yield from spiral_plan)
    #
    conc = kwargs['concentration']
    # image_path = f"{ROOT_PATH}/{USER_PATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{sample_name}_raster_scan.png"
    # print('analyzing spiral scan data and saving the image for the reference')
    # x, y = analyze_spiral_scan(db, uid, conc, None, image_path)
    x, y = analyze_spiral_scan(db, 'bbd9f23f-011e-40eb-b798-eb2a2ad5cfa8', conc, None, None)
    print(f'moving giantxy to the optimal postion ({x}, {y})')
    yield from bps.mv(giantxy.x, x)
    yield from bps.mv(giantxy.y, y)
    print('adjusting gains (final)')
    yield from adjust_ic_gains(**kwargs)
    print('measuring offsets (final)')
    yield from get_offsets(*args, **kwargs)



