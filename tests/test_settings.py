import os

import pytest

from qordoba.settings import load_settings, SettingsError, get_project_file_formats


@pytest.fixture
def env_config_path(curdir):
    root = os.path.abspath(curdir)
    return os.path.join(root, 'fixtures', 'qordoba_env.yml')


@pytest.fixture
def mock_env_config_path(monkeypatch, env_config_path):
    monkeypatch.setenv('QORDOBA_CONFIG', env_config_path)
    monkeypatch.setattr('qordoba.settings.SETTING_PATHS', (env_config_path,
                                                           os.path.abspath(os.path.join(os.getcwd(), '.qordoba.yml')),
                                                           os.path.abspath(
                                                               os.path.join(os.path.expanduser('~'), '.qordoba.yml'))
                                                           ))


@pytest.fixture
def mock_change_dir(monkeypatch, curdir):
    root = os.path.abspath(curdir)
    chdir_path = os.path.join(root, 'fixtures')
    monkeypatch.chdir(chdir_path)
    monkeypatch.setattr('qordoba.settings.SETTING_PATHS', (
        os.environ.get('QORDOBA_CONFIG', ''),
        '.qordoba.yml',
        os.path.abspath(os.path.join(os.path.expanduser('~'), '.qordoba.yml')))
                        )


def test_load_settings_env(mock_env_config_path):
    config, loaded = load_settings()

    assert loaded == True
    assert config['access_token'] == 'aaaaaaa-bbbb-cccc-dddd-fffffffff'
    assert config['project_id'] == 1111
    assert 'push' not in config


def test_load_settings_not_exist():
    test_access_token = '22'
    test_project_id = 33

    config, loaded = load_settings(access_token=test_access_token, project_id=test_project_id)
    assert loaded == False
    assert config['access_token'] == test_access_token
    assert config['project_id'] == test_project_id


def test_load_settings_error():
    with pytest.raises(SettingsError):
        _, _ = load_settings()


def test_load_settings(mock_change_dir):
    config, loaded = load_settings()

    assert loaded is True
    assert config['access_token'] == 'aaaaaaa-bbbb-cccc-dddd-fffffffff'
    assert config['project_id'] == 1111
    assert 'push' in config
    assert 'sources' in config['push']
    assert 'sources/*' == config['push']['sources'][0]['file']


def test_load_settings_overrite(mock_change_dir):
    test_access_token = '22'
    test_project_id = 33
    config, loaded = load_settings(access_token=test_access_token, project_id=test_project_id)

    assert loaded is True
    assert config['access_token'] == test_access_token
    assert config['project_id'] == test_project_id


def test_get_project_file_formats(mock_change_dir):
    settings, loaded = load_settings(access_token='22', project_id='33')
    settings['file_formats'] = {
        'resx': 'resx'
    }
    result = get_project_file_formats(settings)
    assert result['resx'] == 'resx'
