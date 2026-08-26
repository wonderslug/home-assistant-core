# Modern Forms Gen4 Fan Support — Design

## Background

`aiomodernforms` 0.3.0 adds support for Modern Forms/WAC "Gen4" fans, which
speak a `/device` + `/fixture` wire protocol (multiple independently
addressable light fixtures) instead of Gen 1/2/3's flat `/mf` shadow
endpoint (exactly one light). The library's asyncio API stays stable and
generation-agnostic: the integration continues to talk to
`ModernFormsDevice`/`Device`/`State`/`Info` exactly as before. Gen4-ness
shows up as new data (`Device.info.mac_address`/`fan_type` now populated,
`state.light_fixtures` now real per-fixture data) and new capability flags
(`has_sleep_timer()`, `has_adaptive_learning()`, `has_identify()`), not a
new code path to special-case.

Two real Gen4 fans (Radiant 56", model `2603-56`, downlight + uplight) have
been tested against the library by a third party — the behavior below is
confirmed against real hardware, not just the vendor spec.

This design covers all 5 stages of work end to end: the dependency bump and
identity fix, per-fixture light entities (parity), capability gating
(correctness), color-temperature control, and identify buttons (new
functionality). Per Home Assistant's PR conventions (see "Rollout
structure" below), this becomes two `home-assistant-core` PRs — a
dependency-upgrade PR and a stacked feature PR — plus a linked
`home-assistant.io` docs PR.

## What the library gives us

`Device.info` (all generations, including Gen4 now):
- `mac_address` — the fan's WiFi station MAC, populated for Gen4 for the
  first time. This is the config entry's identity.
- `light_type` — non-empty when the fan has at least one light fixture.
  Gen4 now populates it correctly (previously blank).
- `fan_type` — a real model string for Gen4 (e.g. `"2603-56"`), previously
  blank.

`Device.state` (unchanged shape, all generations): the existing flat
fields (`light_on`, `light_brightness`, etc.) still work for every
generation — for Gen4 they mirror the first light fixture. New:
`state.light_fixtures: list[Light]`, populated for every generation now.
For Gen 1/2/3 it's always a single synthetic entry (`address=None,
fixture_type=None`). For Gen4 it's one real entry per fixture the library
found on `/fixture`:

```python
@dataclass
class Light:
    address: int | None  # None only for the legacy synthetic entry
    fixture_type: int | None
    name: str
    on: bool
    brightness: int
    color_temp_kelvin: int | None
    min_color_temp_kelvin: int | None
    max_color_temp_kelvin: int | None
```

A Gen4 fixture's `address` is never `None` — the library only produces
`address=None` for the Gen 1/2/3 synthetic entry, and `light_fixture(None,
...)` actively raises `ModernFormsInvalidSettingsError` when called against
a Gen4 device. There is no code path where a "single-light Gen4 fan" ends
up on the `address is None` branch; the branch is purely a function of
generation via the data the library hands us.

Capability flags on `Device` (extend the existing `has_wind()` pattern —
`number.py` already checks it — don't check `generation` directly):
- `has_sleep_timer()` — new. `False` on Gen4.
- `has_adaptive_learning()` — new. `False` on Gen4.
- `has_identify()` — new. `True` only on Gen4.

Control methods on `ModernFormsDevice` (`coordinator.modern_forms`):
- `fan(...)` gained `identify: bool | None = None` (Gen4 only, silently
  ignored elsewhere).
- `light(...)` unchanged signature, always targets
  `state.light_fixtures[0]`. Gained `color_temp_kelvin` and `identify`.
- New: `light_fixture(address, *, brightness=None, on=None, sleep=None,
  color_temp_kelvin=None, identify=None)` — targets one fixture by
  `address`. `address=None` routes through `/mf` (legacy); passing `None`
  against a Gen4 device raises.
- `decommission()`, `enable_pairing_mode()`, `clear_paired_devices()`,
  `set_schedule(...)` raise `aiomodernforms.ModernFormsNotSupportedError`
  on Gen4. **None of these are called anywhere in the current
  integration**, confirmed by grep — no entity, service, or code path
  reaches them. Note for future maintainers:
  `ModernFormsNotSupportedError` extends plain `Exception`, not
  `ModernFormsError`, so `modernforms_exception_handler` in `__init__.py`
  would *not* catch it today if something ever called one of these four
  methods. This is a real gap but an unreachable one — no fix is needed as
  part of this work, since nothing calls these methods, but it should be
  addressed if a future feature ever does.

## Identity fix (validate, no code change)

`config_flow.py`, `entity.py`, and every entity's `unique_id` construction
already read `info.mac_address`/`info.fan_type` generically — they were
simply broken for Gen4 because the library left those fields blank. Bumping
the `aiomodernforms` requirement fixes this with zero code changes. This
must be validated (not just asserted) via a new Gen4 config-flow test
before any other work proceeds, since every other stage depends on
identity working.

**Action:** bump `manifest.json`'s `requirements` to
`["aiomodernforms==0.3.0"]` (confirmed available on PyPI).

## Per-fixture light entities (parity)

`light.py` currently creates exactly one `ModernFormsLightEntity` per
config entry, unique_id `f"{mac_address}"` (bare, no suffix), always
calling the flat `light()` method. This already works for Gen 1/2/3 and
single-fixture Gen4 fans, but a multi-light Gen4 fan (e.g. the tested
Radiant 56", uplight + downlight) would only ever get one HA light entity,
silently hiding the second fixture.

**Rework `async_setup_entry` to loop `coordinator.data.state.light_fixtures`,
creating one `ModernFormsLightEntity` per `Light`:**

```python
for light in coordinator.data.state.light_fixtures:
    entities.append(
        ModernFormsLightEntity(
            entry_id=config_entry.entry_id,
            coordinator=coordinator,
            light_address=light.address,
        )
    )
```

- **Unique ID branches on `light.address`:**
  - `address is None` (Gen 1/2/3 synthetic entry) → unique_id stays
    exactly `f"{mac_address}"`, matching today's behavior bit for bit.
    This is a hard backward-compatibility constraint — changing it orphans
    every existing entity in every production install.
  - `address is not None` (real Gen4 fixture) → `f"{mac_address}_{address}"`.
- **Control calls branch the same way** for every method (`turn_on`,
  `turn_off`, `async_set_light_sleep_timer`, `async_clear_light_sleep_timer`):
  the `address is None` entity keeps calling `light(...)`; every
  `address is not None` entity calls `light_fixture(address, ...)` instead.
  This isn't just a style choice — `light_fixture(None, ...)` raises
  against a Gen4 device, so getting this branch wrong breaks Gen4 outright.
- **Naming:** real Gen4 fixtures get `_attr_name = light.name` (e.g.
  `"Uplight"`/`"Downlight"`) instead of `_attr_translation_key = "light"`,
  since the name is per-device data, not a fixed string. The legacy
  `address is None` entity keeps `_attr_translation_key = "light"`
  unchanged — no explicit name, so it continues inheriting the device name
  via `_attr_has_entity_name = True`.
- **Setup gating stays** `if not coordinator.data.info.light_type: return`
  — unchanged, now correctly non-empty for Gen4 fans that have lights.

## Capability-gated entities (correctness)

Two gaps exist today that aren't Gen4-specific bugs so much as the
integration never having had a reason to check capability before Gen4
existed:

- `switch.py`: `ModernFormsAdaptiveLearningSwitch` is created
  unconditionally. Gate it on `coordinator.data.has_adaptive_learning()`,
  mirroring the existing `has_wind()` gate in `number.py`.
- `binary_sensor.py` / `sensor.py`: `ModernFormsFanSleepTimerActive` and
  `ModernFormsFanTimerRemainingTimeSensor` are created unconditionally
  regardless of generation. The light sleep-timer entities
  (`ModernFormsLightSleepTimerActive`,
  `ModernFormsLightTimerRemainingTimeSensor`) are gated on `info.light_type`
  alone. Gate all four on `coordinator.data.has_sleep_timer()` — the fan
  ones need this check added, the light ones need it added *in addition
  to* their existing `light_type` check, not instead of it.

Without this, a Gen4 fan gets entities that are permanently meaningless
(always unavailable/static), which is confusing in the UI and in
automations built against them.

## Color temperature control (new functionality)

`light.py` currently only supports `ColorMode.BRIGHTNESS` via a static
`_attr_color_mode`/`_attr_supported_color_modes`. Gen4 light fixtures
report real `min_color_temp_kelvin`/`max_color_temp_kelvin` (confirmed
2700–5000K on the tested Radiant 56") and `color_temp_kelvin` is settable.

- Add `ColorMode.COLOR_TEMP` to `_attr_supported_color_modes` when
  `light.min_color_temp_kelvin is not None and light.max_color_temp_kelvin
  is not None` (true only for real Gen4 fixtures — Gen 1/2/3's synthetic
  entry always has both as `None`).
- Because color mode becomes conditional per-entity, `color_mode` becomes
  a property (`COLOR_TEMP` when temp bounds are present, else
  `BRIGHTNESS`) rather than a static class attribute.
- Expose `color_temp_kelvin`, `min_color_temp_kelvin`,
  `max_color_temp_kelvin` as properties reading straight from the `Light`
  dataclass — no unit conversion, HA's native-Kelvin `LightEntity` attrs
  map directly.
- `async_turn_on` passes `ATTR_COLOR_TEMP_KELVIN` through to
  `light_fixture(address, color_temp_kelvin=...)` when present. The
  `address is None` entity's `light(color_temp_kelvin=...)` call exists in
  the library signature but is moot in practice — that entity never
  advertises `ColorMode.COLOR_TEMP` since Gen 1/2/3 fixtures never have
  temp bounds set.

## Identify buttons (new functionality)

`has_identify()` is Gen4-only and unused by the integration today. New
`button.py` platform (added to `PLATFORMS` in `__init__.py`), following the
existing `ButtonDeviceClass.IDENTIFY` + `EntityCategory.CONFIG` pattern
used elsewhere in the codebase (e.g. `elgato/button.py`):

- **Device-level:** one `ModernFormsIdentifyFanButton`, gated on
  `coordinator.data.has_identify()`, unique_id
  `f"{mac_address}_identify"`, calls
  `coordinator.modern_forms.fan(identify=True)`.
- **Per-fixture:** one `ModernFormsIdentifyLightButton` per entry in
  `state.light_fixtures` (naturally only reachable when `has_identify()`
  is true, since `address is None` fixtures only ever occur on
  Gen 1/2/3 which never has `has_identify() == True`), unique_id
  `f"{mac_address}_{address}_identify"`, name derived from `light.name`
  (e.g. `"Identify Uplight"`), calls
  `coordinator.modern_forms.light_fixture(address, identify=True)`.

Both help a user confirm which physical fan/fixture an HA entity
corresponds to — increasingly useful now that a multi-light Gen4 fan
produces multiple light entities per device.

## Testing

**Automated (pytest, no real network).** The existing suite mocks HTTP
responses directly via `aioclient_mock.post(...)` returning fixture JSON —
it does not run the library's `mock_fan` server. Gen4 detection means
`ModernFormsDevice.update()` tries `/mf` first and only probes `/device` +
`/fixture` on failure, so new Gen4 fixtures need `aioclient_mock` set up to
fail `/mf` and serve `/device`/`/fixture` responses shaped like real Gen4
output. Add a `modern_forms_gen4_call_mock` helper in
`tests/components/modern_forms/__init__.py` mirroring the existing
`modern_forms_breeze_call_mock` pattern, plus new JSON fixtures for a
multi-fixture Gen4 device.

New/updated tests:
- `test_config_flow.py`: a Gen4 fan can be added, unique_id is the mac
  address, model shows the real `fan_type`.
- `test_light.py`: a multi-fixture Gen4 fan creates one entity per
  fixture with correct unique_ids and names; each entity's control calls
  hit `light_fixture(address, ...)`, not `light(...)`; `ColorMode.COLOR_TEMP`
  appears only when temp bounds are present; all existing Gen 1/2/3 tests
  continue passing unchanged as a regression guard.
- `test_switch.py` / `test_binary_sensor.py` / `test_sensor.py`: gated
  entities are absent on Gen4, present on Gen 1/2/3.
- `test_button.py` (new): identify buttons present only when
  `has_identify()` is true, and call the right target (`fan()` vs.
  `light_fixture()`).

**Manual/exploratory verification.** Run the library's mock server
(`python -m mock_fan --generation gen4 --lights 2 --port 8080`) against a
real running Home Assistant instance to walk the config flow UI end to end
and confirm entities render and behave as expected, plus re-run against
`--generation gen1_2` and `gen3` to catch behavioral drift. This is
exploratory verification, not part of the automated suite.

## Rollout structure

This follows the same split Home Assistant already used for this
integration's last dependency bump: `aiomodernforms` 0.2.0 was its own PR
(#177506, "Dependency upgrade" checkbox only), with breeze-mode support
stacked on top as a second PR (#177507, "New feature" checkbox only,
explicitly depending on #177506) — the PR template only allows checking
one "type of change" box and instructs splitting into multiple PRs
otherwise.

**PR 1 (`home-assistant-core`): dependency bump.**
- Bump `manifest.json`'s `requirements` to `["aiomodernforms==0.3.0"]`,
  regenerate `requirements_all.txt`.
- Add the Gen4 config-flow identity test (confirms the bump alone makes
  Gen4 fans addable, with zero other code changes).
- Type of change: Dependency upgrade.

**PR 2 (`home-assistant-core`, stacked on PR 1): Gen4 fan support.**
Bundles the remaining 4 stages as separate commits for reviewability
(each independently testable against both `gen4` and `gen1_2`/`gen3`
fixtures, so a regression is bisectable), matching how the breeze-mode PR
bundled its preset-mode feature and new number entity into one "New
feature" PR:
1. Per-fixture light entities (parity).
2. Capability gating (`switch.py`, `binary_sensor.py`, `sensor.py`).
3. Color temperature support.
4. Identify buttons (new `button.py` platform).
- Type of change: New feature.
- Links to PR 3 in its "Link to documentation pull request" field, per
  the PR template — opened alongside PR 2 rather than deferred until
  after merge.

**PR 3 (`home-assistant.io`): docs, linked from PR 2.** Update
`source/_integrations/modern_forms.markdown`:
- Add `button` to `ha_platforms` and `Button` to `ha_category`.
- New `## Buttons` section describing the identify button(s), noting they
  only appear on Gen4 hardware.
- Update `## Lights` to mention multiple light entities on multi-fixture
  Gen4 fans and color-temperature support where available.
- No `ha_release` bump — that field tracks the integration's original
  release, not per-feature changes.
