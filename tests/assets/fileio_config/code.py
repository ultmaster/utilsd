from utilsd.fileio import Config  # isort:skip

cfg = Config.fromfile('./tests/assets/fileio_config/a.py')
item5 = cfg.item1[0] + cfg.item2.a
