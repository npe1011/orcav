from pathlib import Path
from typing import List, Union, Optional


def print_warnings(messages: Union[str, List[str]]):
    if type(messages) is list:
        for line in messages:
            print(line)
    else:
        print(messages)


def remove_extra_blank_lines(lines: List[str]):
    # Remove head and tail blanks
    while lines and lines[0].strip() == '':
        lines.pop(0)
    while lines and lines[-1].strip() == '':
        lines.pop()
    # Condense >2 blank lines to one.
    result = []
    previous_empty = False
    for line in lines:
        if line.strip() == '':
            if not previous_empty:
                result.append(line)
                previous_empty = True
        else:
            result.append(line)
            previous_empty = False
    return result


def check_file(candidates: List[Path], warnings: bool = True) -> Optional[Path]:
    for file in candidates:
        if file.is_file():
            return file.absolute()
    w = 'Warning: ' + ' or '.join([str(file.name) for file in candidates]) + ' not found.'
    print_warnings(w)
    return None
