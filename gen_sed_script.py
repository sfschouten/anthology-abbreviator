#!/usr/bin/env python3

import os
from os.path import join
import logging
import itertools

import yaml
import regex as re 
from lxml import etree
from bs4 import BeautifulSoup

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger('acl-anthology-abbreviator')

ACL_ANTHOLOGY_URL = 'https://aclanthology.org/'

VENUES_PATH = 'acl-anthology/data/yaml/venues'
VOLUMES_PATH = 'acl-anthology/data/xml/'


def load_venues():
    """
    Loads venues from YAML files.
    """
    venues = {}

    for child in os.listdir(VENUES_PATH):

        child_path = os.path.join(VENUES_PATH, child)
        if not os.path.isfile(child_path):
            continue

        with open(child_path, 'r') as stream:
            try:
                yaml_contents = yaml.safe_load(stream)
            except yaml.YAMLError as e:
                logger.error(e)

        slug = child.split('.')[0]

        # add fields for later
        yaml_contents['volumes'] = []
        yaml_contents['years'] = {}

        venues[slug] = yaml_contents
        
    return venues


def load_volumes(all_venues):
    """
    Loads volumes from XML files.
    """
    rnc = etree.RelaxNG(file=os.path.join(VOLUMES_PATH, 'schema.rnc'))

    all_volumes = []

    for child in os.listdir(VOLUMES_PATH):
        child_path = os.path.join(VOLUMES_PATH, child)

        if not os.path.isfile(child_path) or not child.endswith('.xml'):
            continue
    
        pattern = r'(?P<key_old>[A-Z])(?P<year_old>\d{2})\.(?P<ext_old>.*)|(?P<year_new>\d{4})\.(?P<key_new>.*)\.(?P<ext_new>.*)'
        child_match = re.fullmatch(pattern, child)
        if child_match is None:
            logger.warning(f'Filename pattern did not match for {child_path}!')
            continue 
        key = child_match.group('key_old') or child_match.group('key_new')
        year = child_match.group('year_old') or child_match.group('year_new')
        ext = child_match.group('ext_old') or child_match.group('ext_new')

        if ext != 'xml':
            continue
  
        if len(year) == 2:
            if int(year) < 30:
                year = '20' + year
            else:
                year = '19' + year

        xml_contents = etree.parse(child_path)
        rnc.validate(xml_contents)

        collection = xml_contents.getroot()
        volumes = collection.findall('volume')
        for volume in volumes:
            meta = volume.find('meta')

            # venues
            venues = meta.findall('venue')
            venue_slugs = []
            for venue in venues:
                assert venue.text in all_venues
                venue_slugs.append(venue.text)

            # title
            title = meta.find('booktitle')

            bibtex_title_parts = []
            for elem in title.iter():

                if elem.tag == 'booktitle' and elem.text:
                    bibtex_title_parts.append(elem.text)

                if elem.tag == 'fixed-case':
                    bibtex_title_parts.extend(('{', elem.text, '}'))
                    if elem.tail:
                        bibtex_title_parts.append(elem.tail)

            bibtex_title_text = "".join(bibtex_title_parts)
            title_text = bibtex_title_text.replace('{', '').replace('}', '')

            # build final dict
            volume_dict = {
                'venue_slugs': venue_slugs,
                'title': title_text,
                'bibtex_title': bibtex_title_text,
                'venue_name_in_title': sum((all_venues[slug]['name'] in title_text) for slug in venue_slugs) >= 1,
                'year': year,
            }

            # add final dict to list of all, and venue lists
            all_volumes.append(volume_dict)
            for slug in venue_slugs:
                venue = all_venues[slug]
                venue['volumes'].append(volume_dict)
                if year not in venue['years']:
                    venue['years'][year] = []
                venue['years'][year].append(volume_dict)

    return all_volumes
            

