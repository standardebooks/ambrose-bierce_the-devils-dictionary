#!/usr/bin/python3

from enum import Enum
import xml.etree.ElementTree as ET
import re
import string
from io import StringIO
import os

PART_OF_SPEECH_MAP = {
    "?":        "question",
    ", n.":       "noun",
    ", adj.":     "adjective",
    ", v.t.":     "verb-transitive",
    ", v.i.":     "verb-intransitive",
    ", adv.":     "adverb",
    ", pp.":      "past-participle",
    ", v.":       "verb",
    ", pro.":     "pronoun",
    ", x.":       "unknown",
    ", n.pl.":    "noun-plural",
    ", adj. and n.": 'adjective noun',
}
PART_OF_SPEECH_INVERTED_MAP = {v: k for k, v in PART_OF_SPEECH_MAP.items()}

def parse_attrns(file):
    """Parse file to ElementTree instance. Patch non-prefixed attributes
    with the namespace of the element they belong to.
    """
    events = ("start", )
    root = None
    for event, elem in ET.iterparse(file, events):
        if event == "start":
            if root is None:
                root = elem
            if elem.tag.find("}") < 0:
                continue
            # inherit the uri from the element
            uri, _ = elem.tag[1:].rsplit("}", 1)
            for k, v in elem.attrib.copy().items():
                if k[:1] != "{":
                    # replace the old attribute with a
                    # namespace-prefixed one
                    del elem.attrib[k]
                    k = "{%s}%s" % (uri, k)
                    elem.attrib[k] = v
    return ET.ElementTree(root)

def recurse_text(node):
    s = ""
    if node.tag == '{http://www.w3.org/1999/xhtml}h1':
        s += "."
    if node.text:
        s += node.text
    if node.tag == '{http://www.w3.org/1999/xhtml}dfn':
        s = s.upper()
    if node.tag == '{http://www.w3.org/1999/xhtml}cite' and s[0] == '—':
        s = s[1:]

    for child in node:
        s += " "
        s += recurse_text(child)
        if child.tail:
            s += " "
            s += child.tail

    if node.tag == '{http://www.w3.org/1999/xhtml}dt':
        if '{http://www.w3.org/1999/xhtml}class' in node.attrib:
            clazz = node.attrib['{http://www.w3.org/1999/xhtml}class']
            s += PART_OF_SPEECH_INVERTED_MAP[clazz]
        else:
            s += '.'

    return s

def generate_comparable(s):
    s = re.sub('\n', ' ', s)
    s = re.sub('\s\s+', ' ', s)
    s = re.sub(' ,', ',', s)
    return '\n'.join([s.strip() for s in s.split('.')])

def load_xml(file):
    root = parse_attrns(file).getroot()
    body = root.find('.//{http://www.w3.org/1999/xhtml}body')
    return body

c1 = generate_comparable(recurse_text(load_xml('src/epub/text/body.xhtml')))
c2 = '\n'.join(
    [generate_comparable(recurse_text(load_xml(f'src/epub/text/{c}.xhtml'))) for c in string.ascii_uppercase]
)

open('/tmp/c1', 'w').write(c1)
open('/tmp/c2', 'w').write(c2)
