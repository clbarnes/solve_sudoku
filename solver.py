#!/usr/bin/env python3
import sys

import copy
import logging
from math import sqrt

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger()

DEFAULT_SUDOKU_ORDER = 3

CELL_VSEP = ''
BLOCK_VSEP = '|'
CELL_HSEP = ''
BLOCK_HSEP = '-'
PAD = ' '


def create_template(sudoku_order):
    """
    Create a template string for printing sudoku results.

    Parameters
    ----------
    sudoku_order: int
        The number of cells in a row or column of a subgrid; the number of rows or columns of subgrids in the sudoku.

    Returns
    -------
    str
        Template string used internally by Sudoku.print()
    """
    cell = '{0}{{}}{0}'.format(PAD)
    block_row = CELL_VSEP.join([cell] * sudoku_order)
    row = BLOCK_VSEP.join([block_row] * sudoku_order)
    row_len = len(row) - row.count('}')

    cell_hline = '\n{}\n'.format(CELL_HSEP * row_len) if CELL_HSEP else '\n'
    block_rows = cell_hline.join([row] * sudoku_order)
    block_hline = '\n{}\n'.format(BLOCK_HSEP * row_len) if BLOCK_HSEP else '\n'

    return block_hline.join([block_rows] * sudoku_order)


def validate_array(array):
    """
    Validate an array to ensure that it is sudoku-shaped and has no illegal numbers in it (does not check for clashes).

    Returns sudoku order.

    Parameters
    ----------
    array : list of list
        Initial sudoku cells, where 0 is an empty cell.

    Returns
    -------
    int
        Sudoku order.
    """
    n_rows = len(array)

    assert not sqrt(n_rows) % 1, 'Sudoku width is not a square number'
    sudoku_order = int(sqrt(n_rows))
    valid_numbers = set(range(sudoku_order ** 2 + 1))
    for row in array:
        assert len(row) == n_rows, 'Sudoku is not square'
        assert valid_numbers.issuperset(row), 'Row has illegal numbers in it {}'.format(set(row).difference(valid_numbers))

    return sudoku_order


def load_file(path):
    """
    Load sudoku-like array and its order from CSV file

    Parameters
    ----------
    path : str

    Returns
    -------
    tuple of (list of list, int)
        Initial sudoku array and sudoku order
    """
    with open(path) as f:
        arr_str = f.read().strip()

    return load_str(arr_str)


def load_str(arr_str):
    """
    Load sudoku-like array and its order from CSV-like string

    Parameters
    ----------
    arr_str : str
        CSV string containing initial sudoku

    Returns
    -------
    tuple of (list of list, int)
        Initial sudoku array and sudoku order
    """
    if '\t' in arr_str:
        split = lambda s: s.strip().split('\t')
    elif ',' in arr_str:
        split = lambda s: s.strip().split(',')
    else:
        split = lambda s: iter(s)

    array = [[int(item.strip()) if item else 0 for item in split(row)] for row in arr_str.split('\n')]
    sudoku_order = validate_array(array)
    return array, sudoku_order


class ClashException(Exception):
    """Further moves on an incomplete sudoku are all illegal"""
    pass


class Cell:
    """Class representing single cell of a sudoku grid"""
    def __init__(self, row, col, sudoku_order, value=None):
        """

        Parameters
        ----------
        row : int
            The row index of the cell
        col : int
            The column index of the cell
        sudoku_order : int
            The order of the sudoku to which the cell belongs (used to calculate its subgrid)
        value : int
            Value of the cell (0 or None if empty)
        """
        try:
            value = int(value)
        except ValueError:
            value = 0

        if value:
            self.possibilities = [value]
        else:
            self.possibilities = list(range(1, sudoku_order**2 + 1))

        self.row = row
        self.col = col
        self.subgrid = row // sudoku_order, col // sudoku_order

    @property
    def value(self):
        if len(self.possibilities) == 1:
            return self.possibilities[0]
        else:
            return 0

    @value.setter
    def value(self, val):
        if val in self.possibilities:
            self.possibilities = [val]
        else:
            raise ClashException('Tried to set a cell to an illegal value')

    def eliminate(self, value):
        """
        Eliminate a value from the cell's possibilities

        Parameters
        ----------
        value : int
            Value to eliminate from possibilities

        Returns
        -------
        int
            If there remains only one possibility, return it. Otherwise, 0.
        """
        if len(self.possibilities) == 1 and self.possibilities[0] == value:
            raise ClashException('Tried to eliminate the only possible value from a cell')

        try:
            self.possibilities.remove(value)
            return self.value
        except ValueError:
            return 0

    def matches(self, other):
        """
        Return whether this cell shares a row, column or subgrid with the other. Assumes same sudoku order.

        Parameters
        ----------
        other : Cell

        Returns
        -------
        bool
        """
        return any([self.row == other.row, self.col == other.col, self.subgrid == other.subgrid])

    def __eq__(self, other):
        return self.row == other.row and self.col == other.col


