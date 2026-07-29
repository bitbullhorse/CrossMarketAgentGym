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

`gui.yaml` explicitly enables the guarded local job API used by the GUI:

```bash
cmag service run --config configs/reporting/gui.yaml
```

Execution endpoints are absent when `execution_enabled` is false. When enabled they are forced
to a loopback host, use exact CORS origins, accept only allow-listed workflow types and validate
all editable YAML before creating a job. Do not expose this profile directly to a network; use
SSH port forwarding for a remote CPU/GPU host.
