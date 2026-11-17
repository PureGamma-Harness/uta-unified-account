"""Pure actual-case runtime binding checks, independent of a preflight claim."""
from pathlib import Path

def validate_case_runtime(value,binding):
    if type(value) is not dict:return False
    version=value.get('version_info')
    if type(version) is not list or any(type(i) is not int for i in version) or version!=binding['version_info']:return False
    python=value.get('python')
    token='.'.join(map(str,binding['version_info']))
    if type(python) is not str or python.split(' ',1)[0]!=token:return False
    if type(value.get('executable')) is not str or value['executable']!=str(Path(binding['executable']).resolve()):return False
    if type(value.get('sqlite')) is not str or value['sqlite']!=binding['sqlite']:return False
    if type(value.get('optimize')) is not int or value['optimize']!=0 or value.get('dont_write_bytecode') is not True:return False
    if type(value.get('flags')) is not str or not value['flags'].startswith('sys.flags('):return False
    if value.get('affinity') != [2] or any(type(i) is not int for i in value['affinity']):return False
    if type(value.get('environment')) is not dict or value['environment']!=binding['environment']:return False
    if type(value.get('mapped_libpython')) is not list or value['mapped_libpython']!=binding['mapped_libpython_expected']:return False
    expected={path:binding['files']['libpython']['sha256'] for path in binding['mapped_libpython_expected']}
    if type(value.get('mapped_libpython_sha256')) is not dict or value['mapped_libpython_sha256']!=expected:return False
    return True
