# Obtaining Credentials

This repository does not include the client certificate, private key, CA bundle, or any controller tokens.

Those materials are sensitive and are the end user's responsibility to obtain and store securely.

## Required Files

For the current integration flow you will typically need:

- client certificate PEM
- client private key PEM
- optional CA certificate PEM if you want TLS verification enabled

## Storage Guidance

- keep these files out of git
- keep them out of screenshots and issue reports
- for Home Assistant onboarding, paste the PEM text into the config flow
- for local repository use, keep paste-ready copies under `secrets/`, which is gitignored
- use normal filesystem permissions appropriate for private key material

## What This Repository Will Not Do

- it will not ship private credentials
- it will not generate private credentials for end users
- it will not auto-download or embed secret material

## User Responsibility

If you choose to use this integration, you are responsible for:

- obtaining the required certificate and key lawfully
- storing them securely
- understanding the risk of using local controller credentials on your network
