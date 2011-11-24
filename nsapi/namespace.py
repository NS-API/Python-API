from xml.etree import cElementTree as ET
import copy

def prefix_xmlns(elem):
    xml_with_ns = copy.deepcopy(elem)
    set_prefixes(xml_with_ns, dict(nsapi="http://openov.nl/protocol/nsapi"))
    return xml_with_ns

def set_prefixes(elem, prefix_map):
    # check if this is a tree wrapper
    if not ET.iselement(elem):
        elem = elem.getroot()

    # build uri map and add to root element
    uri_map = {}
    for prefix, uri in prefix_map.items():
        uri_map[uri] = prefix
        elem.set("xmlns:" + prefix, uri)

    # fixup all elements in the tree
    memo = {}
    for elem in elem.getiterator():
        fixup_element_prefixes(elem, uri_map, memo)

    return elem

def fixup_element_prefixes(elem, uri_map, memo):
    def fixup(name):
        try:
            return memo[name]
        except KeyError:
            if name[0] != "{":
                new_name = uri_map[uri_map.keys()[0]] + ":" + name
                memo[name] = new_name
                return new_name
            uri, tag = name[1:].split("}")
            if uri in uri_map:
                new_name = uri_map[uri] + ":" + tag
                memo[name] = new_name
                return new_name
    # fix element name
    name = fixup(elem.tag)
    if name:
        elem.tag = name
    # fix attribute names
    #for key, value in elem.items():
    #    if not key.startswith('xmlns'):
    #        name = fixup(key)
    #        if name != key:
    #            elem.set(name, value)
    #            del elem.attrib[key]
