# Saing Sarinn Shin Pro — Android app

This Android project is a lightweight WebView companion for the hosted owner dashboard.

## Build a debug APK

The GitHub Actions workflow `.github/workflows/build-android-apk.yml` builds the APK on pushes to `android/**` and supports manual runs.

- Workflow: **Build Android APK**
- Output artifact: `saing-sarinn-shin-pro-debug-apk`
- APK path inside the artifact: `app-debug.apk`
- Package: `com.saingsarinnshin.pro`

The artifact is a **debug APK for testing**, not a Play Store release. A release build requires a protected signing key and release configuration.

## Install as a web app

The dashboard is also a Progressive Web App. Open the hosted dashboard in Chrome on Android, open the browser menu, and choose **Install app** or **Add to Home screen** when offered.

## Current product boundaries

- The dashboard and backend are hosted separately.
- Telegram inbound replies are configured through the backend webhook.
- AI agents currently generate drafts in sequence; external publishing, outbound prospecting, automatic payment confirmation, and fulfilment are not enabled.
- The free Render web service uses local SQLite unless a persistent database is configured. Do not rely on it as a permanent production database or sole record store.
