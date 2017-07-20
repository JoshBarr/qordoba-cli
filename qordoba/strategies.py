from __future__ import unicode_literals, print_function

import logging
import os
import yaml

from shebang import shebang

log = logging.getLogger('qordoba')

class Extension(object):
    def __init__(self):
        pass

    def reveal_extension(self, blob):
        filename, file_extension = os.path.splitext(blob)
        return file_extension

    def find_ext(self, d, tag):
        if tag in d:
            yield d[tag]
        for k, v in d.items():
            if isinstance(v, dict):
                for i in self.find_ext(v, tag):
                    yield i, k

    def find(self, blob):
        extension = self.reveal_extension(blob)

        with open("language.yml", 'r') as stream:
            try:
                data = (yaml.load(stream))
                languages = []
                for ext_key_value in self.find_ext(data, 'extensions'):
                    (ext_list, ext_key) = ext_key_value
                    for ext in ext_list:
                        if ext == extension:
                            languages.append(ext_key)
                log.info('File `{}` with extension {} most certainly is of type {}'.format( blob.split('/')[-1:][0], extension, languages[0] ))
                return languages
            except yaml.YAMLError as exc:
                print(exc)


class Shebang():
    def __init__(self):
        pass

    def spot_shebang(self, blob):
        # shebang = parseshebang.parse(blob)
        # os.subprocess.check_call(shebang + ["/my_script.py"])
        # print(shebang)
        print(shebang(blob))
        # firstLine = open(blob, 'r').readline()
        # if firstLine[:2] == '#!':
        #     return True
        # else:
        #     return False


    def find(self, blob):
        if self.spot_shebang(blob):
            pass
        log.info('Strategy Shebang does not apply for file `{}`'.format(blob.split('/')[-1:][0]))


def Filename():
    def __init__():
        pass

    def reveal_filename(self, blob):
        filename, file_extension = os.path.splitext(blob)
        return filename

    def find(self, blob):
        filename = self.reveal_filename(blob)

        with open("language.yml", 'r') as stream:
            try:
                data = (yaml.load(stream))
                languages = []
                for filename_key_value in self.find_ext(data, 'filenames'):
                    assert isinstance(filename_key_value, object)
                    (filename_key, filename_value) = filename_key_value
                    if filename == filename_value:
                        languages.append()
            except:
                pass
