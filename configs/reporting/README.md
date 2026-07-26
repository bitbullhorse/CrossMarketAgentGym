# Reporting configuration

`softwarex.yaml` declares the six required SoftwareX experiment categories and selects the
existing Phase 3, 4, 6, and 7 run artifacts used by the deterministic report:

```bash
cmag report softwarex --config configs/reporting/softwarex.yaml
```

Completed declarations require evidence. Planned and partial declarations remain visible and do
not receive fabricated values. The benchmark partition is descriptive and has no
hyperparameter-selection authority.

`service.yaml` configures the optional read-only report browser:

```bash
cmag service run --config configs/reporting/service.yaml
```

Loopback is the default. A non-loopback host requires `allow_remote: true`; production
authentication and TLS must be provided separately.
