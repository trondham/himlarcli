# Himlar command line tool

## Examples

```bash
cd himlarcli
source bin/activate
./host.py -h
```

## Development

Use virtualenv with global site packages:

```bash
cd himlarcli
virtualenv . --system-site-packages
source bin/activate
python setup.py develop
pip install -r requirements.txt
```
