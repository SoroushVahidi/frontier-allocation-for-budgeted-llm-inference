# Run failure (post-readiness)

```text
Traceback (most recent call last):
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/scripts/run_semantic_diversity_controller_diagnostic.py", line 427, in run_cohere_live
    res = ctrl.run(ex0.question, ex0.answer)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/experiments/controllers.py", line 5587, in run
    g = _normalize_answer(answer) or "__unknown__"
        ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/experiments/controllers.py", line 6739, in _normalize_answer
    stripped = text.strip()
               ^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'strip'

```
