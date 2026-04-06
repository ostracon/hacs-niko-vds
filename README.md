# Niko VDS

Home Assistant custom integration for Niko Home Control VDS snapshot previews.

Current scope:

- discover VDS stations from the controller
- poll preview images from those stations
- expose them as Home Assistant `camera` entities

This repository is intended to be installed through HACS as a custom integration.

[![Open your Home Assistant instance and open the Niko VDS repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ostracon&repository=hacs-niko-vds&category=integration)

## Status

This is an early integration focused only on still preview images. It does not yet implement SIP calls, audio, eventing, or door control.

## Security Notice

This integration does not ship any Niko client certificates, private keys, or tokens.

Obtaining the client certificate and private key required for local controller access is the end user's responsibility.

- Do not commit those files to git.
- Do not open a public issue containing those files.
- Paste them into the Home Assistant config flow fields when onboarding.
- For local development in this repo, keep any extracted PEM text under `secrets/`, which is gitignored.

More detail is in [docs/OBTAINING_CREDENTIALS.md](docs/OBTAINING_CREDENTIALS.md).

## Features

- local access to the controller via mTLS
- VDS discovery using the controller config API
- snapshot download using the same config API used by the programming software
- configurable polling interval
- optional manual MAC list if discovery is incomplete

## Discovery And Naming

The integration can enumerate VDS devices using the controller's config MQTT JSON-RPC API.

Friendly names are used when the controller exposes them. If not, entities fall back to MAC-based names such as `VDS 00112A653D81`.

## Installation

### HACS custom repository

1. Open HACS.
2. Open the custom repositories dialog.
3. Add `https://github.com/ostracon/hacs-niko-vds` as category `Integration`.
4. Install `Niko VDS`.
5. Restart Home Assistant.

### Manual install

Copy `custom_components/niko_vds` into your Home Assistant `custom_components` directory and restart Home Assistant.

## Configuration

After installation, add the integration from Home Assistant:

1. Go to `Settings -> Devices & Services -> Add Integration`.
2. Search for `Niko VDS`.
3. Enter:
   - controller IP
   - client certificate PEM text
   - client key PEM text
   - optional CA certificate PEM text
   - polling interval
   - optional manual MAC list

For local development in this repo, the ignored `secrets/` directory can hold paste-ready PEM text files.

Recommended polling interval:

- default: `10` seconds
- minimum supported in the current flow: `5` seconds

## Development

Repository validation should include:

- HACS GitHub Action
- Hassfest GitHub Action

Custom integration brand assets are shipped from the local `brand/` directory, which Home Assistant supports for custom integrations from Home Assistant `2026.3` onward.

## Roadmap

- improve friendly-name resolution
- diagnostics export
- better entity-level partial failure reporting
- optional manual name overrides
- any future video/event support once the protocol work is clearer
