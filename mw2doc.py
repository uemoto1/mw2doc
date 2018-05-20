#!/usr/bin/env python3
import sys
import os.path
import re
import json
import tempfile
import subprocess
import getpass
import optparse
import http.cookiejar
import urllib.request
import urllib.parse


class MediaWikiAPI:

    def __init__(self, wikiroot):
        self.api_php = urllib.request.urljoin(wikiroot, "api.php")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def _call_api(self, **kwargs):
        api_args = urllib.parse.urlencode(kwargs).encode('utf-8')
        data = json.loads(self.opener.open(self.api_php, api_args).read())
        if 'info' in data:
            sys.stderr.write('[INFO] %s\n' % data['info'])
        if 'warnings' in data:
            sys.stderr.write('[WARNINGS] %s\n' % data['warnings'])
        if 'error' in data:
            sys.stderr.write('[ERROR] %s\n' % data['error'])
            sys.exit(-1)
        return data

    def login(self, username, password):
        token = self._call_api(
            action='login', format='json',
            lgname=username,
        )
        data = self._call_api(
            action='login', format='json',
            lgname=username, lgpassword=password,
            lgtoken=token['login']['token']
        )
        if data['login']['result'] == 'Success':
            sys.stderr.write('[SUCCESS] Login as "%s" (%d)\n' % (
                data['login']['lgusername'], data['login']['lguserid']
            ))
        else:
            sys.stderr.write('[ERROR] Password Rejected\n')
            sys.exit(-1)

    def get_pageid(self, title_list):
        data = self._call_api(
            action='query', format='json',
            titles='|'.join(title_list)
        )
        normalized_table = {
            item['from']: item['to']
            for item in data['query'].get('normalized', {})
        }
        pageid_table = {
            item['title']: pageid
            for pageid, item in data['query']['pages'].items()
        }
        result = [
            pageid_table[normalized_table.get(title, title)]
            for title in title_list
        ]
        return result

    def escaped_title(self, title):
        return re.sub(r"\s+", "_", title)

    def get_content(self, pageid_list):
        # Call MediaWiki API
        data = self._call_api(
            action='query', format='json',
            prop='revisions', rvprop='content',
            pageids='|'.join(pageid_list)
        )
        pages = data['query']['pages']
        result = [
            (pages[pageid]['title'],  pages[pageid]['revisions'][-1]['*'])
            for pageid in pageid_list
        ]
        return result

    def get_images(self, pageid_list):
        data = self._call_api(
            action='query', format='json',
            prop='images', imlimit=500,
            pageids="|".join(pageid_list)
        )
        pages = data['query']['pages']
        result = [
            [item['title'] for item in pages[pageid].get('images', {})]
            for pageid in pageid_list
        ]
        return result

    def get_image_url(self, pageid_list):
        data = self._call_api(
            action='query', format='json',
            prop='imageinfo', iiprop='url',
            pageids="|".join(pageid_list)
        )
        pages = data['query']['pages']
        result = [
            pages[pageid]['imageinfo'][-1]['url']
            for pageid in pageid_list
        ]
        return result


