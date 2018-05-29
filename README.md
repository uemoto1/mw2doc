# mw2doc
Convert the documentation in mediawiki to local document files

## Requirements
* Python 3
* pandoc (https://pandoc.org)

## Usage of this program

To execute , enter following command on your command line:
```
mw2doc.py
```
If execution privilege is not given to the script file, you would run python with giving the script file as a argument:
```
python3 mw2doc.py
```
The program asks your username and password to the editor account of the wiki.

By default, this program reads `default.json` as an input file.
If necessary, users can rewrite `default.json` for their environment.
```
{
   "wiki_api": "https://salmon-tddft.jp/mediawiki/api.php",
   "wiki_ prefix": "https://salmon-tddft.jp/wiki/",
   "rootpage_title": "DevOnly: New_Manual",
   "template_tex": "template.tex"
}
```
The input file is structured in standard JSON format ().
Each item of the top-level dictionary object has been shown in the table:

| Key        | Detail           | 
| ------------- |:-------------:| 
| `wiki_api` | URI to `api.phi` | 
| `wiki_prefix` | URI prefix to mediawiki pages | 
| `rootpage_title` | title of the page having the table of contents | 
| `template_tex` | path to the template file of tex output |
 
To use an your own input file, specify the `-i` option to execute.
For example, if you create `mydoc.json` based on a copy of` default.json`, enter:
```
python3 mw2doc.py - i mydoc.json
```
