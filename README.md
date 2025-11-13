# franklinwh-python

Python bindings to the FranklinWH API, such as it is.

In order to use this, you'll need an access token, and your gateway ID. There's a bundled script which can generate an access token, your gateway ID can be found in the app under More -> Site Address. It's shown as your SN.

```bash
python3 -m pip install franklinwh
```

## Informational scripts

Scripts in [bin](./bin) use the API to show detailed information about your installation but have extra dependencies, install with

```bash
python3 -m pip install franklinwh[bin]
```

Most scripts require email address, password, and probably gateway id (referenced above).

```bash
python3 bin/get_info.py $FRANKLINWH_EMAIL $FRANKLINWH_PASSWORD $FRANKLINWH_GATEWAY_ID
```

## Development

The [Makefile](./Makefile) has a target to assist development and eventual release:

- `prepare` - run this once to install `franklinwh` in **editable mode** and prerequisites for bin and build.

This should be run in the context where you will eventually develop, which could be

- [franklinwh-python](#franklinwh-python)

  In this case a [virtual environment](https://www.w3schools.com/python/python_virtualenv.asp) is recommended.

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- [Home Assistant Core](https://github.com/home-assistant/core) with [FranklinWH integration](https://github.com/richo/homeassistant-franklinwh)

  This has too many permutations to discuss here but is a primary use for this API.

```bash
make prepare
```

## Release

The [Makefile](./Makefile) has targets to assist the release process:

- `build` - build the distribution.
- `release` - upload to PyPi.

The release process involves these steps:

- bump and commit version

  [pyproject.toml/project/version](./pyproject.toml) must be unique and conform to [semantic versioning](https://semver.org/).

> [!NOTE]
> This may already be included in a [Pull Request](<https://github.com/richo/franklinwh-python/pulls>).

- build

  ```bash
  make build
  ```

  Fix any errors and commit the changes.

- upload

  ```bash
  make release
  ```
