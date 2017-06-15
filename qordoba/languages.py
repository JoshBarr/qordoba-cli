from __future__ import unicode_literals, print_function

from qordoba.utils import python_2_unicode_compatible

DEFAULT_LANGUAGE_COUNTRIES = {
    'en': 'en-us',  # possible values 'en-us', 'en-gb', 'en-ca', 'en-au', 'en-ir', 'en-bz', 'en-cb', 'en-jm',
    # 'en-nz', 'en-ph', 'en-za', 'en-tt', 'en-zw'
    'sv': 'sv-se',  # possible values 'sv-fi', 'sv-se'
    'cy': 'cy-az-az',  # possible values 'cy-az-az', 'cy-sr-sp', 'cy-uz-uz'
    'nl': 'nl-nl',  # possible values 'nl-be', 'nl-nl'
    'it': 'it-it',  # possible values 'it-it', 'it-ch'
    'bn': 'bn-bn',  # possible values 'bn-bn', 'bn-in'
    'es': 'es-es',  # possible values 'es-mx', 'es-es', 'es-co', 'es-ar', 'es-pe', 'es-ve', 'es-cl', 'es-ec', 'es-bo',
    #  'es-cr', 'es-do', 'es-sv', 'es-gt', 'es-hn', 'es-ni', 'es-pa', 'es-py', 'es-pr', 'es-uy'
    'zh': 'zh-cn',  # possbile values 'zh-chs', 'zh-cht', 'zh-cn', 'zh-hk', 'zh-mo', 'zh-sg', 'zh-tw'
    'fr': 'fr-fr',  # possbile values 'fr-fr', 'fr-be', 'fr-ca', 'fr-lu', 'fr-mc', 'fr-ch',

}


_LANGUAGES = None


class EmptyLanguageStorage(Exception):
    """
    Empty language storage. Please use `qordoba.languages.init_language_storage` to init.
    """


class LanguageNotFound(Exception):
    """
    Language not found in storage
    """


def is_default_language(lang):
    """

    :type lang: Language
    :return:  Return true or false
    :rtype: bool
    """
    global _LANGUAGES
    return _LANGUAGES[lang.lang] == lang


def normalize_language(lang):
    """
    :type lang: unicode
    :return: Validated language object
    :rtype: qorodoba.language.Language
    """
    global _LANGUAGES
    if _LANGUAGES is None:
        raise EmptyLanguageStorage

    if isinstance(lang, Language):
        return lang

    lang = lang.replace('_', '-').lower()

    lang_obj = _LANGUAGES.get(lang, None)
    if lang_obj is None:
        raise LanguageNotFound('Language `{}` not found.'.format(lang))

    return lang_obj


def init_language_storage(api):
    global _LANGUAGES
    _LANGUAGES = {}
    langs = api.get_languages()


    for data in langs:
        lang = Language(data)
        _LANGUAGES[lang.code] = lang

    for lang in list(_LANGUAGES.values()):
        if lang.lang not in _LANGUAGES:
            default_lang_code = DEFAULT_LANGUAGE_COUNTRIES.get(lang.lang, None)
            if default_lang_code:
                _LANGUAGES[lang.lang] = _LANGUAGES[default_lang_code]
            else:
                _LANGUAGES[lang.lang] = lang


@python_2_unicode_compatible
class Language(object):
    def __init__(self, data):
        self.code = data['code'].lower()
        self.id = data['id']

        self._extra = data
        self._lang = None

    @property
    def lang(self):
        if self._lang is None:
            try:
                self._lang = self.code.split('-')[0]
            except IndexError:
                self._lang = self.code
        return self._lang

    def is_default(self):
        """
        Return if exist only one language_country code or this defined as default
        :return:
        :rtype:
        """
        return is_default_language(self)

    @property
    def name(self):
        try:
            name, _ = self._extra['name'].split('-')
        except ValueError:
            name = self._extra['name']
        return name.strip()

    def __str__(self):
        return self.code

    def __hash__(self):
        return hash(self.code)

    def __eq__(self, other):
        if isinstance(other, self.__class__) and self.code == other.code:
            return True
        return False

    def __ne__(self, other):
        return not self == other


def get_source_language(project):
    return Language(project['source_language'])


def get_destination_languages(project):
    for target_data in project['target_languages']:
        yield Language(target_data)

