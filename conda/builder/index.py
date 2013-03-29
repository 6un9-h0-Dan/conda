import os
import re
import json
import base64
import hashlib
import tarfile
from os.path import join, getmtime

from utils import bzip2, file_info


app_pat = re.compile(r'App-(\w+)/meta\.json$')

def get_app_name(files):
    res = []
    for f in files:
        m = app_pat.match(f)
        if m:
            res.append(m.group(1))
    assert len(res) == 1, res
    return res[0]

def add_app_metadata(t, info):
    info['type'] = 'app'
    files = [m.path for m in t.getmembers()]
    app_name = get_app_name(files)
    meta = json.loads(t.extractfile('App-%s/meta.json' % app_name).read())
    icondata = t.extractfile('App-%s/%s' % (app_name, meta['icon'])).read()
    info['icondata'] = base64.b64encode(icondata)
    info['icon'] = hashlib.md5(icondata).hexdigest()
    info['summary'] = meta.get('summary')

def read_index_tar(tar_path):
    with tarfile.open(tar_path) as t:
        info = json.load(t.extractfile('info/index.json'))
        if any(app_pat.match(m.path) for m in t.getmembers()):
            add_app_metadata(t, info)
        return info


def update_index(dir_path, verbose=False, force=False):
    if verbose:
        print "updating index in:", dir_path
    index_path = join(dir_path, '.index.json')
    if force:
        index = {}
    else:
        try:
            with open(index_path) as fi:
                index = json.load(fi)
        except IOError:
            index = {}

    files = set(fn for fn in os.listdir(dir_path) if fn.endswith('.tar.bz2'))
    for fn in files:
        path = join(dir_path, fn)
        if fn in index and index[fn]['mtime'] == getmtime(path):
            continue
        if verbose:
            print 'updating:', fn
        d = read_index_tar(path)
        d.update(file_info(path))
        index[fn] = d

    # remove files from the index which are not on disk
    for fn in set(index) - files:
        if verbose:
            print "removing:", fn
        del index[fn]

    with open(index_path, 'w') as fo:
        json.dump(index, fo, indent=2, sort_keys=True)

    # --- new repodata
    for fn in index:
        info = index[fn]
        for varname in 'arch', 'platform', 'mtime', 'ucs':
            try:
                del info[varname]
            except KeyError:
                pass

    repodata = {'packages': index, 'info': {}}
    repodata_path = join(dir_path, 'repodata.json')
    with open(repodata_path, 'w') as fo:
        json.dump(repodata, fo, indent=2, sort_keys=True)
    bzip2(repodata_path)
