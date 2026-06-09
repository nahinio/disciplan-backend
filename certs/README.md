# Aiven MySQL CA certificate

Download the CA certificate from your Aiven MySQL service console and save it as `ca.pem` in this folder for **local development**.

This file is gitignored. Never commit certificates.

**On Render:** paste the PEM contents into the `DB_SSL_CA` environment variable instead.
