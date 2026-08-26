# Testing Modern Forms Gen4 fan support in Home Assistant

> **TEMPORARY FILE — DELETE BEFORE MERGING.** This is a testing guide for
> real Gen4 hardware owners trying this branch, added here only so it can
> be pushed alongside the branch for easy sharing. Remove this file (and
> this notice) before opening the actual pull request(s) against
> `home-assistant/core`.

Thanks for helping test this! This branch adds support for Modern Forms/WAC
"Gen4" fans (the newer models with independently-controllable light
fixtures, e.g. the Radiant with an uplight + downlight) to Home Assistant's
built-in Modern Forms integration. It hasn't been merged into Home Assistant
yet.

Rather than touching your real, everyday Home Assistant install, these
steps set up a **separate, throwaway instance of Home Assistant** running
directly from this branch's source code. It only exists on your computer
for testing — it doesn't affect your production instance at all, isn't
connected to it, and you can delete the whole thing afterward with no
cleanup needed on your real system.

This should take about 20-30 minutes, most of it unattended (downloads/builds).

## Before you start

- You'll need a Modern Forms Gen4 fan that's already set up on your Wi-Fi
  network via the Modern Forms app (same as any normal setup — this is just
  a different way of controlling it locally, not a replacement for initial
  pairing).
- **This has to run on a computer on the same local network as the fan** —
  a laptop or desktop at home, not a cloud-hosted dev environment (e.g.
  GitHub Codespaces won't work for this, since it can't reach devices on
  your home network).
- Pick one of the two setup options below. **Option A is recommended** if
  you're willing to install Docker + VS Code — it's the same setup this
  project's own contributors use, and it's the most isolated from your
  regular system. **Option B** is a plain Python setup if you'd rather not
  install Docker.

---

## Option A: VS Code Dev Container (recommended)

### One-time installs (skip anything you already have)

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. [Visual Studio Code](https://code.visualstudio.com/)
3. The [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) for VS Code

### Get the branch running

1. Open VS Code.
2. Press `F1` (or `Ctrl+Shift+P`/`Cmd+Shift+P`) to open the command palette,
   and run: **Dev Containers: Clone Repository in Container Volume**.
3. When prompted for the repository, enter:
   ```
   https://github.com/wonderslug/home-assistant-core
   ```
4. When prompted for the branch, choose or type:
   ```
   modernforms-gen4-fans
   ```
5. VS Code will build a container and set everything up automatically —
   this takes a while the first time (it's building a full Python dev
   environment and installing every Home Assistant dependency). Just let
   it run; you'll see progress in the bottom-right notifications and in a
   terminal panel.
6. Once it's done, open a terminal in VS Code (**Terminal → New Terminal**)
   and start Home Assistant:
   ```bash
   python -m homeassistant -c ./config
   ```
   You can also do this via **Terminal → Run Task… → Run Home Assistant Core**
   instead of typing the command.
7. Wait for a line like `Starting Home Assistant` and then
   `Home Assistant initialized`. VS Code automatically forwards port 8123,
   so a notification should offer to open it in your browser — or just go
   to **http://localhost:8123** yourself.

Skip down to [Complete initial setup](#complete-initial-setup).

---

## Option B: Plain Python setup (no Docker)

### One-time installs

1. [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (the
   Python package/environment manager this project uses). You do **not**
   need to separately install Python first — `uv` will fetch the exact
   version this project needs on its own.
2. `git`

### Get the branch running

```bash
git clone --branch modernforms-gen4-fans --depth 1 https://github.com/wonderslug/home-assistant-core.git
cd home-assistant-core
script/setup
```

`script/setup` creates an isolated virtual environment (`.venv`) inside
this folder, installs every dependency, and creates a fresh, empty
`config/` folder for this throwaway instance — it does not touch anything
outside this cloned folder. This step takes a while the first time.

Then start Home Assistant:

```bash
source .venv/bin/activate
hass -c config
```

Wait for a line like `Starting Home Assistant` and then
`Home Assistant initialized`, then open **http://localhost:8123** in your
browser.

---

## Complete initial setup

Since this is a brand new, empty Home Assistant instance, it'll walk you
through a one-time onboarding wizard the first time you open it (create a
local username/password, confirm your location, etc.) — this is just for
this throwaway instance, unrelated to your real Home Assistant account.
Click through it; the details don't matter for testing.

## Add your Gen4 fan

- **Settings → Devices & services → + Add integration**, search for
  **Modern Forms**, and enter your fan's IP address (check your router's
  connected-devices list if you don't know it).
- Auto-discovery may not find it automatically in this setup (the
  networking involved doesn't always carry the discovery broadcast the
  same way your normal network does) — manually entering the IP always
  works.
- If you can't connect, first check that this new instance can even reach
  the fan on your network by running (Option A: in the VS Code terminal;
  Option B: in the same terminal, with `.venv` still active):
  ```bash
  curl -v -m 5 http://<fan-ip-address>
  ```
  Any response (even an error page) means the network path is fine and the
  problem is elsewhere; a timeout means this instance can't reach your fan
  over the network — for Option A that's a Docker networking issue worth
  mentioning when you report back.

## What to test

Please try each of these and let me know what does and doesn't work:

- [ ] **Setup itself**: does adding the fan succeed? Does the device page
  show the right model number (e.g. "2603-56")?
- [ ] **Fan controls**: on/off, speed, direction — should all work exactly
  as before.
- [ ] **Multiple lights**: if your fan has more than one light fixture
  (e.g. uplight + downlight), you should now see **one light entity per
  fixture** in Home Assistant, each independently controllable — not just
  one light entity for the whole fan.
- [ ] **Brightness**: does each light's brightness slider work correctly,
  and only affect that one fixture?
- [ ] **Color temperature**: if your light fixture(s) support it, you
  should see a color-temperature control on the light entity. Try setting
  it to a few different values and confirm the light actually changes
  color.
- [ ] **Identify buttons**: on the fan's device page, you should see an
  "Identify" button entity for the fan itself, plus one more per light
  fixture (e.g. "Identify Uplight"). Press each one and confirm the
  correct physical thing flashes/blinks in response.
- [ ] **Entities that should be *absent***: Gen4 fans don't have "sleep
  timer" or "adaptive learning" — confirm you do **not** see an Adaptive
  Learning switch, or Sleep Timer sensors/binary sensors, on your Gen4 fan.

## If something goes wrong

- **Check the logs** right in the terminal where Home Assistant is
  running — errors print there directly.
- **Turn on debug logging** for more detail — add this to
  `config/configuration.yaml` and restart Home Assistant (`Ctrl+C` in the
  terminal, then re-run the `hass`/`python -m homeassistant` command):
  ```yaml
  logger:
    logs:
      homeassistant.components.modern_forms: debug
      aiomodernforms: debug
  ```
- **Grab diagnostics**: on the integration's device page, use the
  three-dot menu → **Download diagnostics**. This is the single most
  useful thing you can send back if something looks wrong — it's
  automatically scrubbed of your MAC address, account email, and any
  schedule data before it's generated.

## When you're done

Just stop it — `Ctrl+C` in the terminal running Home Assistant. For Option
A, you can delete the dev container/volume from Docker Desktop or VS
Code's "Dev Containers" panel. For Option B, delete the cloned folder.
Nothing outside that folder/container was ever touched.

## Reporting results

Let me know directly what you tried and what happened — screenshots of the
entity list and/or a diagnostics download are the most useful things to
include if anything looks off.

Thank you for testing!