class Document:

    ptn_content = re.compile(r"([#\*]+)\s*(\[\[(.+?)(\|.+?)?\]\]|.+)")
    ptn_heading = re.compile("(=+)\s*(.*?)\s*(=+)")

    def __init__(self, mediawiki, title='', keyword='Contents'):
        self.mwapi = mediawiki
        self.keyword = keyword
        self.root_title = title
        self._content_tbl = []
        self._buff = []

    def _import_page(self, code, baselevel=2):
        for line in code.splitlines():
            m_heading = self.ptn_heading.search(line.strip())
            if m_heading:
                level = len(m_heading[1])
                title = m_heading[2]
                tag = "=" * (level + baselevel - 1)
                self._buff += [" ".join([tag, title, tag])]
                continue
            self._buff += [line.rstrip()]

    def _parse_content_tbl(self, code):
        self.content_tbl = []
        parse_flag = False
        for line in code.splitlines():
            m_heading = self.ptn_heading.search(line)
            if m_heading:
                parse_flag = (m_heading.group(2) == self.keyword)
                continue
            if parse_flag:
                m_content = self.ptn_content.search(line)
                if m_content:
                    level = len(m_content.group(1)) + 1
                    if m_content.group(3) is None:
                        title = ""
                        alias = m_content.group(2).strip()
                    elif m_content.group(4) is None:
                        title = m_content.group(3).strip()
                        alias = title
                    else:
                        title = m_content.group(3).strip()
                        alias = m_content.group(4).strip()
                    self._content_tbl += [(level, title, alias)]

    def _get_filetitles(self, pageid):
        [filetitle_list] = self.mwapi.get_images([pageid])
        file_pageid_list = self.mwapi.get_pageid(filetitle_list)
        temp_title_list, temp_pageid_list = [], []

        for filetitle, file_pageid in zip(filetitle_list, file_pageid_list):
            if int(file_pageid) > 0:
                etitle = self.mwapi.escaped_title(filetitle)
                temp_title_list += [etitle]
                temp_pageid_list += [file_pageid]

        temp_url_list = self.mwapi.get_image_url(temp_pageid_list)

        for temp_title, temp_url in zip(temp_title_list, temp_url_list):
            self.database[temp_title.lower()] = temp_url

    def download_figs(self, pardir):
        filename_list = []
        for title, url in self.database.items():
            if re.match('(file:|media:).*', title, re.I):
                if title.endswith('.png') or title.endswith('.jpeg'):
                    filename = os.path.join(pardir, url.split('/')[-1])
                    urllib.request.urlretrieve(url, filename)
                    filename_list += [filename]

    def generate(self, code=''):

        if not code:
            [root_pageid] = self.mwapi.get_pageid([self.root_title])
            [(_, code)] = self.mwapi.get_content([root_pageid])

        self._parse_content_tbl(code)

        self.database = {}

        for level, title, alias in self._content_tbl:
            tag = '=' * level
            self._buff += [' '.join([tag, alias, tag])]
            if title:
                sys.stdout.write("R: %s\n" % title)
                [pageid] = self.mwapi.get_pageid([title])

                if int(pageid) < 0:
                    sys.stdout.write("E: %s\n" % title)
                    sys.exit(-1)

                [(item, content)] = self.mwapi.get_content([pageid])
                self._import_page(content, level)
                etitle = self.mwapi.escaped_title(item)
                self.database[etitle.lower()] = alias

                self._get_filetitles(pageid)

    def export(self):
        ptn_link = re.compile(
            r"\[\[\s*(media:|file:)?\s*(.*?)\s*(#.*?)?(\|.*?)?\s*\]\]", re.I)
        self.refs = set([])

        def rule(m):
            title = m[2]
            if m[3] is None:
                section = ""
            else:
                section = m[3]
            if m.group(4) is None:
                alias = title
            else:
                alias = m.group(4)[1:]
            if m[1] is None:
                if section:
                    result = "[[%s|%s]]" % (section, alias)
                else:
                    etitle = self.mwapi.escaped_title(title)
                    if etitle.lower() in self.database:
                        result = "[[%s%s|%s]]" % (title, section, alias)
                    else:
                        url = "https://salmon-tddft.jp/wiki/%s" % etitle
                        result = '%s<ref>%s</ref>' % (alias, url)
            else:
                etitle = self.mwapi.escaped_title(title)
                if etitle.endswith(".png") or etitle.endswith(".jpeg"):
                    result = "[[File:%s]]" % title
                else:
                    url = "https://salmon-tddft.jp/wiki/File:%s" % etitle
                    result = '%s<ref>%s</ref>' % (alias, url)
            return result

        return "\n".join(
            [ptn_link.sub(rule, line) for line in self._buff]
        ) + "\n=References=\n"


code = """


== Contents == 
# Theoretical Background
## [[Samples|Sample Codes]]
"""


def main():

    parser = optparse.OptionParser()
    parser.add_option("-u", "--username", dest="username",
                      default="", type=str, help="Login User")
    parser.add_option("-p", "--password", dest="password",
                      default="", type=str, help="Login Password")
    parser.add_option("-o", "--outdir", dest="outdir",
                      default=os.curdir, help="Output Directory")
    parser.add_option("-q", "--quiet", dest="quiet",
                      default=False, action="store_true", help="No Message")
    opts, args = parser.parse_args()

    mwapi = MediaWikiAPI("https://salmon-tddft.jp/mediawiki/api.php")
    
    if opts.username:
        # Request Password
        if opts.password:
            password = opts.password
        else:
            password = getpass.getpass()
        # Login
        mwapi.login(opts.username, password)
    
    doc = Document(mwapi)
    doc.generate(code)

    with tempfile.TemporaryDirectory() as tempdir:
        file_mw = os.path.join(tempdir, 'document.mw')
        file_tex = os.path.join(tempdir, 'document.tex')
        file_docx = os.path.join(tempdir, 'document.docx')

        with open(file_mw, 'w') as fh_mw:
            fh_mw.write(doc.export())
            doc.download_figs(tempdir)

        subprocess.call([
            'pandoc',
            '-f', 'mediawiki',
            '-i', file_mw,
            '-o', file_tex,
            '-s',
            '--table-of-contents',
            '--number-sections',
        ], cwd=tempdir)

        subprocess.call([
            'pandoc',
            '-f', 'mediawiki',
            '-i', file_mw,
            '-o', file_docx,
        ], cwd=tempdir)
        os.rename(file_docx, "output.docx")


if __name__ == '__main__':
    main()
