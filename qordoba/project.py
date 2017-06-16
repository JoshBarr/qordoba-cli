from __future__ import unicode_literals, print_function

import json
import functools

import logging
import requests

from qordoba.utils import build_url

try:
    from json import JSONDecodeError
except ImportError:
    # pythont27
    class JSONDecodeError(ValueError):
        pass

log = logging.getLogger('qordoba')

API_URL = 'https://app.qordoba.com/api/'

DEFAULT_MILESTONE_ID = -100


class QordobaResponseError(Exception):
    """
    The base API exception
    """

    def __init__(self, message):
        if isinstance(message, dict):
            self.extra = message
            self.message = message.get('errMessage') or json.dumps(message)
        else:
            self.message = message

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.message)

    def __str__(self):
        return self.message


class FileAlreadyExistResponse(QordobaResponseError):
    pass


def exception_from_response(resp):
    error_cls = QordobaResponseError

    try:
        data = resp.json()

        if 'already exist' in data.get('errMessage'):
            error_cls = FileAlreadyExistResponse

    except (TypeError, JSONDecodeError, ValueError):
        if resp.content:
            data = resp.content.decode('utf-8')
        else:
            data = 'An error occurred while making a {} request to {}'.format(resp.request.method, resp.request.url)

    return error_cls(data)


class PageStatus:
    enabled = 'enabled'
    completed = 'completed'
    preparing = 'preparing'
    disabled = 'disabled'


class ResponsePaginatedResult(object):
    def __init__(self, source_name, func, args, kwargs):
        self._source_name = source_name

        self._func = func
        self._nativa_args = args
        self._nativa_kwargs = kwargs
        self._limit = kwargs.get('limit', 50)
        self._offset = kwargs.get('offset', 0)
        self._next_offset = 0

        self._total_result = None
        self._result = []

    def request_next(self):
        kwargs = {k: v for k, v in self._nativa_kwargs.items()}
        kwargs['offset'] = self._next_offset
        result = self._func(*self._nativa_args, **kwargs)
        self._result.extend(result[self._source_name])
        self._total_result = result['meta']['paging']['total_results']

        self._next_offset += self._limit
        return result[self._source_name]

    def has_next(self):
        return self._total_result is None or len(self._result) < self._total_result

    def __len__(self):
        return self._total_result

    def __iter__(self):
        for res in self._result:
            yield res

        while self.has_next():
            next_result = self.request_next()
            for res in next_result:
                yield res

    def filter_by(self, func):
        for res in iter(self):
            if func(res):
                yield res

    def get_one(self):
        return next(iter(self))

    def get(self, limit):
        count = 0
        res_iter = iter(self)
        while count < limit:
            yield next(res_iter)
            count += 1


def paginated(source_name):
    def wrapper(func):
        @functools.wraps(func)
        def _wrap(*args, **kwargs):
            return ResponsePaginatedResult(source_name, func, args, kwargs)

        return _wrap

    return wrapper


def _debug_response(resp):
    try:
        log.debug('Request({}):\nmethod: {}\nheaders: {}\nbody: {}'.format(
            resp.request.url,
            resp.request.method,
            resp.request.headers,
            resp.request.body or ''
        ))

        log.debug('Response({}):\nstatus_code: {}\nstatus: {}\nheaders: {}\nerror_text: {}'.format(
            resp.url,
            resp.status_code,
            resp.reason,
            resp.headers,
            resp.text if resp.status_code >= 400 else ''
        ))
    except UnicodeDecodeError:
        log.debug('Request debug was disabled because of unsupported terminal encoding')


