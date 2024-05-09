import xml.etree.ElementTree as ET
from datetime import datetime
from numpy import random as nprand
from hashlib import sha256
from pathlib import Path

def arbitrary_hash(n=12):
    # Get time and random number to update hash
    time = datetime.now()
    rnum = nprand.randint(0,9999)
    # Make the hash
    h = sha256()
    h.update(f'{time}-{rnum}'.encode())
    h.digest()
    # Only return up to first n characters
    return h.hexdigest()[:n]

class Calculation(object):
    """Calculation metadata class"""
    
    # Constructor

    def __init__(self, location:str, id:str=None, description:str=None, \
                 created:str=None, status:str=None, parent:str=None) -> None:
        # Set the standard internal variables, none of which should be callable
        self.id = arbitrary_hash() if id is None else str(id)
        self._check_id()
        try:
            self.location = str(Path(location))
        except:
            raise RuntimeError("Could not parse location for C-{self.id}: {location}")
            
        self.description = description
        try:
            self.created = datetime.fromisoformat(created) if created is not(None) \
                           else datetime.now().replace(microsecond=0)
            self.created = self.created.isoformat()
        except ValueError:
            raise RuntimeError(f"Could not parse datetime for C-{self.id}: {created}")
        self.status = str(status) if parent is not(None) else None
        self.parent = str(parent) if parent is not(None) else None
        # Make sure to update the member _xml_root variable
        self._update_xml()
    
    # Alternate constructors

    @classmethod
    def from_xml(cls, xml:ET.Element):
        id = xml.attrib['id']
        location = xml.attrib['location']
        calc = cls(location, id)
        for e in xml:
            setattr(calc, e.tag, e.text)
        calc._update_xml()
        return calc

    @classmethod
    def from_yaml(cls, yml:str):
        # TODO: Implement from_yaml
        pass

    # Helpful methods that don't require instantiation
    
    @staticmethod
    def check_id(id):
        """Return true if the ID is viable"""
        banned_characters = ['/','\\','*']
        violations = [key for key in banned_characters if key in id]
        return (len(violations) == 0), violations
        
    # Internal checks

    def _check_id(self) -> None:
        """Raise an error when attempting to create a bad ID"""
        viable, violations = self.check_id(self.id)
        if not viable:
            raise RuntimeError("ID cannot contain: \'{}\'".format('\', \''.join(violations)))

    def _update_xml(self) -> None:
        # Update root
        root_attrib = {'id': self.id, 'location': str(self.location)}
        self._xml_root = ET.Element('calculation', root_attrib)
        # Pythonically update the xml element tree with all members variables
        # that don't start with _
        members = [attr for attr in dir(self) if not callable(getattr(self, attr)) \
                   and not attr.startswith("_") and not attr in ['id','location']]
        for member in members:
            xml_attr = f"_xml_{member}"
            self.__setattr__(xml_attr, ET.SubElement(self._xml_root, member))
            xml_attr = self.__getattribute__(xml_attr)
            if self.__getattribute__(member) is not(None):
                xml_attr.text = str(self.__getattribute__(member))
        # Prettify with indentation
        ET.indent(self._xml_root)

    # Object conversion methods

    def to_xml(self) -> ET.Element:
        """Export an XML element containing calculation data"""
        self._update_xml()
        return self._xml_root
        
    def to_xml_string(self) -> str:
        """Return a string of the prettified xml"""
        self._update_xml()
        return ET.tostring(self._xml_root, encoding='unicode')
    
# Public functions

class Database(object):
    """Browse a calculation database"""

    def __init__(self, path:str) -> None:
        self.root = self.load_xml(path)
        self.calculations = [Calculation.from_xml(c) for c in self.root.findall('calculation')]
    
    @staticmethod
    def load_xml(path:str) -> ET.Element:
        """Parse and load a database file into memory"""
        path = Path(path)
        if not path.exists():
            raise RuntimeError("Cannot load file. Does not exist.")
        tree = ET.parse(path)
        return tree.getroot()
    
    @staticmethod
    def fetch_all_from_file(path:str):
        root = Database.load_xml(path)
        calculations = [Calculation.from_xml(c) for c in root.findall('calculation')]
        return calculations

    @staticmethod
    def fetch_from_file(path:str, id:str) -> Calculation:
        matches = [c for c in Database.fetch_all_from_file(path) if c.id == id]
        if len(matches) > 1:
            raise IndexError("Multiple matching entries found!")
        if len(matches) == 0:
            raise RuntimeError("No matching entries found!")
        return matches[0]
    
    @staticmethod
    def export(database:Database, file:str) -> None:
        file_path = Path(file)
        with file_path.open('w') as f:
            f.write()

def export_db(database:ET.Element, path:str) -> None:
    """
    Export the given XML database to the specified path.
    Overwrite existing files.
    """
    pass

def fetch_from_db(database:ET.Element, id:str) -> Calculation:
    """Return a matching calculation object by id from the database"""
    pass
