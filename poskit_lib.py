from vasptypes import Ion, Poscar, Incar, Potcar
import vasptypes_extension as vte
from argparse import Namespace
from pathlib import Path
import numpy as np
from argparse import ArgumentParser, Namespace
from copy import deepcopy

# Notes to whoever attempts to maintain this:
#
# 1. While default values for run function arguments exist
#    in the function definition, they are overridden by the 
#    argument parser default values, which if not specified
#    is None.
#
# 2. The Subcommand class and any of its subclasses are NOT
#    meant to be instantiated as objects. They are containers
#    for each subcommand, its parser, and its functions that
#    enable easy additions without modifying the main program,
#    reduce redundancy, and help organization.
#
# 3. The run function in each subcommand MUST take the exact
#    same arguments as are created in its parser's namespace.
#    In addition, it must also take any that are present in
#    the parent parser's namespace (currently only 'verbose'
#    and 'no_write').

# Template class for subcommands. Must be derived from to be
# automatically discovered.
class Subcommand:
    description = ""
    parser = ArgumentParser()
    @staticmethod
    def run():
        pass

class convert(Subcommand):
    description='Convert the ion position mode of a given POSCAR'
    parser = ArgumentParser()
    parser.add_argument( 'input', type=str, help='Input file' )
    parser.add_argument( '-m', '--mode', default='toggle', choices=['cartesian','direct','toggle'],
                        type=str, help='Convert to cartesian, direct, or automatically determine <DEFAULT toggle>' )
    parser.add_argument( '-o', '--output', type=str,
                        help='Output file <DEFAULT \'file-stem\'_converted.\'file-suffix\'>' )

    @staticmethod
    def run(input:str, mode:str, output:str=None,\
            verbose:bool=False, no_write:bool=False) -> None:
    
        # Determine output location
        input_path = Path(input)
        output_path = Path(f"{input_path.stem}_convert{input_path.suffix}")\
            if output is None else Path(output)
        
        # Verbose message
        if verbose:
            print( f"Converting ion position mode of {input_path}" )

        # Read in file
        poscar = Poscar.from_file(input_path)

        # If toggle mode, choose the correct
        match mode.lower():
            case "toggle":
                poscar._toggle_mode()
            case "cartesian":
                poscar._convert_to_cartesian()
            case "direct":
                poscar._convert_to_direct()
            case _:
                raise RuntimeError('Unknown conversion')
        
        # Write the new POSCAR
        if not(no_write):
            poscar.to_file(output_path)

        if verbose:
            if no_write:
                print( 'No changes written' )
            else:
                print( f"Changes written to {output_path}" )

class vacuum(Subcommand):
    description='Add vacuum layers to a given POSCAR'
    parser = ArgumentParser()
    parser.add_argument( 'input', type=str, help='Input file' )
    parser.add_argument( 'depth', nargs=3, type=float,
                        help='Vacuum layer depth in Angstroms along a, b, and c lattice vectors' )
    parser.add_argument( '-o', '--output', type=str,
                        help='Output file <DEFAULT \'file-stem\'_vacuum.\'file-suffix\'>' )

    @staticmethod
    def run(input:str, depth:np.array, output:str=None,\
                verbose:bool=False, no_write:bool=False) -> None:

        # Determine output location
        input_path = Path(input)
        output_path = Path(f"{input_path.stem}_vacuum{input_path.suffix}")\
            if output is None else Path(output)

        # Verbose message
        if verbose:
            print( f'Adding vacuum depth {depth} A to {input_path}' )

        # Read in the file
        poscar = Poscar.from_file(input_path)

        # Convert the POSCAR to cartesian
        poscar._convert_to_cartesian()

        # TODO: Interpret the depth, which may be 3 independent values

        # TODO: Take into account non-unity scaling factors

        # Add the vacuum layer in only the c-direction (roughly)
        # Take the 3 valued depth, cast to 3x3 diagonal matrix, and add to lattice
        if type(depth) != np.array:
            depth = np.array(depth)
        poscar.lattice += np.diag(depth)

        # Write the new POSCAR
        if not(no_write):
            poscar.to_file(output_path)
        
        # Verbosity messages
        if verbose:
            if no_write:
                print( 'No changes written' )
            else:
                print( 'Changes written to {}'.format(output_path) )

class potcar(Subcommand):
    description = 'Create a potcar from given input'
    parser = ArgumentParser()
    parser.add_argument( 'input', type=str,
                        help='Source POSCAR for creating the list of species/potentials \
                            for the POTCAR | May also specify \'none\' to instead use the list argument alone' )
    parser.add_argument( '-o', '--output', type=str, default='POTCAR', help='Output file <DEFAULT POTCAR>' )
    parser.add_argument( '-p', '--potentials', nargs='+', default=[],
                        help='List of potentials | Useful for potentials that differ from the ion species name')
    parser.add_argument( '-d', '--directory', default='./potcar', type=str,
                        help='Directory of POTCAR folders <DEFAULT ./potcar/> | Can be used \
                            to specify PBE or LDA manually' )

    @staticmethod
    def run(input:str, output:str='POTCAR', potentials:list=[], directory:str='.',
            verbose:bool=False, no_write:bool=False):
        # Cast input, output, and directory to paths
        input_path = Path(input)
        output_path = Path(output)
        directory_path = Path(directory)

        # Initialize the species list
        species = []

        # If the POSCAR is 'none', then use the provided list
        if input_path.stem.lower() == "none":
            if len(potentials) < 1:
                raise RuntimeError('Since POSCAR is "none", a potentials list must be provided!')
            species = potentials

        # If the POSCAR is a file (not 'none')
        else:
            poscar = Poscar.from_file(input_path)
            species = list(poscar.species.keys())
        
        # Create the potcar object
        potcar = Potcar(species, directory_path)

        # Verbose species message
        if verbose:
            if directory_path.name.lower() in ["gga", "lda"]:
                print( f"Using {directory_path.name.upper()} potentials" )
            elif len(species) > 1:
                print( "Using GGA potentials" )
            else:
                print( "Using LDA potentials" )

        # Generate and write the potcar
        if no_write:
            if verbose:
                print( 'No changes written' )
            return
        
        potcar.generate_file(output_path)

        if verbose:
            print( 'Changes written to {}'.format(output_path) )

