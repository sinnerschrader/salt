# -*- coding: utf-8 -*-
'''
Module for managing locales on POSIX-like systems.
'''
from __future__ import absolute_import

# Import python libs
import logging
import re

# Import salt libs
import salt.utils
import salt.ext.six as six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'locale'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return __virtualname__


def _parse_localectl():
    '''
    Get the 'System Locale' parameters from localectl
    '''
    ret = {}
    for line in __salt__['cmd.run']('localectl').splitlines():
        cols = [x.strip() for x in line.split(':', 1)]
        if len(cols) > 1:
            cur_param = cols.pop(0)
        if cur_param == 'System Locale':
            try:
                key, val = re.match('^([A-Z_]+)=(.*)$', cols[0]).groups()
            except AttributeError:
                log.error('Odd locale parameter "{0}" detected in localectl '
                          'output. This should not happen. localectl should '
                          'catch this. You should probably investigate what '
                          'caused this.'.format(cols[0]))
            else:
                ret[key] = val.replace('"', '')
    return ret


def _localectl_get():
    '''
    Use systemd's localectl command to get the current locale
    '''
    return _parse_localectl().get('LANG', '')


def _localectl_set(locale=''):
    '''
    Use systemd's localectl command to set the LANG locale parameter, making
    sure not to trample on other params that have been set.
    '''
    locale_params = _parse_localectl()
    locale_params['LANG'] = str(locale)
    args = ' '.join(['{0}="{1}"'.format(k, v)
                     for k, v in six.iteritems(locale_params)])
    cmd = 'localectl set-locale {0}'.format(args)
    return __salt__['cmd.retcode'](cmd) == 0


def list_avail():
    '''
    Lists available (compiled) locales

    CLI Example:

    .. code-block:: bash

        salt '*' locale.list_avail
    '''
    cmd = 'locale -a'
    out = __salt__['cmd.run'](cmd).split('\n')
    return out


def get_locale():
    '''
    Get the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.get_locale
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        return _localectl_get()
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/sysconfig/i18n'
    elif 'Debian' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/default/locale'
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale show'
        return __salt__['cmd.run'](cmd).strip()

    try:
        return __salt__['cmd.run'](cmd).split('=')[1].replace('"', '')
    except IndexError:
        return ''


def set_locale(locale):
    '''
    Sets the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.set_locale 'en_US.UTF-8'
    '''
    if 'Arch' in __grains__['os_family']:
        return _localectl_set(locale)
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/i18n', '^LANG=.*', 'LANG="{0}"'.format(locale)
        )
        __salt__['cmd.run'](
            'grep "^LANG=" /etc/sysconfig/i18n || echo "\nLANG={0}" '
            '>> /etc/sysconfig/i18n'.format(locale)
        )
    elif 'Debian' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/default/locale', '^LANG=.*', 'LANG="{0}"'.format(locale)
        )
        __salt__['cmd.run'](
            'grep "^LANG=" /etc/default/locale || '
            'echo "\nLANG={0}" >> /etc/default/locale'.format(locale)
        )
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale set {0}'.format(locale)
        return __salt__['cmd.retcode'](cmd) == 0

    return True


def _normalize_locale(locale):
    lang_encoding = locale.split('.')
    lang_split = lang_encoding[0].split('_')
    if len(lang_split) > 1:
        lang_split[1] = lang_split[1].upper()
    lang_encoding[0] = '_'.join(lang_split)
    if len(lang_encoding) > 1:
        if len(lang_split) > 1:
            lang_encoding[1] = lang_encoding[1].lower().replace('-', '')
    return '.'.join(lang_encoding)


def avail(locale):
    '''
    Check if a locale is available

    CLI Example:

    .. code-block:: bash

        salt '*' locale.avail 'en_US.UTF-8'
    '''
    normalized_locale = _normalize_locale(locale)
    avail_locales = __salt__['locale.list_avail']()
    locale_exists = next((True for x in avail_locales
       if _normalize_locale(x.strip()) == normalized_locale), False)
    return locale_exists


def gen_locale(locale):
    '''
    Generate a locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.gen_locale 'en_US.UTF-8'
    '''
    if __grains__.get('os') == 'Debian':
        __salt__['file.replace'](
            '/etc/locale.gen',
            '# {0} '.format(locale),
            '{0} '.format(locale),
            append_if_not_found=True
        )
        __salt__['cmd.run'](
            'locale-gen {0}'.format(locale)
        )
    elif __grains__.get('os') == 'Ubuntu':
        __salt__['file.touch'](
            '/var/lib/locales/supported.d/{0}'.format(locale.split('_')[0])
        )
        __salt__['file.append'](
            '/var/lib/locales/supported.d/{0}'.format(locale.split('_')[0]),
            '{0} {1}'.format(locale, locale.split('.')[1])
        )
        __salt__['cmd.run'](
            'locale-gen'
        )

    return True
