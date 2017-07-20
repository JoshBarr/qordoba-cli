from __future__ import unicode_literals, print_function

import errno
import logging
import os
import shutil
from argparse import ArgumentTypeError
import itertools
import operator
import requests, zipfile
try:
    import StringIO
except ImportError:
    import io

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


def pull_bulk(api, src_to_dest_paths, dest_languages_page_ids, dest_languages_ids, pattern):
    log.info('Starting bulk download for all files and languages in project')
    '''making request to our internal api: export_files_bulk (POST). This request downloads all files for given language'''
    res = api.download_files(dest_languages_page_ids, dest_languages_ids)
    '''the api return a url and accesstoken for the Google Cloud server where Qordoba saves the translated files'''
    r = requests.get(res, stream=True)
    '''unzipping the returned zipfile for python2 or python3'''
    try:
        z = zipfile.ZipFile(StringIO.StringIO(r.content))
    except:
        z = zipfile.ZipFile(io.BytesIO(r.content))

    if not os.path.exists('Bulk_Download'):
        os.makedirs('Bulk_Download')


    '''iterating through the src and dest languages of the project downloads step by step all files.
     the files will be downloaded into earlier defined folder patterns for the poject'''
    for src_path, dest_path in set(src_to_dest_paths):
        log.info('Downloading files...')

        root = os.getcwd() + '/' + 'Bulk_Download'
        '''extract zip folder to root folder'''
        zip_files = z.namelist()
        z.extractall(root, zip_files)

        '''if dest directory doesn't exist, we created it'''
        root_src_dir = os.path.join(os.getcwd(), src_path)
        if dest_path[:1] == '.':
            dest_path = dest_path[2:]
        root_dest_dir = os.path.join(os.getcwd(), dest_path)

        '''first, the zip files are stored in the original zip-directory-name.
         second, the project defined folder patterns are created if they were missing
         third, files are moved from zip folder to defined folder patterns
         zip folders are completely deleted'''
        # if pattern is not None:
        #     if not os.path.exists(root_dest_dir):
        #         os.makedirs(root_dest_dir)
        #     for src_dir, dirs, files in os.walk(root_src_dir):
        #         for file_ in files:
        #             src_file = os.path.join(root_src_dir, file_)
        #             dest_file = os.path.join(root_dest_dir, file_)
        #             shutil.move(src_file, dest_file)
        #         if os.path.exists(root_src_dir):
        #             shutil.rmtree(root_src_dir)


def pull_command(curdir, config, force=False, bulk=False, languages=(), in_progress=False, update_action=None,
                 files=(), **kwargs):
    api = ProjectAPI(config)
    init_language_storage(api)
    project = api.get_project()
    dest_languages = list(get_destination_languages(project))
    if languages:
        languages = validate_languges_input(languages, dest_languages)
    else:
        languages = dest_languages

    '''prepare variables for pull_bulk command'''
    src_language = get_source_language(project)
    src_language_code = src_language.code
    src_language_id = src_language.id
    dest_languages_page_ids = []
    dest_languages_ids = [src_language_id]
    src_to_dest_paths = []

    pattern = get_pull_pattern(config, default=None)
    status_filter = [PageStatus.enabled, ]

    if in_progress is False:
        log.debug('Pull only completed translations.')
        status_filter = [PageStatus.completed, ]


    for language in languages:

        is_started = False
        current_page_path = None

        if not files:
            pages = api.page_search(language.id, status=status_filter)
        else:
            pages = []
            for search_term in files:
                result = api.page_search(language.id, status=status_filter, search_string=search_term)
                pages = itertools.chain(pages, result)

        for page in pages:
            is_started = True
            page_status = api.get_page_details(language.id, page['page_id'], )

            """
            If searching for specific files, skip those that don't match the search criteria.
            """
            if files:
                needle = None
                for file_name in files:
                    remote_file_name = page_status['url'].partition('_')[2]
                    if file_name in remote_file_name:
                        needle = page_status['url']
                if needle is None:
                    continue
                else:
                    log.info('Found matching translation file src `{}` language `{}`'.format(
                        format_file_name(page),
                        language.code,
                    ))

            dest_languages_page_ids.append(page['page_id'])
            dest_languages_ids.append(language.id)

            milestone = None
            if in_progress:
                milestone = page_status['status']['id']
                log.debug('Selected status for page `{}` - {}'.format(page_status['id'], page_status['status']['name']))

            dest_path = create_target_path_by_pattern(curdir, language, pattern=pattern,
                                                      source_name=page_status['name'],
                                                      content_type_code=page_status['content_type_code'])
            if pattern is not None:
                stripped_dest_path = ((dest_path.native_path).rsplit('/', 1))[0]
                src_to_dest_paths.append(tuple((language.code, stripped_dest_path)))
            src_to_dest_paths.append(tuple((language.code, language.code)))

            '''adding the src langauge to the dest_path_of_src_language pattern'''
            dest_path_of_src_language = create_target_path_by_pattern(curdir, src_language, pattern=pattern, source_name=page_status['name'], content_type_code=page_status['content_type_code'])

            if pattern is not None:
                stripped_dest_path_of_src_language = ((dest_path_of_src_language.native_path).rsplit('/', 1))[0]
                src_to_dest_paths.append(tuple((src_language_code, stripped_dest_path_of_src_language)))
            src_to_dest_paths.append(tuple((src_language_code, src_language_code)))


            if not bulk:
                '''checking if file extension wanted in config file matches downloaded file. If not, continue'''
                valid_extension = pattern.split('.')[-1]
                file_extension = page['url'].split('.')[-1]
                if valid_extension != file_extension:
                    continue

                log.info('Starting Download of translation file(s) for src `{}` and language `{}`'.format(format_file_name(page), language.code))
                if os.path.exists(dest_path.native_path) and not force:

                    log.warning('Translation file already exists. `{}`'.format(dest_path.native_path))
                    answer = FileUpdateOptions.get_action(update_action) or ask_select(FileUpdateOptions.all, prompt='Choice: ')

                    if answer == FileUpdateOptions.skip:
                        log.info('Download translation file `{}` was skipped.'.format(dest_path.native_path))
                        continue

                    elif answer == FileUpdateOptions.new_name:
                        while os.path.exists(dest_path.native_path):
                            dest_path = ask_question('Set new filename: ', answer_type=dest_path.replace)
                            # pass to replace file

                res = api.download_file(page_status['id'], language.id, milestone=milestone)
                res.raw.decode_content = True  # required to decompress content

                if not os.path.exists(os.path.dirname(dest_path.native_path)):
                    try:
                        os.makedirs(os.path.dirname(dest_path.native_path))
                    except OSError as exc:  # Guard against race condition
                        if exc.errno != errno.EEXIST:
                            raise

                with open(dest_path.native_path, 'wb') as f:
                    shutil.copyfileobj(res.raw, f)

                log.info('Downloaded translation file `{}` for src `{}` and language `{}`'.format(dest_path.native_path, format_file_name(page), language.code))

        if not is_started:
            log.info('Nothing to download for language `{}`'.format(language.code))

    if bulk:
        pull_bulk(api, src_to_dest_paths, dest_languages_page_ids, dest_languages_ids, pattern=pattern)
