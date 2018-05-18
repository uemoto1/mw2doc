#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import re


class MediaWikiAPI:

    def __init__(self, wikiroot):
        self.api_php = urllib.request.urljoin(wikiroot, "api.php")
        self.index_php = urllib.request.urljoin(wikiroot, "index.php")
    
    def _escaped_title(self, title):
        return '_'.join([
            item.capitalize() for item in re.split(r"\s+", title)
        ])

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
            for pageid in pageid_list: 
        ]
        return result
        
    def get_images(self, pageid_list):
        result = set([])
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='images', pageids="|".join(pageid_list)
        ))
        pages = data['query']['pages']
        for pageid in pageid_list:
            result (
                set([item['title'] for item in pages[pageid]['images']])
            )
        return list(result)
        
    def save_uploaded_file(self, title, filename):
        special_page = "%s?Special:Filepath/%s" % (self.index_php, title)
        with urllib.request.urlopen(special_page) as response:
            with open(filename, "wb") as fh:
                fh.write(response.read())

#api.php?action=query&titles=File:Albert%20Einstein%20Head.jpg&prop=imageinfo&&iiprop=ur

class Document:

    ptn_link = re.compile(r"([#\*]+)\s*(\[\[(.+?)(\|.+?)?\]\]|.+)")
    ptn_contents = re.compile(r"=+\s*Contents\s*=+", re.IGNORECASE)
    ptn_level = re.compile("(=+)\s*(.*?)\s*(=+)")

    def _parse_child_page(self, code, baselevel=1):
        buff = []
        for line in code.splitlines():
            result = ptn_level.match(line.strip())
            if result:
                level = len(result.group(1))
                title = result.group(2)
                tag = "=" * (level + baselevel - 1)
                buff += [" ".join([tag, title, tag])]
            else:
                buff += [line.rstrip()]
        return buff

    def _read_root_page(self, code):
        state = 0
        header, content_tbl, footer = [], [], []
        for line in code.splitlines():

            if state == 0:
                if ptn_key.search(line):
                    state = 1
                else:
                    header += [line]
                continue

            elif state == 1:

                result = ptn_link.match(line.strip())
                if result:
                    level = len(result.group(1)) + 1
                    if result.group(3) is None:
                        page = ""
                        title = result.group(2).strip()
                    elif result.group(4) is None:
                        page = result.group(3).strip()
                        title = page
                    else:
                        page = result.group(3).strip()
                        title = result.group(4).strip()
                    content_tbl += [(level, page, title)]
                else:
                    state = 2
                continue

            elif state == 2:
                footer += [line]
                continue

        return header, content_tbl, footer


def main():
    pass


if __name__ == '__main__':
    main()
