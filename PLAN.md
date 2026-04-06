# Niko VDS Integration Plan

## Goal

Build a HACS-installable Home Assistant custom integration focused on one thing for v0:

- discover Niko VDS stations
- poll preview images from them
- expose those preview images as Home Assistant camera entities

## Scope For The First Milestone

- custom integration domain: `niko_vds`
- config flow for controller IP and pasted PEM credential text
- configurable polling interval with a safe default of `10` seconds
- VDS enumeration using the controller's config MQTT JSON-RPC API
- snapshot retrieval using `AddressingApi.DownloadVdsData(macAddress)`
- one Home Assistant camera entity per VDS endpoint
- HACS packaging, README, install button, and validation workflows

## Security And Secret Handling

- do not commit private keys, client certs, CA bundles, tokens, or captured device dumps
- keep `.gitignore` entries for secret and capture files
- document that obtaining the client cert/key is the end user's responsibility
- store pasted certificate material in the Home Assistant config entry
- for local development, keep copy/paste PEM text in gitignored `secrets/` files

## Discovery Strategy

### Primary path

Use the same credential model as snapshot retrieval:

1. fetch an LTS token via mTLS from `https://<controller>:4443/lts/v1/credentials`
2. connect to config MQTT on port `8883`
3. call `AddressingApi.GetKnownDevices`
4. extract `VdsDiscoveredDeviceInfo` items and their MAC addresses

### Friendly names

Current evidence:

- `GetKnownDevices` returns VDS MACs and metadata
- it does not currently return a populated `displayName`

Plan:

- use a controller-provided friendly name if present in discovery data
- otherwise fall back to `VDS <mac>`
- keep a path open for richer naming later if another controller API or optional token source exposes names

### Manual fallback

- support manual MAC entry in config or options for cases where discovery is incomplete

## Home Assistant Architecture

### Config flow

Collect:

- controller IP
- client certificate PEM text
- client key PEM text
- optional CA certificate PEM text
- verify TLS on or off
- polling interval
- optional manual MAC list

Validation:

- fetch an LTS token
- confirm config MQTT connectivity
- attempt discovery

### Runtime

- one coordinator per config entry
- refresh snapshots on the configured interval
- refresh discovery on a slower cache window so every poll does not fully rediscover devices
- create one camera entity per VDS MAC

### Entity behavior

- entity platform: `camera`
- latest snapshot is served via `async_camera_image`
- expose MAC, IP, software version, product ID, and button count as state attributes

## HACS And Repository Layout

- standard custom integration layout under `custom_components/niko_vds/`
- include `manifest.json`, `hacs.json`, and `brand/` images
- add GitHub workflows for HACS validation and Hassfest
- README should include:
  - HACS custom repo instructions
  - My Home Assistant HACS link
  - security notice about certificate/key acquisition
  - current scope limitations

## Risks And Follow-Up Work

- friendly names may remain MAC-based until a better naming source is identified
- polling every `5` seconds may be too aggressive on some controllers, so default to `10`
- future work can add:
  - richer naming
  - diagnostics
  - manual name overrides
  - better partial-failure handling
  - media stream or event support if the protocol work becomes clear