class ProjectAPI(object):
    def __init__(self, config):
        self._config = config

    def do_post(self, url, files=None, json=None, data=None, headers=None, **kwargs):
        headers = self.build_headers(custom_headers=headers)

        resp = requests.post(url, files=files, json=json, data=data, headers=headers, **kwargs)
        print('{}\n{}\n{}\n\n'.format(
            '-----------START-----------',
            "post" + ' ' + resp.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in resp.headers.items()),
        ))
        print("DO POST")
        _debug_response(resp)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise exception_from_response(resp)
        else:
            return resp

    def do_put(self, url, files=None, json=None, data=None, headers=None, **kwargs):
        headers = self.build_headers(custom_headers=headers)

        resp = requests.put(url, files=files, json=json, data=data, headers=headers, **kwargs)
        print('{}\n{}\n{}\n\n'.format(
            '-----------START-----------',
            "put" + ' ' + resp.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in resp.headers.items()),
        ))
        print("DO PUT")

        _debug_response(resp)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise exception_from_response(resp)
        else:
            return resp

    def do_get(self, url, headers=None, **kwargs):
        headers = self.build_headers(custom_headers=headers)

        resp = requests.get(url, headers=headers, **kwargs)

        print('{}\n{}\n{}\n\n'.format(
            '-----------START-----------',
            "get" + ' ' + resp.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in resp.headers.items()),
        ))
        print("DO GET")
        _debug_response(resp)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise exception_from_response(resp)
        else:
            return resp

    def do_delete(self, url, headers=None, json=None, **kwargs):
        headers = self.build_headers(custom_headers=headers)

        resp = requests.delete(url, json=json, headers=headers, **kwargs)
        print('{}\n{}\n{}\n\n'.format(
            '-----------START-----------',
            "delete" + ' ' + resp.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in resp.headers.items()),
        ))
        print("DO DELETE")

        _debug_response(resp)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise exception_from_response(resp)
        else:
            return resp

    def build_headers(self, custom_headers=None):
        default_headers = {
            'X-AUTH-TOKEN': self._config['access_token'],
        }

        if custom_headers:
            default_headers.update(custom_headers)

        return default_headers

    def build_url(self, *args, **kwargs):
        return build_url(API_URL, *args, **kwargs)

    def get_languages(self):
        params = (
            'languages',
        )
        language_url = self.build_url(*params)

        resp = self.do_get(language_url)
        return resp.json()['languages']

    def get_project(self):
        params = (
            'projects',
            str(self._config['project_id'])
        )

        resp = self.do_get(self.build_url(*params))
        return resp.json()['project']

    @paginated('projects')
    def get_projects(self, limit=50, offset=0):
        """
        Example response:
            {
              "projects": [
                {
                  "id": 3502,
                  "source_language": {
                    "id": 94,
                    "name": "English - United States",
                    "code": "en-us",
                    "direction": "ltr",
                    "override_order": "aaa - aaa - English - United States"
                  },
                  "created": 1483118107000,
                  "creator": {
                    "id": 1528,
                    "name": "Ashley Bewick",
                    "timezone": "America/Los_Angeles"
                  },
                  "target_languages": [
                    {
                      "id": 222,
                      "name": "Spanish - Mexico",
                      "code": "es-mx",
                      "direction": "ltr",
                      "meta": {
                        "user_assigned": false
                      }
                    }
                  ],
                  "name": "www.expedia.com",
                  "content_type": {
                    "name": "Website",
                    "content_source": null
                  },
                  "platform": null,
                  "version": "",
                  "project_type": 1,
                  "status": 10
                },
                {
                  "id": 3487,
                  "source_language": {
                    "id": 94,
                    "name": "English - United States",
                    "code": "en-us",
                    "direction": "ltr",
                    "override_order": "aaa - aaa - English - United States"
                  },
                  "created": 1482388184000,
                  "creator": {
                    "id": 6,
                    "name": "May Habib",
                    "avatar": "https://storage.googleapis.com/storage.qordoba.com/e651880f-c40d-47b5-ac65-298ae9453741_may (1)__scaled__cropped__scaled.jpg",
                    "timezone": "America/Los_Angeles"
                  },
                  "target_languages": [
                    {
                      "id": 150,
                      "name": "Japanese - Japan",
                      "code": "ja-jp",
                      "direction": "ltr",
                      "meta": {
                        "user_assigned": false
                      }
                    },
                    {
                      "id": 234,
                      "name": "Spanish - Spain",
                      "code": "es-es",
                      "direction": "ltr",
                      "meta": {
                        "user_assigned": false
                      }
                    }
                  ],
                  "name": "JSON test",
                  "content_type": {
                    "name": "Strings",
                    "content_source": "upload-file"
                  },
                  "platform": null,
                  "version": "",
                  "project_type": 2,
                  "status": 1
                }
              ],
              "meta": {
                "paging": {
                  "total_results": 466
                }
              }
            }
        :return:
        """
        params = (
            'organizations',
            str(self._config['organization_id']),
            'projects',
        )
        query = {
            'limit': limit,
            'offset': offset
        }

        project_list_url = self.build_url(*params, **query)

        resp = self.do_get(project_list_url)
        # @todo add pagination
        return resp.json()

    def upload_file(self, stream, file_name, mimetype='', force=False):
        params = (
            'projects',
            str(self._config['project_id']),
            'files'

        )

        query = {}
        if force:
            query['update'] = 'true'
        # @todo bug in endpoint. Can't upload file without `update` query param

        upload_url = self.build_url(*params, **query)

        values = {
            'file_names': json.dumps([{"upload_id": "", "file_name": str(file_name)}])
        }

        resp = self.do_post(upload_url, files={'file': (str(file_name), stream, mimetype)}, data=values)
        return resp.json()

    def upload_anytype_file(self, stream, file_name, content_type_code,
                            mimetype='application/octet-stream', force=False, **kwargs):
        """
        Upload file to qordoba app.

        Example response:
        {
            "result":"success",
            "upload_id":"3cada1ed-d837-4178-937a-a76887169aef_android_strings_sample_file987.xml",
            "version_tags":[],
            "file_name":"android_strings_sample_file987.xml",
            "columns":null,
            "duplicated_in_projects":[],
            "docKey":null,
            "excelRowsWithError":null
        }

        :param bool force: Force upload. Update existed file
        :param stream: File Stream
        :param str file_name: Unique file name.
        :param str content_type_code:
        :param mimetype: Request mimetype. By default application/octet-stream
        :return: Upload result. Contains upload_id required to append file to the project
        """
        params = (
            'organizations',
            str(self._config['organization_id']),
            'upload',
            'uploadFile_anyType'
        )
        query = {
            'projectId': self._config['project_id'],
            'content_type_code': content_type_code
        }

        upload_url = self.build_url(*params, **query)

        values = {
            'file_names': json.dumps([])
        }

        resp = self.do_post(upload_url, files={'file': (str(file_name), stream, mimetype)}, data=values)
        log.debug('Response body: {}'.format(resp.json()))
        return resp.json()

    def update_upload_anyType_file(self, stream, file_name, file_id, mimetype='application/octet-stream'):
        """

        :param stream: File Stream
        :param str file_name: Unique file name.
        :param int file_id: File ID to replace
        :param mimetype: Request mimetype. By default application/octet-stream
        :return: Upload result. Contains upload_id required to append file to the project
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'files',
            str(file_id),
            'update',
            'upload'
        )

        upload_url = self.build_url(*params)

        resp = self.do_post(upload_url, files={'file': (str(file_name), stream, mimetype)})
        log.debug('Response body: {}'.format(resp.json()))
        return resp.json()

    def apply_upload_file(self, upload_id, file_id):
        """

        :param str upload_id: Unique upload ID provided by "update_upload_anyType_file" response
        :param int file_id: File ID to replace
        :return:
        """

        params = (
            'projects',
            str(self._config['project_id']),
            'files',
            str(file_id),
            'update',
            'apply'
        )

        payload = {
            'new_file_id': upload_id
        }

        upload_url = self.build_url(*params)

        resp = self.do_put(upload_url, json=payload)
        log.debug('Response body: {}'.format(resp.json()))
        return resp.json()

    def append_file(self, upload_id, file_name, source_columns=None, reference_columns=None, version_tag=None):
        """
        Attach uploaded file to qordoba project.

        :param str upload_id: Unique upload ID provided by "upload_anytype_file" response
        :param str file_name: Unique file name.
        :param source_columns:
        :param reference_columns:
        :param str version_tag:
        :param bool force:
        :return:
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'append_files'
        )

        query = {}

        payload = {
            'id': upload_id,
            'file_name': file_name,
            'source_columns': source_columns or []
        }
        if reference_columns is not None:
            payload['reference_columns'] = reference_columns
        if version_tag is not None:
            payload['version_tag'] = version_tag

        upload_url = self.build_url(*params, **query)

        resp = self.do_post(upload_url, json=[payload, ])

        log.debug('Response body: {}'.format(resp.json()))
        return resp.json()

    def _download_raw_file(self, token, filename):
        params = (
            'file',
            'download'
        )

        query = {
            'token': token,
            'filename': filename
        }

        download_url = self.build_url(*params, **query)

        return self.do_get(download_url, stream=True)

    def download_file(self, page_id, language_id, milestone=None):
        if milestone is None:
            milestone = DEFAULT_MILESTONE_ID

        params = (
            'projects',
            str(self._config['project_id']),
            'languages',
            str(language_id),
            'pages',
            str(page_id),
            'segments',
            'milestones',
            str(milestone),
            'export'
        )

        download_url = self.build_url(*params)

        resp = self.do_get(download_url)

        data = resp.json()

        return self._download_raw_file(data['token'], data['filename'])

    def create_download_url_for_zip(self, token, filename):
        params = (
            'file',
            'download'
        )

        query = {
            'token': token,
            'filename': filename
        }

        return self.build_url(*params, **query)

    def download_files(self, page_ids, languages, milestone=None):
        """
        Download archive with translation for selected languages.
        :param list page_ids:
        :param list languages:
        :return:
        """
        params = (
            'projects',
            self._config['project_id'],
            'export_files_bulk'
        )
        download_url = self.build_url(*params)

        payload = {
            'bilingual': False,
            'language_ids': languages,
            'page_ids': page_ids

        }

        resp = self.do_post(download_url, json=payload)

        data = resp.json()
        return self.create_download_url_for_zip(data['token'], data['filename'])

    @paginated('files')
    def get_pages(self, language_id, limit=50, offset=0):
        """
        Example response:
        {
          "files": [
            {
              "id": 723885,
              "title": "1_key_value_json_file_sample.json",
              "url": "d2301ad5-940d-4787-85d2-49358cb88681_key_value_json_file_sample.json",
              "type": "page",
              "root": false,
              "status": {
                "id": "pending",
                "color": 1,
                "name": "Pending Implementation"
              },
              "display_name": "1_key_value_json_file_sample.json",
              "version_of": 723885
            }
          ],
          "meta": {
            "paging": {
              "total_results": 1
            }
          }
        }
        :param language_id:
        :type language_id:
        :return:
        :rtype:
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'languages',
            str(language_id),
            'files'
        )
        query = {
            'limit': limit,
            'offset': offset
        }

        pages_url = self.build_url(*params, **query)

        resp = self.do_get(pages_url)

        return resp.json()

    def get_page_stats(self, language_id, page_id):
        """
        Example response:
            {
              "result" : "success",
              "stats" : 12,
              "complete_segment_count" : 0
            }
        :param language_id:
        :param page_id:
        :return:
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'languages',
            str(language_id),
            'files',
            str(page_id),
            'stats'
        )

        stats_url = self.build_url(*params)

        resp = self.do_get(stats_url)

        return resp.json()

    def get_page_details(self, language_id, page_id):
        """
        Example response:
            {
                "page" : {
                    "id" : 727300,
                    "name" : "dkimagepickercontroller-dkimagepickercontroller.bundle-dkimagepickercontroller.strings",
                    "content_type" : "Strings",
                    "url" : "d8c8b77d-b82d-4a78-8cf3-f7e9dba71a10_dkimagepickercontroller-dkimagepickercontroller.bundle-dkimagepickercontroller.strings",
                    "enabled" : true,
                    "published" : false,
                    "page_fully_loaded" : true,
                    "title" : "dkimagepickercontroller-dkimagepickercontroller.bundle-dkimagepickercontroller.strings",
                    "type" : "page",
                    "assignees" : [ {
                      "id" : 1624,
                      "client_id" : "1624",
                      "avatar" : null,
                      "account_status" : "signed_up",
                      "first_name" : "Polina",
                      "last_name" : "Popadenko",
                      "full_name" : "Polina Popadenko",
                      "email" : "polina.popadenko@dev-pro.net",
                      "job_title" : null,
                      "timezone" : "Europe/Helsinki",
                      "phone_number" : null,
                      "last_online" : 1483699344000,
                      "notifications" : {
                        "frequency" : "immediately",
                        "types" : {
                          "calendar_reminders" : true,
                          "team_activity" : false
                        }
                      }
                    } ],
                    "preview" : "",
                    "strings" : 13,
                    "strings_in_tm" : 99,
                    "status" : {
                      "id" : 7952,
                      "project_id" : 3466,
                      "order" : 0,
                      "name" : "Editing"
                    },
                    "le_last_saved" : 1483643204000,
                    "root" : false,
                    "display_name" : "dkimagepickercontroller-dkimagepickercontroller.bundle-dkimagepickercontroller.strings",
                    "next_page" : {
                      "id" : 727299,
                      "name" : "localdemo-infoplist.strings"
                    },
                    "update" : 1483643204000,
                    "created_at" : 1483643204000,
                    "content_type_code" : "macStrings"
                    }
                }
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'languages',
            str(language_id),
            'pages',
            str(page_id)
        )

        page_url = self.build_url(*params)

        resp = self.do_get(page_url)

        return resp.json()['page']

    def get_report_progress(self, language_id=None):
        """
        Example response:
            {
              "languages": [
                {
                  "id": 190,
                  "code": "ru-ru",
                  "name": "Russian - Russia",
                  "segments": 12,
                  "words": 80,
                  "total": 12,
                  "total_words": 80,
                  "milestones": [
                    {
                      "id": -100,
                      "name": "Completed",
                      "order": 1000,
                      "count": 2,
                      "words_count": 8,
                      "percent": 16.67
                    },
                    {
                      "id": 7865,
                      "name": "Proofreading",
                      "order": 1,
                      "count": 10,
                      "words_count": 72,
                      "percent": 83.33
                    },
                    {
                      "id": 7864,
                      "name": "Editing",
                      "order": 0,
                      "count": 0,
                      "words_count": 0,
                      "percent": 0
                    }
                  ]
                },
                {
                  "id": 150,
                  "code": "ja-jp",
                  "name": "Japanese - Japan",
                  "segments": 12,
                  "words": 80,
                  "total": 12,
                  "total_words": 80,
                  "milestones": [
                    {
                      "id": -100,
                      "name": "Completed",
                      "order": 1000,
                      "count": 0,
                      "words_count": 0,
                      "percent": 0
                    },
                    {
                      "id": 7865,
                      "name": "Proofreading",
                      "order": 1,
                      "count": 0,
                      "words_count": 0,
                      "percent": 0
                    },
                    {
                      "id": 7864,
                      "name": "Editing",
                      "order": 0,
                      "count": 12,
                      "words_count": 80,
                      "percent": 100
                    }
                  ]
                },
                {
                  "id": 92,
                  "code": "en-gb",
                  "name": "English - United Kingdom",
                  "segments": 12,
                  "words": 80,
                  "total": 12,
                  "total_words": 80,
                  "milestones": [
                    {
                      "id": -100,
                      "name": "Completed",
                      "order": 1000,
                      "count": 0,
                      "words_count": 0,
                      "percent": 0
                    },
                    {
                      "id": 7865,
                      "name": "Proofreading",
                      "order": 1,
                      "count": 0,
                      "words_count": 0,
                      "percent": 0
                    },
                    {
                      "id": 7864,
                      "name": "Editing",
                      "order": 0,
                      "count": 12,
                      "words_count": 80,
                      "percent": 100
                    }
                  ]
                }
              ]
            }
        :rtype: list
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'reports',
            'progress'
        )

        # Available query params:
        # - limit (doesn't work)
        # - offset (doesn't work)
        # - sortby
        # - order - asc/des
        query = {}
        if language_id:
            query['language_id'] = language_id

        progress_url = self.build_url(*params, **query)

        resp = self.do_get(progress_url)

        return resp.json()

    @paginated('pages')
    def page_search(self, language_id, status=None, limit=50, offset=0, search_string=None):
        """
        Example response:
            {
              "pages": [
                {
                  "id": 833802,
                  "page_id": 723885,
                  "type": "page",
                  "enabled": true,
                  "published": false,
                  "completed": false,
                  "url": "1_key_value_json_file_sample.json",
                  "live_updates": false,
                  "pre_translate": false,
                  "segment_count": 12,
                  "update": 1482169101000,
                  "created_at": 1481893268000,
                  "preparing": false,
                  "deleted": false
                },
                {
                  "id": 833801,
                  "page_id": 723663,
                  "type": "page",
                  "enabled": true,
                  "published": false,
                  "completed": true,
                  "url": "server.ru.yml",
                  "live_updates": false,
                  "pre_translate": false,
                  "segment_count": 0,
                  "update": 1482169101000,
                  "created_at": 1481738775000,
                  "preparing": false,
                  "error_id": 1000,
                  "error_message": "Unsupported node type",
                  "deleted": false
                },
                {
                  "id": 833800,
                  "page_id": 723662,
                  "type": "page",
                  "enabled": true,
                  "published": false,
                  "completed": true,
                  "url": "server.en.yml",
                  "live_updates": false,
                  "pre_translate": false,
                  "segment_count": 0,
                  "update": 1482169101000,
                  "created_at": 1481738501000,
                  "preparing": false,
                  "error_id": 1000,
                  "error_message": "404 Not Found\nNot Found",
                  "deleted": false
                }
              ],
              "meta": {
                "paging": {
                  "total_results": 3,
                  "total_enabled": 3
                }
              }
            }
        :param language_id:
        :type language_id:
        :return:
        :rtype: ResponsePaginatedResult
        """
        params = (
            'projects',
            str(self._config['project_id']),
            'languages',
            str(language_id),
            'page_settings',
            'search'
        )
        query = {'limit': limit,
                 'offset': offset}

        page_url = self.build_url(*params, **query)
        body = {}
        if status:
            body['status'] = status
        if search_string:
            body['title'] = search_string

        resp = self.do_post(page_url, json=body)

        log.debug('ResponseContent: {}'.format(resp.content))
        return resp.json()

    def delete_page(self, page_id):
        params = (
            'organizations',
            str(self._config['organization_id']),
            'projects',
            str(self._config['project_id']),
            'pages',
            str(page_id)
        )

        delete_url = self.build_url(*params)

        resp = self.do_delete(delete_url)


        return resp.json()