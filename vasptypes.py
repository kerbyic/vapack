from pathlib import Path
import numpy as np
import itertools as it
from ast import literal_eval
import re

# Storage of position mode (direct or cartesian) is _only_ done in the POSCAR.
# The units on position of an ion makes no sense unless taken into context with
# a POSCAR.
class Ion(object):
    """
    An atom or ion contained within a POSCAR.
    Only has information that is immediately relevant to
    the ion itself. It has limited context of its container.
    """
    # Note: Index is not included here since it strictly applies
    # to the relative placement of the entry in the POSCAR file.
    # Indices are maintained where ion lists are relevant.
    def __init__(self, position:np.array=np.zeros(3),
                species:str="H",
                selective_dynamics:np.array=np.ones(3,dtype=bool),
                velocity:np.array=np.zeros(3)):
        """
        Initialize an oject to contain ion information.
        """
        self.position = position
        self.species = species
        self.selective_dynamics = selective_dynamics
        self.velocity = velocity
        self._reinforce_types()

    def _reinforce_types(self):
        """
        Check the types and ensure they are consistent with expectations.
        """
        self.position = np.array(self.position, dtype=float)
        self.species = str(self.species)
        self.selective_dynamics = np.array(self.selective_dynamics, dtype=bool)
        self.velocity = np.array(self.velocity, dtype=float)

    def _apply_transformation(self, transform:np.array, tol:float=1e-8) -> None:
        """
        Given transformation matrix (3x3), transform the coordinates of the ion.
        """
        A = transform.reshape(3,3)
        r = A @ self.position
        r = r * np.array(np.abs(r)>tol, dtype=int)
        self.position = r

    @staticmethod
    def list_to_bools(v):
        """
        Method to convert selective dynamics flags from strings to bools.
        Enforces expected characters and length.
        """
        if len(v) != 3:
            raise RuntimeError('Bad selective dynamics length on ion!')
        l = []
        for i in v:
            match i:
                case 'T': l.append(True)
                case 'F': l.append(False)
                case _: RuntimeError('Bad selective dynamics character on ion!')
        return np.array(l, dtype=bool)

# For use in POSCAR type hinting and ion portability
class Ions(list[Ion]):
    def __init__(self, ions:list[Ion]=[], indices:list=[]):
        self.indices = indices
        super().__init__(ions)

# Class for an INCAR since it's basically just a dictionary
class Incar(dict):

    # Use the normal dictionary constructor
    # Add a comments list on the side
    def __init__(self, d:dict, comments:list=[]):
        self.comments = comments
        super().__init__(d)

    @classmethod
    def from_file(cls, input:str="INCAR"):
        input_path = Path(input)
        incar_dict = {}
        comment_list = []

        with input_path.open('r') as incar_file:
            incar_text = incar_file.readlines()
            for line in incar_text:
                line = line.strip()
                # Line formatting sanity checks
                if len(line) == 0:
                    continue
                if line[0] in ('#','!'):
                    continue
                if not('=' in line):
                    continue
                # Retrieve values without extra whitespace
                key, value = [i.strip() for i in line.split('=',maxsplit=1)]
                comment = ''
                # Determine if there are additional comments after the values
                if '!' in value or '#' in value:
                    comment_start = np.array([value.find('!'), value.find('#')])
                    comment_start *= -1 if -1 in comment_start else 1
                    comment_start = np.abs( comment_start.min() )
                    comment = value[comment_start+1:].strip()
                    value = value[:comment_start].strip()
                # Make sure the key and value aren't blank
                if len(key) == 0 or len(value) == 0:
                    continue
                # Evaluate the value string to cast as the appropriate type
                # Defaults to original string in event of failure
                try:
                    value = literal_eval(value)
                except ValueError:
                    pass
                except SyntaxError:
                    pass
                # Modify the return dictionary and list
                incar_dict[str(key)] = value
                comment_list.append(comment)
        
        return cls(incar_dict, comment_list)
    
# Class for containing POTCAR info
# Does not store POTCAR string, but can create it
class Potcar(object):
    """
    """
    def __init__(self, potentials:list=[], directory:str='.'):
        self.potentials = potentials
        self.directory = Path(directory)
        if not(self.directory.exists()):
            raise RuntimeError('Provided potcar directory does not exist!')
        
    @classmethod
    def from_poscar(cls, input:str='POSCAR', directory:str='.'):
        poscar = Poscar.from_file(input)
        return cls(list(poscar.species.keys()), directory)

    def generate_string(self) -> str:
        # Choose the LDA or PBE automatically if it isn't specified
        if not(self.directory.name.lower() in ['gga', 'lda']):
            if len(self.potentials) > 1:
                directory = Path(self.directory, 'GGA')
            else:
                directory = Path(self.directory, 'LDA')

        # Create a list of paths for the species' POTCARs
        potential_paths = [ Path(directory, sp, 'POTCAR') for sp in self.potentials ]

        # Return the POTCARs as one concatenated string
        contents = ''
        for sp in potential_paths:
            contents += sp.read_text()

        return contents
    
    def generate_file(self, output:str='POTCAR', parents:bool=True) -> None:
        # Choose the LDA or PBE automatically if it isn't specified
        output_path = Path(output)
        parent = output_path.parent
        Path.mkdir(parent, parents=parents, exist_ok=True)
        with output_path.open('w') as f:
            f.write(self.generate_string())


