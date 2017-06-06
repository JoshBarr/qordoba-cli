from __future__ import unicode_literals, print_function

import logging
import os
import shutil
from argparse import ArgumentTypeError
import requests, zipfile, StringIO
import sys
import tempfile

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
        raise ArgumentTypeError('Selected languages not configured in project as target languages: `{}`'
                                .format(','.join((str(i) for i in not_valid))))

    return list(selected_langs)

def pull_command(curdir, config, force=False, languages=(), in_progress=False, update_action=None, **kwargs):
    api = ProjectAPI(config)
    init_language_storage(api)
    project = api.get_project()

    target_languages = get_destination_languages(project)
    source_language = get_source_language(project)
    source_name = source_language.code
    source_content_type_code = None
    target_languages_page_ids = []
    target_languages_ids = []
    source_to_target_paths = {}

    if languages:
        languages = validate_languges_input(languages, target_languages)
    else:
        languages = target_languages

    pattern = get_pull_pattern(config, default=None)

    status_filter = [PageStatus.enabled, ]
    if in_progress is False:
        log.debug('Pull only completed translations.')
        status_filter = [PageStatus.completed, ]

    for language in languages:
        is_started = False
        for page in api.page_search(language.id, status=status_filter):
            milestone = None
            is_started = True

            target_languages_page_ids.append(page['page_id'])
            target_languages_ids.append(language.id)

            page_status = api.get_page_details(language.id, page['page_id'],  )

            log.info('Downloading translation file for source `{}` and language `{}`'.format(
                format_file_name(page),
                language.code,
            ))
            
            milestone = None
            if in_progress:
                milestone = page_status['status']['id']
                log.debug('Selected status for page `{}` - {}'.format(page_status['id'], page_status['status']['name']))

            target_path = create_target_path_by_pattern(curdir, language, pattern=pattern,
                                                        source_name=page_status['name'],
                                                        content_type_code=page_status['content_type_code'])

            stripped_target_path = ((target_path.native_path).rsplit('/',1))[0]
            source_to_target_paths[language.code] = stripped_target_path
            
            # adding the source langauge to the target_path_of_source_language pattern so the source language will be also pulled  
            target_path_of_source_language = create_target_path_by_pattern(curdir, source_language, pattern=pattern,
                                                        source_name=source_name,
                                                        content_type_code=source_content_type_code)

            stripped_target_path_of_source_language = ((target_path_of_source_language.native_path).rsplit('/',1))[0]
            source_to_target_paths[source_name] = stripped_target_path_of_source_language

            if os.path.exists(target_path.native_path) and not force:
                log.warning('Translation file already exists. `{}`'.format(target_path.native_path))
                answer = FileUpdateOptions.get_action(update_action) or ask_select(FileUpdateOptions.all,
                                                                                   prompt='Choice: ')
                if answer == FileUpdateOptions.skip:
                    log.info('Download translation file `{}` was skipped.'.format(target_path.native_path))
                    continue
                elif answer == FileUpdateOptions.new_name:
                    while os.path.exists(target_path.native_path):
                        target_path = ask_question('Set new filename: ', answer_type=target_path.replace)
                # pass to replace file

        if not is_started:
            log.info('Nothing to download for language `{}`'.format(language.code))
    
    ## makeing request to our internal api: export_files_bulk (POST). This request downloads all files for given language
    res = api.download_files(target_languages_page_ids, target_languages_ids)

    ##the api return a url and accesstoken for the google cloud server where Qordobas saves the translated files
    r = requests.get(res, stream=True)
    ## unzipping the returned zipfile
    z = zipfile.ZipFile(StringIO.StringIO(r.content))

    ## iterating through the source and target languages of the project downloads step by step all files.
    ## the files will be downloaded into earlier defined folder patterns for the poject
    for source_path, target_path in source_to_target_paths.iteritems():
        root = os.getcwd()
        temp_folder_path = tempfile.mktemp()

        #extract zip folder to root folder
        zip_files =z.namelist()
        dirs_to_extract = [d for d in zip_files if d.startswith(source_path) ]
        z.extractall(root, dirs_to_extract)

        # if target directory doesn't exist, we created it
        root_src_dir = os.path.join(os.getcwd(), source_path)
        root_dst_dir = os.path.join(os.getcwd(), target_path)

        ## first, the zip files are stored in the original zip-directory-name. 
        ## second, the project defined folder patterns are created if they were missing
        ## thirs, files are moved from zip folder to defined folder patterns
        ## zip folders are completely deleted
        for src_dir, dirs, files in os.walk(root_src_dir):
            dst_dir = src_dir.replace(root_src_dir, root_dst_dir, 1)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)
            for file_ in files:
                src_file = os.path.join(src_dir, file_)
                dst_file = os.path.join(dst_dir, file_)
                if os.path.exists(dst_file):
                    os.remove(dst_file)
                shutil.move(src_file, dst_dir)
            shutil.rmtree(root_src_dir)

            log.info('Updated/added translation file to folder `{}` for source `{}` and language `{}` '
               .format(target_path,
                  source_path,
                  source_path))