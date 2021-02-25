#!/usr/bin/python3

from enum import Enum
import xml.etree.ElementTree as ET
import re
import string
from io import StringIO
import os

TEMPLATE_CHAPTER_XML = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/, se: https://standardebooks.org/vocab/1.0" xml:lang="en-US">
  <head>
    <title>
      The Devil's Dictionary, by Ambrose Bierce
    </title>
    <link href="../css/core.css" rel="stylesheet" type="text/css"/>
    <link href="../css/local.css" rel="stylesheet" type="text/css"/>
  </head>
  <body epub:type="bodymatter z3998:fiction">
    <section epub:type="chapter" />
  </body>
</html>
""".strip()

STORIES = [
    'ABRIDGE', 'ARREST', 'BOUNTY', 'CEMETERY', 'CRAYFISH', 'ELECTRICITY', 'EPIGRAM', 'EXILE',
    'INTRODUCTION', 'MORAL', 'RELIGION', 'RESPLENDENT', 'RIGHTEOUSNESS', 'SAW', 'SCIMITAR', 'TREE',
    'WOMAN', 'YOUTH'
]

MATCH_STORY = re.compile(f"({'|'.join(STORIES)})")

PLAYS = [
    'EXECUTIVE', 'INSURANCE'
]

MATCH_PLAY = re.compile(f"({'|'.join(PLAYS)})")

ET.register_namespace('epub', 'http://www.idpf.org/2007/ops')

class Classification(Enum):
    DEFN = 'defn'
    LETR = 'letr'
    NAME = 'name'
    QUOT = 'quot'
    RAW = 'raw'
 
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

def titlecase_word(word):
    word = word.lower()
    word = re.sub('(?<=[ -])(\w)', lambda x: x[1].upper(), word)
    word = word[0].upper() + word[1:]
    return word

def split_word(word):
    PART_OF_SPEECH_MAP = {
        "n.":       ["noun"],
        "adj.":     ["adjective"],
        "v.t.":     ["verb-transitive"],
        "v.i.":     ["verb-intransitive"],
        "adv.":     ["adverb"],
        "pp.":      ["past-participle"],
        "p.p.":     ["past-participle"],
        "v.":       ["verb"],
        "pro.":     ["pronoun"],
        "pron.":    ["pronoun"],
        "x.":       ["unknown"],
        "n.pl.":    ["noun-plural"],
        "adj. and n.": ['adjective', 'noun'],
    }

    # Special cases
    if word[:4] == 'BABE':
        return (['Babe', 'Baby'], ['noun'])
    if word[:6] == 'TZETZE':
        return (['Tzetze Fly', 'Tsetse Fly'], ['noun'])
    if word[:9] == 'CONFIDANT':
        return (['Confidant', 'Confidante'], ['noun'])

    # Cui Bono?
    if word[-1] == '?':
        return ([titlecase_word(word[:-1])], ['question'])

    bits = word.split(',')
    if len(bits) == 1:
        return ([titlecase_word(word.strip('.'))], None)

    return ([titlecase_word(bits[0])], PART_OF_SPEECH_MAP[bits[1].strip()])

def classify_paragraph(current_letter, text):
    if re.match('[A-Z\-\ \']+, [avnpx]', text):
        return Classification.DEFN
    if re.match('(ABRACADABRA|BABE|CONFIDANT|CUI BONO|FORMA|HABEAS|LL\.D|R\.I\.P|TZETZE)', text):
        return Classification.DEFN
    if text[0:3] == f"{current_letter}, ":
        return Classification.LETR
    if text[0:5] == f"{current_letter} is ":
        return Classification.LETR
    if text[0:5] == f"{current_letter} in ":
        return Classification.LETR
    if text[0:3] == f"{current_letter} (":
        return Classification.LETR
    if text == 'Blary O\'Gary' or text == '(Old play)' or text == 'Thomas M. and Mary Frazer' or text == 'Rev. Dr. Mucker':
        return Classification.NAME
    if text[0:20] == '"The Mad Philosopher':
        return Classification.NAME
    if text[0:20] == '"The Devil on Earth"':
        return Classification.NAME
    if text == '"Chronicles of the Classes"' or text == '"The Sturdy Beggar"':
        return Classification.NAME
    if text == "Gooke's Meditations" or text[0:9] == "Trauvells" or text[0:9] == "Biography":
        return Classification.NAME
    if re.match('^[A-Z]\.[A-Z]\.$', text):
        return Classification.NAME
    if re.match('^[A-Z]\.[A-Z]\. [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z]\.[A-Z]\.[A-Z]\.$', text):
        return Classification.NAME
    if re.match('^[A-Z][a-z]+ [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z][a-z]+ (the|de) [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z]\. [A-Z][a-z]+ [A-Z][a-z]+$', text):
        return Classification.NAME
    if re.match('^[A-Z][a-z]+$', text):
        return Classification.NAME
    return Classification.QUOT

def collect_text(elem):
    s = ""
    s += elem.text.strip()
    for child in elem:
        if child.text:
            s += child.text.strip()
        if child.tail:
            s += child.tail.strip()
    return s

def process_defn(tag):
    s = collect_text(tag)

    word = None
    if s[0:5] == 'LL.D.':
        word = 'LL.D.'
    elif (match := re.match('^([A-Z\ ]+\?) ', s)):
        word = match[1]
    elif (match := re.match('^[A-Z]+\.$', s)):
        word = match[0]
    elif (match := re.match('^[A-Z]+, ([a-z]+\.)+$', s)):
        word = match[0]
    elif (match := re.match('^[A-Z]+, [a-z]+\. and [a-z]+\.', s)):
        word = match[0]
    elif (match := re.match('^[A-Z\ \-]+, ([a-z]+\.)+', s)):
        word = match[0]
    else:
        match = re.match('^(.*?\.) ', s)
        word = match[1]

    # print(word)

    # Now, remove the actual definition from the remainder
    tag.text = tag.text.lstrip()[len(word):].lstrip()
    # print(tag.text)

    if len(tag.text) > 0:
        if tag.text[0] in string.ascii_lowercase:
            throw("Unexpected lowercase char in definition")

    return word

root = parse_attrns('src/epub/text/body.xhtml').getroot()
body = root.find('.//{http://www.w3.org/1999/xhtml}body')

entries = {}
current_letter = None
current_entry = None
definition_count = 0
letter_count = 0
max_indent = 0
current_word = None

for child in body:
    if child.tag == '{http://www.w3.org/1999/xhtml}h1':
        current_word = None
        letter = child.text.strip()
        if len(letter) == 1:
            current_letter = letter
            entries[current_letter] = []
            current_entry = None
            # print(f"{current_letter}")
        continue
    if not current_letter:
        continue

    if child.tag == '{http://www.w3.org/1999/xhtml}pre':
        # Make sure we don't have any definitions jammed into <pre> blocks
        if not MATCH_PLAY.match(current_word):
            assert(not re.match('^[A-Z][A-Z][A-Z]', child.text.strip()))

        # Collect text
        s = ""
        s += child.text
        for child in child:
            s += f"<em>{child.text}</em>"
            s += child.tail

        lines = s.split('\n')
        while len(lines[0].strip()) == 0:
            lines.pop(0)
        while len(lines[-1].strip()) == 0:
            lines.pop()

        blockquote = ET.SubElement(child, '{http://www.w3.org/1999/xhtml}blockquote')

        if MATCH_STORY.match(current_word):
            blockquote.attrib["{http://www.idpf.org/2007/ops}type"] = "se:short-story"
            p = ET.SubElement(blockquote, '{http://www.w3.org/1999/xhtml}p')
            p.text = ''
            first = True
            for s in lines:
                indent = s[:3] == '   ' and not first
                if len(s) == 0 or indent:
                    p = ET.SubElement(blockquote, '{http://www.w3.org/1999/xhtml}p')
                    p.text = ''
                    first = True
                    if indent:
                        print(f"Probably an indent for {current_word}")
                    else:
                        continue

                first = False
                p.text += s
        else:
            blockquote.attrib["{http://www.idpf.org/2007/ops}type"] = "z3998:poem"

            p = ET.SubElement(blockquote, '{http://www.w3.org/1999/xhtml}p')
            first = True
            for s in lines:
                if len(s) == 0:
                    p = ET.SubElement(blockquote, '{http://www.w3.org/1999/xhtml}p')
                    first = True
                    continue
                if not MATCH_PLAY.match(current_word):
                    if len(s.strip()) > 60:
                        print('LONG: ' + current_word) 
                if first:
                    first = False
                else:
                    ET.SubElement(p, '{http://www.w3.org/1999/xhtml}br')
                indent = (len(s) - len(s.lstrip()) - 2)
                if indent % 4 != 0:
                    print(indent)
                    print(s)
                indent = indent // 4
                span = ET.SubElement(p, '{http://www.w3.org/1999/xhtml}span')
                if indent > 0:
                    span.attrib["{http://www.w3.org/1999/xhtml}class"] = f"i{indent}"
                max_indent = max(indent, max_indent)
                span.text = s.strip()

        # Replace blockquote with the child
        child = blockquote            
        current_entry.append([classified, child])
        pass
    if child.tag == '{http://www.w3.org/1999/xhtml}p':
        text = collect_text(child)
        if len(text) == 0:
            continue
        classified = classify_paragraph(current_letter, text)
        if classified == Classification.LETR:
            letter_count += 1
            assert(current_entry == None)
            entries[current_letter].append([[classified, child]])
            continue
        if classified == Classification.DEFN:
            definition_count += 1
            current_entry = []
            entries[current_letter].append(current_entry)
            current_word = process_defn(child)
        if classified == Classification.NAME:
            # Note that most names are pseudonyms:
            # https://donswaim.com/bierce-pseudonyms.html
            child = ET.SubElement(child, "{http://www.w3.org/1999/xhtml}cite")
            child.text = f"—{text}"
            # print(text)
        current_entry.append([classified, child, current_word])

print(f"{definition_count} definitions found")
print(f"{letter_count} letter definitions found")
print(f"{max_indent} max indent")

chapter = 0
for c in string.ascii_uppercase:
    chapter += 1
    template = parse_attrns(StringIO(TEMPLATE_CHAPTER_XML)).getroot()
    section = template.find('.//{http://www.w3.org/1999/xhtml}section')
    section.attrib['{http://www.w3.org/1999/xhtml}id'] = f'chapter-{chapter}'

    template.find('.//{http://www.w3.org/1999/xhtml}title').text = c.upper()

    h2 = ET.SubElement(section, "{http://www.w3.org/1999/xhtml}h2")
    h2.attrib['{http://www.idpf.org/2007/ops}type'] = 'title'
    h2.text = c.upper()

    dl = ET.SubElement(section, "{http://www.w3.org/1999/xhtml}dl")
    for entry in entries[c]:
        if entry[0][0] == Classification.DEFN:
            word = entry[0][2]
            word, part_of_speech = split_word(word)
            for word in word:
                dt = ET.SubElement(dl, "{http://www.w3.org/1999/xhtml}dt")
                dfn = ET.SubElement(dt, "{http://www.w3.org/1999/xhtml}dfn")
                dfn.text = word
                if part_of_speech:
                    dt.attrib['{http://www.w3.org/1999/xhtml}class'] = f"{' '.join(part_of_speech)}"
            dd = ET.SubElement(dl, "{http://www.w3.org/1999/xhtml}dd")
            
            for elem in entry:
                e = elem[1]
                if e.tag == '{http://www.w3.org/1999/xhtml}p':
                    if len(e.text.strip()) == 0 and len(list(e)) == 0:
                        print(f"skipping empty p for {word}")
                        continue
                dd.append(e)

            changed = True
            while changed:
                changed = False
                index = 0
                for elem in list(dd)[:-1]:
                    if elem.tag == '{http://www.w3.org/1999/xhtml}blockquote' and dd[index + 1].tag == '{http://www.w3.org/1999/xhtml}cite':
                        elem[-1].tail = ' '
                        elem.append(dd[index + 1])
                        dd.remove(dd[index + 1])
                        changed = True
                        break
                    index += 1

        else:
            print(f"Header for {c}")
            header = ET.SubElement(section, "{http://www.w3.org/1999/xhtml}header")
            header.append(h2)
            entry[0][1].attrib['{http://www.idpf.org/2007/ops}type'] = 'epigraph'
            header.append(entry[0][1])
            section.remove(h2)
            section.remove(header)
            section.insert(0, header)

    if len(list(dl)) == 0:
        section.remove(dl)

    output = ET.tostring(template, encoding="utf-8", default_namespace="http://www.w3.org/1999/xhtml")
    output = output.replace(b"&lt;em&gt;", b"<em>")
    output = output.replace(b"&lt;/em&gt;", b"</em>")
    # ET.ElementTree(template).write(f"src/epub/text/{c}.xhtml", default_namespace="http://www.w3.org/1999/xhtml")
    open(f"src/epub/text/{c.lower()}.xhtml", 'wb').write(output)

all_files = ' '.join([f"src/epub/text/{c}.xhtml" for c in string.ascii_lowercase]);
os.system(f"~/.local/bin/se clean {all_files}")

