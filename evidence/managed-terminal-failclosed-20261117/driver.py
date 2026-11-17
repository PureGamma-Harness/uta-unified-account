import importlib.util,pathlib,unittest
suite=unittest.defaultTestLoader.discover('tests',pattern='test_managed_terminal_evidence.py')
p=pathlib.Path('evidence/reviews/managed-terminal-extractor-independent-20261117/first_negative_controls.py')
s=importlib.util.spec_from_file_location('preserved_independent_counterexamples',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(m))
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
