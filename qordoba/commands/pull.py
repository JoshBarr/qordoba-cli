from __future__ import unicode_literals, print_function

import logging
import os
import shutil
from argparse import ArgumentTypeError
import requests, zipfile
try:
    from StringIO import StringIO
except ImportError:
    import io
    # from io import StringIO

from qordoba.commands.utils import mkdirs, ask_select, ask_question
from qordoba.languages import get_destination_languages, get_source_language, init_language_storage, normalize_language
from qordoba.project import ProjectAPI, PageStatus
from qordoba.settings import get_pull_pattern
from qordoba.sources import create_target_path_by_pattern

log = logging.getLogger('qordoba')


def format_file_name(page):
    if page.get('version_tag'):
        return '{} [{}]'.format(page['url'], page['version_tag'])
    return page['url']


class FileUpdateOptions(object):
    skip = 'Skip'
    replace = 'Replace'
    new_name = 'Set new filename'

    all = skip, replace, new_name

    _actions = {
        'skip': skip,
        'replace': replace,
        'set_new': new_name
    }

    @classmethod
    def get_action(cls, name):
        return cls._actions.get(name, None)


def validate_languges_input(languages, project_languages):
    selected_langs = set()
    for l in languages:
        selected_langs.add(normalize_language(l))

    not_valid = selected_langs.difference(set(project_languages))
    if not_valid:
        raise ArgumentTypeError('Selected languages not configured in project as dest languages: `{}`'
                                .format(','.join((str(i) for i in not_valid))))

    return list(selected_langs)


def pull_bulk(api, src_to_dest_paths, dest_languages_page_ids, dest_languages_ids):
    '''making request to our internal api: export_files_bulk (POST). This request downloads all files for given language'''
    res = api.download_files(dest_languages_page_ids, dest_languages_ids)
    #the api return a url and accesstoken for the google cloud server where Qordobas saves the translated files
    r = requests.get(res, stream=True)
    # unzipping the returned zipfile for python2 or python3
    try:
        z = zipfile.ZipFile(StringIO.StringIO(r.content))
    except:
        z = zipfile.ZipFile(io.BytesIO(r.content))


    # iterating through the src and dest languages of the project downloads step by step all files.
    # the files will be downloaded into earlier defined folder patterns for the poject
    for src_path, dest_path in set(src_to_dest_paths):
        log.info('Downloading translation files in bulks for language `{}` to destination `{}`'.format(
            src_path,
            dest_path,
        ))
        root = os.getcwd()

        # extract zip folder to root folder
        zip_files = z.namelist()
        dirs_to_extract = [d for d in zip_files if d.startswith(src_path)]
        z.extractall(root, dirs_to_extract)

        # if dest directory doesn't exist, we created it
        root_src_dir = os.path.join(os.getcwd(), src_path)
        root_dest_dir = os.path.join(os.getcwd(), dest_path)

        # first, the zip files are stored in the original zip-directory-name.
        # second, the project defined folder patterns are created if they were missing
        # third, files are moved from zip folder to defined folder patterns
        # zip folders are completely deleted
        for tuple_ in os.walk(root_src_dir):
            src_dir, dirs, files = tuple_
            dest_dir = src_dir.replace(root_src_dir, root_dest_dir, 1)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            for file_ in files:
                src_file = os.path.join(src_dir, file_)
                dest_file = os.path.join(dest_dir, file_)
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.move(src_file, dest_dir)

def pull_command(curdir, config, force=False, bulk=False, languages=(), in_progress=False, update_action=None,
                 **kwargs):
    api = ProjectAPI(config)
    init_language_storage(api)
    project = api.get_project()
    dest_languages = list(get_destination_languages(project))
    if languages:
        languages = validate_languges_input(languages, dest_languages)
    else:
        languages = dest_languages

    # prepare variables for pull_bulk command
    src_language = get_source_language(project)
    src_language_id = src_language.id
    src_language_code = src_language.code
    dest_languages_page_ids = []
    dest_languages_ids = []
    src_to_dest_paths = []

    pattern = get_pull_pattern(config, default=None)
    status_filter = [PageStatus.enabled, ]

    if in_progress is False:
        log.debug('Pull only completed translations.')
        status_filter = [PageStatus.completed, ]

    for language in languages:
        print("----------")
        print(language.code)
        print("LANGUAGE")
        print("----------")

        is_started = False

        for page in api.page_search(language.id, status=status_filter):
            is_started = True
            page_status = api.get_page_details(language.id, page['page_id'], )
            dest_languages_page_ids.append(page['page_id'])
            dest_languages_ids.append(language.id)

            log.info('Starting Download of tranlation file(s) for src `{}` and language `{}`'.format(
                format_file_name(page),
                language.code,
            ))

            milestone = None
            if in_progress:
                milestone = page_status['status']['id']
                log.debug('Selected status for page `{}` - {}'.format(page_status['id'], page_status['status']['name']))


            dest_path = create_target_path_by_pattern(curdir, language, pattern=pattern,
                                                      source_name=page_status['name'],
                                                      content_type_code=page_status['content_type_code'])
            stripped_dest_path = ((dest_path.native_path).rsplit('/', 1))[0]
            src_to_dest_paths.append(tuple((language.code, stripped_dest_path)))

            # adding the src langauge to the dest_path_of_src_language pattern so the src language will be also pulled
            dest_path_of_src_language = create_target_path_by_pattern(curdir, src_language, pattern=pattern,
                                                                      source_name=page_status['name'],
                                                                      content_type_code=page_status[
                                                                          'content_type_code'])
            src_page_status_id = page_status['id']
            stripped_dest_path_of_src_language = ((dest_path_of_src_language.native_path).rsplit('/', 1))[0]
            src_to_dest_paths.append(tuple((src_language_code, stripped_dest_path_of_src_language)))

            if not bulk:
                if os.path.exists(dest_path.native_path) and not force:
                    log.warning('Translation file already exists. `{}`'.format(dest_path.native_path))
                    answer = FileUpdateOptions.get_action(update_action) or ask_select(FileUpdateOptions.all,
                                                                                       prompt='Choice: ')
                    if answer == FileUpdateOptions.skip:
                        log.info('Download translation file `{}` was skipped.'.format(dest_path.native_path))
                        continue
                    elif answer == FileUpdateOptions.new_name:
                        while os.path.exists(dest_path.native_path):
                            dest_path = ask_question('Set new filename: ', answer_type=dest_path.replace)
                            # pass to replace file
                res = api.download_file(src_page_status_id, src_language_id, milestone=milestone)
                res.raw.decode_content = True  # required to decompress content
                # ensure to create all directories
                mkdirs(os.path.dirname(dest_path_of_src_language.native_path))
                # copy content to dest path
                with open(dest_path_of_src_language.native_path, 'wb') as f:
                    shutil.copyfileobj(res.raw, f)

                res = api.download_file(page_status['id'], language.id, milestone=milestone)
                res.raw.decode_content = True  # required to decompress content
                # ensure to create all directories
                mkdirs(os.path.dirname(dest_path.native_path))
                # copy content to dest path
                with open(dest_path.native_path, 'wb') as f:
                    shutil.copyfileobj(res.raw, f)

                log.info('Downloaded translation file `{}` for src `{}` and language `{}`'
                         .format(dest_path.native_path,
                                 format_file_name(page),
                                 language.code))
        if not is_started:
            log.info('Nothing to download for language `{}`'.format(language.code))

    if bulk:
        print(src_to_dest_paths)
        pull_bulk(api, src_to_dest_paths, dest_languages_page_ids, dest_languages_ids)
