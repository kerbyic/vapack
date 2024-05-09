#!/usr/bin/python3

from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser
from sys import argv
from xml.etree import ElementTree as ET
import numpy as np

DEFAULT_FAIL_DICT = {'FAILED': '> [!Error] Failed to read!'}

def get_xml_root(file:str) -> ET.Element:
    return ET.parse(file).getroot()

def inline_value_string(head:str, fields:dict) -> str:
    '''
    Return a formatted string of the given dictionary, ready for Obsidian.
    '''
    ss = f'### {head}\n\n'
    for field, value in fields.items():
        # If it's the DEFAULT_FAIL_DICT, then just grab the content and go
        if field == 'FAILED':
            ss += str(value + '\n')
            break

        if not(type(value[0]) in [tuple, list, np.array]):
            ss += f'[ {field}:: {value[0]} ] {value[1]}\n'
        else:
            ss += f'[ {field}:: ' + ', '.join([str(j) for j in value[0]]) + f' ] {value[1]}\n'
    return ss


def get_lattices(root:ET.Element) -> dict:
    '''
    Return a dictionary containing the initial and final lattice parameters
    '''
    try:
        structure_list = root.findall('structure')
    
        for s in structure_list:
            if s.get('name') == 'initialpos':
                minit = np.vstack( [ np.array(v.text.split()) for v in s.find('crystal').find('varray') ] )

            if s.get('name') == 'finalpos':
                mfinal = np.vstack( [ np.array(v.text.split()) for v in s.find('crystal').find('varray') ] )

        vinit = [np.linalg.norm(v) for v in minit]
        vfinal = [np.linalg.norm(v) for v in mfinal]
        
        lattice_dict = {'a_i' : [vinit, 'Å'], 'a_f' : [vfinal, 'Å']}

    except:
        return DEFAULT_FAIL_DICT
    
    return lattice_dict


def get_ions(root:ET.Element) -> dict:
    '''
    Return a count of the ions in the system
    '''
    try:
        n = int(root.find('atominfo').find('atoms').text)
    except:
        return DEFAULT_FAIL_DICT
    
    return {'ions' : [n,'']}


def get_energies(root:ET.Element) -> dict:
    '''
    Return a dictionary of the various energies
    '''
    try:
        energies = root.findall('calculation')[-1].find('energy')
        
        en_free, en_wo_entropy, en_0 = [float(e.text) for e in energies]

        energy_dict = {'en_fr' : [en_free, 'eV'],
                    'en_we' : [en_wo_entropy, 'eV'],
                    'en_0' : [en_0, 'eV'],
                    'en_we/atom' : [en_wo_entropy/get_ions(root)['ions'][0], 'eV/ion']}
    except:
        return DEFAULT_FAIL_DICT
    
    return energy_dict


def get_fermienergy(root:ET.Element) -> dict:
    '''
    Return the fermi energy of the final configuration
    '''
    try:
        dos = root.find('calculation').find('dos')
        for entry in dos:
            if entry.get('name') == 'efermi':
                efermi = float(entry.text)
    except:
        return DEFAULT_FAIL_DICT
    
    return {'efermi' : [efermi, 'eV']}
        

def get_bandgap(root:ET.Element) -> dict:
    '''
    Return a dictionary containing the bandgap energy
    '''
    # Get the entire DOS branch
    dos = root.find('calculation').find('dos')

    dos_i = dos.find('i')
    efermi = float(dos_i.text) if dos_i.get('name') == 'efermi' else 0

    # Retrieve the total DOS, discarding partial
    dos_total = dos.find('total')
    dos_total_set = dos_total.find('array').find('set')
    for i in dos_total_set:
        print(i)
        # for j in i:
        #     print(j)

    return efermi


def execute(arguments):

    parser = ArgumentParser(description='Extract information from simulations in a given directory')

    parser.add_argument('source', type=str, help='Source directory for simulations. Searched recursively.')
    parser.add_argument('destination', type=str, help='Destination directory to put generated files.')
    parser.add_argument('project', type=str, help='Project name used to tag generated files.')
    parser.add_argument('-i','--indicator', type=str, default='vasprun.xml', help='Pattern to match to detect a simulation directory')
    parser.add_argument('-d','--data', type=str, default='vasprun.xml', help='Data file to pull from in each calculation directory')
    parser.add_argument('-t','--tag', type=str, default='tag.txt', help='The file containing the hash for tagging')
    parser.add_argument('--force',  action='store_true', help='Force overwrite of existing files.')
    parser.add_argument('--dryrun', action='store_true', help='Do not write any output.')

    args = parser.parse_args(arguments)

    # Set the variables
    data_file = args.data
    tag_file = args.tag
    indicator_file = args.indicator
    source_dir = args.source
    destination_pd = args.destination
    project_name = args.project
    force = args.force
    dryrun = args.dryrun

    # Get the current time
    creation_time = datetime.now().replace(microsecond=0).isoformat()

    # Make the destination parent folder
    if not(dryrun):
        Path(destination_pd).mkdir(parents=True, exist_ok=True)

    # Recursively search through the source for all calculation folders
    source_files = [v.resolve() for v in Path(source_dir).rglob(indicator_file)]

    # Quit with message if nothing found
    if len(source_files) < 1:
        raise(RuntimeError('Did not find any simulations'))

    # For each calculation folder
    for source_file in source_files:
        # Get the calculation folder
        calc_dir = Path(*source_file.parts[:-1])

        # Get the tag to name the new dir
        src_tag = ''
        src_tag_file = Path(calc_dir, tag_file)

        if not(src_tag_file.exists()):
            print( f'Could not find {src_tag_file}' )
            continue

        with src_tag_file.open('r') as f:
            src_tag = f.read().strip()

        # Make sure there's actually something in src_tag
        if len(src_tag) < 1:
            raise(RuntimeError(f'Tag file {src_tag_file} empty'))

        # Create the destination directory
        dst_calc_dir = Path(destination_pd, src_tag)
        if not(dryrun):
            dst_calc_dir.mkdir(parents=True, exist_ok=True)
        
        # Create frontmatter
        frontmatter = f'---\naliases: [{src_tag}]\ntags: [{project_name}]\ncreation: {creation_time}\n---\n\n'

        # Get the source for (meta)data
        calc_data_file = Path(calc_dir, data_file)
        
        # If the source exists, extract the metadata to body, else leave blank
        body = ''
        if calc_data_file.exists():
            try:
                root = get_xml_root(str(calc_data_file))
                body += inline_value_string("Ions", get_ions(root)) + '\n'
                body += inline_value_string("Lattice", get_lattices(root)) + '\n'
                body += inline_value_string("Energy", get_energies(root)) + '\n'
                body += inline_value_string("DOS", get_fermienergy(root)) + '\n'
            except ET.ParseError:
                body = '> [!Error] Failed to Parse'
                print(f'!!! Failed to read {calc_data_file}. Skipping !!!')
        else:
            body = '> [!Warning] No data at extraction time'
            print(f'Skipping extraction of {calc_data_file}')

        # Create the file and write to it
        dst_data_file = Path(dst_calc_dir, src_tag + '.md')
        if dst_data_file.exists() and not(force):
            print(f'Skipping {dst_data_file}')
            continue

        # Write to the file if it's not a dryrun
        if not(dryrun):
            with dst_data_file.open('w') as f:
                f.write(frontmatter)
                f.write(body)
                print(f'Wrote to {dst_data_file}')
        else:
            print(f'Would have written to {dst_data_file}')


if __name__ == "__main__":
    execute(argv[1:])