def add_candidate_acronyms(all_venues, all_volumes):
    """
    """

    for idx, volume in enumerate(all_volumes):
        candidates = {}
        vol_venues = [all_venues[slug] for slug in volume['venue_slugs']]

        # Check if there are candidate acronyms in the proceedings title.
        if volume['title']:
            pattern =(r'(?!(?:NLP|NLG|NLU|MT|AI|[IVX]+)\b)\b'   # Acronyms that, on their own, should not be included.
                      r'(?<!@[ ]?)'             # Ignore acronyms which are preceded by and @ (indicating it is the acronym of the host venue, rather than the volume).
                      r'((?:'
                          r'[A-z]*'             # Any number of letters  
                          r'[-]?'               # optionally followed by hyphen
                          r'[A-Z]{2,}'          # followed by at least to capital letters
                          r'(?:[\-][A-z])?'     # optionally followed by a hyphen and a letter (avoid capturing hyphens connecting acronym with the year)
                          r'[A-z]*'             # followed by any number of letters
                          r'(?:[ ][A-z])?'      # optionally followed by a space and a letter (avoid capturing spaces between acronym and a year)
                      r')+)'
                      r'(?:[ |-]?([0-9]+))?'    # optionally followed by numbers (either ordinal or year) 
                      r'(?!\w)')                # ending with a non-word character
            matches = list(re.finditer(pattern, volume['title']))
            if matches:
                parentheses = [volume['title'][match_.span()[0]-1] == '(' for match_ in matches]
                candidates['acronym-ish'] = [(match_[0], match_[1], match_[2]) for match_, p in zip(matches, parentheses) if not p]
                candidates['parentheses'] = [(match_[0], match_[1], match_[2]) for match_, p in zip(matches, parentheses) if p]

        # Construct candidate based on venues and year
        joint_venues = '-'.join([venue['acronym'] for venue in vol_venues])
        year = volume['year']
        candidates['venues_year'] = (f"{joint_venues} {year}", joint_venues, year)

        volume['candidate_acronyms'] = candidates


def create_substitution_patterns(all_venues, all_volumes):

    def proc_string(volume):
        return 'Proc. of ' if volume['title'].startswith('Proceedings of') else ""

    def stage_0():
        return []

    def stage_1(volume):
        year = volume['year']
        venues = [all_venues[slug] for slug in volume['venue_slugs']]
        
        # If the volume is the only one for that year and venue, we use the 'venue year' acronym.
        only_volume = all([len(venue['years'][year]) == 1 for venue in venues])
        if not only_volume:
            return None

        acronym = volume['candidate_acronyms']['venues_year'][0]
        shortened = proc_string(volume) + '{' + acronym + '}'

        if not volume['venue_name_in_title']:
            logger.info(f'Lonely volume where venue name does not appear in title.')
            logger.info(f" title={volume['title']}")
            logger.info(f' venues:')
            for venue in venues:
                logger.info(f"  - acronym={venue['acronym']}, name={venue['name']}")

        return volume['bibtex_title'], shortened

    def stage_2(volume):
        venues = [all_venues[slug] for slug in volume['venue_slugs']]
        
        # If the venue name(s) appear(s) in the title we can substitute for the venue acronym(s).
        if volume['venue_name_in_title']:
            venue_names = r")|(".join([r".*".join([re.escape(v['name']) for v in vs]) for vs in itertools.permutations(venues)])
            pattern = r"(.*)(?:(" + venue_names + r"))(.*)"
            
            match_ = re.search(pattern, volume['title'])
            if match_:
                suffix = match_.groups()[-1]
                acronym = volume['candidate_acronyms']['venues_year'][0]
                shortened = proc_string(volume) + '{' + acronym + '}' + (suffix or '')
                return volume['bibtex_title'], shortened 
            else:
                logger.error('No match for combined venue names!')
                logger.error(f" volume.title={volume['title']}")
                logger.error(f" pattern={pattern}")

    def stage_3(volume):
        # TODO
        if volume['candidate_acronyms']['venues_year'][0] in volume['title']:
            return 


    # TODO: Improve efficiency by keeping track of which volume titles we have taken care of throughout the stages, and only applying stages after that to the remainder.

    sed_lines = []
    
    logger.info(f'Starting stage 0 ...')
    sed_lines.append('# -- stage 0 --')
    sed_lines.extend(stage_0())

    for s,stage in enumerate([stage_1, stage_2, stage_3], start=1):
        logger.info(f'Starting stage {s} ...')
        sed_lines.append(f'# -- stage {s} --')

        for volume in all_volumes:
            pattern = stage(volume)
             
            # If we decided on an acronym use it to create the shortened title.
            if pattern is not None:
                find_str, replace_str = pattern
                original = re.escape(find_str).replace('/', '\/')
                substitute = re.escape(replace_str).replace('/', '\/')
                sed_lines.append(f"s/{original}/{substitute}/g") 

    # write replacements to file
    with open('abbreviate.sed', 'w') as f:
        for line in sed_lines:
            f.write(f"{line}\n")


if __name__ == '__main__':

    venues = load_venues()
    volumes = load_volumes(venues)

    add_candidate_acronyms(venues, volumes)

    create_substitution_patterns(venues, volumes)

    """
    for volume in volumes:
        if len(volume['candidate_acronyms']) == 1:
            continue
        
        print(volume['bibtex_title'])

        for slug in volume['venue_slugs']:
            print('\t', venues[slug]['name'])

        for key, candidate in volume['candidate_acronyms'].items():
            print(key, candidate)

        print()
    """

