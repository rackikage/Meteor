"""Reverse engineering layer — static binary/file analysis on local artifacts.

Read-only forensics: file identification, strings, signature scan, symbol tables.
Use only on files you own or are authorized to analyze in a lab.
"""

from app.reverse.layer import ReverseEngineeringLayer

__all__ = ["ReverseEngineeringLayer"]