class slabfreeze(Subcommand):
    description = "Change the selective dynamics flags for all ions inside defined box"
    parser = ArgumentParser()
    parser.add_argument( 'input', type=str, help='Input file' )
    parser.add_argument( 'dimensions', nargs=3, type=str,
                        help='Allow for motion along dimension with T or F' )
    parser.add_argument( '-x', '--x_range', nargs=2, type=float,
                        help='Lower and upper x range' )
    parser.add_argument( '-y', '--y_range', nargs=2, type=float,
                        help='Lower and upper y range' )
    parser.add_argument( '-z', '--z_range', nargs=2, type=float,
                        help='Lower and upper z range' )
    parser.add_argument( '-m', '--mode', choices=['cartesian','c','k','direct','d'], type=str,
                        help='Dimensions provided in Cartesian or Direct mode <DEFAULT Mode of POSCAR>' )
    parser.add_argument( '-o', '--output', type=str,
                        help='Output file <DEFAULT \'file-stem\'_frozen.\'file-suffix\'>' )
    parser.add_argument( '-p', '--preserve_unspecified', action='store_true',
                        help="Overwrite the existing selective dynamics flags")

    @staticmethod
    def run(input:str, x_range:list[float]=None, y_range:list[float]=None, z_range:list[float]=None,
            dimensions:list=[], mode:str=None, output:str=None, preserve_unspecified:bool=False,
            verbose:bool=False, no_write:bool=False):
        # Read the input file
        input_path = Path(input)
        poscar = Poscar.from_file(input)

        # Initialize the output path
        output_path = Path(f"{input_path.stem}_frozen{input_path.suffix}") if output is None\
            else Path(output)

        # Verbose message
        if verbose:
            print( f'Creating POSCAR from {input_path}' )
            print( 'Using {} mode'.format('auto' if mode is None else mode) )
            range_str = []
            if not(x_range is None):
                range_str.append(f"{x_range[0]} <= x <= {x_range[1]}")
            if not(y_range is None):
                range_str.append(f"{y_range[0]} <= y <= {y_range[1]}")
            if not(z_range is None):
                range_str.append(f"{z_range[0]} <= z <= {z_range[1]}")
            range_str = ', '.join(range_str)
            print( f'Applying selective dynamics {dimensions} to ions inside {range_str}' )

        # Convert the dimensions to bool
        dimensions = Ion.list_to_bools(dimensions)
        
        # Get box selection of ions
        selection = vte.box_select(poscar, x_range, y_range, z_range, mode)

        # Change the selective dynamics of selection
        for i, _ in enumerate(poscar.ions):
            d = dimensions
            if not( i in selection.indices ):
                if preserve_unspecified:
                    continue
                # poscar.ions[i].selective_dynamics = np.array([True]*3, dtype=bool)
                d = Ion.list_to_bools(['T','T','T'])
            poscar.ions[i].selective_dynamics = d
        poscar.selective_dynamics = True

        # Final verbose message
        if verbose:
            print(f"Switched {len(selection)}/{len(poscar.ions)} ions")

        # Write the modified poscar
        poscar.to_file(output_path)

class interpolate(Subcommand):
    description = 'Linearly interpolate images for a NEB calculation from two POSCAR files'
    parser = ArgumentParser()
    parser.add_argument( 'file1', type=str, help='Input file 1' )
    parser.add_argument( 'file2', type=str, help='Input file 2' )
    parser.add_argument( '-i', '--images', type=int,
                        help='Number of interpolated images to create', default=1 )
    parser.add_argument( '-c', '--center', action="store_true",
                        help='Center the POSCARS about center of mass (unused)' )

    @staticmethod
    def run(file1:str, file2:str, images:int=1, center:bool=False,
            verbose:bool=False, no_write:bool=False):
        # Load the anchors
        poscar1 = Poscar.from_file(file1)
        poscar2 = Poscar.from_file(file2)

        # TODO: Check if the headers match

        # Ensure that there are the same number of ions in each
        if len(poscar1.ions) != len(poscar2.ions):
            raise RuntimeError('Number of ions do not match!')
        
        # Ensure no ions cross the unit cell boundaries
        for i, (ion1, ion2) in enumerate(zip(poscar1.ions, poscar2.ions)):
            if (np.sign(ion1.position)*np.sign(ion2.position)).sum() != 3:
                print(f"Warning: Ion {i} crossed boundary between anchors!")

        # Template the output poscar image
        image_template = deepcopy(poscar1)

        # Disable selective dynamics in the output
        image_template.selective_dynamics = False

        # Interpolate between ion positions and save to template
        for i in range(images+2):
            # Erase the existing ion data in the template
            image_template.ions = []
            # Get interpolated ion positions
            for ion1, ion2 in zip(poscar1.ions, poscar2.ions):
                new_ion = Ion()
                new_ion.position = ion1.position + (ion2.position-ion1.position)/(images+1)*i
                new_ion.species = ion1.species
                image_template.ions.append(new_ion)
            # Create output path
            output_path = Path( ".", str(i).zfill(2), "POSCAR" )
            # Write the file
            image_template.to_file(output_path)
