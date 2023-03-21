Node('see_demo_equipment',
    'Do  not use, it needs to be rewritten....',
    'tcp://10767',
)

Mod('tc1',
    'frappy_demo.modules.CoilTemp',
    '',
    sensor="X34598T7",
)

Mod('tc2',
    'frappy_demo.modules.CoilTemp',
    '',
    sensor="X39284Q8",
)


for i in [1,2]:
    Mod('sensor%d' % i,
        'frappy_ess.epics.EpicsReadable',
        '',
        epics_version="v4",
        value_pv="DEV:KRDG%d" % i,
        group="Lakeshore336",
    )

    Mod('loop%d' % i,
        'frappy_ess.epics.EpicsTempCtrl',
        '',
        epics_version="v4",
        group="Lakeshore336",
        value_pv="DEV:KRDG%d" % i,
        target_pv="DEV:SETP_S%d" % i,
        heaterrange_pv="DEV:RANGE_S%d" % i,
    )