# Class to parse and store POSCAR data in a rich, type hinted, format
class Poscar(object):
    """
    """
    def __init__(self, comment:str="", scale:np.array=np.ones(3,dtype=float),
                 lattice:np.array=np.identity(3,dtype=float), species:dict= {},
                 selective_dynamics:bool=False, mode:str='Direct', ions:Ions=[],
                 lattice_velocity:np.array=np.zeros((3,3)), mdextra:str=""):
        """
        Initialize a POSCAR from argument data only
        """
        self.comment = comment
        self.scale = scale
        self.lattice = lattice
        self.species = species
        self.selective_dynamics = selective_dynamics
        self.mode = mode
        self.ions = ions
        self.lattice_velocity = lattice_velocity
        self.mdextra = mdextra

    def __str__(self):
        """
        Automatic string conversion
        """
        return self.to_string()
    
    def _reconcile_ions(self):
        """
        Count the population of each species of ions and update
        the self contained species list.
        This is useful for ensuring agreement between ion counts
        and species populations since it's more intuitive to edit
        ions directly.
        """
        # Make sure the species list is in order
        species = {}
        for ion in self.ions:
            isp = ion.species.lower().capitalize()
            if species.__contains__(isp):
                species[isp] += 1
            else:
                species[isp] = 1
        self.species = species
        # Make sure the ions are sorted properly
        ions = []
        for sp in self.species.keys():
            mask = [ i.species==sp for i in self.ions ]
            ions += list( it.compress(self.ions, mask) )
        self.ions = ions

    def _toggle_mode(self) -> None:
        """
        Change the position mode from direct to cartesian or vice-versa.
        """
        if self.is_direct():
            self._convert_to_cartesian()
        elif self.is_cartesian():
            self._convert_to_direct()
        else:
            raise RuntimeError('Unrecognized mode descriptor when attempting to toggle!')

    def _convert_to_direct(self, error=False) -> None:
        """
        Convert the mode to direct.
        Optionally raise a RuntimeError if it is already direct.
        """
        # Check to make sure it's not already direct
        if self.is_direct():
            if error:
                raise RuntimeError('POSCAR is already in direct mode.')
            return
        
        # Create the transformation matrix
        A = self.lattice.transpose()
        Ainv = np.linalg.inv(A)
        # Convert all ion positions to fractions of the lattice vectors and round to zero

        for i,_ in enumerate(self.ions):
            self.ions[i]._apply_transformation(Ainv)

        # Change the mode string
        self.mode = "Direct"

    def _convert_to_cartesian(self, error=False) -> None:
        """
        Convert the mode to cartesian.
        Optionally raise a runtimeError if it is already cartesian.
        """
        # Check to make sure it's not already cartesian
        if self.is_cartesian():
            if error:
                raise RuntimeError('POSCAR is already in cartesian mode.')
            return
        
        # Convert all ion positions to fractions of the lattice vectors and round to zero
        # Create the transformation matrix and tolerance
        A = self.lattice.transpose()
        for i, ion in enumerate(self.ions):
            self.ions[i]._apply_transformation(A)

        # Change the mode string
        self.mode = "Cartesian"

    def _constrain(self) -> None:
        """
        Make sure all ions lie within boundary of cell.
        """
        # Convert to direct
        converted = False
        if self.is_cartesian():
            self._convert_to_direct()
            converted = True

        # If any direct mode coordinate exceeds +-1
        # subtract the floor from that coordinate, keeping the fraction
        for i, ion in enumerate(self.ions):
            self.ions[i].position = ion.position - ion.position // 1

        # Reconvert if necessary
        if converted:
            self._convert_to_cartesian()

    def is_cartesian(self) -> bool:
        """
        Return true if position mode is cartesian.
        """
        return self.mode[0].lower() in ('c','k')
    
    def is_direct(self) -> bool:
        """
        Return true if position mode is direct.
        """
        return self.mode[0].lower() == 'd'

    @classmethod
    def from_file(cls, poscar_file:str):
        """
        Return a POSCAR object with data matching the provided poscar_file.
        """
        file_path = Path(poscar_file)

        with file_path.open('r') as f:
            # Read comment line
            s_comment = f.readline().strip()

            # Read scaling factor(s)
            scale = f.readline().strip().split()
            if len(scale) == 1:
                scale = scale*3
            elif len(scale) != 3:
                raise ValueError( 'Wrong number of scaling \
                                 factors supplied in POSCAR!' )
            s_scale = np.array(scale, dtype=float)

            # Read lattice vectors
            vec = np.array([],dtype=float)
            for _ in range(3):
                line = f.readline()
                v = np.array(line.strip().split(), dtype=float)
                vec = np.append(vec, v)
            s_lattice = vec.reshape((3,3))

            # Mandatory check, species names
            # Enforce capitalization
            line = f.readline()
            species = []
            if line.replace(' ','').strip().isalpha():
                species = [sp.lower().capitalize() for sp in line.split() ]
                line = f.readline()
            
            # Read ions per species
            counts = line.strip().split()
            # Handle the optional case of no species specified
            if len(species) == 0:
                species = ['H'+str(i+1) for i in range(len(counts))]
            elif len(species) != len(counts):
                raise RuntimeError('Mismatch between species and ion counts!')
            s_species = {str(sp.lower().capitalize()):int(ct) for sp, ct in zip(species,counts)}

            # Optional check, selective dynamics
            line = f.readline()
            s_selective_dynamics = False
            if line[0].lower() == 's':
                s_selective_dynamics = True
                line = f.readline()

            # Read ion position mode
            if line[0].lower() in ('c','k'):
                s_mode = 'Cartesian'
            elif line[0].lower() == 'd':
                s_mode = 'Direct'
            else:
                raise RuntimeError('Unknown position mode')
            
            # Read in ion 
            s_ions = []
            ions = it.chain.from_iterable([ [sp]*c for sp, c in s_species.items() ])
            for sp in ions:
                line = f.readline().split()
                r = np.array(line[0:3], dtype=float)
                sd = ['True']*3
                if s_selective_dynamics:
                    sd = np.array([ False if f=='F' else True for f in line[3:6]], dtype=bool)
                v = np.zeros(3)
                s_ions.append(Ion(r, sp, sd, v))

            # Leave velocity as zero
            # Leave mdextra as empty

            return cls(s_comment, s_scale, s_lattice, s_species,
                       s_selective_dynamics, s_mode, s_ions)

    def to_string(self) -> str:
        """
        Return a formatted string of the POSCAR dictionary as would be found in a file.
        """
        # Write comment line
        poscar_string = ""
        poscar_string += self.comment + '\n'

        # Write scaling factor
        if np.allclose(self.scale, [self.scale[0]]*3):
            poscar_string += '  {:>11.8f}\n'.format(self.scale[0])
        else:
            poscar_string += '  {:>11.8f}  {:>11.8f}  {:>11.8f}\n'.format(*self.scale)

        # Write lattice vectors
        for i in self.lattice:
            poscar_string += '    {:>11.8f}  {:>11.8f}  {:>11.8f}\n'.format(*i)
        
        # Write the species names
        line = ''
        # If all the species are placeholder H0, H1, H2, ..., then skip writing this line
        if False in [ bool(re.match( r"H[0-9]+", sp )) for sp in self.species.keys() ]:
            line += ' '.join( [f"{sp:>6s}" for sp in self.species.keys()] ) + '\n'
        else:
            line = ''
        poscar_string += line

        # Write species numbers
        line = ''
        line += ' '.join( [f"{c:>6d}" for c in self.species.values()] ) + '\n'
        poscar_string += line

        # Write selective dynamics if enabled
        if self.selective_dynamics:
            poscar_string += 'Selective dynamics\n'

        # Write position mode
        poscar_string += self.mode + '\n'

        # Write the ion positions with selective dynamics tags if needed
        for ion in self.ions:
            line = '{:>11.8f}  {:>11.8f}  {:>11.8f}'.format(*ion.position)
            if self.selective_dynamics:
                line += ' {:>1s} {:>1s} {:>1s}'.format(*[ 'T' if t else 'F' for t in ion.selective_dynamics])
            poscar_string += line + '\n'

        # TODO: Write littec vector and ion velocities and MD extra

        return poscar_string
    
    def to_file(self, file:str, parents=True) -> None:
        """
        Write the POSCAR to the given file.
        """
        file = Path(file)
        parent = file.parent
        Path.mkdir(parent, parents=parents, exist_ok=True)
        with file.open('w') as f:
            f.write(self.to_string())
        
    def generate_potcar_str(self, potcar_dir:str='.') -> str:
        """
        Generate a POTCAR for the current POSCAR.
        """
        # Define pseudopotential path
        potcar = Potcar(self.species.keys(), potcar_dir)
        return potcar.generate_string()
    
    def generate_potcar_file(self, potcar_dir:str='.', output:str='POTCAR', parents=True) -> None:
        """
        Generate and write a POTCAR for the current POSCAR.
        """
        potcar = Potcar(self.species.keys(), potcar_dir)
        potcar.generate_file(output)

    def edit_ions(self, ions:Ions):
        """
        Overwrite matching ions in the POSCAR by index.
        """
        for i, ion in zip(ions.indices, ions):
            self.ions[i] = ion
        self._reconcile_ions()

    def remove_ions(self, ions:Ions):
        """
        Remove the ions provided in the list according to index.
        """
        for i in ions.indices:
            self.ions.pop(i)
        self._reconcile_ions()