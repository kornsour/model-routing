"""model_routing: an experiment harness for measuring model-routing tradeoffs.

The core abstraction is deliberately paradigm-agnostic so the same runner and
report can later serve tabular, vision, and search experiments:

* a :class:`~model_routing.types.Task` is a unit of work with a grader,
* a :class:`~model_routing.types.Candidate` is a concrete model you could send it
  to (provider + model + settings),
* a router decides which candidate(s) handle a task,
* every model invocation is a :class:`~model_routing.types.CallRecord`, and the
  router's decision for one task is an :class:`~model_routing.types.Outcome`.

Cost is always computed two ways: whatever the provider reports, and a
list-price computation from token usage so providers are comparable.
"""

__version__ = "0.1.0"
