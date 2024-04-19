#!/usr/bin/env python3

"""
Command line program that provides easy access to tools in Vasp Tool Kit
"""

import numpy as np
import poskit_lib as pkl
from argparse import ArgumentParser
from pathlib import Path
import sys
from copy import deepcopy

# Function to adjust vacuums within a unit cell
def add_vacuum(args):
    # Verbose message
    if args.verbose:
        print( 'Adding vacuum depth {} A to {}'.format(args.depth, args.file) )

    # Determine output location
    file = Path(args.file)
    if args.output is None:
        args.output = '{}_vacuum{}'.format( file.stem, file.suffix )

    # Read in the file
    poscar = pkl.Base.read_poscar( args.file )

    # Create the new POSCAR
    poscar = pkl.Base.add_vacuum( poscar, args.depth )

    # Write the new POSCAR
    if not(args.nowrite):
        pkl.Base.write_poscar(poscar, args.output)

        if args.verbose:
            print( 'Changes written to {}'.format(args.output) )
    
    # Or don't write, it's up to you
    else:
        if args.verbose:
            print( 'No changes written' )
        pass


# Function to convert the position mode of a 
def convert(args):
    # Verbose message
    if args.verbose:
        print( 'Converting ion position mode of {}'.format(args.file) )

    # Determine output location
    file = Path(args.file)
    if args.output is None:
        args.output = '{}_converted{}'.format( file.stem, file.suffix )
    
    # Read in file
    poscar = pkl.Base.read_poscar(args.file)

    # If toggle mode, choose the correct
    if args.mode.lower() == 'toggle':
        if poscar['rmode'] == 'Cartesian':
            args.mode = 'direct'
        else:
            args.mode = 'cartesian'

    # Convert based on mode
    if args.mode.lower() == 'direct':
        poscar = pkl.Base.convert_direct(poscar)

    elif args.mode.lower() == 'cartesian':
        poscar = pkl.Base.convert_cartesian(poscar)

    else:
        raise ValueError( 'Unknown conversion mode \'{}\''.format(args.mode) )
    
    # Write the new POSCAR
    if not(args.nowrite):
        pkl.Base.write_poscar(poscar, args.output)

        if args.verbose:
            print( 'Changes written to {}'.format(args.output) )

    # Or don't, again!
    else:
        if args.verbose:
            print( 'No changes written' )
        pass


# Function to create a potcar, either from a list of potcars or from a poscar
def potcar(args):

    # Initialize species list
    species = []

    # If the POSCAR is none, then use the provided list
    if args.poscar.lower() == 'none':
        species = args.list
    
    # If the POSCAR is a file (not 'none')
    else:
        poscar = pkl.Base.read_poscar(args.poscar)
        species = poscar['species']

    # Verbose species message
    if args.verbose:
        if args.poscar.lower() != 'none':
            print( 'Creating a POTCAR from {}'.format(args.poscar) )
        print( 'Using species/potentials {}'.format(species) )

    # Verbose potential approximation method message
    directory = Path(args.directory)
    if args.verbose:
        if directory.name.lower() in ['pbe', 'lda']:
            print( 'Using {} potentials'.format(directory.name.upper()) )
        elif len(species) > 1:
            print( 'Using PBE potentials' )
        else:
            print( 'Using LDA potentials' )

    # Generate and write the potcar
    if not(args.nowrite):
        pkl.Base.write_potcar( species, args.directory, args.output )

        if args.verbose:
            print( 'Changes written to {}'.format(args.output) )

    # Or don't... you get the idea
    else:
        if args.verbose:
            print( 'No changes written' )
        pass


# Function to freez ions using a box
def freeze(args):
    
    # Initialize file
    poscar = pkl.Base.read_poscar( args.file )

    # Initialize output
    file = Path(args.file)
    if args.output is None:
        args.output = '{}_frozen{}'.format( file.stem, file.suffix )

    # Verbose message
    if args.verbose:
        print( 'Creating POSCAR from {}'.format(args.file) )

    # If mode was not set, grab it automatically
    if args.mode is None:
        args.mode = poscar['rmode']

    # Convert the POSCAR to the correct mode if necessary
    converted = False
    if poscar['rmode'].lower() != args.mode.lower():
        poscar = pkl.Base.convert_toggle(poscar)
        converted = True

    # Verbose message
    if args.verbose:
        print( 'Using {} mode'.format(args.mode) )

    # Check that the modes are the same, otherwise, throw an error now
    if poscar['rmode'].lower() != args.mode.lower():
        raise ValueError( 'Unrecognized position mode' )

    # Verbose message
    if args.verbose:
        print( 'Applying selective dynamics {} to ions inside ({}, {}, {}) to ({}, {}, {})'.format(args.dimensions, *(args.lower), *(args.upper)) )

    # Pass the parameters to the freeze method
    poscar = pkl.Base.sd_box( poscar, args.lower, args.upper, args.dimensions )

    # If converted, then convert once more
    if converted:
        poscar = pkl.Base.convert_toggle(poscar)

    # Write the modified poscar
    pkl.Base.write_poscar( poscar, args.output )


