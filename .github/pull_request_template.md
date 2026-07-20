## Summary

<!-- What changes, and what concrete problem does it solve? -->

## Boundary and compatibility

<!-- Does this belong to the stable kernel, a host adapter, or a deprecated compatibility surface? -->

- Stable ten-symbol API impact: <!-- none, additive, or breaking -->
- Serialized record / replay impact: <!-- none or explain -->
- Trust-boundary impact: <!-- none or explain -->

## Evidence and testing

<!-- List the checks run and the evidence level supported. Authored cases are conformance evidence, not benchmark evidence. -->

```text
commands and results
```

## Checklist

- [ ] The change is focused and includes regression tests where behavior changed.
- [ ] Kernel and host responsibilities remain explicit; no second acceptance-authority path was added.
- [ ] Stable API, reason-code, serialization, and migration effects are documented.
- [ ] Evidence claims match the demonstrated evidence level and do not imply benchmark or SOTA proof.
- [ ] No tests or security checks were weakened to make the change pass.
- [ ] No secrets, private data, generated run artifacts, caches, or local environment files are included.
- [ ] User-facing changes are reflected in the README, changelog, or release notes as appropriate.
