from __future__ import unicode_literals, print_function

import logging
import os
import shutil
from argparse import ArgumentTypeError
import requests, zipfile, StringIO
import tempfile

from qordoba.commands.utils import mkdirs, ask_select, ask_question
from qordoba.languages import get_destination_languages, get_source_language, init_language_storage, normalize_language
from qordoba.project import ProjectAPI, PageStatus
from qordoba.settings import get_pull_pattern
from qordoba.sources import create_dest_path_by_pattern

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
        raise ArgumentTypeError('Selected languages not configured in project as dst languages: `{}`'
                                .format(','.join((str(i) for i in not_valid))))

    return list(selected_langs)

def pull_bulk(api, src_to_dest_to_filename_paths, dest_languages_page_ids, dest_languages_ids):
    ## makeing request to our internal api: export_files_bulk (POST). This request downloads all files for given language
    res = api.download_files(dest_languages_page_ids, dest_languages_ids)
    print('src_to_dest_to_filename_paths:  {}'.format(src_to_dest_to_filename_paths))
    ##the api return a url and accesstoken for the google cloud server where Qordobas saves the translated files
    r = requests.get(res, stream=True)
    ## unzipping the returned zipfile
    z = zipfile.ZipFile(StringIO.StringIO(r.content))

    ## iterating through the src and dst languages of the project downloads step by step all files.
    ## the files will be downloaded into earlier defined folder patterns for the poject
    for src_path, dest_path, file_dest_name in src_to_dest_to_filename_paths:
        log.info('Downloading tranlation files in bulks for language `{}` to destination `{}`'.format(
                src_path,
                dest_path,
            ))

        root = os.getcwd()
        temp_folder_path = tempfile.mktemp()

        #extract zip folder to root folder
        zip_files =z.namelist()
        dirs_to_extract = [d for d in zip_files if d.startswith(src_path) ]
        z.extractall(root, dirs_to_extract)

        # if dst directory doesn't exist, we created it
        root_src_dir = os.path.join(os.getcwd(), src_path)
        root_dest_dir = os.path.join(os.getcwd(), dest_path)

        ## first, the zip files are stored in the original zip-directory-name. 
        ## second, the project defined folder patterns are created if they were missing
        ## thirs, files are moved from zip folder to defined folder patterns
        ## zip folders are completely deleted
        for src_dir, dirs, files in os.walk(root_src_dir):
            dest_dir = src_dir.replace(root_src_dir, root_dest_dir, 1)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            for file_ in files:
                src_file = os.path.join(src_dir, file_)
                dest_file = os.path.join(dest_dir, file_)
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.move(src_file, dest_dir)
                print("file_ name: {}".format(file_))
                print(file_)
                [os.rename(file_, file_.replace(file_, file_dest_name)) for file_ in os.listdir(dest_dir) if not file_.startswith('.')]

            shutil.rmtree(root_src_dir)

def pull_command(curdir, config, force=False, bulk=False, languages=(), in_progress=False, update_action=None, **kwargs):
    api = ProjectAPI(config)
    control_number_one = 0
    init_language_storage(api)
    project = api.get_project()
    dst_languages = list(get_destination_languages(project))
    if languages:
        languages = validate_languges_input(languages, dst_languages)
    else:
        languages = dst_languages

    # prepare var for pull_bulk command
    dest_languages = get_destination_languages(project)
    src_language = get_source_language(project)
    src_language_id = src_language.id
    control_number_two = 0
    src_name = src_language.code
    dest_languages_page_ids = []
    dest_languages_ids = []
    src_to_dest_to_filename_paths = []

    pattern = get_pull_pattern(config, default=None)
    status_filter = [PageStatus.enabled, ]

    if in_progress is False:
        log.debug('Pull only completed translations.')
        status_filter = [PageStatus.completed, ]

    for language in languages:
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

            dest_path = create_dest_path_by_pattern(curdir, language, pattern=pattern,
                                                        source_name=page_status['name'],
                                                        content_type_code=page_status['content_type_code'])
            stripped_dest_path = ((dest_path.native_path).rsplit('/',1))[0]
            src_to_dest_to_filename_paths = (language.code, stripped_dest_path, format(dest_path))


            if control_number_one == 0:
                # adding the src langauge to the dest_path_of_src_language pattern so the src language will be also pulled 
                dest_path_of_src_language = create_dest_path_by_pattern(curdir, src_language, pattern=pattern,
                                                            source_name=page_status['name'],
                                                            content_type_code=page_status['content_type_code'])
                src_page_status_id = page_status['id']
                stripped_dest_path_of_src_language = ((dest_path_of_src_language.native_path).rsplit('/',1))[0]
                src_to_dest_to_filename_paths = (language.code, stripped_dest_path_of_src_language, format(dest_path_of_src_language))
                control_number_one = 1

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
                if control_number_two == 0:
                    res = api.download_file(src_page_status_id, src_language_id, milestone=milestone)
                    res.raw.decode_content = True  # required to decompress content
                    # ensure to create all directories
                    mkdirs(os.path.dirname(dest_path_of_src_language.native_path))
                    # copy content to dest path
                    with open(dest_path_of_src_language.native_path, 'wb') as f:
                        shutil.copyfileobj(res.raw, f)
                    control_number_two = 1
                    
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
        pull_bulk(api, src_to_dest_to_filename_paths, dest_languages_page_ids, dest_languages_ids)
