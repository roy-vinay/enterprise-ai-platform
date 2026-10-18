# Judge validation v1: pending

The implementation is testable offline. The judge is **not validated**.

No scores, human labels, or gold labels have been manufactured. The 60-response
set needs Vinay's approval before either reviewer begins labeling. A second
reviewer is still TBD. Local Ollama is not installed in this execution environment.

After approval, independent labeling, and adjudication, run `make judge-validate`.
It will replace this status artifact with measured scores and failure analysis.
Held-out and real-model evaluation remain gated until the configured bar passes.
