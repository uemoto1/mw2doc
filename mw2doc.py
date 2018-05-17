#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json


class MediaWikiAPI:

    def __init__(self, wikiroot):
        self.api_php = urllib.response.urljoin(wikiroot, "api.php")
        self.index_php = urllib.response.urljoin(wikiroot, "index.php")

    def _call_api(self, **kwargs):
        api_args = urllib.parse.urlencode(kwargs).encode('utf-8')
        request = urllib.request.Request(self.api_addr, api_args)
        with urllib.request.urlopen(request) as response:
            if response.getcode() != 200:
                raise ValueError('Fail to connect "%s"' % self.api_addr)
            data = response.read()
        return data

    def get_content(self, title):
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='revisions', rvprop='content',
            titles=title
        ))
        pages = data['query']['pages']
        page = pages[pages.keys()[0]]
        title = page['title']
        if 'missing' in page:
            raise ValueError('Page "%s" is not found' % title)
        for revision in page['revisions']:
            content = revision['*']
        return title, content

    def get_images(self, title):
        data = json.loads(self._call_api(
            action='query', format='json',
            prop='revisions', rvprop='content',
            titles=title
        ))
        pages = data['query']['pages']
        page = pages[pages.keys()[0]]
        title = page['title']
        if 'missing' in page:
            raise ValueError('Page "%s" is not found' % title)
        for revision in page['revisions']:
            content = revision['*']
        return title, content
    
    def save_uploaded_file(self, title, filename):
        special_page = "%s?Special:Filepath/%s" % (self.index_php, title)
        with urllib.request.urlopen(special_page) as response:
            with open(filename, "wb") as fh:
                fh.write(response.read())
    


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