def cells_from_arr(arr, order):
    """
    Generate sudoku cells from a valid array.

    Parameters
    ----------
    arr : list of list
    order : int

    Returns
    -------
    tuple of Cell
    """
    return tuple(
        Cell(row_idx, col_idx, order, value)
        for row_idx, row in enumerate(arr)
        for col_idx, value in enumerate(row)
    )


class Sudoku:
    """A class representing sudokus of arbitrary size."""
    placeholder = ' '

    def __init__(self, arr):
        """
        Parameters
        ----------
        arr : numpy array or list of lists in C order representing known cells
        """
        sudoku_order = validate_array(arr)
        self.cells = cells_from_arr(arr, sudoku_order)
        self.template = create_template(sudoku_order)

    @classmethod
    def from_file(cls, path):
        """
        Generate sudoku from CSV file.

        Parameters
        ----------
        path : str

        Returns
        -------
        Sudoku
        """
        arr, _ = load_file(path)
        return cls(arr)

    def eliminate(self, cell):
        """
        Given a cell with a determined value, eliminate that value from all cells sharing a row, column or block

        Parameters
        ----------
        cell : Cell
            Cell whose value is now determined
        """
        value = cell.value
        if not value:
            return
        for idx, other_cell in enumerate(self.cells):
            if cell == other_cell:
                continue
            if cell.matches(other_cell):
                newly_set = other_cell.eliminate(value)
                if newly_set:
                    self.eliminate(other_cell)

    def solve(self, callback=None):
        """
        Return a solved copy of this sudoku.

        Parameters
        ----------
        callback : callable
            Function to be called every time the function recurses

        Returns
        -------
        Sudoku
            Solved sudoku
        """
        new_sudoku = copy.deepcopy(self)
        ret_val = new_sudoku._easy_step()

        if callback:
            callback(new_sudoku.progress)

        if ret_val is None:
            logger.info('Sudoku solved!')
            return new_sudoku

        cell_idx, possibilities = ret_val
        possibilities = list(possibilities)

        for possibility in possibilities:
            new_sudoku2 = copy.deepcopy(new_sudoku)
            new_sudoku2.cells[cell_idx].value = possibility
            try:
                return new_sudoku2.solve(callback)
            except ClashException:
                continue

        raise ClashException('This sudoku is not solvable from the given state')

    def _easy_step(self):
        if self.is_solved:
            return None

        for cell in self.cells:
            if cell.value:
                self.eliminate(cell)

        if not self.is_solved:
            return min(
                [
                    (cell_idx, cell.possibilities)
                    for cell_idx, cell in enumerate(self.cells)
                    if len(cell.possibilities) > 1
                ],
                key=lambda x: (len(x[1]), x[0])
            )

    def __str__(self):
        return self.template.format(*[cell.value or self.placeholder for cell in self.cells])

    def print(self):
        s = str(self)
        print(s)
        return s

    @property
    def progress(self):
        return sum(bool(cell.value) for cell in self.cells) / len(self.cells)

    @property
    def is_solved(self):
        return all(cell.value for cell in self.cells)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        raise ValueError('Please supply path for sudoku CSV, e.g. "sudokus/example.csv"')
    sudoku = Sudoku.from_file(path)
    sudoku.print()
    solved = sudoku.solve()
    print('\n\nSOLVED\n\n')
    solved.print()
