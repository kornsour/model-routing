# Planning notebooks

The capacity-planning notebook (`planning.ipynb`, in the analysts' repo)
compares simulated runs across capacity settings. It reads run results with
`orchestra.store.loads(text)` / `orchestra.store.load(path)`: the run file
format (version 2) is the one interchange format for run results, so the
notebook, the dashboard and the archive all share one parser.

Today the analysts produce those files by calling `orchestra.run` from Python
and `orchestra.store.save`. They would rather drive everything from the shell
with `orchestra run`.
