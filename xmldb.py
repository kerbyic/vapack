#!/usr/bin/env python3

from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import sys

parser = ArgumentParser(argument_default='-h')
subparsers = parser.add_subparsers()

parser_new = subparsers.add_parser( 'convert', help='Convert the ion position mode of a given POSCAR' )


nargs = len(sys.argv)
if nargs < 2:
    parser.print_help()
    exit()