def interpolate(args):
    """
    Linearly interpolate images for an NEB calculation from two POSCAR files
    """
    # Load the anchoring POSCARs
    poscar1 = pkl.Base.read_poscar(args.file1)
    poscar2 = pkl.Base.read_poscar(args.file2)

    # Erase any selective dynamics information since it's superfluous
    poscar1['sdynam'] = False
    poscar2['sdynam'] = False

    # TODO: Check if the headers match

    # Ensure that there are the same number of ions in each
    if len(poscar1['rions']) != len(poscar2['rions']):
        raise RuntimeError('Number of ions do not match!')
    
    # Ensure no ions cross the unit cell boundaries
    for r1, r2, i in zip(poscar1['rions'], poscar2['rions'], range(1,len(poscar1['rions'])+1)):
            # Check that the ion doesn't cross a boundary, output warning if it does
            if (np.sign(r1)*np.sign(r2)).sum() != 3:
                print(f"Warning: Ion {i} crossed  boundary between anchor points")
    
    # Template the output poscar image
    image_template = deepcopy(poscar1)
    
    # Interpolate between ion positions and save to template
    nimages = args.images
    for i in range(nimages+2):
        # Erase the existing ion data in the template
        image_template['rions'] = []
        # Get interpolated ion positions
        for r1, r2 in zip(poscar1['rions'], poscar2['rions']):
            nr = r1 + (r2-r1)/(nimages+1)*i
            image_template['rions'].append(nr)
        # Create output path
        ipath = Path( ".", str(i).zfill(2), "POSCAR" )
        # Create the parent directory
        ipath.parent.mkdir(parents = True, exist_ok=True)
        # Write the file
        with ipath.open('w') as f:
            f.write(pkl.Base.gen_poscar(image_template))
    

# Define top level parser
parser = ArgumentParser( description='Do things for VASP' )
parser.add_argument( '-v', '--verbose', action='store_true' )
parser.add_argument( '-n', '--nowrite', action='store_true' )
subparsers = parser.add_subparsers()

# Define convert command
parser_convert = subparsers.add_parser( 'convert', help='Convert the ion position mode of a given POSCAR' )
parser_convert.add_argument( 'file', type=str, help='Input file' )
parser_convert.add_argument( '-m', '--mode', default='toggle', choices=['cartesian','direct','toggle'], type=str, help='Convert to cartesian, direct, or automatically determine <DEFAULT toggle>' )
parser_convert.add_argument( '-o', '--output', type=str, help='Output file <DEFAULT \'file-stem\'_converted.\'file-suffix\'>' )
parser_convert.set_defaults( func=convert )

# Define potcar command
parser_potcar = subparsers.add_parser( 'potcar', help='Create a potcar from given input' )
parser_potcar.add_argument( 'poscar', type=str, help='Source POSCAR for creating the list of species/potentials for the POTCAR | May also specify \'none\' to instead use the list argument alone' )
parser_potcar.add_argument( '-o', '--output', type=str, default='POTCAR', help='Output file <DEFAULT POTCAR>' )
parser_potcar.add_argument( '-l', '--list', nargs='+', help='List of potentials | Useful for potentials that differ from the ion species name')
parser_potcar.add_argument( '-d', '--directory', default='./potcar', type=str, help='Directory of POTCAR folders <DEFAULT ./potcar/> | Can be used to specify PBE or LDA manually' )
parser_potcar.set_defaults( func=potcar )

# Define add_vacuum command
parser_vacuum = subparsers.add_parser( 'vacuum', help='Add vacuum layers to a given POSCAR' )
parser_vacuum.add_argument( 'file', type=str, help='Input file' )
parser_vacuum.add_argument( 'depth', nargs=3, type=float, help='Vacuum layer depth in Angstroms along a, b, and c lattice vectors' )
parser_vacuum.add_argument( '-o', '--output', type=str, help='Output file <DEFAULT \'file-stem\'_vacuum.\'file-suffix\'>' )
parser_vacuum.set_defaults( func=add_vacuum )

# Define freeze command
parser_freeze = subparsers.add_parser( 'freeze', help='Change the selective dynamics flags for all ions inside defined box' )
parser_freeze.add_argument( 'file', type=str, help='Input file' )
parser_freeze.add_argument( '-l', '--lower', nargs=3, required=True, type=float, help='Lower bound coordinates for box | Either (x,y,z) or (a,b,c)' )
parser_freeze.add_argument( '-u', '--upper', nargs=3, required=True, type=float, help='Upper bound coordinates for box | Either (x,y,z) or (a,b,c)' )
parser_freeze.add_argument( '-d', '--dimensions', nargs=3, required=True, type=str, help='Allow for motion along dimension with T or F' )
parser_freeze.add_argument( '-m', '--mode', choices=['cartesian','direct'], type=str, help='Dimensions provided in Cartesian or Direct mode <DEFAULT Mode of POSCAR>' )
parser_freeze.add_argument( '-o', '--output', type=str, help='Output file <DEFAULT \'file-stem\'_frozen.\'file-suffix\'>' )
parser_freeze.set_defaults( func=freeze )

# Define interpolate command
parser_freeze = subparsers.add_parser( 'interpolate', help='Linearly interpolate images for an NEB calculation from two POSCAR files' )
parser_freeze.add_argument( 'file1', type=str, help='Input file 1' )
parser_freeze.add_argument( 'file2', type=str, help='Input file 2' )
parser_freeze.add_argument( '-i', '--images', type=int, help='Number of interpolated images to create', default=1 )
parser_freeze.add_argument( '-c', '--center', action="store_true", help='Center the POSCARS about center of mass (unused)' )
parser_freeze.set_defaults( func=interpolate )

# Run this stuff
args = parser.parse_args()

if args.__contains__('func'):
    args.func(args)
else:
    parser.print_help(sys.stderr)
    sys.exit(1)
