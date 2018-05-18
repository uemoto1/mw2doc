#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import re
import sys
import os.path
import tempfile
import subprocess


class MediaWikiAPI:

    def __init__(self, wikiroot):
        self.api_php = urllib.request.urljoin(wikiroot, "api.php")
        self.index_php = urllib.request.urljoin(wikiroot, "index.php")


    def _call_api(self, **kwargs):
        api_args = urllib.parse.urlencode(kwargs).encode('utf-8')
        request = urllib.request.Request(self.api_php, api_args)
        with urllib.request.urlopen(request) as response:
            if response.getcode() != 200:
                raise ValueError('Fail to connect "%s"' % self.api_php)
            data = response.read()
        return data

    def get_pageid(self, title_list):
        data = json.loads(self._call_api(
            action='query', format='json',
            titles='|'.join(title_list)
        ))
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
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='revisions', rvprop='content',
            pageids='|'.join(pageid_list)
        ))
        pages = data['query']['pages']
        result = [
            (pages[pageid]['title'],  pages[pageid]['revisions'][-1]['*'])
            for pageid in pageid_list
        ]
        return result

    def get_images(self, pageid_list):
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='images', imlimit=999,
            pageids="|".join(pageid_list)
        ))
        pages = data['query']['pages']
        result = [
            [item['title'] for item in pages[pageid].get('images', {})]
            for pageid in pageid_list
        ]
        return result

    def get_image_url(self, pageid_list):
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='imageinfo', iiprop='url',
            pageids="|".join(pageid_list)
        ))
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
                level = len(m_heading.group(1))
                title = m_heading.group(2)
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
        [file_title_list] = self.mwapi.get_images([pageid])
        file_pageid_list = self.mwapi.get_pageid(file_title_list)
        temp_title_list, temp_pageid_list = [], []

        for file_title, file_pageid in zip(file_title_list, file_pageid_list):
            if int(file_pageid) > 0:
                escaped_title = self.mwapi.escaped_title(file_title)
                temp_title_list += [escaped_title]
                temp_pageid_list += [file_pageid]

        temp_url_list = self.mwapi.get_image_url(temp_pageid_list)

        for temp_title, temp_url in zip(temp_title_list, temp_url_list):
            self.database[temp_title] = temp_url

    def download(self, pardir):
        for title, url in self.database.items():
            if title.startswith('file:'):
                if title.endswith('.png') or title.endswith('.jpeg'):
                    filename = os.path.join(pardir, url.split('/')[-1])
                    urllib.request.urlretrieve(url, filename)
                    sys.stdout.write("%s\n->%s" % (url, filename))

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
                escaped_title = self.mwapi.escaped_title(item)
                self.database[escaped_title] = alias

                self._get_filetitles(pageid)




    def export(self):
        ptn_link = re.compile(r"\[\[\s*(media:|file:)?\s*(.*?)\s*(#.*?)?(\|.*?)?\s*\]\]", re.I)
        
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
                
                e_title = self.mwapi.escaped_title(title)
                if e_title in self.database:
                    if section:
                        result = "[[%s|%s]]" % (section, alias)
                    else:
                        result = "[[%s|%s]]" % (title, alias)
                else:
                    result = "%s<ref>https://salmon-tddft.jp/wiki/%s</ref>" % (alias, e_title)

            
            else:
                e_title = self.mwapi.escaped_title(title)
                if e_title.endswith(".png") or e_title.endswith(".jpeg"):
                    result = m[0]
                else:
                    result = "%s<ref>https://salmon-tddft.jp/wiki/File:%s</ref>" % (alias, e_title)
                
            return result
        
        

        return "\n".join(
            [ptn_link.sub(rule, line) for line in self._buff]
        )


code = """


== Contents == 
# Theoretical Background
## [[Samples]]
"""


def main():

    mw = MediaWikiAPI("https://salmon-tddft.jp/mediawiki/api.php")
    doc = Document(mw)
    doc.generate(code)

    with tempfile.TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'mediawiki.txt'), 'w') as inpfile:
            inpfile.write(doc.export())
            doc.download(tempdir)
            
        subprocess.call([
            'pandoc', '-f', 'mediawiki',
            '-i', inpfile.name,
            '-o', sys.argv[1]
        ])


if __name__ == '__main__':
    main()
