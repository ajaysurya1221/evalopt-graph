# Authored grading controls

These small fixtures reproduce five *failure mechanisms* exposed by the public
v1 semantic audit. They are development conformance controls, not held-out tasks
or new workflow results. No retained model output is executed by these tests.

`fixed_width` distinguishes a genuine UnicodeDecodeError/ValueError subclass
from an incorrect parser. `object_copy` includes a baseline, a real deep-copy
regression and a clean alternative. `binary_framing` has one endian defect with
two supported consequences. The two probe families report unavailable evidence
with an actual process exit of 3, separately from their task outcomes.

Local tests explicitly select trusted-fixture subprocess mode. Python `-I`
isolates imports/configuration; it is not an operating-system security sandbox.
Untrusted candidate execution requires a separately provided sandbox invoker.
